"""
뉴스 관련성 분석

1. 벡터 유사도 사전 필터 — ChromaDB에서 회사 관련 청크와 가까운 뉴스만 통과
2. LLM 근거 생성 — 통과된 뉴스에 대해 "왜 관련 있는지" 한 문장 생성
"""

from dataclasses import dataclass

import ollama

from src.obsidian.embedder import query_similar
from src.sources.base import NewsItem

_LLM_MODEL = "gemma4:e2b"
_SIM_THRESHOLD = 0.75  # ChromaDB cosine distance (낮을수록 유사, ≤0.75 통과)
_TOP_K = 3              # 유사 청크 조회 수

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


def _build_prompt(company: str, context: str, title: str, snippet: str) -> str:
    return (
        f"You are an investment analyst for {company}.\n\n"
        f"Reference document (investment memo excerpt):\n{context}\n\n"
        f"News title: {title}\n"
        f"News summary: {snippet or 'N/A'}\n\n"
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
    results: list[AnalyzedItem] = []
    seen_urls: set[str] = set()

    for item in items:
        # URL 중복 제거
        if item.url in seen_urls:
            continue
        seen_urls.add(item.url)

        # 자회사/관계사 기사 필터 (예: "현대차증권" 기사가 "현대차" 분석에 혼입 방지)
        if _is_subsidiary_article(item.title, company):
            continue

        # 명백한 잡음 제거: 한국어 없는 순수 영어 제목이면서 금융/투자와 무관한 패턴
        korean_chars = sum(1 for c in item.title if '가' <= c <= '힣')
        if korean_chars == 0 and len(item.title) > 10:
            lower = item.title.lower()
            # 통화 변환기 등 명백한 비금융 잡음만 제거
            junk_patterns = ["convert ", "calculator", "to armenian", "to japanese yen"]
            if any(p in lower for p in junk_patterns):
                continue

        query_text = f"{item.title} {item.snippet or ''}"
        similar = query_similar(query_text, n_results=_TOP_K,
                                chroma_path=chroma_path, company_filter=company)

        if not similar:
            # ChromaDB 비어있으면 모두 통과 (fallback)
            results.append(AnalyzedItem(item=item, reason="(인덱스 없음 — 키워드 매칭)", distance=0.0))
            continue

        best = similar[0]
        if best["distance"] > sim_threshold:
            continue  # 유사도 기준 미달 → 제외

        # LLM 근거 생성 (스트리밍 필수 — non-stream이 빈 응답을 반환하는 모델)
        context = best["document"][:600]
        prompt = _build_prompt(company, context, item.title, item.snippet or "")
        try:
            parts = []
            for chunk in ollama.generate(model=_LLM_MODEL, prompt=prompt,
                                         options={"num_predict": 120},
                                         think=False, stream=True):
                parts.append(chunk.response or "")
            reason = "".join(parts).strip()
        except Exception as e:
            reason = f"(LLM 오류: {e})"

        reason = reason.strip()
        if not reason or any(p in reason for p in _REJECT_PHRASES):
            continue

        results.append(AnalyzedItem(item=item, reason=reason, distance=best["distance"]))

    results.sort(key=lambda x: x.distance)
    return results
