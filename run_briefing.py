#!/usr/bin/env python3
"""
Briefing Agent — Digest 요약 → 대화체 아침/저녁 브리핑 → Telegram 전송

사용:
  python run_briefing.py --vault ./agent_vault
  python run_briefing.py --vault ./agent_vault --date 2026-05-14
  python run_briefing.py --vault ./agent_vault --dry-run
"""

import argparse
import os
import re
from datetime import datetime, timezone
from pathlib import Path

_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from src.commander.scanner import scan_daily_notes
from src.obsidian.digest import append_record
from src.telegram.sender import send

_MODEL = "llama-3.3-70b-versatile"
_GROQ_BASE_URL = "https://api.groq.com/openai/v1"


def _read_digest_blocks(vault_path: Path, date_str: str) -> list[str]:
    digest_path = vault_path / "Digest" / f"{date_str}.md"
    if not digest_path.exists():
        return []
    text = digest_path.read_text(encoding="utf-8")
    blocks = re.findall(r"> \[!\w+\] .+?(?=\n> \[!|\Z)", text, re.DOTALL)
    plain = []
    for b in blocks:
        lines = [ln.lstrip("> ").strip() for ln in b.strip().splitlines()]
        plain.append("\n".join(l for l in lines if l))
    return plain


def _build_briefing_prompt(
    date_str: str,
    top_companies: list[tuple[str, float, int]],
    digest_blocks: list[str],
) -> str:
    top_str = "\n".join(
        f"  {c} (중요도 {s:.2f}, 뉴스 {n}건)" for c, s, n in top_companies[:5]
    )
    digest_str = "\n\n---\n".join(digest_blocks[:4]) if digest_blocks else "없음"

    return f"""You are AgentVault, a personal investment assistant.
Today is {date_str}.

Top companies by importance today:
{top_str}

Commander actions generated today:
{digest_str}

Write a SHORT conversational morning briefing. Rules:
- Use ONLY Korean (한국어만 사용). Zero English, Chinese, Russian, or other languages.
- 3-5 sentences. Natural and friendly tone, like a trusted analyst colleague.
- Mention 2-3 most important themes or companies.
- Last sentence must be: "오늘 주목할 기업: X ★★★★★ / Y ★★★★☆ / Z ★★★★☆"
- No markdown headers, no bullet lists, no bold text.
- Output the briefing text ONLY. Nothing else.
"""


_CJK_REPLACE = {
    "増加": "증가", "減少": "감소", "成長": "성장", "市場": "시장",
    "技術": "기술", "投資": "투자", "企業": "기업", "分析": "분석",
    "強化": "강화", "拡大": "확대", "増大": "증대", "向上": "향상",
}

def _sanitize(text: str) -> str:
    for zh, ko in _CJK_REPLACE.items():
        text = text.replace(zh, ko)
    # 남은 한자/일본어(CJK Unified) 제거
    text = re.sub(r"[一-鿿぀-ヿ]", "", text)
    # Cyrillic 제거
    text = re.sub(r"[Ѐ-ӿ]", "", text)
    return text.strip()


def _call_groq(prompt: str) -> str:
    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=os.environ.get("GROQ_API_KEY", ""),
            base_url=_GROQ_BASE_URL,
        )
        resp = client.chat.completions.create(
            model=_MODEL,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = (resp.choices[0].message.content or "").strip()
        return _sanitize(raw)
    except Exception as e:
        return f"브리핑 생성 실패: {e}"


def _stars(score: float) -> str:
    if score >= 0.85:
        return "★★★★★"
    if score >= 0.70:
        return "★★★★☆"
    if score >= 0.55:
        return "★★★☆☆"
    return "★★☆☆☆"


def main() -> None:
    parser = argparse.ArgumentParser(description="Briefing Agent")
    parser.add_argument("--vault", required=True, help="Obsidian 볼트 경로")
    parser.add_argument("--date", default=None, help="날짜 YYYY-MM-DD (기본: 오늘)")
    parser.add_argument("--dry-run", action="store_true", help="Telegram 전송 없이 출력만")
    args = parser.parse_args()

    vault = Path(args.vault).resolve()
    date_str = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    print(f"=== Briefing Agent [{date_str}] ===")

    # 1. Daily 노트 스캔 (휴리스틱만, 빠르게)
    print("스캔 중...")
    results = scan_daily_notes(vault, date_str, use_llm=False)
    if not results:
        print("  Daily 노트 없음 — 종료")
        return

    top = [(r.company, r.score, r.news_count) for r in results[:5]]
    print(f"  {len(results)}개 기업 / 상위: {', '.join(c for c, _, _ in top[:3])}")

    # 2. Digest 블록 읽기
    blocks = _read_digest_blocks(vault, date_str)
    print(f"  Digest 블록: {len(blocks)}개")

    # 3. 브리핑 생성
    print("브리핑 생성 중...")
    prompt = _build_briefing_prompt(date_str, top, blocks)
    briefing = _call_groq(prompt)
    print(f"\n--- 생성된 브리핑 ---\n{briefing}\n---\n")

    # 4. Digest에 기록
    append_record(
        vault,
        title=f"아침 브리핑 — {date_str}",
        body=briefing,
        level="info",
        date=date_str,
    )

    # 5. Telegram 전송
    top_line = " / ".join(f"{c} {_stars(s)}" for c, s, _ in top[:3])
    message = f"*AgentVault 브리핑 — {date_str}*\n\n{briefing}\n\n_{top_line}_"

    if args.dry_run:
        print("[dry-run] Telegram 전송 건너뜀")
        print(f"전송 예정 메시지:\n{message}")
        return

    ok = send(message)
    print(f"Telegram {'전송 완료' if ok else '전송 실패'}")


if __name__ == "__main__":
    main()
