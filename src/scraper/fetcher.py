"""
기사 본문 스크래핑

★★★★★ 등급 기사(벡터 거리 ≤ 0.45)에 한해 본문 전체를 가져온다.
BeautifulSoup → 실패 시 Playwright 폴백.
"""

import time
import requests
from bs4 import BeautifulSoup

_TIMEOUT = 8
_MAX_BODY_CHARS = 3000
_DELAY = 0.5  # 요청 간격 (초)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
}

# 사이트별 본문 선택자 (우선순위 순)
_SELECTORS = [
    {"id": "articleBodyContents"},      # Naver 뉴스
    {"id": "articeBody"},               # Naver 일부
    {"id": "newsEndContents"},          # Naver Finance
    {"class": "article-body"},
    {"class": "news_body"},
    {"class": "article_body"},
    {"class": "content-article"},
    {"class": "view_con"},
    "article",
]


def _extract_text(soup: BeautifulSoup) -> str:
    """선택자 우선순위대로 본문 텍스트를 추출한다."""
    for sel in _SELECTORS:
        if isinstance(sel, dict):
            key, val = next(iter(sel.items()))
            tag = soup.find(attrs={key: val})
        else:
            tag = soup.find(sel)
        if tag:
            # 불필요한 태그 제거
            for t in tag.find_all(["script", "style", "figure", "aside"]):
                t.decompose()
            text = tag.get_text(separator=" ", strip=True)
            if len(text) > 100:  # 너무 짧으면 다음 선택자 시도
                return text
    return ""


def fetch_body(url: str) -> str | None:
    """
    기사 URL에서 본문을 추출한다.

    Returns:
        본문 텍스트 (최대 3000자), 실패 시 None
    """
    try:
        time.sleep(_DELAY)
        resp = requests.get(url, timeout=_TIMEOUT, headers=_HEADERS)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"

        soup = BeautifulSoup(resp.text, "html.parser")
        text = _extract_text(soup)

        if not text:
            return _fetch_body_playwright(url)

        return text[:_MAX_BODY_CHARS]

    except Exception:
        return None


def _fetch_body_playwright(url: str) -> str | None:
    """JavaScript 렌더링이 필요한 페이지용 Playwright 폴백."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_extra_http_headers({"Accept-Language": "ko-KR,ko;q=0.9"})
            page.goto(url, timeout=15000, wait_until="domcontentloaded")
            page.wait_for_timeout(1500)

            soup = BeautifulSoup(page.content(), "html.parser")
            browser.close()

            text = _extract_text(soup)
            return text[:_MAX_BODY_CHARS] if text else None
    except Exception:
        return None
