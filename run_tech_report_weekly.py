#!/usr/bin/env python3
"""
TechReportAgent Phase 3 — 주간 전 섹터 weekly 리포트 자동 생성

매주 월요일(기본) LaunchAgent가 실행. 11개 섹터 × 핵심 토픽 weekly 리포트 생성.
개별 Telegram 전송 없이 완료 후 통합 요약 1건 전송.

사용:
  python run_tech_report_weekly.py --vault ./agent_vault
  python run_tech_report_weekly.py --vault ./agent_vault --dry-run
  python run_tech_report_weekly.py --vault ./agent_vault --sectors AI 반도체 바이오
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

from src.tech_report.collector import collect
from src.tech_report.reporter import generate_report, save_report
from src.obsidian.digest import append_record

# 섹터별 주간 업데이트 대표 토픽
# 토픽은 해당 섹터의 현재 핵심 이슈를 반영하는 키워드
_WEEKLY_TOPICS: dict[str, str] = {
    "AI":       "AI 인프라 주간동향",
    "반도체":   "반도체 공급망 주간동향",
    "바이오":   "바이오 파이프라인 주간동향",
    "헬스케어": "헬스케어 주간동향",
    "디스플레이":"디스플레이 주간동향",
    "2차전지":  "배터리 소재 주간동향",
    "자동차":   "전기차 자율주행 주간동향",
    "에너지":   "에너지 전력 주간동향",
    "우주방산": "우주방산 주간동향",
    "양자컴퓨팅":"양자컴퓨팅 주간동향",
    "로보틱스": "로보틱스 주간동향",
}


def run_weekly(vault: Path, sectors: list[str], date_str: str, dry_run: bool) -> None:
    results: list[dict] = []
    total = len(sectors)

    for i, sector in enumerate(sectors, 1):
        topic = _WEEKLY_TOPICS.get(sector, f"{sector} 주간동향")
        print(f"\n[{i}/{total}] {sector} — {topic}")

        try:
            articles = collect(sector, topic, days=7)
            print(f"  수집: {len(articles)}건")

            content = generate_report(sector, topic, articles, report_type="weekly")
            if not content:
                print(f"  [오류] 리포트 생성 실패")
                results.append({"sector": sector, "ok": False, "path": None})
                continue

            if dry_run:
                print(f"  [dry-run] 리포트 {len(content.splitlines())}줄 생성됨 (저장 안 함)")
                results.append({"sector": sector, "ok": True, "path": None})
                continue

            path = save_report(vault, sector, topic, content, date_str, report_type="weekly")
            print(f"  저장: {path.name}")
            results.append({"sector": sector, "ok": True, "path": path, "content": content})

        except Exception as e:
            print(f"  [오류] {e}")
            results.append({"sector": sector, "ok": False, "path": None})

    if dry_run:
        print(f"\n--- dry-run 완료 ({sum(r['ok'] for r in results)}/{total} 성공) ---")
        return

    _notify_summary(vault, results, date_str)


def _notify_summary(vault: Path, results: list[dict], date_str: str) -> None:
    ok_results = [r for r in results if r["ok"] and r["path"]]
    failed = [r["sector"] for r in results if not r["ok"]]

    # Digest 기록
    lines = []
    for r in ok_results:
        rel = "/".join(r["path"].parts[-3:])
        lines.append(f"- [{r['sector']}]({rel})")
    if failed:
        lines.append(f"\n실패: {', '.join(failed)}")

    append_record(
        vault,
        title=f"Weekly TechReport — {date_str}",
        body="\n".join(lines),
        level="info",
        date=date_str,
    )

    # Telegram 통합 요약
    try:
        from src.telegram.sender import send
    except ImportError:
        return

    report_list = "\n".join(
        f"• *{r['sector']}*: `{r['path'].name}`"
        for r in ok_results
    )
    fail_str = f"\n실패: {', '.join(failed)}" if failed else ""
    msg = (
        f"*주간 테크 리포트 완료* ({date_str})\n\n"
        f"{report_list}"
        f"{fail_str}\n\n"
        f"총 {len(ok_results)}/{len(results)}개 섹터 완료"
    )
    send(msg)


def main() -> None:
    parser = argparse.ArgumentParser(description="TechReportAgent Weekly — 전 섹터 주간 리포트")
    parser.add_argument("--vault",    required=True, help="Obsidian 볼트 경로")
    parser.add_argument("--date",     default=None,  help="날짜 YYYY-MM-DD (기본: 오늘)")
    parser.add_argument("--sectors",  nargs="+",     default=None,
                        help="특정 섹터만 실행 (기본: 전 섹터)")
    parser.add_argument("--dry-run",  action="store_true",
                        help="저장·전송 없이 생성만 확인")
    args = parser.parse_args()

    vault    = Path(args.vault).resolve()
    date_str = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sectors  = args.sectors or list(_WEEKLY_TOPICS.keys())

    print(f"=== TechReport Weekly [{date_str}] — {len(sectors)}개 섹터 ===")
    run_weekly(vault, sectors, date_str, args.dry_run)
    print(f"\n완료")


if __name__ == "__main__":
    main()
