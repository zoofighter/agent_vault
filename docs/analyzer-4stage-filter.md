# analyzer.py 4단계 필터

## 현재 구조 (2단계)

```
뉴스 전체
    → [Stage 3] ChromaDB 벡터 유사도 필터 (distance ≤ 0.55)
        → [Stage 4] LLM 근거 생성 (통과한 것 최대 25개)
```

LLM은 벡터 필터를 통과한 **모든 기사**에 개별 호출 — 회사당 최대 25회, 38개사 기준 최대 950회/실행.

---

## 개선안 (4단계, `use_prefilter=True`)

```
뉴스 전체
    → [Stage 1] 티커 직접 매칭   (LLM 없음, 즉시)  → 확정 관련, 템플릿 근거
    → [Stage 2] 키워드 매칭      (LLM 없음, 즉시)  → 확정 관련, 템플릿 근거
    → [Stage 3] 벡터 유사도 필터 (ChromaDB)        → 미매칭 기사만
        → [Stage 4] LLM 근거 생성                  → Stage 3 통과한 것만
```

Stage 1~2 매칭 기사는 LLM 없이 템플릿 근거로 결과에 바로 추가.
나머지만 기존 Stage 3~4 경로로 처리.

---

## 사용법

### `analyze()` 파라미터

```python
analyze(
    items,
    company="NVIDIA",
    sim_threshold=0.60,
    chroma_path="data/chroma",
    company_keywords="Blackwell,GB300,H100",
    use_prefilter=True,    # ← 기본값: 4단계 필터 활성화
)
```

`use_prefilter=True` (기본): 4단계 필터 활성화.  
`use_prefilter=False`: 기존 2단계 동작 그대로.

### collect_news.py에서 켜는 방법

```python
# collect_news.py 146번째 줄 부근
analyzed = analyze(
    items_for,
    company=name,
    sim_threshold=threshold,
    chroma_path=CHROMA_PATH,
    company_keywords=kw_map.get(name, ""),
    use_prefilter=True,    # ← 추가
)
```

### 단독 테스트

```python
from src.sources.base import NewsItem
from src.llm.analyzer import analyze

items = [
    NewsItem(title="NVDA Blackwell shipments accelerate", url="http://a",
             snippet="", source="test", company="NVIDIA", query=""),
    NewsItem(title="Random market news", url="http://b",
             snippet="", source="test", company="NVIDIA", query=""),
]

# 기존 방식
results_old = analyze(items, company="NVIDIA", use_prefilter=False)

# 4단계 방식
results_new = analyze(items, company="NVIDIA", use_prefilter=True)

for r in results_new:
    print(r.item.title, "→", r.reason)
# NVDA Blackwell shipments accelerate → 키워드 매칭: Blackwell
# (Random market news는 벡터 필터로 넘어감)
```

---

## 내부 구현

### 신규 파일: `src/llm/company_index.py`

`companies.csv`를 모듈 로드 시 1회 파싱, 두 딕셔너리 제공.

```python
TICKER_INDEX:  dict[str, str]        # "NVIDIA" → "NVDA", "삼성전자" → "005930"
KEYWORD_INDEX: dict[str, list[str]]  # "NVIDIA" → ["Blackwell", "H100", ...]
```

### Stage 1 — 티커 매칭

뉴스 제목+스니펫 전문에 ticker 문자열이 등장하는지 확인.

```python
def _stage1_ticker_match(item, company) -> bool:
    ticker = TICKER_INDEX.get(company, "")
    text = f"{item.title} {item.snippet or ''}"
    return ticker in text
```

결과: `reason = "NVDA 직접 언급"`, `distance = 0.0`

### Stage 2 — 키워드 매칭

뉴스 제목+스니펫에 keywords 중 하나 이상 포함되는지 확인.

```python
def _stage2_keyword_match(item, company) -> tuple[bool, str]:
    keywords = KEYWORD_INDEX.get(company, [])
    text = f"{item.title} {item.snippet or ''}".lower()
    matched = [kw for kw in keywords if kw.lower() in text]
    return bool(matched), ", ".join(matched[:3])
```

결과: `reason = "키워드 매칭: Blackwell, H100"`, `distance = 0.1`

### Stage 3~4 — 기존 로직 유지

prefilter 매칭 기사의 URL은 `prefiltered_urls`에 기록,
벡터 필터 루프에서 건너뜀 → 중복 처리 없음.

---

## 예상 LLM 호출 감소량

### 가정

- 회사당 수집 뉴스: 평균 20개
- 38개사 × 20개 = **760개 기사/실행**
- 현재 벡터 필터 통과율: 약 30% → LLM 호출 **228회/실행**

### use_prefilter=True 시 예상 흐름

| 단계 | 처리 방식 | 비고 | 잔여 |
|------|----------|------|------|
| 수집 전체 | - | - | 760개 |
| Stage 1 티커 매칭 | 확정 관련, 즉시 결과 추가 | LLM 0회 | 760개* |
| Stage 2 키워드 매칭 | 확정 관련, 즉시 결과 추가 | LLM 0회 | ~456개** |
| Stage 3 벡터 필터 | ChromaDB (기존) | - | ~137개 |
| Stage 4 LLM | 근거 생성 | - | **~137회** |

\* Stage 1은 탈락이 아닌 확정 분류 — 카운트는 유지, 벡터 필터 진입에서 제외  
\*\* keywords 미매칭 기사 약 40% 탈락 추정

### 절감 요약

| 항목 | 현재 (`use_prefilter=False`) | 개선 (`use_prefilter=True`) |
|------|-------|-------|
| ChromaDB 조회 | 760회 | ~456회 (-40%) |
| LLM 호출 | ~228회 | ~137회 (-40%) |
| LLM 최대 대기 (30초/회) | 6,840초 | 4,110초 |
| **실행 시간 절감** | - | **약 45분** |

키워드 매칭이 잘 설계된 기업(반도체/AI 종목)은 절감 효과가 더 큼.
키워드가 너무 일반적인 경우(예: "클라우드") 오탐 가능 → companies.csv keywords 정밀도가 중요.

---

## 트레이드오프

| 항목 | `use_prefilter=False` | `use_prefilter=True` |
|------|------|------|
| LLM 근거 품질 | 볼트 컨텍스트 기반 문장 | 템플릿 (Stage 1~2 매칭분) |
| 처리 속도 | 느림 | 빠름 |
| 오탐 가능성 | 낮음 (벡터 유사도 기반) | 일부 있음 (키워드 단순 매칭) |
| companies.csv 의존성 | 낮음 | 높음 (keywords 품질 중요) |

기본값 `True`로 4단계 필터 활성화. 기존 동작이 필요하면 `False`로 명시.

---

## 관련 파일

| 파일 | 역할 |
|------|------|
| `src/llm/analyzer.py` | `analyze()` — `use_prefilter` 파라미터, `_stage1_ticker_match()`, `_stage2_keyword_match()` |
| `src/llm/company_index.py` | `companies.csv` → `TICKER_INDEX`, `KEYWORD_INDEX` 빌드 |
| `companies.csv` | ticker, keywords 컬럼이 Stage 1~2의 데이터 소스 |

---

## 참조

- `a_0504_hanky/news_curation/relevance.py` — `ReferenceIndex`, 2단계 매칭 설계 원형
- `a_0429_mini_perp/stock_perplexity/nodes/content_evaluator.py` — `SOURCE_WEIGHTS`, 배치 평가 패턴
