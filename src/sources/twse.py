"""
대만 TWSE/MOPS 중요공시 수집

TWSE 상장사 대상 (ticker 접미사: .TW)
  - 미디어텍   2454.TW
  - 난야        2408.TW
  - Delta      2308.TW

전략:
  1차) Playwright로 MOPS 검색 결과 렌더링 → 공시 목록 추출
  2차) Playwright 미설치 시 → Google News (번체 중국어) 폴백

MOPS 중요공시 URL:
  https://mops.twse.com.tw/mops/web/t91sb01
  (안티스크래핑 → Playwright 필요)
"""

import re
import time
import urllib.parse
from datetime import datetime, timedelta, timezone

from .base import BaseSource, NewsItem

_MOPS_URL   = "https://mops.twse.com.tw/mops/web/t91sb01"
_MOPS_BASE  = "https://mops.twse.com.tw"


def _ticker_to_co_id(ticker: str) -> str:
    """'2454.TW' → '2454'"""
    return ticker.upper().replace(".TW", "").strip()


def _date_str_tw(dt: datetime) -> str:
    return dt.strftime("%Y%m%d")


def _parse_mops_html(html: str, company: str, ticker: str, days: int) -> list[NewsItem]:
    """MOPS 중요공시 목록 HTML 파싱"""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days) if days else None
    items: list[NewsItem] = []

    row_pat  = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
    # MOPS 날짜: YYYY/MM/DD 또는 ROC 민국력 YYY/MM/DD
    date_pat = re.compile(r"(\d{3,4}/\d{2}/\d{2})")
    link_pat = re.compile(r'href="([^"]+)"[^>]*>([^<]{5,200})</a>', re.I)

    for row_m in row_pat.finditer(html):
        row = row_m.group(1)
        if "<td" not in row:
            continue

        date_m = date_pat.search(row)
        if not date_m:
            continue
        parts = date_m.group(1).split("/")
        try:
            year = int(parts[0])
            if year < 1000:
                year += 1911   # 民國曆 → 西曆
            pub_dt = datetime(year, int(parts[1]), int(parts[2]), tzinfo=timezone.utc)
        except (ValueError, IndexError):
            continue

        if cutoff and pub_dt < cutoff:
            continue

        link_m = link_pat.search(row)
        if link_m:
            href  = link_m.group(1)
            title = re.sub(r"\s+", " ", link_m.group(2)).strip()
            url   = href if href.startswith("http") else _MOPS_BASE + href
        else:
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
            title = ""
            for cell in reversed(cells):
                t = re.sub(r"<[^>]+>", "", cell).strip()
                if len(t) > 8:
                    title = t; break
            if not title:
                continue
            url = _MOPS_URL

        items.append(NewsItem(
            title=title,
            url=url,
            snippet="",
            source="twse",
            company=company,
            query=ticker,
            published=pub_dt.strftime("%Y-%m-%d"),
        ))

    return items


def _fetch_playwright(co_id: str, start: datetime, end: datetime) -> str:
    """Playwright로 MOPS 공시 목록 렌더링 (POST 폼 방식)"""
    from playwright.sync_api import sync_playwright
    import urllib.parse

    # POST 데이터를 URL 인코딩해 data: URL로 직접 제출
    form_data = urllib.parse.urlencode({
        "co_id":   co_id,
        "b_date":  _date_str_tw(start),
        "e_date":  _date_str_tw(end),
        "step":    "1",
        "firstin": "true",
        "off":     "1",
    })

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_extra_http_headers({"Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8"})
        # fetch POST via JS evaluation
        page.goto("about:blank")
        html = page.evaluate(f"""async () => {{
            const resp = await fetch('{_MOPS_URL}', {{
                method: 'POST',
                headers: {{
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Referer': 'https://mops.twse.com.tw/mops/',
                }},
                body: '{form_data}',
            }});
            return await resp.text();
        }}""")
        browser.close()

    return html


def _fallback_google(company: str, days: int) -> list[NewsItem]:
    """Google News 번체 중국어 폴백"""
    from .google_news import GoogleNewsSource
    gnews = GoogleNewsSource(lang="zh", country="TW", max_results=10)
    return gnews.search(company, company, days)


class TWSeSource(BaseSource):
    """대만 TWSE/MOPS 중요공시 — .TW 티커 전용
    Playwright 설치 시 공시 직접 수집, 미설치 시 Google News 폴백.
    """

    def __init__(self, max_results: int = 20):
        self.max_results = max_results

    def search(self, query: str, company: str, days: int = 7) -> list[NewsItem]:
        """query 자리에 TW 티커를 넘긴다 (예: '2454.TW')."""
        ticker = query.upper()
        if not ticker.endswith(".TW"):
            return []

        co_id = _ticker_to_co_id(ticker)
        today  = datetime.now(timezone.utc)
        start  = today - timedelta(days=days)

        try:
            html  = _fetch_playwright(co_id, start, today)
            items = _parse_mops_html(html, company, ticker, days)
            if items:
                print(f"  [TWSE] '{ticker}' → {len(items)}건 (Playwright)")
                return items[: self.max_results]
        except ImportError:
            pass
        except Exception as e:
            print(f"  [TWSE] '{ticker}' Playwright 오류: {e}")

        # Google News 번체 중국어 폴백
        items = _fallback_google(company, days)
        print(f"  [TWSE→GoogleNews] '{company}' → {len(items)}건")
        return items[: self.max_results]
