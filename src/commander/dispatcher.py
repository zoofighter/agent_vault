"""
상위 ScanResult → Claude API → 액션 명령 텍스트 생성

비용 제어: 하루 최대 max_commands 개 기업에만 Cloud LLM 호출.
"""

import os
import re
from dataclasses import dataclass

from src.commander.scanner import ScanResult

_MODEL = "llama-3.3-70b-versatile"
_GROQ_BASE_URL = "https://api.groq.com/openai/v1"
_SCORE_THRESHOLD = 0.45
_MAX_COMMANDS = 3

_STARS_MAP = {(0.85, 1.0): "★★★★★", (0.70, 0.85): "★★★★☆",
              (0.55, 0.70): "★★★☆☆", (0.40, 0.55): "★★☆☆☆"}


def _stars(score: float) -> str:
    for (lo, hi), s in _STARS_MAP.items():
        if lo <= score <= hi:
            return s
    return "★☆☆☆☆"


@dataclass
class Command:
    company: str
    title: str
    body: str
    actions: str
    stars: str
    score: float
    command_type: str


def _build_prompt(r: ScanResult) -> str:
    titles_str = "\n".join(f"- {t}" for t in r.top_titles)
    themes_str = ", ".join(r.key_themes) if r.key_themes else "없음"
    return f"""You are AgentVault Commander, an investment monitoring AI.

Company: {r.company}
Date: {r.date}
News count today: {r.news_count}
Importance score: {r.score:.2f}
Key themes detected: {themes_str}

Top news titles:
{titles_str}

Daily synthesis (excerpt):
{r.synthesis[:1200]}

---
Generate a concise action command for the investor.
IMPORTANT: Write ONLY in Korean. Do NOT use Chinese, Japanese, Russian, or any other language characters.
Output EXACTLY this format (no extra text):

TYPE: [report_found|theme_surge|thesis_conflict|deep_analysis]
TITLE: [한 줄 제목, 최대 50자]
BODY: [2-3문장. 왜 중요한지, 어떤 신호인지]
ACTIONS:
- [구체적 액션 1]
- [구체적 액션 2]
"""


def _parse_response(text: str, r: ScanResult) -> Command:
    def extract(key: str) -> str:
        m = re.search(rf"^{key}:\s*(.+)$", text, re.MULTILINE)
        return m.group(1).strip() if m else ""

    cmd_type = extract("TYPE") or "deep_analysis"
    title = extract("TITLE") or f"{r.company} 주목 필요"
    body = extract("BODY") or r.score_reason

    # Extract action bullets
    m = re.search(r"^ACTIONS:\s*\n((?:\s*[-•]\s*.+\n?)+)", text, re.MULTILINE)
    actions = m.group(1).strip() if m else f"- {r.company} 관련 심층 분석 수행"

    return Command(
        company=r.company,
        title=title,
        body=body,
        actions=actions,
        stars=_stars(r.score),
        score=r.score,
        command_type=cmd_type,
    )


def _call_groq(prompt: str) -> str:
    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=os.environ.get("GROQ_API_KEY", ""),
            base_url=_GROQ_BASE_URL,
        )
        resp = client.chat.completions.create(
            model=_MODEL,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content or ""
    except Exception as e:
        return f"TYPE: deep_analysis\nTITLE: {e}\nBODY: Groq API 호출 실패\nACTIONS:\n- 수동 확인 필요"


def generate_commands(
    results: list[ScanResult],
    max_commands: int = _MAX_COMMANDS,
    score_threshold: float = _SCORE_THRESHOLD,
) -> list[Command]:
    """상위 스코어 기업에 대해 Claude API로 액션 명령 생성."""
    candidates = [r for r in results if r.score >= score_threshold][:max_commands]
    commands: list[Command] = []

    for r in candidates:
        print(f"  [commander] {r.company} (score={r.score:.2f}) — 명령 생성 중...")
        prompt = _build_prompt(r)
        raw = _call_groq(prompt)
        cmd = _parse_response(raw, r)
        commands.append(cmd)
        print(f"    → [{cmd.stars}] {cmd.title}")

    return commands
