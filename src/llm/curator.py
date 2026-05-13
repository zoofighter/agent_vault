"""
뉴스 큐레이팅 — 테마별 종합 분석

선별된 뉴스 전체를 LLM에 한번에 넘겨
"오늘의 핵심 테마 + 투자 시사점" 형태의 합성 리포트를 생성한다.
"""

from datetime import datetime, timezone
from pathlib import Path

import ollama

from src.llm.analyzer import AnalyzedItem
from src.obsidian.embedder import query_similar

_LLM_MODEL = "gemma4:e2b"
_CURATED_SUBFOLDER = "Curated"


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
        f"Today's relevant news ({company}):\n{news_lines}\n\n"
        "Write a concise daily research brief in Korean with this exact structure:\n\n"
        "## 오늘의 핵심 테마\n"
        "(List 2-4 thematic groups. For each: theme name, 1-2 sentence summary of what happened)\n\n"
        "## 투자 시사점\n"
        "(3-5 bullet points connecting today's news to the investment thesis above. "
        "Be specific: what changed, what it means for the position, any risks or catalysts)\n\n"
        "Write in Korean. Be concise and analytical, not just descriptive."
    )


def curate(
    company: str,
    analyzed: list[AnalyzedItem],
    vault_path: str | Path,
    date_str: str | None = None,
    chroma_path: str = "data/chroma",
    dry_run: bool = False,
) -> Path | None:
    """
    선별된 뉴스를 종합 분석하여 Curated/ 폴더에 저장한다.
    """
    if not analyzed:
        return None

    vault = Path(vault_path)
    if date_str is None:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    collected_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    company_dir = vault / "Companies" / company
    if not company_dir.exists():
        print(f"  [skip] '{company}' 폴더 없음")
        return None

    # 뉴스 목록을 간결하게 직렬화
    news_lines = "\n".join(
        f"- {a.item.title} ({a.item.source})"
        for a in analyzed[:30]  # 너무 길면 컨텍스트 초과
    )

    context = _get_vault_context(company, chroma_path)

    prompt = _build_curation_prompt(company, context, news_lines)

    print(f"  [curator] {company} — LLM 합성 중...")
    parts = []
    try:
        for chunk in ollama.generate(
            model=_LLM_MODEL,
            prompt=prompt,
            options={"num_predict": 1200},
            think=False,
            stream=True,
        ):
            parts.append(chunk.response or "")
    except Exception as e:
        print(f"  [curator] LLM 오류: {e}")
        return None

    synthesis = "".join(parts).strip()
    if not synthesis:
        print(f"  [curator] LLM 응답 없음")
        return None

    content = f"""---
type: curated
company: "{company}"
date: {date_str}
collected: {collected_at}
news_count: {len(analyzed)}
tags:
  - curated
  - {company}
---

# {company} 큐레이팅 — {date_str}

> 관련 뉴스 {len(analyzed)}건 기반 · {collected_at}

{synthesis}

---

*참조: [[{date_str}]] (뉴스 전체 목록)*
"""

    curated_dir = company_dir / _CURATED_SUBFOLDER
    note_path = curated_dir / f"{date_str}.md"

    if dry_run:
        print(f"  [dry-run] {note_path.relative_to(vault)}")
        print(synthesis[:400])
        return note_path

    curated_dir.mkdir(exist_ok=True)
    note_path.write_text(content, encoding="utf-8")
    print(f"  → {note_path.relative_to(vault)}")
    return note_path
