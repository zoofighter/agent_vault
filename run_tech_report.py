#!/usr/bin/env python3
"""
TechReportAgent Phase 1 — 메르 스타일 섹터 기술 리포트 생성

사용:
  python run_tech_report.py --sector 반도체 --topic CoWoS --vault ./agent_vault
  python run_tech_report.py --sector AI --topic MoE --vault ./agent_vault --type onboarding
  python run_tech_report.py --sector 바이오 --topic GLP-1 --vault ./agent_vault --dry-run

지원 섹터: AI, 반도체, 바이오, 헬스케어, 디스플레이, 2차전지, 자동차,
          에너지, 우주방산, 양자컴퓨팅, 로보틱스
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

from src.tech_report.collector import collect, SECTOR_QUERIES
from src.tech_report.reporter import generate_report, save_report, notify

_VALID_SECTORS = list(SECTOR_QUERIES.keys())
_VALID_TYPES = ["issue", "onboarding", "weekly"]


def main() -> None:
    parser = argparse.ArgumentParser(description="TechReportAgent — 메르 스타일 리포트 생성")
    parser.add_argument("--sector", required=True,
                        help=f"섹터 지정: {', '.join(_VALID_SECTORS)}")
    parser.add_argument("--topic",  required=True,
                        help="리포트 토픽 키워드 (예: CoWoS, HBM, GLP-1)")
    parser.add_argument("--vault",  required=True,
                        help="Obsidian 볼트 경로 (agent_vault)")
    parser.add_argument("--type",   default="issue", dest="report_type",
                        choices=_VALID_TYPES,
                        help="리포트 유형: issue(기본) / onboarding / weekly")
    parser.add_argument("--days",   type=int, default=7,
                        help="뉴스 수집 기간 (일, 기본: 7)")
    parser.add_argument("--date",   default=None,
                        help="날짜 YYYY-MM-DD (기본: 오늘)")
    parser.add_argument("--dry-run", action="store_true",
                        help="파일 저장·Telegram 전송 없이 리포트 내용만 출력")
    args = parser.parse_args()

    sector = args.sector
    topic  = args.topic
    vault  = Path(args.vault).resolve()
    date_str = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if sector not in _VALID_SECTORS:
        print(f"[오류] 지원하지 않는 섹터: {sector}")
        print(f"  지원 목록: {', '.join(_VALID_SECTORS)}")
        return

    print(f"=== TechReportAgent [{sector} / {topic}] {date_str} ===")

    # Phase 1: 뉴스 수집
    print(f"\n[1/3] 뉴스 수집 중 ({args.days}일 범위)...")
    articles = collect(sector, topic, days=args.days)
    print(f"  수집: {len(articles)}건")
    if not articles:
        print("  [경고] 뉴스를 수집하지 못했음. 토픽 키워드를 확인하거나 인터넷 연결을 점검해라.")

    # Phase 2: 리포트 생성
    print(f"\n[2/3] 리포트 생성 중 (Groq / {args.report_type})...")
    report_content = generate_report(sector, topic, articles, args.report_type)
    if not report_content:
        print("  [오류] 리포트 생성 실패. GROQ_API_KEY를 확인해라.")
        return

    lines = report_content.splitlines()
    print(f"  생성: {len(lines)}줄")

    # dry-run: 내용 출력 후 종료
    if args.dry_run:
        print("\n--- 리포트 미리보기 (dry-run) ---")
        print(report_content[:2000])
        if len(report_content) > 2000:
            print(f"\n... (이하 {len(report_content) - 2000}자 생략)")
        print("--- dry-run 완료 (저장·전송 없음) ---")
        return

    # Phase 3: 저장 + 알림
    print(f"\n[3/3] 저장 및 알림...")
    report_path = save_report(vault, sector, topic, report_content, date_str, args.report_type)
    print(f"  저장: {report_path}")

    notify(vault, sector, topic, report_path, report_content, date_str)
    print(f"  알림: Telegram + Digest 완료")

    print(f"\n완료: Reports/{sector}/{report_path.name}")


if __name__ == "__main__":
    main()
