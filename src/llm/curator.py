"""
뉴스 큐레이팅 — LLM 합성 텍스트 생성

선별된 뉴스 전체를 LLM에 한번에 넘겨
"오늘의 핵심 테마 + 투자 시사점" 형태의 합성 리포트를 생성한다.
파일 쓰기는 하지 않는다 — writer.py가 뉴스 목록과 합쳐서 Daily/에 저장한다.
"""

import ollama

from src.llm.analyzer import AnalyzedItem
from src.obsidian.embedder import query_similar

_LLM_MODEL = "gemma4:e2b"


def _get_vault_context(company: str, chroma_path: str) -> str:
    """ChromaDB에서 회사 투자 메모 핵심 내용을 추출한다."""
    results = query_similar(company, n_results=3, chroma_path=chroma_path,
                            company_filter=company)
    chunks = [r["document"] for r in results]
    return "\n\n".join(chunks[:2])[:800]


def _build_curation_prompt(company: str, context: str, news_lines: str) -> str:
    return (
        f"You are a senior investment analyst covering {company}.\n\n"
        f"Investment thesis and key monitoring points:\n{context}\n\n"
        f"Today's relevant news ({company}) — format: title → relevance reason:\n{news_lines}\n\n"
        "Write a concise daily research brief in Korean with this EXACT structure "
        "(output all seven sections in order, no extras):\n\n"
        "## 오늘의 핵심 뉴스 TOP 3\n"
        "(Pick the 3 most impactful articles from the list above. "
        "For each: article title in bold, then one sentence explaining why it matters most for investors)\n\n"
        "## 오늘의 핵심 테마\n"
        "(2-4 thematic groups. Each: bold theme name + 1-2 sentence summary)\n\n"
        "## 투자 시사점\n"
        "(3-5 bullet points. Each: what changed today and what it means for the position)\n\n"
        "## 논거 검증\n"
        "(ONE sentence only: did today's news strengthen / maintain / weaken the investment thesis? "
        "State which thesis point was affected and why)\n\n"
        "## 리스크 업데이트\n"
        "(Bullet points for risks newly highlighted or escalated TODAY. "
        "Skip if nothing new. Do NOT repeat known standing risks.)\n\n"
        "## 모니터링 포인트\n"
        "(Bullet points: upcoming events, dates, or indicators to watch next — "
        "earnings, policy decisions, competitor announcements, key metrics)\n\n"
        "## 경쟁사/섹터 동향\n"
        "(Bullet points for competitor or sector news that affects this company. "
        "State the implication for this company explicitly. Skip if none.)\n\n"
        "Write in Korean. Be analytical and specific, not just descriptive."
    )


def synthesize(
    company: str,
    analyzed: list[AnalyzedItem],
    chroma_path: str = "data/chroma",
) -> str | None:
    """
    LLM 합성 텍스트를 반환한다. 파일 쓰기 없음.
    실패 또는 뉴스 없으면 None 반환.
    """
    if not analyzed:
        return None

    news_lines = "\n".join(
        f"- {a.item.title} → {a.reason}"
        for a in analyzed[:30]
    )

    context = _get_vault_context(company, chroma_path)
    prompt = _build_curation_prompt(company, context, news_lines)

    print(f"  [curator] {company} — LLM 합성 중...")
    parts = []
    try:
        for chunk in ollama.generate(
            model=_LLM_MODEL,
            prompt=prompt,
            options={"num_predict": 2000},
            think=False,
            stream=True,
        ):
            parts.append(chunk.response or "")
    except Exception as e:
        print(f"  [curator] LLM 오류: {e}")
        return None

    result = "".join(parts).strip()
    if not result:
        print(f"  [curator] LLM 응답 없음")
        return None
    return result
