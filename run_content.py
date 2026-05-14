#!/usr/bin/env python3
"""
Content Writer Agent — Daily 노트 → 블로그/유튜브 스크립트 초안 생성

사용:
  python run_content.py --vault ./agent_vault
  python run_content.py --vault ./agent_vault --date 2026-05-14
  python run_content.py --vault ./agent_vault --mode blog
  python run_content.py --vault ./agent_vault --mode youtube
  python run_content.py --vault ./agent_vault --company 삼성전자
  python run_content.py --vault ./agent_vault --dry-run
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

from src.content.curator import select_candidates
from src.content.writer import generate_blog, generate_youtube_script
from src.content.publisher import save_blog, save_youtube


def main() -> None:
    parser = argparse.ArgumentParser(description="Content Writer Agent")
    parser.add_argument("--vault", required=True, help="Obsidian 볼트 경로")
    parser.add_argument("--date", default=None, help="날짜 YYYY-MM-DD (기본: 오늘)")
    parser.add_argument("--mode", choices=["blog", "youtube", "both"], default="blog")
    parser.add_argument("--company", default=None, help="특정 기업만 처리")
    parser.add_argument("--max", type=int, default=3, dest="max_candidates")
    parser.add_argument("--min-score", type=float, default=0.35)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    vault = Path(args.vault).resolve()
    date_str = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    print(f"=== Content Writer Agent [{date_str}] mode={args.mode} ===")

    candidates = select_candidates(vault, date_str, args.min_score, args.max_candidates)

    if args.company:
        candidates = [c for c in candidates if c.company == args.company]

    if not candidates:
        print("  콘텐츠 소재 없음 (min_score 낮추거나 날짜 확인)")
        return

    print(f"  소재 {len(candidates)}개 선별")
    for c in candidates:
        print(f"  {c.company}: score={c.content_score:.2f} news={c.news_count}")

    saved: list[Path] = []

    for c in candidates:
        print(f"\n[{c.company}] 콘텐츠 생성 중...")

        if args.mode in ("blog", "both"):
            print("  블로그 초안...", end=" ", flush=True)
            blog_content = generate_blog(c)
            path = save_blog(vault, c, blog_content, dry_run=args.dry_run)
            saved.append(path)
            if not args.dry_run:
                print(f"저장: {path.relative_to(vault)}")
            else:
                print("(dry-run)")

        if args.mode in ("youtube", "both"):
            print("  유튜브 스크립트...", end=" ", flush=True)
            yt_content = generate_youtube_script(c)
            path = save_youtube(vault, c, yt_content, dry_run=args.dry_run)
            saved.append(path)
            if not args.dry_run:
                print(f"저장: {path.relative_to(vault)}")
            else:
                print("(dry-run)")

    print(f"\n완료: {len(saved)}개 파일 저장")


if __name__ == "__main__":
    main()
