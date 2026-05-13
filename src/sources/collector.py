"""
뉴스 수집 오케스트레이터

KRX 상장사:   Naver News + Naver Finance + DuckDuckGo (한국어 쿼리)
해외 상장사:  Yahoo Finance RSS + DuckDuckGo (영어 쿼리)
"""

import csv
from pathlib import Path
from .base import NewsItem
from .duckduckgo import DuckDuckGoSource
from .naver import NaverNewsSource
from .yahoo_finance import YahooFinanceSource

COMPANIES_CSV = Path(__file__).resolve().parents[2] / "companies.csv"


def _load_company(name: str) -> dict | None:
    with open(COMPANIES_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["name"] == name:
                kw_raw = row.get("keywords", "")
                row["keywords"] = [k.strip() for k in kw_raw.split(",") if k.strip()]
                return row
    return None


def _build_queries(company: dict) -> list[str]:
    """회사별 검색 쿼리 — KRX는 한국어, 해외는 영어 키워드 우선"""
    name     = company["name"]
    ticker   = company.get("ticker", "")
    keywords = company.get("keywords", [])
    is_krx   = company.get("exchange", "") == "KRX"

    if is_krx:
        queries = [name]
        if keywords:
            queries.append(f"{name} {' '.join(keywords[:2])}")
    else:
        # 해외 기업: ticker가 기본 쿼리, 영어 키워드 조합
        base = ticker or name
        queries = [base]
        eng_kw = [k for k in keywords if not any("가" <= c <= "힣" for c in k)]
        if eng_kw:
            queries.append(f"{base} {' '.join(eng_kw[:2])}")

    return queries


def collect(
    company_names: list[str],
    days: int = 7,
    naver_finance_items: list[NewsItem] | None = None,
) -> list[NewsItem]:
    """
    지정 기업 목록의 최근 N일 뉴스를 수집하고 URL 중복 제거 후 반환.

    Args:
        company_names: companies.csv 의 name 컬럼 값 목록
        days: 수집 기간
        naver_finance_items: 이미 수집된 Naver Finance 기사 (KRX 기업에만 배분)
    """
    ddg   = DuckDuckGoSource(delay=2.0, max_results=10)
    naver = NaverNewsSource()
    yahoo = YahooFinanceSource(max_results=15)

    if not naver.available:
        print("[info] NAVER_CLIENT_ID 미설정 — Naver 소스 비활성화")

    all_items: list[NewsItem] = []
    seen_urls: set[str] = set()

    def _add(item: NewsItem) -> None:
        if item.url and item.url not in seen_urls:
            seen_urls.add(item.url)
            all_items.append(item)

    for name in company_names:
        company = _load_company(name)
        if not company:
            print(f"[warn] '{name}' — companies.csv에 없음")
            continue

        is_krx  = company.get("exchange", "") == "KRX"
        ticker  = company.get("ticker", "")
        queries = _build_queries(company)
        print(f"\n[{name}] 쿼리: {queries}  {'(KRX)' if is_krx else '(해외)'}")

        if is_krx:
            # ── 한국 상장사 ──────────────────────────────
            for query in queries:
                if naver.available:
                    for item in naver.search(query, name, days):
                        _add(item)
                for item in ddg.search(query, name, days):
                    _add(item)

            # Naver Finance 기사 배분 (호출자가 미리 수집해 전달)
            if naver_finance_items:
                import copy
                for item in naver_finance_items:
                    cloned = copy.copy(item)
                    cloned.company = name
                    _add(cloned)

        else:
            # ── 해외 상장사 ──────────────────────────────
            # Yahoo Finance RSS (ticker 기반, 영어)
            if ticker:
                for item in yahoo.search(ticker, name, days):
                    _add(item)

            # DuckDuckGo (영어 쿼리)
            for query in queries:
                for item in ddg.search(query, name, days):
                    _add(item)

    all_items.sort(key=lambda x: x.published or "", reverse=True)
    return all_items
