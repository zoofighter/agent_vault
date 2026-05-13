"""
일본 TSE TDnet (Timely Disclosure Network) 기업 공시 수집

TSE 상장사 대상 (ticker 접미사: .T)
  - 소프트뱅크    9984.T
  - 키옥시아      285A.T
  - 도쿄일렉트론  8035.T

전략:
  1차) Playwright로 TDnet 검색 결과 렌더링 (JS 렌더링 필요)
  2차) Playwright 미설치 시 → Google News (일본어) 폴백

TDnet 공시 검색:
  https://www.release.tdnet.info/inbs/I_main_00.html
  ?target=S&SC={stock_code}&KD=1&KDATE={YYYYMMDD}
"""

import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from .base import BaseSource, NewsItem

_TDNET_SEARCH = "https://www.release.tdnet.info/inbs/I_main_00.html"
_TDNET_BASE   = "https://www.release.tdnet.info"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en;q=0.9",
}


def _ticker_to_stock_code(ticker: str) -> str:
    """'9984.T' → '9984'  |  '285A.T' → '285A'"""
    return ticker.upper().replace(".T", "").strip()


def _parse_tdnet_html(html: str, company: str, ticker: str, days: int) -> list[NewsItem]:
    """TDnet 검색 결과 HTML 파싱"""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days) if days else None
    items: list[NewsItem] = []

    row_pat  = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
    date_pat = re.compile(r"(\d{4}/\d{2}/\d{2})")
    link_pat = re.compile(r'href="([^"]+)"[^>]*>\s*([^<]{5,300})\s*</a>', re.I)

    for row_m in row_pat.finditer(html):
        row = row_m.group(1)
        if "<td" not in row:
            continue

        date_m = date_pat.search(row)
        if not date_m:
            continue
        try:
            pub_dt = datetime.strptime(date_m.group(1), "%Y/%m/%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue

        if cutoff and pub_dt < cutoff:
            continue

        link_m = link_pat.search(row)
        if not link_m:
            continue

        href  = link_m.group(1)
        title = re.sub(r"\s+", " ", link_m.group(2)).strip()
        if len(title) < 5:
            continue

        url = href if href.startswith("http") else _TDNET_BASE + "/" + href.lstrip("/")

        items.append(NewsItem(
            title=title,
            url=url,
            snippet="",
            source="tse",
            company=company,
            query=ticker,
            published=pub_dt.strftime("%Y-%m-%d"),
        ))

    return items


def _fetch_playwright(stock_code: str, days: int) -> list[str]:
    """Playwright로 TDnet 검색 결과 HTML 목록 수집 (날짜별)"""
    from playwright.sync_api import sync_playwright

    htmls: list[str] = []
    today = datetime.now(timezone.utc)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_extra_http_headers({"Accept-Language": "ja,en;q=0.9"})

        # 최근 days일 중 겹치는 날짜만 조회 (최대 14일 범위)
        scan_days = min(days, 14)
        for delta in range(scan_days):
            target = today - timedelta(days=delta)
            params = {
                "target": "S", "pref": "0", "LGTKN": "",
                "KFLG": "0", "SKEY": "1",
                "SC":   stock_code,
                "KD":   "1",
                "KDATE": target.strftime("%Y%m%d"),
            }
            url = _TDNET_SEARCH + "?" + urllib.parse.urlencode(params)
            try:
                page.goto(url, timeout=15000, wait_until="networkidle")
                page.wait_for_timeout(1000)
                htmls.append(page.content())
            except Exception:
                pass

        browser.close()

    return htmls


def _fallback_google(company: str, days: int) -> list[NewsItem]:
    """Google News 일본어 폴백"""
    from .google_news import GoogleNewsSource
    gnews = GoogleNewsSource(lang="ja", country="JP", max_results=10)
    return gnews.search(company, company, days)


class TSESource(BaseSource):
    """일본 TSE TDnet 기업 공시 — .T 티커 전용
    Playwright 설치 시 TDnet 직접 수집, 미설치 시 Google News 폴백.
    """

    def __init__(self, max_results: int = 20):
        self.max_results = max_results

    def search(self, query: str, company: str, days: int = 7) -> list[NewsItem]:
        """query 자리에 JP 티커를 넘긴다 (예: '9984.T')."""
        ticker = query.upper()
        if not ticker.endswith(".T"):
            return []

        stock_code = _ticker_to_stock_code(ticker)
        all_items: list[NewsItem] = []
        seen_urls: set[str] = set()

        try:
            htmls = _fetch_playwright(stock_code, days)
            for html in htmls:
                for item in _parse_tdnet_html(html, company, ticker, days):
                    if item.url not in seen_urls:
                        seen_urls.add(item.url)
                        all_items.append(item)

            if all_items:
                print(f"  [TSE] '{ticker}' → {len(all_items)}건 (Playwright)")
                return all_items[: self.max_results]
        except ImportError:
            pass
        except Exception as e:
            print(f"  [TSE] '{ticker}' Playwright 오류: {e}")

        # Google News 일본어 폴백
        items = _fallback_google(company, days)
        print(f"  [TSE→GoogleNews] '{company}' → {len(items)}건")
        return items[: self.max_results]
