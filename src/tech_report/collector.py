"""
TechReport Collector — 섹터 키워드로 뉴스 수집

기존 GoogleNewsSource(한국어+영어)를 재활용. 회사명 대신 섹터 토픽 키워드로 쿼리.
"""

from __future__ import annotations

from pathlib import Path
import sys

# 프로젝트 루트 기준 import
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.sources.google_news import GoogleNewsSource

SECTOR_QUERIES: dict[str, list[str]] = {
    "AI":       ["{topic} AI 인공지능 최신 동향", "{topic} artificial intelligence"],
    "반도체":   ["{topic} 반도체 공정 패키징 기술", "{topic} semiconductor chip packaging"],
    "바이오":   ["{topic} 바이오 임상 신약 파이프라인", "{topic} biotech clinical trial"],
    "헬스케어": ["{topic} 헬스케어 의료기기 디지털헬스", "{topic} healthcare medical device"],
    "디스플레이":["{topic} 디스플레이 OLED 패널 기술", "{topic} display OLED panel"],
    "2차전지":  ["{topic} 배터리 양극재 음극재 소재", "{topic} battery cathode anode material"],
    "자동차":   ["{topic} 전기차 자율주행 자동차", "{topic} electric vehicle autonomous driving"],
    "에너지":   ["{topic} 에너지 전력 원전 ESS 그리드", "{topic} energy power nuclear grid"],
    "우주방산": ["{topic} 우주 위성 방산 무기체계", "{topic} space satellite defense weapon"],
    "양자컴퓨팅":["{topic} 양자컴퓨팅 큐비트", "{topic} quantum computing qubit error"],
    "로보틱스": ["{topic} 로보틱스 휴머노이드 로봇 액추에이터", "{topic} robotics humanoid actuator"],
}

_KO_SOURCE = GoogleNewsSource(max_results=10, lang="ko", country="KR")
_EN_SOURCE = GoogleNewsSource(max_results=10, lang="en", country="US")


def collect(sector: str, topic: str, days: int = 7) -> list[dict]:
    """섹터 + 토픽으로 한국어·영어 뉴스 수집.

    Returns: list of {"title", "url", "snippet", "source", "published"}
    """
    templates = SECTOR_QUERIES.get(sector, ["{topic}", "{topic} news"])
    queries = [t.format(topic=topic) for t in templates]

    items: list[dict] = []
    seen_titles: set[str] = set()

    for i, query in enumerate(queries):
        source = _KO_SOURCE if i % 2 == 0 else _EN_SOURCE
        try:
            results = source.search(query=query, company=sector, days=days)
            for r in results:
                key = r.title.lower()[:60]
                if key not in seen_titles:
                    seen_titles.add(key)
                    items.append({
                        "title": r.title,
                        "url": r.url,
                        "snippet": r.snippet,
                        "source": r.source,
                        "published": r.published or "",
                    })
        except Exception as e:
            print(f"  [collector] '{query}' 수집 실패: {e}")

    return items
