#!/usr/bin/env python3
"""
뉴스 수집 CLI

사용법:
    python collect_news.py
    python collect_news.py --companies "삼성전자,Google,현대차,SK하이닉스" --days 7
    python collect_news.py --output results.json
"""

import argparse
import dataclasses
import json
from src.sources.collector import collect

DEFAULT_COMPANIES = "삼성전자,Google,현대차,SK하이닉스"


def main():
    parser = argparse.ArgumentParser(description="Obsidian 뉴스 수집기")
    parser.add_argument('--companies', default=DEFAULT_COMPANIES,
                        help='쉼표 구분 기업명 (기본: 삼성전자,Google,현대차,SK하이닉스)')
    parser.add_argument('--days', type=int, default=7,
                        help='수집 기간 일수 (기본: 7)')
    parser.add_argument('--output', default=None,
                        help='JSON 저장 경로 (미지정 시 콘솔 출력)')
    args = parser.parse_args()

    names = [n.strip() for n in args.companies.split(',') if n.strip()]
    print(f"수집 대상: {names}")
    print(f"기간: 최근 {args.days}일\n")

    items = collect(names, days=args.days)

    print(f"\n{'='*50}")
    print(f"총 {len(items)}건 수집 완료")
    for name in names:
        count = sum(1 for i in items if i.company == name)
        src_counts = {}
        for i in items:
            if i.company == name:
                src_counts[i.source] = src_counts.get(i.source, 0) + 1
        detail = ', '.join(f"{s}:{n}" for s, n in src_counts.items())
        print(f"  {name}: {count}건  ({detail})")

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump([dataclasses.asdict(i) for i in items], f, ensure_ascii=False, indent=2)
        print(f"\n→ {args.output} 저장 완료")
    else:
        print(f"\n--- 샘플 (최신 10건) ---")
        for item in items[:10]:
            print(f"[{item.company}] {item.published or '?'} | {item.source}")
            print(f"  {item.title}")
            print(f"  {item.url[:80]}")


if __name__ == '__main__':
    main()
