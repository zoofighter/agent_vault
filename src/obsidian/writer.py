"""
Obsidian 일일 뉴스 노트 저장

회사별로 하루에 파일 하나(YYYY-MM-DD.md)를 생성한다.
이미 존재하는 파일은 덮어쓴다 (당일 재실행 시 최신 상태 반영).
"""

from datetime import datetime, timezone
from pathlib import Path

from src.llm.analyzer import AnalyzedItem

COMPANIES_FOLDER = "Companies"
NEWS_SUBFOLDER = "News"


def _source_label(source: str) -> str:
    return {
        "naver":         "Naver 뉴스",
        "naver_finance": "Naver 금융",
        "duckduckgo":    "DuckDuckGo",
        "yahoo_finance": "Yahoo Finance",
        "google_news":   "Google News",
        "hkex":          "HKEX 공시",
        "twse":          "TWSE/MOPS 공시",
        "tse":           "TSE TDnet 공시",
    }.get(source, source)


def _stars(distance: float, reason: str) -> str:
    """코사인 거리(0~0.75)를 별점 5단계로 변환한다. 낮을수록 관련성 높음."""
    if "인덱스 없음" in reason:
        return "☆☆☆☆☆"  # 인덱스 없이 통과된 항목은 별점 없음
    if distance <= 0.45:
        return "★★★★★"
    if distance <= 0.55:
        return "★★★★☆"
    if distance <= 0.63:
        return "★★★☆☆"
    if distance <= 0.70:
        return "★★☆☆☆"
    return "★☆☆☆☆"


def _build_daily_note(
    company: str,
    date_str: str,
    analyzed: list[AnalyzedItem],
    collected_at: str,
) -> str:
    header = f"""---
type: news-digest
company: "{company}"
date: {date_str}
collected: {collected_at}
count: {len(analyzed)}
tags:
  - news
  - {company}
---

# {company} 뉴스 — {date_str}

> 수집 {len(analyzed)}건 · {collected_at}
"""

    if not analyzed:
        return header + "\n관련 뉴스 없음\n"

    sections = []
    for i, a in enumerate(analyzed, 1):
        item = a.item
        src = _source_label(item.source)
        snippet = (item.snippet or "").strip()
        reason = a.reason.strip()
        stars = _stars(a.distance, reason)

        block = f"""
## {i}. {item.title}

- **관련도**: {stars} `{a.distance:.2f}`
- **출처**: [{src}]({item.url})
- **관련 근거**: {reason}

{snippet}
"""
        sections.append(block)

    return header + "\n".join(sections)


def write_daily(
    company: str,
    analyzed: list[AnalyzedItem],
    vault_path: str | Path,
    date_str: str | None = None,
    dry_run: bool = False,
) -> Path | None:
    """
    회사별 일일 뉴스 노트를 저장하고 파일 경로를 반환한다.
    """
    vault = Path(vault_path)
    if date_str is None:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    collected_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    company_dir = vault / COMPANIES_FOLDER / company
    if not company_dir.exists():
        print(f"  [skip] '{company}' 폴더 없음: {company_dir}")
        return None

    news_dir = company_dir / NEWS_SUBFOLDER
    note_path = news_dir / f"{date_str}.md"

    content = _build_daily_note(company, date_str, analyzed, collected_at)

    if dry_run:
        print(f"  [dry-run] {note_path.relative_to(vault)}")
        print(content[:400] + ("..." if len(content) > 400 else ""))
        return note_path

    news_dir.mkdir(exist_ok=True)
    note_path.write_text(content, encoding="utf-8")
    return note_path
