"""
Google News RSS — 회사명/키워드로 전 세계 뉴스 수집

모든 거래소 기업에 범용 적용. 국내 기업은 한국어 쿼리, 해외는 영어 쿼리.
URL: https://news.google.com/rss/search?q={query}&hl={lang}&gl={country}&ceid={country}:{lang}
"""

import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from .base import BaseSource, NewsItem

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}

_BASE_URL = "https://news.google.com/rss/search"


def _rss_url(query: str, lang: str = "en", country: str = "US") -> str:
    params = {
        "q":    query,
        "hl":   f"{lang}-{country}",
        "gl":   country,
        "ceid": f"{country}:{lang}",
    }
    return _BASE_URL + "?" + urllib.parse.urlencode(params)


def _strip_cdata(text: str) -> str:
    m = re.match(r"<!\[CDATA\[(.*?)\]\]>", text, re.S)
    return m.group(1).strip() if m else text.strip()


def _clean_snippet(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return text.strip()[:300]


def _parse_rss(xml: str, company: str, query: str, days: int) -> list[NewsItem]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days) if days else None
    items: list[NewsItem] = []

    for block in re.findall(r"<item>(.*?)</item>", xml, re.S):
        title_m = re.search(r"<title>(.*?)</title>",         block, re.S)
        link_m  = re.search(r"<link>\s*(.*?)\s*</link>",     block, re.S)
        desc_m  = re.search(r"<description>(.*?)</description>", block, re.S)
        date_m  = re.search(r"<pubDate>(.*?)</pubDate>",     block, re.S)

        if not title_m or not link_m:
            continue

        title   = _strip_cdata(title_m.group(1))
        url     = _strip_cdata(link_m.group(1))
        snippet = _clean_snippet(_strip_cdata(desc_m.group(1))) if desc_m else ""
        published = None

        if date_m:
            try:
                pub_dt = parsedate_to_datetime(date_m.group(1).strip())
                if cutoff and pub_dt < cutoff:
                    continue
                published = pub_dt.strftime("%Y-%m-%d")
            except Exception:
                pass

        # Google News 리다이렉트 URL 정리 (읽기 가능한 URL로 유지)
        items.append(NewsItem(
            title=title,
            url=url,
            snippet=snippet,
            source="google_news",
            company=company,
            query=query,
            published=published,
        ))

    return items


class GoogleNewsSource(BaseSource):
    """Google News RSS — 거래소 무관하게 사용 가능"""

    def __init__(self, max_results: int = 15, lang: str = "en", country: str = "US"):
        self.max_results = max_results
        self.lang    = lang
        self.country = country

    def search(self, query: str, company: str, days: int = 7) -> list[NewsItem]:
        url = _rss_url(query, self.lang, self.country)
        try:
            req = urllib.request.Request(url, headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                xml = resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            print(f"  [GoogleNews] '{query}' 오류: {e}")
            return []

        time.sleep(0.5)
        items = _parse_rss(xml, company, query, days)
        return items[: self.max_results]


def make_korean() -> "GoogleNewsSource":
    """한국어 뉴스 전용 인스턴스"""
    return GoogleNewsSource(lang="ko", country="KR")


def make_english() -> "GoogleNewsSource":
    """영어 뉴스 전용 인스턴스"""
    return GoogleNewsSource(lang="en", country="US")
