"""
Yahoo Finance RSS 뉴스 소스

https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US
"""

import re
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from .base import BaseSource, NewsItem

_RSS_URL = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def _strip_cdata(text: str) -> str:
    m = re.match(r"<!\[CDATA\[(.*?)\]\]>", text, re.S)
    return m.group(1).strip() if m else text.strip()


def _parse_rss(xml: str, company: str, ticker: str, days: int) -> list[NewsItem]:
    items = []
    cutoff = None
    if days:
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    for block in re.findall(r"<item>(.*?)</item>", xml, re.S):
        title_m = re.search(r"<title>(.*?)</title>", block, re.S)
        link_m  = re.search(r"<link>(.*?)</link>",  block, re.S)
        desc_m  = re.search(r"<description>(.*?)</description>", block, re.S)
        date_m  = re.search(r"<pubDate>(.*?)</pubDate>", block, re.S)

        if not title_m or not link_m:
            continue

        title   = _strip_cdata(title_m.group(1))
        url     = _strip_cdata(link_m.group(1))
        snippet = _strip_cdata(desc_m.group(1)) if desc_m else ""
        published = None

        if date_m:
            try:
                pub_dt = parsedate_to_datetime(date_m.group(1).strip())
                if cutoff and pub_dt < cutoff:
                    continue
                published = pub_dt.strftime("%Y-%m-%d")
            except Exception:
                pass

        items.append(NewsItem(
            title=title,
            url=url,
            snippet=snippet,
            source="yahoo_finance",
            company=company,
            query=ticker,
            published=published,
        ))

    return items


class YahooFinanceSource(BaseSource):
    """Yahoo Finance RSS — 비KRX 해외 기업용"""

    def __init__(self, max_results: int = 15):
        self.max_results = max_results

    @property
    def available(self) -> bool:
        return True

    def search(self, query: str, company: str, days: int = 7) -> list[NewsItem]:
        """query 자리에 ticker를 넘긴다 (예: 'GOOGL')."""
        ticker = urllib.parse.quote(query)
        url = _RSS_URL.format(ticker=ticker)
        import time
        xml = None
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers=_HEADERS)
                with urllib.request.urlopen(req, timeout=12) as resp:
                    xml = resp.read().decode("utf-8", errors="replace")
                break
            except Exception as e:
                if "429" in str(e) and attempt < 2:
                    time.sleep(3 * (attempt + 1))
                else:
                    print(f"  [YahooFinance] '{query}' 오류: {e}")
                    return []
        if not xml:
            return []

        items = _parse_rss(xml, company, query, days)
        return items[: self.max_results]
