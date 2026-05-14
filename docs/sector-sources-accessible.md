---
title: 섹터별 데이터 소스 — 실용 가이드 (낮은 진입장벽)
type: system-doc
created: 2026-05-14
related: technical-report-requirements.md
---

# 섹터별 데이터 소스 — 실용 가이드

> 메르 블로그 스타일 리포트 작성에 실제로 쓸 수 있는 소스.
> 논문·학술 DB 제외. 뉴스·기업 발표·커뮤니티 기반.
> **이미 AgentVault에 구현된 소스 포함.**

---

## 이미 구현된 소스 (재활용 가능)

AgentVault `src/sources/`에 이미 있는 소스들이다. 추가 작업 없이 바로 쓸 수 있다.

| 소스 | 파일 | 커버리지 |
|------|------|----------|
| Google News RSS | `google_news.py` | 전 섹터, 한국어·영어 동시 |
| Naver News API | `naver.py` | 한국 기업·산업 뉴스 |
| Yahoo Finance RSS | `yahoo_finance.py` | 미국 상장기업 뉴스·실적 |
| DuckDuckGo | `duckduckgo.py` | 영어권 뉴스 범용 |

**활용 방향**: 기업 이름 대신 **섹터 키워드**로 쿼리를 바꾸면 된다.

```python
# 기존: "SK하이닉스 HBM"
# 변경: "HBM 반도체 패키징 기술" → 섹터 수준 기사 수집
```

---

## 추가할 소스 — 한국어

### 전자신문 (etnews.com)
반도체·디스플레이·배터리·AI 분야 국내 1위 전문지

| 항목 | 내용 |
|------|------|
| 접근 방법 | RSS |
| 인증 | 불필요 |
| 난이도 | 쉬움 |

```
반도체: https://www.etnews.com/rss/etnews_semiconductor.xml
디스플레이: https://www.etnews.com/rss/etnews_display.xml
배터리: https://www.etnews.com/rss/etnews_battery.xml
AI·SW: https://www.etnews.com/rss/etnews_ai.xml
```

---

### The Elec (디일렉)
반도체·디스플레이 국내 전문 뉴스레터. 공급망·수율·부품 단위 심층 보도.

| 항목 | 내용 |
|------|------|
| 접근 방법 | RSS + 웹 크롤링 |
| 한국어 | thelec.kr |
| 영어 | en.thelec.kr |
| 난이도 | 쉬움 |

```
https://www.thelec.kr/rss/allArticle.xml
https://en.thelec.kr/rss/allArticle.xml
```

메르 스타일과 가장 유사한 심층 기사 제공.
"삼성 GAA 수율 60% 돌파" 같은 구체적 수치 기반 기사가 많다.

---

### 연합뉴스
국내 주요 뉴스와이어. 기업 공시·정부 정책 발표 속보.

| 항목 | 내용 |
|------|------|
| 접근 방법 | RSS |
| 난이도 | 쉬움 |

```
경제: https://www.yna.co.kr/rss/economy.xml
산업: https://www.yna.co.kr/rss/industry.xml
```

---

### 네이버 증권 뉴스
종목별 뉴스 집계. 특정 종목 코드로 관련 기사 전체 수집 가능.

| 항목 | 내용 |
|------|------|
| 접근 방법 | 경량 크롤링 |
| 난이도 | 보통 |

```python
# 삼성전자 관련 뉴스
url = "https://finance.naver.com/item/news.nhn?code=005930"
# BeautifulSoup으로 기사 제목·링크 파싱
```

---

## 추가할 소스 — 영어

### 기업 공식 뉴스룸 RSS

기업이 직접 발표하는 제품 출시·파트너십·실적 소식. 가장 신뢰도 높다.

| 기업 | RSS URL |
|------|---------|
| Samsung Newsroom | `https://news.samsung.com/global/feed` |
| NVIDIA Blog | `https://blogs.nvidia.com/feed/` |
| Apple Newsroom | `https://www.apple.com/newsroom/rss-feed.xml` |
| Microsoft Blog | `https://blogs.microsoft.com/feed/` |
| Google Blog | `https://blog.google/rss/` |
| Meta AI | `https://ai.meta.com/blog/rss/` |
| Tesla IR | 공시 페이지 직접 크롤링 |

---

### Hacker News (기술 커뮤니티)

실리콘밸리 개발자·투자자들이 공유하는 기술 뉴스. AI·반도체 섹터 선행 지표 역할.

| 항목 | 내용 |
|------|------|
| 접근 방법 | Algolia API (무료, 인증 불필요) |
| 형식 | JSON |
| 난이도 | 쉬움 |

```python
import requests

resp = requests.get(
    "https://hn.algolia.com/api/v1/search",
    params={
        "query": "TSMC packaging CoWoS",
        "tags": "story",
        "hitsPerPage": 10,
    },
)
stories = resp.json()["hits"]
for s in stories:
    print(s["title"], s["url"], s["points"])
```

주가보다 6~12개월 앞서 기술 트렌드를 논의하는 경향이 있다.

---

### Reddit 커뮤니티

| 서브레딧 | 섹터 | 특징 |
|----------|------|------|
| r/investing | 전체 | 개인투자자 종목 분석 |
| r/semiconductor | 반도체 | 공정·장비 기술 토론 |
| r/electricvehicles | 자동차·배터리 | EV 실사용 + 기술 |
| r/singularity | AI | AGI·LLM 동향 |
| r/biotech | 바이오 | 임상 결과·파이프라인 |

```python
import requests

# Reddit 공개 JSON API (인증 불필요)
resp = requests.get(
    "https://www.reddit.com/r/semiconductor/new.json",
    params={"limit": 25},
    headers={"User-Agent": "AgentVault/1.0"},
)
posts = resp.json()["data"]["children"]
```

---

### TechCrunch RSS

AI·스타트업·빅테크 뉴스. 투자·M&A 소식이 빠르다.

```
https://techcrunch.com/feed/
https://techcrunch.com/category/artificial-intelligence/feed/
```

---

### FRED API (미국 연방준비제도)

금리·물가·공급망 지수 등 매크로 데이터. 섹터 분석의 거시 맥락용.

| 항목 | 내용 |
|------|------|
| 접근 방법 | API (무료 키) |
| 키 발급 | fred.stlouisfed.org 에서 무료 |
| 난이도 | 쉬움 |

```python
import requests

resp = requests.get(
    "https://api.stlouisfed.org/fred/series/observations",
    params={
        "series_id": "PPIACO",   # 생산자물가지수 (배터리 소재 가격 참조)
        "api_key": "YOUR_KEY",
        "file_type": "json",
        "limit": 12,
        "sort_order": "desc",
    },
)
data = resp.json()["observations"]
```

**유용한 FRED 시리즈**:

| 코드 | 내용 |
|------|------|
| `PPIACO` | 생산자물가지수 (소재 비용 파악) |
| `DCOILWTICO` | WTI 원유 가격 (자동차·화학 섹터) |
| `T10YIE` | 10년 기대 인플레이션 (금리 방향) |
| `MRTSSM44X72USS` | 미국 소매 판매 (소비재 섹터) |

---

## 섹터별 소스 조합

| 섹터 | 주 소스 | 보조 소스 |
|------|---------|----------|
| **AI** | Google News RSS + HN API | NVIDIA·MS·Meta 뉴스룸 RSS |
| **반도체** | The Elec RSS + 전자신문 RSS | HN API + Samsung Newsroom |
| **바이오** | Google News RSS (한국어) | 연합뉴스 + Reddit r/biotech |
| **헬스케어** | Naver News API | 연합뉴스 + Google News |
| **디스플레이** | The Elec RSS + 전자신문 RSS | Samsung Newsroom |
| **2차전지** | 전자신문 RSS + Google News | FRED API (소재가격) |
| **자동차** | Google News RSS | Tesla IR + Reddit r/electricvehicles |

---

## 기존 시스템과의 통합 방법

새 소스를 추가할 때 기존 `src/sources/base.py`의 `BaseSource` 인터페이스를 따른다.

```python
# src/sources/thelec.py 예시
class TheElecSource(BaseSource):
    RSS_URL = "https://www.thelec.kr/rss/allArticle.xml"

    def fetch(self, company: str, **kwargs) -> list[NewsItem]:
        # RSS 파싱 → keyword 필터링 → NewsItem 반환
        ...
```

기존 `src/sources/google_news.py`와 동일한 패턴. 구현 30분이면 충분.

---

## 관련 문서

- [technical-report-requirements.md](technical-report-requirements.md) — 리포트 요건정의서
- [sector-data-sources.md](sector-data-sources.md) — 학술 소스 상세 (arXiv·PubMed 등)
- [technical-report-concept.md](technical-report-concept.md) — 개념 배경
