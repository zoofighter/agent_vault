"""
Yahoo Finance RSS 뉴스 소스

https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US

429 방지: 24시간 TTL 디스크 캐시 (data/cache/yahoo/)
"""

import re
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from .base import BaseSource, NewsItem

_RSS_URL = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}
_CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache" / "yahoo"
_CACHE_TTL = 23 * 3600  # 23시간 (하루 1회 배치 기준)


def _cache_path(ticker: str) -> Path:
    safe = ticker.replace("/", "_").replace(".", "_")
    return _CACHE_DIR / f"{safe}.xml"


def _load_cache(ticker: str) -> str | None:
    p = _cache_path(ticker)
    if not p.exists():
        return None
    age = time.time() - p.stat().st_mtime
    if age > _CACHE_TTL:
        return None
    return p.read_text(encoding="utf-8")


def _save_cache(ticker: str, xml: str) -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(ticker).write_text(xml, encoding="utf-8")


def _strip_cdata(text: str) -> str:
    m = re.match(r"<!\[CDATA\[(.*?)\]\]>", text, re.S)
    return m.group(1).strip() if m else text.strip()


def _parse_rss(xml: str, company: str, ticker: str, days: int) -> list[NewsItem]:
    items = []
    cutoff = None
    if days:
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
        raw_ticker = query
        ticker = urllib.parse.quote(query)
        url = _RSS_URL.format(ticker=ticker)

        # 캐시 확인
        xml = _load_cache(raw_ticker)
        if xml:
            items = _parse_rss(xml, company, raw_ticker, days)
            return items[: self.max_results]

        # 네트워크 요청 (3회 재시도)
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers=_HEADERS)
                with urllib.request.urlopen(req, timeout=12) as resp:
                    xml = resp.read().decode("utf-8", errors="replace")
                _save_cache(raw_ticker, xml)
                break
            except Exception as e:
                if "429" in str(e) and attempt < 2:
                    time.sleep(5 * (attempt + 1))
                else:
                    print(f"  [YahooFinance] '{query}' 오류: {e}")
                    return []
        if not xml:
            return []

        items = _parse_rss(xml, company, raw_ticker, days)
        return items[: self.max_results]
