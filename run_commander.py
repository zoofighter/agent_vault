#!/usr/bin/env python3
"""
Commander Agent — Daily 노트 분석 → Inbox.md 액션 명령 생성

사용:
  python run_commander.py --vault ./agent_vault
  python run_commander.py --vault ./agent_vault --date 2026-05-14
  python run_commander.py --vault ./agent_vault --no-llm   # 휴리스틱만
  python run_commander.py --vault ./agent_vault --max 5
"""

import argparse
import os
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
from src.commander.dispatcher import generate_commands
from src.commander.notifier import push_commands, push_theme_surges


def main() -> None:
    parser = argparse.ArgumentParser(description="Commander Agent")
    parser.add_argument("--vault", required=True, help="Obsidian 볼트 경로")
    parser.add_argument("--date", default=None, help="분석 날짜 YYYY-MM-DD (기본: 오늘)")
    parser.add_argument("--max", type=int, default=3, dest="max_commands",
                        help="최대 명령 수 (기본: 3)")
    parser.add_argument("--threshold", type=float, default=0.45,
                        help="명령 생성 최소 점수 (기본: 0.45)")
    parser.add_argument("--no-llm", action="store_true",
                        help="Local LLM 스코어링 건너뜀 (휴리스틱만)")
    parser.add_argument("--theme-min", type=int, default=3,
                        help="테마 급등 감지 최소 기업 수 (기본: 3)")
    args = parser.parse_args()

    vault = Path(args.vault).resolve()
    date_str = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    print(f"=== Commander Agent [{date_str}] ===")
    print(f"볼트: {vault}")

    # Phase 1: 스캔
    print("\n[Phase 1] Daily 노트 스캔 중...")
    results = scan_daily_notes(vault, date_str, use_llm=not args.no_llm)
    if not results:
        print(f"  [{date_str}] Daily 노트 없음 — 종료")
        return
    print(f"  {len(results)}개 기업 스캔 완료")
    for r in results[:5]:
        print(f"  {r.company}: score={r.score:.2f} news={r.news_count} — {r.score_reason[:40]}")

    # Phase 2: 명령 생성
    print(f"\n[Phase 2] 액션 명령 생성 (threshold={args.threshold}, max={args.max_commands})...")
    commands = generate_commands(results, args.max_commands, args.threshold)

    # Phase 3: Inbox 기록
    print("\n[Phase 3] Inbox.md 기록...")
    if commands:
        push_commands(commands, vault)
    push_theme_surges(results, vault, args.theme_min)

    total = len(commands)
    print(f"\n완료: 명령 {total}개 Inbox.md에 기록")


if __name__ == "__main__":
    main()
