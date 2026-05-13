"""
홍콩 HKEX (HKEXnews) 기업 공시·뉴스 수집

HKEX 상장사 대상 (ticker 접미사: .HK)
  - 텐센트   0700.HK
  - 알리바바  9988.HK
  - BYD      1211.HK
  - 샤오미   1810.HK

전략:
  1차) Playwright로 HKEXnews 검색 결과 렌더링 → 공시 목록 추출
  2차) Playwright 미설치 시 → Google News (중국어) 폴백
"""

import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from .base import BaseSource, NewsItem

_HKEX_SEARCH = (
    "https://www.hkexnews.hk/listedco/listconews/advancedsearch"
    "/search_active_main_en.aspx"
)
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9,zh;q=0.8",
    "Referer": "https://www.hkexnews.hk/",
}
_HKEX_BASE = "https://www.hkexnews.hk"


def _ticker_to_stock_id(ticker: str) -> str:
    """'0700.HK' → '700' (선행 0 제거)"""
    return ticker.upper().replace(".HK", "").lstrip("0") or "0"


def _date_str(dt: datetime) -> str:
    return dt.strftime("%Y%m%d")


def _parse_hkex_html(html: str, company: str, ticker: str, days: int) -> list[NewsItem]:
    """HKEX 검색 결과 HTML 파싱"""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days) if days else None
    items: list[NewsItem] = []

    # DD/MM/YYYY 날짜 + 링크 패턴
    date_pat = re.compile(r"(\d{2}/\d{2}/\d{4})")
    link_pat = re.compile(r'href="(/[^"]+\.(?:htm|html|pdf))["\s]', re.I)
    title_pat = re.compile(r'<td[^>]*>\s*([^<]{10,300})\s*</td>', re.I)

    for block in re.split(r"<tr", html, flags=re.I):
        date_m = date_pat.search(block)
        if not date_m:
            continue
        try:
            pub_dt = datetime.strptime(date_m.group(1), "%d/%m/%Y").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if cutoff and pub_dt < cutoff:
            continue

        link_m = link_pat.search(block)
        if not link_m:
            continue
        url = _HKEX_BASE + link_m.group(1)

        # 제목: 가장 긴 텍스트 셀
        candidates = title_pat.findall(block)
        title = max(candidates, key=len, default="").strip() if candidates else ""
        title = re.sub(r"\s+", " ", title)
        if len(title) < 6:
            continue

        items.append(NewsItem(
            title=title,
            url=url,
            snippet="",
            source="hkex",
            company=company,
            query=ticker,
            published=pub_dt.strftime("%Y-%m-%d"),
        ))

    return items


def _fetch_playwright(ticker: str, stock_id: str, start: datetime, end: datetime) -> str:
    """Playwright로 HKEXnews 검색 결과 HTML 가져오기"""
    from playwright.sync_api import sync_playwright

    params = {
        "strAccNos": "",
        "stockId":   stock_id,
        "dateRange": "custom",
        "startDate": _date_str(start),
        "endDate":   _date_str(end),
        "category":  "",
        "listType":  "0",
    }
    url = _HKEX_SEARCH + "?" + urllib.parse.urlencode(params)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_extra_http_headers({"Accept-Language": "en-US,en;q=0.9"})
        page.goto(url, timeout=20000, wait_until="networkidle")
        page.wait_for_timeout(2000)
        html = page.content()
        browser.close()

    return html


def _fallback_google(company: str, days: int) -> list[NewsItem]:
    """Google News 중국어 폴백"""
    from .google_news import GoogleNewsSource
    gnews = GoogleNewsSource(lang="zh", country="HK", max_results=10)
    return gnews.search(company, company, days)


class HKEXSource(BaseSource):
    """홍콩 HKEX 기업 공시 — .HK 티커 전용
    Playwright 설치 시 공시 목록 직접 수집, 미설치 시 Google News 폴백.
    """

    def __init__(self, max_results: int = 20):
        self.max_results = max_results

    def search(self, query: str, company: str, days: int = 7) -> list[NewsItem]:
        """query 자리에 HK 티커를 넘긴다 (예: '0700.HK')."""
        ticker = query.upper()
        if not ticker.endswith(".HK"):
            return []

        stock_id = _ticker_to_stock_id(ticker)
        today    = datetime.now(timezone.utc)
        start    = today - timedelta(days=days)

        try:
            html = _fetch_playwright(ticker, stock_id, start, today)
            items = _parse_hkex_html(html, company, ticker, days)
            if items:
                print(f"  [HKEX] '{ticker}' → {len(items)}건 (Playwright)")
                return items[: self.max_results]
        except ImportError:
            pass  # Playwright 미설치
        except Exception as e:
            print(f"  [HKEX] '{ticker}' Playwright 오류: {e}")

        # Google News 중국어 폴백
        items = _fallback_google(company, days)
        print(f"  [HKEX→GoogleNews] '{company}' → {len(items)}건")
        return items[: self.max_results]
