"""
뉴스 관련성 분석

1. 벡터 유사도 사전 필터 — ChromaDB에서 회사 관련 청크와 가까운 뉴스만 통과
2. LLM 근거 생성 — 통과된 뉴스에 대해 "왜 관련 있는지" 한 문장 생성
"""

import threading
from dataclasses import dataclass

import ollama

from src.obsidian.embedder import query_similar
from src.scraper.fetcher import fetch_body
from src.sources.base import NewsItem

_LLM_MODEL = "gemma4:e2b"
_SIM_THRESHOLD = 0.50  # ChromaDB cosine distance (낮을수록 유사, ≤0.50 통과)
_TOP_K = 3              # 유사 청크 조회 수
_LLM_TIMEOUT = 30       # 개별 기사 LLM 호출 최대 대기 시간(초)
_MAX_LLM_ITEMS = 25     # 회사당 LLM 호출 상한 (거리 오름차순 상위 N개)

# LLM이 "무관" 대신 쓸 수 있는 거절 표현 — 모두 필터
_REJECT_PHRASES = (
    "무관", "관련 없음", "관련성 없음", "해당 없음",
    "관련 정보 없음", "관련된 정보 없음", "직접적인 관련 없음", "직접 관련 없음", "정보 없음",
    "연관성은 없", "관련성은 없", "관련성이 없", "영향을 주지 않", "영향은 없", "영향이 없",
    "not relevant", "irrelevant", "no relevance", "no direct relevance",
)

# 회사명 prefix를 공유하는 자회사/관계사 기사를 걸러낼 접미사 목록
# 예: "현대차증권" 기사가 "현대차" 검색에 혼입되는 것을 방지
_SUBSIDIARY_SUFFIXES = ("증권", "금융", "보험", "캐피탈", "자산운용", "저축은행")


@dataclass
class AnalyzedItem:
    item: NewsItem
    reason: str          # LLM이 생성한 관련 근거
    distance: float      # 가장 가까운 청크의 거리


def _is_subsidiary_article(title: str, company: str) -> bool:
    """회사명 prefix를 공유하는 자회사 기사 여부 (예: 현대차 검색 시 현대차증권 기사)"""
    for suffix in _SUBSIDIARY_SUFFIXES:
        if (company + suffix) in title and not company.endswith(suffix):
            return True
    return False


def _call_llm_with_timeout(prompt: str, timeout: int = _LLM_TIMEOUT) -> str:
    """ollama.generate 스트리밍을 별도 스레드에서 실행, timeout 초 초과 시 빈 문자열 반환."""
    result: list[str] = []
    error: list[str] = []

    def _run():
        try:
            parts = []
            for chunk in ollama.generate(model=_LLM_MODEL, prompt=prompt,
                                         options={"num_predict": 120},
                                         think=False, stream=True):
                parts.append(chunk.response or "")
            result.append("".join(parts).strip())
        except Exception as e:
            error.append(str(e))

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        return "(타임아웃)"
    if error:
        return f"(LLM 오류: {error[0]})"
    return result[0] if result else ""


def _build_prompt(company: str, context: str, title: str, snippet: str) -> str:
    return (
        f"You are an investment analyst for {company}.\n\n"
        f"Reference document (investment memo excerpt):\n{context}\n\n"
        f"News title: {title}\n"
        f"News content: {snippet or 'N/A'}\n\n"
        "In ONE Korean sentence (under 50 characters), explain why this news is relevant "
        f"for {company} investors. "
        "If not relevant at all, reply with exactly '무관' and nothing else."
    )


def analyze(
    items: list[NewsItem],
    company: str,
    sim_threshold: float = _SIM_THRESHOLD,
    chroma_path: str = "data/chroma",
) -> list[AnalyzedItem]:
    """
    뉴스 목록을 벡터 유사도로 필터링하고 LLM 근거를 생성한다.

    Args:
        items: 단일 회사의 뉴스 목록
        company: 회사명 (ChromaDB 소스 필터용 힌트)
        sim_threshold: 이 거리 이하인 뉴스만 통과

    Returns:
        관련 있는 뉴스 + 근거 목록 (거리 오름차순)
    """
    seen_urls: set[str] = set()

    # ── 1단계: 벡터 필터 (LLM 없음) ──────────────────────────────────────────
    candidates: list[tuple[NewsItem, float, str]] = []  # (item, distance, context)
    fallback_items: list[NewsItem] = []

    for item in items:
        if item.url in seen_urls:
            continue
        seen_urls.add(item.url)

        if _is_subsidiary_article(item.title, company):
            continue

        korean_chars = sum(1 for c in item.title if '가' <= c <= '힣')
        if korean_chars == 0 and len(item.title) > 10:
            lower = item.title.lower()
            junk_patterns = ["convert ", "calculator", "to armenian", "to japanese yen"]
            if any(p in lower for p in junk_patterns):
                continue

        query_text = f"{item.title} {item.snippet or ''}"
        similar = query_similar(query_text, n_results=_TOP_K,
                                chroma_path=chroma_path, company_filter=company)

        if not similar:
            fallback_items.append(item)
            continue

        best = similar[0]
        if best["distance"] > sim_threshold:
            continue

        candidates.append((item, best["distance"], best["document"]))

    # ── 2단계: 상위 N개에만 LLM 호출 ─────────────────────────────────────────
    candidates.sort(key=lambda x: x[1])
    candidates = candidates[:_MAX_LLM_ITEMS]

    results: list[AnalyzedItem] = []

    # ChromaDB 없을 때 fallback — fallback도 상한 적용
    for item in fallback_items[:max(0, _MAX_LLM_ITEMS - len(candidates))]:
        results.append(AnalyzedItem(item=item, reason="(인덱스 없음 — 키워드 매칭)", distance=0.0))

    for item, distance, context_doc in candidates:
        body = None
        if distance <= 0.35:  # 매우 관련성 높은 기사만 본문 스크래핑
            body = fetch_body(item.url)

        context = context_doc[:600]
        content = body or item.snippet or ""
        prompt = _build_prompt(company, context, item.title, content)
        reason = _call_llm_with_timeout(prompt, timeout=_LLM_TIMEOUT)

        reason = reason.strip()
        if not reason or any(p in reason for p in _REJECT_PHRASES):
            continue

        results.append(AnalyzedItem(item=item, reason=reason, distance=distance))

    results.sort(key=lambda x: x.distance)
    return results
