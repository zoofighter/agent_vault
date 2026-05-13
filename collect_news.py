#!/usr/bin/env python3
"""
뉴스 수집 CLI

사용법:
    python collect_news.py
    python collect_news.py --companies "삼성전자,현대차" --days 3
    python collect_news.py --vault ./sample_vault --dry-run
"""

import argparse
import os
from pathlib import Path

_env_file = Path(__file__).parent / '.env'
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip())

from src.obsidian.indexer import get_changed_files
from src.obsidian.embedder import index_files
from src.sources.collector import collect
from src.sources.naver_finance import NaverFinanceSource
from src.sources.base import NewsItem
from src.llm.analyzer import analyze
from src.obsidian.writer import write_daily

DEFAULT_COMPANIES = "삼성전자,Google,현대차,SK하이닉스"
DEFAULT_VAULT = Path(__file__).parent / "sample_vault"
CHROMA_PATH = "data/chroma"


def main():
    parser = argparse.ArgumentParser(description="Obsidian 뉴스 수집기")
    parser.add_argument('--companies', default=DEFAULT_COMPANIES)
    parser.add_argument('--days', type=int, default=7)
    parser.add_argument('--vault', default=str(DEFAULT_VAULT))
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--skip-index', action='store_true',
                        help='볼트 재인덱싱 건너뜀 (빠른 재실행용)')
    args = parser.parse_args()

    names = [n.strip() for n in args.companies.split(',') if n.strip()]
    vault = Path(args.vault)

    # ── Phase A: 볼트 증분 인덱싱 ──────────────────────────────────────
    if not args.skip_index:
        print("=== Phase A: 볼트 인덱싱 ===")
        changed = get_changed_files(vault)
        if changed:
            print(f"변경 파일 {len(changed)}개 임베딩 중...")
            total = index_files(changed, chroma_path=CHROMA_PATH)
            print(f"임베딩 완료: {total}청크")
        else:
            print("변경된 볼트 파일 없음 — 인덱스 최신 상태")
    else:
        print("=== Phase A: 인덱싱 건너뜀 ===")

    # ── Phase B: 뉴스 수집 ────────────────────────────────────────────
    print(f"\n=== Phase B: 뉴스 수집 (대상: {names}) ===")

    # Naver API + DuckDuckGo
    all_items: list[NewsItem] = collect(names, days=args.days)

    # 네이버 금융 메인 뉴스 (전사 공유, 회사별로 복사)
    print("\n[NaverFinance] 메인 뉴스 수집 중...")
    nf_items_raw = NaverFinanceSource().fetch_all()
    print(f"  수집: {len(nf_items_raw)}건")
    nf_items: list[NewsItem] = []
    for name in names:
        for item in nf_items_raw:
            import copy
            cloned = copy.copy(item)
            cloned.company = name
            nf_items.append(cloned)
    all_items.extend(nf_items)

    # 회사별 집계
    for name in names:
        cnt = sum(1 for i in all_items if i.company == name)
        print(f"  {name}: {cnt}건")

    # ── Phase C: 벡터 유사도 필터 + LLM 근거 생성 ──────────────────────
    print(f"\n=== Phase C: 관련성 분석 ===")
    written_paths = []

    for name in names:
        items_for = [i for i in all_items if i.company == name]
        print(f"\n[{name}] {len(items_for)}건 분석 중...")

        analyzed = analyze(items_for, company=name, chroma_path=CHROMA_PATH)
        print(f"  → 관련 뉴스 {len(analyzed)}건 선별")

        path = write_daily(
            company=name,
            analyzed=analyzed,
            vault_path=vault,
            dry_run=args.dry_run,
        )
        if path:
            written_paths.append(path)

    # ── 결과 요약 ─────────────────────────────────────────────────────
    print(f"\n{'='*50}")
    if args.dry_run:
        print(f"[dry-run] 저장 예정: {len(written_paths)}개 파일")
    else:
        print(f"완료: {len(written_paths)}개 파일 저장")
        for p in written_paths:
            print(f"  {p.relative_to(vault)}")


if __name__ == '__main__':
    main()
