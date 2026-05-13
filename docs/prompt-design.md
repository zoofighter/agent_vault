---
title: 프롬프트 설계 — 뉴스 분석 & 큐레이팅
tags:
  - system
  - llm
  - prompt
created: 2026-05-13
---

# 프롬프트 설계 — 뉴스 분석 & 큐레이팅

이 시스템은 두 단계에서 LLM을 호출한다.
각 단계의 목적, 입력 구성, 설계 판단을 정리한다.

---

## 전체 흐름

```
수집된 뉴스 (N건)
    │
    ▼
[1단계] 벡터 유사도 필터 (ChromaDB)
    │  거리 > 0.75 → 제외
    ▼
[1단계] analyzer 프롬프트  ← 기사 1건씩, LLM 호출 N회
    │  '무관' 또는 빈 응답 → 제외
    ▼
선별된 뉴스 (M건, M < N)  →  News/ 저장
    │
    ▼
[2단계] curator 프롬프트   ← 선별 기사 전체, LLM 호출 1회
    │
    ▼
테마별 종합 분석            →  Curated/ 저장
```

---

## 1단계 — Analyzer 프롬프트

**파일:** `src/llm/analyzer.py` → `_build_prompt()`

**목적:** 기사 1건이 이 회사 투자 판단에 관련 있는지 판정하고, 관련 있으면 이유 한 문장을 생성한다.

### 실제 프롬프트 구조

```
You are an investment analyst for {company}.

Reference document (investment memo excerpt):
{context}            ← ChromaDB에서 뽑은 볼트 문서 청크 (최대 600자)

News title: {title}
News summary: {snippet}

In ONE Korean sentence (under 50 characters), explain why this news
is relevant for {company} investors.
If not relevant at all, reply with exactly '무관' and nothing else.
```

### 입력 설명

| 변수 | 내용 | 출처 |
|------|------|------|
| `{company}` | 회사명 (예: 삼성전자) | `companies.csv` |
| `{context}` | 볼트 문서 중 이 기사와 가장 유사한 청크 | ChromaDB 벡터 검색 |
| `{title}` | 뉴스 제목 | Naver / DuckDuckGo / NaverFinance |
| `{snippet}` | 뉴스 발췌문 (없으면 N/A) | 동일 |

### 설계 판단

> [!info] 왜 프롬프트를 영어로 작성했나
> `gemma4:e2b`는 thinking 모델이다. 한국어 전체 프롬프트를 주면 thinking 단계에서 토큰을 모두 소비하고 실제 응답(`response` 필드)이 비어버린다. 영어로 지시하고 한국어 제목/문서만 삽입하면 thinking 없이 바로 응답한다. `think=False` 옵션도 함께 사용.

> [!info] 왜 `context`를 ChromaDB에서 가져오나
> "이 기사가 관련 있다"는 판단을 키워드가 아니라 **내 투자 관점**으로 하기 위해서다. ChromaDB에는 볼트의 메모·분석 문서가 임베딩되어 있고, 기사 텍스트와 가장 가까운 청크를 `context`로 넘긴다. 즉, LLM은 내가 어떤 포인트를 중요하게 보는지를 참고해서 관련성을 판단한다.

> [!tip] 거절 표현 게이트 (확장)
> `gemma4:e2b`는 "관련 없다"는 뜻을 다양한 표현으로 반환한다. `"무관"` 하나만 걸러서는 부족하다.
> 아래 `_REJECT_PHRASES` 목록 중 하나라도 포함되면 제외한다.
>
> ```python
> _REJECT_PHRASES = (
>     "무관", "관련 없음", "관련성 없음", "해당 없음",
>     "관련 정보 없음", "관련된 정보 없음", "직접적인 관련 없음", "직접 관련 없음", "정보 없음",
>     "연관성은 없", "관련성은 없", "관련성이 없", "영향을 주지 않", "영향은 없", "영향이 없",
>     "not relevant", "irrelevant", "no relevance", "no direct relevance",
> )
> ```

### 파라미터

| 파라미터 | 값 | 이유 |
|----------|----|------|
| `num_predict` | 120 | 한 문장이면 충분, 짧을수록 빠름 |
| `think` | False | thinking 모드 비활성화 (빈 응답 방지) |
| `stream` | True | non-stream은 이 모델에서 빈 응답 반환 |

### 사전 필터 — LLM 호출 전

벡터 유사도 게이트 외에 두 가지 사전 필터가 LLM 호출 전에 적용된다.

**1) 자회사명 필터 (`_is_subsidiary_article`)**

```python
_SUBSIDIARY_SUFFIXES = ("증권", "금융", "보험", "캐피탈", "자산운용", "저축은행")

def _is_subsidiary_article(title: str, company: str) -> bool:
    for suffix in _SUBSIDIARY_SUFFIXES:
        if (company + suffix) in title and not company.endswith(suffix):
            return True
    return False
```

`"현대차"` 검색 결과에 `"현대차증권"` 기사가 포함되는 현상을 방지한다. 회사명이 더 긴 다른 법인명의 접두사인 경우 제외.

**2) 잡음 기사 필터**

영문 제목 중 통화 변환기·계산기 등 명백한 비금융 패턴을 포함한 기사를 제외한다.

```python
junk_patterns = ["convert ", "calculator", "to armenian", "to japanese yen"]
```

---

## 2단계 — Curator 프롬프트

**파일:** `src/llm/curator.py` → `_build_curation_prompt()`

**목적:** 1단계를 통과한 기사 전체(최대 30건)를 한 번에 넘겨, 테마별 그룹핑 + 투자 시사점을 합성한다.

### 실제 프롬프트 구조

```
You are a senior investment analyst covering {company}.

Investment thesis and key monitoring points:
{context}            ← ChromaDB에서 뽑은 볼트 문서 2개 청크 (최대 800자)

Today's relevant news ({company}) — format: title → relevance reason:
- {뉴스 제목1} → {관련 근거1}
- {뉴스 제목2} → {관련 근거2}
...                  ← 선별된 기사 최대 30건 (제목 + Analyzer 이유)

Write a concise daily research brief in Korean with this EXACT structure
(output all six sections in order, no extras):

## 오늘의 핵심 테마
(2-4 thematic groups. Each: bold theme name + 1-2 sentence summary)

## 투자 시사점
(3-5 bullet points. Each: what changed today and what it means for the position)

## 논거 검증
(ONE sentence only: did today's news strengthen / maintain / weaken the investment thesis?
State which thesis point was affected and why)

## 리스크 업데이트
(Bullet points for risks newly highlighted or escalated TODAY.
Skip if nothing new. Do NOT repeat known standing risks.)

## 모니터링 포인트
(Bullet points: upcoming events, dates, or indicators to watch next —
earnings, policy decisions, competitor announcements, key metrics)

## 경쟁사/섹터 동향
(Bullet points for competitor or sector news that affects this company.
State the implication for this company explicitly. Skip if none.)

Write in Korean. Be analytical and specific, not just descriptive.
```

### 입력 설명

| 변수 | 내용 | 출처 |
|------|------|------|
| `{company}` | 회사명 | `companies.csv` |
| `{context}` | 볼트 투자 메모 핵심 청크 2개 | ChromaDB (회사명으로 쿼리) |
| 뉴스 목록 | 1단계 통과 기사 제목 + **Analyzer 이유** | analyzer 출력 |

### 설계 판단

> [!info] 왜 제목만 넘기지 않고 이유도 함께 넘기나
> 기존에는 제목만 전달했다. 이유(reason)를 함께 넘기면 LLM이 각 기사를 왜 선별했는지 맥락을 알 수 있다.
> 특히 `## 경쟁사/섹터 동향` 섹션에서 "왜 이 경쟁사 기사가 이 회사에 관련됐는지"를 LLM이 더 정확하게 판단할 수 있다.
>
> 형식: `- 뉴스 제목 → Analyzer가 생성한 관련 근거 한 문장`

> [!info] 왜 6개 섹션인가
> 기존 2개(테마, 시사점)는 "오늘 무슨 일이 있었나 + 내 포지션에 어떤 의미인가"까지만 답한다.
> 추가된 4개 섹션이 커버하는 질문:
> - **논거 검증**: 내 판단이 지금도 맞는가? (확신 강도 트래킹)
> - **리스크 업데이트**: 오늘 새로 생긴 위험은 무엇인가?
> - **모니터링 포인트**: 다음에 무엇을 확인해야 하나?
> - **경쟁사/섹터 동향**: 주변 환경 변화가 이 회사에 미치는 함의는?

> [!info] 왜 출력 구조를 명시적으로 지정하나
> LLM에게 자유 형식을 주면 매번 다른 구조로 응답한다. `## 오늘의 핵심 테마` / `## 투자 시사점` 헤더를 고정하면 Obsidian에서 항상 같은 레이아웃으로 렌더링되고, 나중에 파싱도 쉬워진다.

> [!tip] 'Be concise and analytical, not just descriptive'
> 지시하지 않으면 LLM은 기사를 요약·나열하는 데 그친다. 이 한 줄이 "오늘 이 소식이 투자 판단에 어떤 의미인가"라는 분석적 관점을 강제한다.

### 파라미터

| 파라미터 | 값 | 이유 |
|----------|----|------|
| `num_predict` | 2000 | 6개 섹션 = 기존 대비 분량 증가 |
| `think` | False | 1단계와 동일한 이유 |
| `stream` | True | 동일 |

---

## 두 프롬프트 비교

| | Analyzer (1단계) | Curator (2단계) |
|---|---|---|
| 호출 횟수 | 기사 N건 × 1회 | 1회 |
| 입력 크기 | 기사 1건 + 청크 1개 | 기사 목록 30건 + 청크 2개 |
| 출력 | 한 문장 또는 `무관` | 구조화된 리포트 (300~600자) |
| 역할 | 필터 + 태깅 | 종합 분석 |
| 저장 위치 | `News/YYYY-MM-DD.md` | `Curated/YYYY-MM-DD.md` |

---

## ChromaDB 컨텍스트가 핵심인 이유

두 프롬프트 모두 `{context}`에 **볼트 문서**를 넣는다.
이것이 단순 뉴스 알림과 다른 점이다.

```
볼트 메모 (내가 쓴 투자 논리)
    "HBM4 엔비디아 공급 재개 시 DS 부문 수익성 급반등"
    "파운드리 2nm 수율 안정화 → 퀄컴 물량 확보"
           ↓  임베딩  →  ChromaDB
뉴스 제목+본문  →  벡터 거리 계산  →  가장 가까운 볼트 청크  →  프롬프트 context
```

결국 LLM은 **"이 회사를 어떤 눈으로 봐야 하는가"** 를 내 메모에서 읽고,
그 기준으로 기사를 판단한다.

---

## 관련 파일

- [[analyzer.py 경로]]: `src/llm/analyzer.py`
- [[curator.py 경로]]: `src/llm/curator.py`
- [[embedder.py 경로]]: `src/obsidian/embedder.py` (ChromaDB 쿼리)
- [[설계 문서]]: `docs/incremental-indexing-design.md`
