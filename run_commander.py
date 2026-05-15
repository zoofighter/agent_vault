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
import subprocess
from datetime import datetime, timezone
from pathlib import Path

_THEME_SECTOR_MAP: dict[str, str] = {
    "HBM": "반도체", "CoWoS": "반도체", "EUV": "반도체",
    "GAA": "반도체", "HBM3E": "반도체", "패키징": "반도체",
    "AI 반도체": "AI", "LLM": "AI", "MoE": "AI", "추론": "AI",
    "GLP-1": "바이오", "임상": "바이오", "ADC": "바이오",
    "전고체": "2차전지", "양극재": "2차전지", "리튬": "2차전지",
    "FSD": "자동차", "자율주행": "자동차", "전기차": "자동차",
    "OLED": "디스플레이", "MicroLED": "디스플레이",
    "SMR": "에너지", "원전": "에너지", "ESS": "에너지",
    "Starlink": "우주방산", "LEO": "우주방산", "드론": "우주방산",
    "큐비트": "양자컴퓨팅", "양자": "양자컴퓨팅",
    "휴머노이드": "로보틱스", "로봇": "로보틱스",
}

_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from src.commander.scanner import scan_daily_notes
from src.commander.dispatcher import generate_commands
from src.commander.notifier import push_commands, push_theme_surges, push_watchlist_recs
from src.commander.watchlist_recommender import recommend as recommend_watchlist


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
    parser.add_argument("--dry-run", action="store_true",
                        help="TechReport 트리거 시뮬레이션만 (subprocess 호출 생략)")
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
    commands = generate_commands(results, args.max_commands, args.threshold, vault_path=vault)

    # Phase 3: Inbox 기록
    print("\n[Phase 3] Inbox.md 기록...")
    if commands:
        push_commands(commands, vault)
    push_theme_surges(results, vault, args.theme_min)

    total = len(commands)

    # Phase 3.5: theme_surge → TechReport 자동 트리거
    print("\n[Phase 3.5] theme_surge → TechReport 자동 트리거...")
    _candidates = [r for r in results if r.score >= args.threshold][:args.max_commands]
    triggered: set[tuple[str, str]] = set()

    def _themes_from_text(text: str) -> list[str]:
        """cmd title/body에서 _THEME_SECTOR_MAP 키 검색 — key_themes 폴백용"""
        return [t for t in _THEME_SECTOR_MAP if t in text]

    def _already_reported(sector: str, theme: str) -> bool:
        """오늘 날짜 TechReport 파일 존재 여부 확인 (크로스런 중복 방지)"""
        import re as _re
        safe = _re.sub(r"[^\w가-힣\-]", "_", theme)
        return (vault / "Reports" / sector / f"{date_str}_{safe}.md").exists()

    for cmd, scan in zip(commands, _candidates):
        if cmd.command_type == "theme_surge":
            themes = scan.key_themes or _themes_from_text(cmd.title + " " + cmd.body)
            for theme in themes:
                sector = _THEME_SECTOR_MAP.get(theme)
                if not sector:
                    continue
                if (sector, theme) in triggered:
                    continue
                triggered.add((sector, theme))
                if _already_reported(sector, theme):
                    print(f"  이미 생성됨 — 건너뜀: {sector}/{theme}")
                    continue
                print(f"  theme_surge → TechReport: {sector}/{theme}")
                if not args.dry_run:
                    subprocess.run([
                        "python", "run_tech_report.py",
                        "--sector", sector,
                        "--topic",  theme,
                        "--vault",  str(vault),
                    ], cwd=str(Path(__file__).parent))
    if not triggered:
        print("  theme_surge 없음")

    # Phase 4: 신규 편입 후보 추천
    print("\n[Phase 4] 신규 편입 후보 탐색...")
    candidates = recommend_watchlist(vault, date_str)
    push_watchlist_recs(candidates, vault, date_str)

    print(f"\n완료: 명령 {total}개 / 편입 후보 {len(candidates)}개")


if __name__ == "__main__":
    main()
