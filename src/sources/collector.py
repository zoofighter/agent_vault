"""
뉴스 수집 오케스트레이터

- KRX 상장사: Naver News + DuckDuckGo
- 해외 상장사: DuckDuckGo 전용
- URL 기준 중복 제거
"""

import csv
from pathlib import Path
from .base import NewsItem
from .duckduckgo import DuckDuckGoSource
from .naver import NaverNewsSource

COMPANIES_CSV = Path(__file__).resolve().parents[2] / "companies.csv"


def _load_company(name: str) -> dict | None:
    with open(COMPANIES_CSV, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            if row['name'] == name:
                kw_raw = row.get('keywords', '')
                row['keywords'] = [k.strip() for k in kw_raw.split(',') if k.strip()]
                return row
    return None


def _build_queries(company: dict) -> list[str]:
    """회사별 검색 쿼리 생성 — 최대 2개"""
    name = company['name']
    keywords = company.get('keywords', [])

    queries = [name]
    if keywords:
        # 핵심 키워드 2개 추가한 두 번째 쿼리
        queries.append(f"{name} {' '.join(keywords[:2])}")
    return queries


def collect(company_names: list[str], days: int = 7) -> list[NewsItem]:
    """
    지정 기업 목록의 최근 N일 뉴스를 수집하고 URL 중복 제거 후 반환.

    Args:
        company_names: companies.csv 의 name 컬럼 값 목록
        days: 수집 기간 (1 | 7 | 30 — DDG timelimit 매핑)

    Returns:
        NewsItem 리스트 (중복 제거, 날짜 내림차순)
    """
    ddg = DuckDuckGoSource(delay=2.0, max_results=10)
    naver = NaverNewsSource()

    if not naver.available:
        print("[info] NAVER_CLIENT_ID 미설정 — Naver 소스 비활성화")

    all_items: list[NewsItem] = []
    seen_urls: set[str] = set()

    for name in company_names:
        company = _load_company(name)
        if not company:
            print(f"[warn] '{name}' — companies.csv에 없음")
            continue

        is_korean = company.get('exchange', '') == 'KRX'
        queries = _build_queries(company)
        print(f"\n[{name}] 쿼리: {queries}")

        for query in queries:
            # 한국 상장사: Naver 우선
            if is_korean and naver.available:
                for item in naver.search(query, name, days):
                    if item.url and item.url not in seen_urls:
                        seen_urls.add(item.url)
                        all_items.append(item)

            # 전체: DuckDuckGo
            for item in ddg.search(query, name, days):
                if item.url and item.url not in seen_urls:
                    seen_urls.add(item.url)
                    all_items.append(item)

    # 날짜 내림차순 정렬 (None은 맨 뒤)
    all_items.sort(key=lambda x: x.published or '', reverse=True)
    return all_items
