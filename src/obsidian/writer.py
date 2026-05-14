"""
Obsidian 일일 뉴스 노트 저장

종합 분석(synthesis) + 뉴스 목록을 Daily/ 폴더에 단일 파일로 저장한다.
"""

from datetime import datetime, timezone
from pathlib import Path

from src.llm.analyzer import AnalyzedItem
from src.obsidian.company_manager import company_dir as _company_dir

DAILY_SUBFOLDER = "Daily"


def _recent_daily_links(daily_dir: Path, current_stem: str, n: int = 3) -> list[str]:
    """current_stem 이전 Daily 노트 wikilink 목록 (최신순)."""
    notes = sorted(
        (p for p in daily_dir.glob("*.md") if p.stem != current_stem),
        reverse=True,
    )
    return [f"[[{p.stem}]]" for p in notes[:n]]


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
        return "☆☆☆☆☆"
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
    synthesis: str | None = None,
) -> str:
    header = f"""---
type: daily-brief
company: "{company}"
date: {date_str}
collected: {collected_at}
news_count: {len(analyzed)}
tags:
  - daily
  - {company}
---

# {company} — {date_str}

> 관련 뉴스 {len(analyzed)}건 · {collected_at}
"""

    synthesis_block = ""
    if synthesis:
        synthesis_block = f"""
## 종합 분석

{synthesis}

---
"""

    if not analyzed:
        return header + synthesis_block + "\n관련 뉴스 없음\n"

    news_header = f"\n## 뉴스 목록 ({len(analyzed)}건)\n"
    sections = []
    for i, a in enumerate(analyzed, 1):
        item = a.item
        src = _source_label(item.source)
        snippet = (item.snippet or "").strip()
        reason = a.reason.strip()
        stars = _stars(a.distance, reason)

        block = f"""
### {i}. {item.title}

- **관련도**: {stars} `{a.distance:.2f}`
- **출처**: [{src}]({item.url})
- **관련 근거**: {reason}

{snippet}
"""
        sections.append(block)

    return header + synthesis_block + news_header + "\n".join(sections)


def _build_footer(daily_dir: Path, date_str: str) -> str:
    links = _recent_daily_links(daily_dir, date_str)
    if not links:
        return ""
    return "\n---\n\n**이전 노트**: " + " · ".join(links) + "\n"


def write_daily(
    company: str,
    analyzed: list[AnalyzedItem],
    vault_path: str | Path,
    date_str: str | None = None,
    date_suffix: str = "",
    synthesis: str | None = None,
    dry_run: bool = False,
) -> Path | None:
    """
    기업별 일일 Daily 노트(종합분석 + 뉴스목록)를 저장하고 경로를 반환한다.
    """
    vault = Path(vault_path)
    if date_str is None:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    date_str = date_str + date_suffix
    collected_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        co_dir = _company_dir(vault, company)
    except ValueError as e:
        print(f"  [skip] {e}")
        return None

    if not co_dir.exists():
        print(f"  [skip] '{company}' 폴더 없음: {co_dir}")
        return None

    daily_dir = co_dir / DAILY_SUBFOLDER
    note_path = daily_dir / f"{date_str}.md"

    content = _build_daily_note(company, date_str, analyzed, collected_at, synthesis)
    footer = _build_footer(daily_dir, date_str)
    content += footer

    if dry_run:
        print(f"  [dry-run] {note_path.relative_to(vault)}")
        print(content[:400] + ("..." if len(content) > 400 else ""))
        return note_path

    daily_dir.mkdir(exist_ok=True)
    note_path.write_text(content, encoding="utf-8")
    return note_path
