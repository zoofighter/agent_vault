import os
import json
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from .base import BaseSource, NewsItem

_BASE_URL = "https://openapi.naver.com/v1/search/news.json"


class NaverNewsSource(BaseSource):
    """Naver News Search API — KRX 상장 한국 기업용"""

    def __init__(self, client_id: str = None, client_secret: str = None, display: int = 10):
        self.client_id = client_id or os.getenv('NAVER_CLIENT_ID', '')
        self.client_secret = client_secret or os.getenv('NAVER_CLIENT_SECRET', '')
        self.display = display

    @property
    def available(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def search(self, query: str, company: str, days: int = 7) -> list[NewsItem]:
        if not self.available:
            return []

        params = urllib.parse.urlencode({'query': query, 'display': self.display, 'sort': 'date'})
        req = urllib.request.Request(
            f"{_BASE_URL}?{params}",
            headers={
                'X-Naver-Client-Id': self.client_id,
                'X-Naver-Client-Secret': self.client_secret,
            },
        )

        cutoff = datetime.now() - timedelta(days=days)
        items = []
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())

            for r in data.get('items', []):
                pub_str = r.get('pubDate', '')
                published = None
                try:
                    pub_dt = datetime.strptime(pub_str, '%a, %d %b %Y %H:%M:%S %z')
                    if pub_dt.replace(tzinfo=None) < cutoff:
                        continue
                    published = pub_dt.strftime('%Y-%m-%d')
                except ValueError:
                    pass

                def strip_tags(s: str) -> str:
                    return s.replace('<b>', '').replace('</b>', '').replace('&amp;', '&').replace('&quot;', '"')

                items.append(NewsItem(
                    title=strip_tags(r.get('title', '')),
                    url=r.get('originallink') or r.get('link', ''),
                    snippet=strip_tags(r.get('description', '')),
                    source='naver',
                    company=company,
                    query=query,
                    published=published,
                ))
        except Exception as e:
            print(f"  [Naver] '{query}' 오류: {e}")
        return items
