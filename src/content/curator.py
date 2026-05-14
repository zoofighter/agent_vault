"""
콘텐츠 소재 선별

Daily 노트 중 콘텐츠 제작 가치가 있는 것을 선별한다.
- news_count, star_avg, synthesis 구조 기반 휴리스틱
"""

import re
from dataclasses import dataclass
from pathlib import Path

_STAR_VALUES = {"★★★★★": 5, "★★★★☆": 4, "★★★☆☆": 3, "★★☆☆☆": 2, "★☆☆☆☆": 1}

_CONTENT_SECTIONS = (
    "오늘의 핵심 뉴스 TOP 3",
    "오늘의 핵심 테마",
    "투자 시사점",
    "논거 검증",
    "리스크 업데이트",
)


@dataclass
class ContentCandidate:
    company: str
    date: str
    note_path: Path
    news_count: int
    synthesis: str
    content_score: float  # 0-1, higher = better content potential


def _parse_note(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")

    m = re.search(r"^news_count:\s*(\d+)", text, re.MULTILINE)
    news_count = int(m.group(1)) if m else 0

    m = re.search(r"## 종합 분석\n\n(.*?)(?:\n---|\Z)", text, re.DOTALL)
    synthesis = m.group(1).strip() if m else ""

    stars = re.findall(r"(★[★☆]{4})", text)
    star_avg = sum(_STAR_VALUES.get(s, 0) for s in stars) / len(stars) if stars else 0

    # Check how many content sections exist in synthesis
    section_count = sum(1 for s in _CONTENT_SECTIONS if s in synthesis)

    return {
        "news_count": news_count,
        "synthesis": synthesis,
        "star_avg": star_avg,
        "section_count": section_count,
    }


def _content_score(parsed: dict) -> float:
    nc = min(parsed["news_count"] / 10.0, 1.0)
    star = parsed["star_avg"] / 5.0
    sections = parsed["section_count"] / len(_CONTENT_SECTIONS)
    return round(nc * 0.3 + star * 0.4 + sections * 0.3, 3)


def select_candidates(
    vault_path: Path,
    date_str: str,
    min_score: float = 0.35,
    max_candidates: int = 5,
) -> list[ContentCandidate]:
    """date_str 날짜의 Daily 노트 중 콘텐츠 가치 있는 것 반환 (점수 순)."""
    candidates: list[ContentCandidate] = []

    for note_path in vault_path.glob(f"Companies/*/*/Daily/{date_str}*.md"):
        company = note_path.parent.parent.name
        parsed = _parse_note(note_path)
        score = _content_score(parsed)

        if score >= min_score and parsed["synthesis"]:
            candidates.append(ContentCandidate(
                company=company,
                date=date_str,
                note_path=note_path,
                news_count=parsed["news_count"],
                synthesis=parsed["synthesis"],
                content_score=score,
            ))

    return sorted(candidates, key=lambda c: c.content_score, reverse=True)[:max_candidates]
