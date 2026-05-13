import time
from ddgs import DDGS
from .base import BaseSource, NewsItem

# DDG timelimit: 'd'=1일, 'w'=1주, 'm'=1달
_TIMELIMIT = {1: 'd', 7: 'w', 30: 'm'}


def _parse_date(raw: str | None) -> str | None:
    """ISO timestamp → 'YYYY-MM-DD' 변환, 실패 시 None"""
    if not raw:
        return None
    return raw[:10] if len(raw) >= 10 else raw


class DuckDuckGoSource(BaseSource):
    def __init__(self, delay: float = 3.0, max_results: int = 10, max_retries: int = 2):
        self.delay = delay
        self.max_results = max_results
        self.max_retries = max_retries

    def search(self, query: str, company: str, days: int = 7) -> list[NewsItem]:
        timelimit = _TIMELIMIT.get(days, 'w')
        items = []

        for attempt in range(self.max_retries + 1):
            try:
                with DDGS() as ddgs:
                    for r in ddgs.news(query, max_results=self.max_results, timelimit=timelimit):
                        items.append(NewsItem(
                            title=r.get('title', ''),
                            url=r.get('url', ''),
                            snippet=r.get('body', ''),
                            source='duckduckgo',
                            company=company,
                            query=query,
                            published=_parse_date(r.get('date')),
                        ))
                break  # 성공
            except Exception as e:
                if '403' in str(e) and attempt < self.max_retries:
                    wait = self.delay * (attempt + 2)
                    print(f"  [DDG] '{query}' 레이트 리밋 — {wait:.0f}초 대기 후 재시도")
                    time.sleep(wait)
                else:
                    print(f"  [DDG] '{query}' 오류: {e}")
                    break

        time.sleep(self.delay)
        return items
