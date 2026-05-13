"""
네이버 금융 메인 뉴스 스크래퍼

https://finance.naver.com/news/mainnews.naver 에서 최신 금융 뉴스를 수집하여
각 회사와의 관련성은 analyzer 단계에서 벡터 유사도로 판별한다.
"""

import re
import urllib.request
from datetime import datetime, timezone
from .base import BaseSource, NewsItem

_URL = "https://finance.naver.com/news/mainnews.naver"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
}


def _strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html).strip()


def _decode_entities(text: str) -> str:
    return (text
            .replace("&ldquo;", '"').replace("&rdquo;", '"')
            .replace("&lsquo;", "'").replace("&rsquo;", "'")
            .replace("&hellip;", "…").replace("&amp;", "&")
            .replace("&lt;", "<").replace("&gt;", ">")
            .replace("&nbsp;", " "))


def _parse_articles(html: str) -> list[dict]:
    """news_read.naver 링크에서 제목·URL 추출"""
    articles = []
    seen_urls: set[str] = set()

    # href="/news/news_read.naver?..." >제목<
    pattern = re.compile(
        r'href=["\'](/news/news_read\.naver\?[^"\']+)["\'][^>]*>'
        r'\s*([^<]{5,120}?)\s*[·.]{0,5}\s*</a>',
        re.S,
    )
    for m in pattern.finditer(html):
        url = "https://finance.naver.com" + m.group(1).split("&amp;")[0].replace("&amp;", "&")
        # 중복 article_id 방지
        art_id = re.search(r'article_id=(\d+)', url)
        key = art_id.group(1) if art_id else url
        if key in seen_urls:
            continue
        seen_urls.add(key)

        title = _decode_entities(_strip_tags(m.group(2)).strip())
        # 탐색 메뉴 텍스트 제외
        if len(title) < 6 or title in {"뉴스", "뉴스선택됨", "주요뉴스", "전체뉴스"}:
            continue

        articles.append({"title": title, "url": url, "snippet": ""})

    return articles


class NaverFinanceSource(BaseSource):
    """네이버 금융 메인 뉴스 — 회사 무관하게 전체 수집, 관련성은 analyzer가 판별"""

    @property
    def available(self) -> bool:
        return True

    def fetch_all(self) -> list[NewsItem]:
        """회사명 없이 네이버 금융 메인 뉴스를 수집한다."""
        try:
            req = urllib.request.Request(_URL, headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode("euc-kr", errors="replace")
        except Exception as e:
            print(f"  [NaverFinance] 수집 오류: {e}")
            return []

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        items = []
        for art in _parse_articles(html):
            items.append(NewsItem(
                title=art["title"],
                url=art["url"],
                snippet=art["snippet"],
                source="naver_finance",
                company="",       # analyzer 단계에서 매핑
                query="네이버금융메인",
                published=today,
            ))

        return items

    def search(self, query: str, company: str, days: int = 7) -> list[NewsItem]:
        """BaseSource 호환용 — 실제로는 fetch_all 사용"""
        items = self.fetch_all()
        for item in items:
            item.company = company
        return items
