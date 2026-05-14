"""
Daily 노트 스캔 + 중요도 평가

오늘 생성된 모든 Daily 노트를 읽고 Local LLM으로 중요도 점수를 계산한다.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

import ollama

_LLM_MODEL = "gemma4:e2b"

_IMPORTANT_KEYWORDS = (
    "급등", "급락", "실적", "발표", "우선권", "돌파", "신기록", "충격",
    "계약", "인수", "합병", "파산", "제재", "규제", "핵심", "전략",
    "분기", "어닝", "가이던스", "목표가", "상향", "하향", "리콜",
    "리포트", "투자의견", "매수", "매도", "hold",
    "surge", "plunge", "record", "deal", "contract", "acquisition",
)

_STAR_VALUES = {"★★★★★": 5, "★★★★☆": 4, "★★★☆☆": 3, "★★☆☆☆": 2, "★☆☆☆☆": 1}


@dataclass
class ScanResult:
    company: str
    date: str
    note_path: Path
    news_count: int
    synthesis: str
    top_titles: list[str] = field(default_factory=list)
    key_themes: list[str] = field(default_factory=list)
    score: float = 0.0
    score_reason: str = ""


def _parse_daily_note(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")

    # frontmatter news_count
    m = re.search(r"^news_count:\s*(\d+)", text, re.MULTILINE)
    news_count = int(m.group(1)) if m else 0

    # synthesis block (between ## 종합 분석 and ---)
    synthesis = ""
    m = re.search(r"## 종합 분석\n\n(.*?)(?:\n---|\Z)", text, re.DOTALL)
    if m:
        synthesis = m.group(1).strip()

    # extract news titles (### N. title)
    titles = re.findall(r"^### \d+\. (.+)$", text, re.MULTILINE)

    # average star rating
    stars_found = re.findall(r"(★[★☆]{4})", text)
    star_avg = 0.0
    if stars_found:
        vals = [_STAR_VALUES.get(s, 0) for s in stars_found]
        star_avg = sum(vals) / len(vals)

    # keyword hits in synthesis
    combined = synthesis + " ".join(titles)
    keyword_hits = sum(1 for kw in _IMPORTANT_KEYWORDS if kw.lower() in combined.lower())

    return {
        "news_count": news_count,
        "synthesis": synthesis,
        "titles": titles[:10],
        "star_avg": star_avg,
        "keyword_hits": keyword_hits,
    }


def _heuristic_score(parsed: dict) -> float:
    nc = min(parsed["news_count"] / 15.0, 1.0)
    star = parsed["star_avg"] / 5.0
    kw = min(parsed["keyword_hits"] / 5.0, 1.0)
    return round(nc * 0.35 + star * 0.45 + kw * 0.20, 3)


def _llm_score(company: str, synthesis: str) -> tuple[float, str]:
    if not synthesis:
        return 0.0, "synthesis 없음"
    prompt = (
        f"You are evaluating investment importance for {company}.\n\n"
        f"Daily news synthesis:\n{synthesis[:1500]}\n\n"
        "Rate the investment importance 0.0-1.0 and give a one-sentence reason.\n"
        'Reply ONLY with valid JSON: {"score": 0.X, "reason": "..."}'
    )
    try:
        resp = ollama.generate(model=_LLM_MODEL, prompt=prompt,
                               options={"num_predict": 80}, think=False)
        raw = resp.response.strip()
        import json
        m = re.search(r'\{.*?\}', raw, re.DOTALL)
        if m:
            data = json.loads(m.group())
            score = float(data.get("score", 0))
            reason = str(data.get("reason", ""))
            return min(max(score, 0.0), 1.0), reason
    except Exception:
        pass
    return 0.0, "LLM 스코어링 실패"


def _extract_themes(synthesis: str) -> list[str]:
    themes = re.findall(r"##\s*오늘의 핵심 테마\s*\n(.*?)(?=##|\Z)", synthesis, re.DOTALL)
    if not themes:
        return []
    block = themes[0]
    items = re.findall(r"\*\*(.+?)\*\*", block)
    return items[:4]


def scan_daily_notes(
    vault_path: Path,
    date_str: str,
    use_llm: bool = True,
) -> list[ScanResult]:
    """date_str 날짜의 모든 Daily 노트를 읽고 중요도 순으로 정렬한 ScanResult 반환."""
    results: list[ScanResult] = []

    for note_path in sorted(vault_path.glob(f"Companies/*/*/Daily/{date_str}*.md")):
        company = note_path.parent.parent.name
        parsed = _parse_daily_note(note_path)

        score = _heuristic_score(parsed)
        score_reason = "휴리스틱"

        # LLM refine if synthesis exists and heuristic score is meaningful
        if use_llm and parsed["synthesis"] and score >= 0.3:
            llm_s, llm_r = _llm_score(company, parsed["synthesis"])
            if llm_s > 0:
                score = round((score + llm_s) / 2, 3)
                score_reason = llm_r

        results.append(ScanResult(
            company=company,
            date=date_str,
            note_path=note_path,
            news_count=parsed["news_count"],
            synthesis=parsed["synthesis"],
            top_titles=parsed["titles"][:5],
            key_themes=_extract_themes(parsed["synthesis"]),
            score=score,
            score_reason=score_reason,
        ))

    return sorted(results, key=lambda r: r.score, reverse=True)
