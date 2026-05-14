import time
import concurrent.futures
from ddgs import DDGS
from .base import BaseSource, NewsItem

# DDG timelimit: 'd'=1일, 'w'=1주, 'm'=1달
_TIMELIMIT = {1: 'd', 7: 'w', 30: 'm'}
_REQUEST_TIMEOUT = 15   # DDGS HTTP 타임아웃 (초)
_CALL_TIMEOUT   = 20   # 전체 호출 타임아웃 (초) — 라이브러리 행업 방어


def _parse_date(raw: str | None) -> str | None:
    if not raw:
        return None
    return raw[:10] if len(raw) >= 10 else raw


def _do_search(query: str, max_results: int, timelimit: str) -> list[dict]:
    with DDGS(timeout=_REQUEST_TIMEOUT) as ddgs:
        return list(ddgs.news(query, max_results=max_results, timelimit=timelimit))


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
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                    future = ex.submit(_do_search, query, self.max_results, timelimit)
                    results = future.result(timeout=_CALL_TIMEOUT)
                for r in results:
                    items.append(NewsItem(
                        title=r.get('title', ''),
                        url=r.get('url', ''),
                        snippet=r.get('body', ''),
                        source='duckduckgo',
                        company=company,
                        query=query,
                        published=_parse_date(r.get('date')),
                    ))
                break
            except concurrent.futures.TimeoutError:
                print(f"  [DDG] '{query}' 타임아웃 ({_CALL_TIMEOUT}s) — 스킵")
                break
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
