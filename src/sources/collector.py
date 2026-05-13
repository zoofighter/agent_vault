"""
뉴스 수집 오케스트레이터 — 거래소별 소스 라우팅

거래소별 소스:
  KRX/KOSDAQ : Naver News + Naver Finance + DuckDuckGo (한국어) + Google News KR
  NASDAQ/NYSE: Yahoo Finance RSS + DuckDuckGo (영어) + Google News EN
  HKEX       : Yahoo Finance RSS + HKEX 공시 + DuckDuckGo + Google News EN
  TWSE       : Yahoo Finance RSS + TWSE MOPS + DuckDuckGo + Google News EN
  TSE        : Yahoo Finance RSS + TSE TDnet + DuckDuckGo + Google News EN
  SZSE       : Yahoo Finance RSS + DuckDuckGo + Google News EN  (중국 본토 직접접근 제한)
  PRIVATE    : DuckDuckGo + Google News EN
"""

import csv
from pathlib import Path
from .base import NewsItem
from .duckduckgo import DuckDuckGoSource
from .naver import NaverNewsSource
from .yahoo_finance import YahooFinanceSource
from .google_news import GoogleNewsSource, make_korean, make_english
from .hkex import HKEXSource
from .twse import TWSeSource
from .tse import TSESource

COMPANIES_CSV = Path(__file__).resolve().parents[2] / "companies.csv"

# 거래소 → 소스 구성 매핑
_EXCHANGE_PROFILE: dict[str, dict] = {
    "KRX":    {"lang": "ko", "has_hkex": False, "has_twse": False, "has_tse": False},
    "KOSDAQ": {"lang": "ko", "has_hkex": False, "has_twse": False, "has_tse": False},
    "HKEX":   {"lang": "en", "has_hkex": True,  "has_twse": False, "has_tse": False},
    "TWSE":   {"lang": "en", "has_hkex": False, "has_twse": True,  "has_tse": False},
    "TSE":    {"lang": "en", "has_hkex": False, "has_twse": False, "has_tse": True},
    "SZSE":   {"lang": "en", "has_hkex": False, "has_twse": False, "has_tse": False},
    "NYSE":   {"lang": "en", "has_hkex": False, "has_twse": False, "has_tse": False},
    "NASDAQ": {"lang": "en", "has_hkex": False, "has_twse": False, "has_tse": False},
    "PRIVATE":{"lang": "en", "has_hkex": False, "has_twse": False, "has_tse": False},
}


def _load_company(name: str) -> dict | None:
    with open(COMPANIES_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["name"] == name:
                kw_raw = row.get("keywords", "")
                row["keywords"] = [k.strip() for k in kw_raw.split(",") if k.strip()]
                return row
    return None


def _build_queries(company: dict) -> list[str]:
    """회사별 검색 쿼리 목록.
    DuckDuckGo/Google News용: 회사명 또는 영문 키워드 조합.
    Yahoo Finance용: ticker 직접 사용 (별도로 호출).
    """
    name     = company["name"]
    ticker   = company.get("ticker", "")
    keywords = company.get("keywords", [])
    exchange = company.get("exchange", "")
    is_korean = exchange in ("KRX", "KOSDAQ")
    # NYSE/NASDAQ 미국 상장 티커만 DDG 검색에 사용 (HK/TW/JP 티커는 결과 없음)
    is_us_ticker = exchange in ("NYSE", "NASDAQ") and "." not in ticker

    if is_korean:
        queries = [name]
        if keywords:
            queries.append(f"{name} {' '.join(keywords[:2])}")
    else:
        # 회사명 기반 쿼리 (DDG/GoogleNews 공통)
        queries = [name]
        eng_kw = [k for k in keywords if not any("가" <= c <= "힣" for c in k) and k.lower() != name.lower()]
        if eng_kw:
            queries.append(f"{name} {' '.join(eng_kw[:2])}")
        # 미국 상장 티커는 추가 검색어로 사용
        if is_us_ticker:
            queries.insert(0, ticker)

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
        days: 수집 기간 (일)
        naver_finance_items: 이미 수집된 Naver Finance 기사 (KRX 기업에만 배분)
    """
    ddg     = DuckDuckGoSource(delay=2.0, max_results=10)
    naver   = NaverNewsSource()
    yahoo   = YahooFinanceSource(max_results=15)
    gnews_en = make_english()
    gnews_ko = make_korean()
    hkex    = HKEXSource(max_results=20)
    twse    = TWSeSource(max_results=20)
    tse     = TSESource(max_results=20)

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

        exchange = company.get("exchange", "")
        ticker   = company.get("ticker", "")
        queries  = _build_queries(company)
        profile  = _EXCHANGE_PROFILE.get(exchange, _EXCHANGE_PROFILE["PRIVATE"])
        is_korean = exchange in ("KRX", "KOSDAQ")

        print(f"\n[{name}] 거래소={exchange} 쿼리={queries}")

        if is_korean:
            # ── 한국 상장사 ──────────────────────────────────────────
            for query in queries:
                if naver.available:
                    for item in naver.search(query, name, days):
                        _add(item)
                for item in ddg.search(query, name, days):
                    _add(item)
                for item in gnews_ko.search(query, name, days):
                    _add(item)

            # Naver Finance 기사 배분 (호출자가 미리 수집해 전달)
            if naver_finance_items:
                import copy
                for item in naver_finance_items:
                    cloned = copy.copy(item)
                    cloned.company = name
                    _add(cloned)

        else:
            # ── 해외 상장사 ──────────────────────────────────────────

            # Yahoo Finance RSS (ticker 기반)
            if ticker:
                for item in yahoo.search(ticker, name, days):
                    _add(item)

            # 거래소별 공시 소스
            if profile["has_hkex"] and ticker:
                for item in hkex.search(ticker, name, days):
                    _add(item)

            elif profile["has_twse"] and ticker:
                for item in twse.search(ticker, name, days):
                    _add(item)

            elif profile["has_tse"] and ticker:
                for item in tse.search(ticker, name, days):
                    _add(item)

            # DuckDuckGo + Google News (영어)
            for query in queries:
                for item in ddg.search(query, name, days):
                    _add(item)
                for item in gnews_en.search(query, name, days):
                    _add(item)

    all_items.sort(key=lambda x: x.published or "", reverse=True)
    return all_items
