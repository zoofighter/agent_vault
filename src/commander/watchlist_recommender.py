"""
Watchlist Recommender — 하루 Daily 노트를 분석해서 신규 편입 후보 기업 추천

신호 5가지를 종합해서 점수를 매긴다:
  1. 뉴스 제목 직접 언급  — 추적 기업 뉴스에 타사 ticker/사명 등장
  2. 종합분석 텍스트 언급 — synthesis 블록에서 LLM이 추출
  3. 볼트 Memo 언급       — 사용자가 직접 메모에 쓴 기업
  4. 테마 섹터 동반자     — 오늘 강세 테마의 핵심 기업인데 미추적 상태
  5. 교차 기업 관계       — 공급망·고객사·경쟁사로 자주 등장
"""

import csv
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

_MODEL = "llama-3.3-70b-versatile"
_GROQ_BASE_URL = "https://api.groq.com/openai/v1"
_MAX_CANDIDATES = 5


@dataclass
class WatchlistCandidate:
    name: str
    ticker: str
    region: str
    reason: str           # 한 줄 요약
    signals: list[str]    # 어떤 신호에서 잡혔는지
    score: float          # 0~10
    source_companies: list[str] = field(default_factory=list)  # 언급 출처 기업


def _load_existing(companies_csv: Path) -> set[str]:
    """현재 추적 중인 기업 이름 집합 (소문자)."""
    names: set[str] = set()
    if not companies_csv.exists():
        return names
    with companies_csv.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            names.add(row["name"].strip().lower())
            if row.get("ticker"):
                names.add(row["ticker"].strip().lower())
    return names


def _collect_daily_content(vault_path: Path, date_str: str) -> list[dict]:
    """오늘 Daily 노트에서 회사명, 뉴스 제목, synthesis 추출."""
    docs = []
    for note in sorted(vault_path.glob(f"Companies/*/*/Daily/{date_str}*.md")):
        company = note.parent.parent.name
        text = note.read_text(encoding="utf-8")

        titles = re.findall(r"^### \d+\. (.+)$", text, re.MULTILINE)
        m = re.search(r"## 종합 분석\n\n(.*?)(?:\n---|\Z)", text, re.DOTALL)
        synthesis = m.group(1).strip()[:800] if m else ""

        docs.append({
            "company": company,
            "titles": titles[:15],
            "synthesis": synthesis,
        })
    return docs


def _collect_memo_text(vault_path: Path) -> str:
    """Memos/ 폴더 전체 텍스트 (최대 3000자)."""
    chunks = []
    for memo in sorted(vault_path.glob("Companies/*/*/Memos/*.md")):
        chunks.append(memo.read_text(encoding="utf-8")[:400])
        if sum(len(c) for c in chunks) > 3000:
            break
    return "\n".join(chunks)


def _build_prompt(
    docs: list[dict],
    existing_names: set[str],
    memo_text: str,
) -> str:
    existing_list = ", ".join(sorted(n for n in existing_names if len(n) > 2)[:60])

    content_parts = []
    for d in docs[:12]:
        titles_str = "\n".join(f"  - {t}" for t in d["titles"][:8])
        content_parts.append(
            f"[{d['company']}]\n뉴스:\n{titles_str}\n분석: {d['synthesis'][:300]}"
        )
    content_str = "\n\n".join(content_parts)

    return f"""You are an investment research assistant analyzing today's news to find companies worth adding to a watchlist.

CURRENT WATCHLIST (already tracked, do NOT recommend these):
{existing_list}

TODAY'S NEWS AND ANALYSIS:
{content_str}

USER MEMOS (companies explicitly noted by user):
{memo_text[:800] if memo_text else "없음"}

---
TASK: Identify up to {_MAX_CANDIDATES} companies NOT in the current watchlist that deserve monitoring.

Consider these signals:
1. Companies directly mentioned in news titles (tickers or names)
2. Companies referenced in analysis as suppliers, customers, or competitors
3. Companies the user mentioned in their memos
4. Sector peers of high-momentum companies not yet tracked
5. Emerging players in themes active today (AI infra, battery, semiconductor equipment, etc.)

IMPORTANT: Write ONLY in Korean. Use ONLY Korean characters. No English except for tickers and company names.
Output EXACTLY this JSON object (no extra text):

{{
  "candidates": [
    {{
      "name": "회사명 (영문)",
      "ticker": "TICKER or 없음",
      "region": "US/KR/CN/TW/JP/EU",
      "reason": "한 줄 추천 이유 (왜 지금 주목해야 하는가)",
      "signals": ["신호1", "신호2"],
      "score": 7.5,
      "source_companies": ["언급 출처 기업1", "언급 출처 기업2"]
    }}
  ]
}}"""


def _call_groq(prompt: str) -> list[dict]:
    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=os.environ.get("GROQ_API_KEY", ""),
            base_url=_GROQ_BASE_URL,
        )
        resp = client.chat.completions.create(
            model=_MODEL,
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        raw = (resp.choices[0].message.content or "").strip()
        # JSON 배열 혹은 {"candidates": [...]} 형태 모두 처리
        data = json.loads(raw)
        if isinstance(data, list):
            return data
        for v in data.values():
            if isinstance(v, list):
                return v
        return []
    except Exception as e:
        print(f"  [watchlist] LLM 호출 실패: {e}")
        return []


def _parse_candidates(raw: list[dict]) -> list[WatchlistCandidate]:
    result = []
    for item in raw:
        try:
            result.append(WatchlistCandidate(
                name=str(item.get("name", "Unknown")),
                ticker=str(item.get("ticker", "없음")),
                region=str(item.get("region", "US")),
                reason=str(item.get("reason", "")),
                signals=[str(s) for s in item.get("signals", [])],
                score=float(item.get("score", 5.0)),
                source_companies=[str(c) for c in item.get("source_companies", [])],
            ))
        except Exception:
            continue
    return sorted(result, key=lambda c: c.score, reverse=True)[:_MAX_CANDIDATES]


def _format_digest_body(candidates: list[WatchlistCandidate]) -> str:
    lines = []
    for i, c in enumerate(candidates, 1):
        ticker_str = f" ({c.ticker})" if c.ticker and c.ticker != "없음" else ""
        source_str = f" — {', '.join(c.source_companies[:2])}" if c.source_companies else ""
        signals_str = " · ".join(c.signals[:2])
        lines.append(
            f"**{i}. {c.name}{ticker_str}** [{c.region}] 점수 {c.score:.1f}/10{source_str}\n"
            f"> {c.reason}\n"
            f"> 신호: {signals_str}"
        )
    return "\n\n".join(lines)


def recommend(
    vault_path: Path,
    date_str: str,
    companies_csv: Path | None = None,
) -> list[WatchlistCandidate]:
    """오늘 Daily 노트 분석 → 신규 편입 후보 반환."""
    if companies_csv is None:
        companies_csv = vault_path.parent / "companies.csv"

    existing = _load_existing(companies_csv)
    docs = _collect_daily_content(vault_path, date_str)
    if not docs:
        return []

    memo_text = _collect_memo_text(vault_path)
    prompt = _build_prompt(docs, existing, memo_text)

    raw = _call_groq(prompt)
    candidates = _parse_candidates(raw)

    # 이미 추적 중인 기업 필터링 (LLM이 실수로 포함시킨 경우 제거)
    candidates = [
        c for c in candidates
        if c.name.lower() not in existing and c.ticker.lower() not in existing
    ]
    return candidates
