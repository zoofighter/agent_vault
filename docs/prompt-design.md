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

> [!tip] '무관' 탈출 게이트
> 출력이 `'무관'`이거나 빈 문자열이면 해당 기사를 최종 목록에서 제외한다. 이중 필터(벡터 거리 + LLM 판단)로 노이즈를 줄인다.

### 파라미터

| 파라미터 | 값 | 이유 |
|----------|----|------|
| `num_predict` | 120 | 한 문장이면 충분, 짧을수록 빠름 |
| `think` | False | thinking 모드 비활성화 (빈 응답 방지) |
| `stream` | True | non-stream은 이 모델에서 빈 응답 반환 |

---

## 2단계 — Curator 프롬프트

**파일:** `src/llm/curator.py` → `_build_curation_prompt()`

**목적:** 1단계를 통과한 기사 전체(최대 30건)를 한 번에 넘겨, 테마별 그룹핑 + 투자 시사점을 합성한다.

### 실제 프롬프트 구조

```
You are a senior investment analyst covering {company}.

Investment thesis and key monitoring points:
{context}            ← ChromaDB에서 뽑은 볼트 문서 2개 청크 (최대 800자)

Today's relevant news ({company}):
- {뉴스 제목1} ({출처})
- {뉴스 제목2} ({출처})
...                  ← 선별된 기사 최대 30건 제목 목록

Write a concise daily research brief in Korean with this exact structure:

## 오늘의 핵심 테마
(List 2-4 thematic groups. For each: theme name, 1-2 sentence summary)

## 투자 시사점
(3-5 bullet points connecting today's news to the investment thesis above.
Be specific: what changed, what it means for the position, any risks or catalysts)

Write in Korean. Be concise and analytical, not just descriptive.
```

### 입력 설명

| 변수 | 내용 | 출처 |
|------|------|------|
| `{company}` | 회사명 | `companies.csv` |
| `{context}` | 볼트 투자 메모 핵심 청크 2개 | ChromaDB (회사명으로 쿼리) |
| 뉴스 목록 | 1단계 통과 기사 제목 + 소스 | analyzer 출력 |

### 설계 판단

> [!info] 왜 기사 본문이 아닌 제목만 넘기나
> 기사 30건의 전체 본문을 넘기면 컨텍스트 윈도우를 초과한다. 제목만으로도 LLM이 테마를 파악하기에 충분하며, 세부 내용이 필요한 경우 뉴스 파일(`News/`)을 직접 참조하면 된다.

> [!info] 왜 출력 구조를 명시적으로 지정하나
> LLM에게 자유 형식을 주면 매번 다른 구조로 응답한다. `## 오늘의 핵심 테마` / `## 투자 시사점` 헤더를 고정하면 Obsidian에서 항상 같은 레이아웃으로 렌더링되고, 나중에 파싱도 쉬워진다.

> [!tip] 'Be concise and analytical, not just descriptive'
> 지시하지 않으면 LLM은 기사를 요약·나열하는 데 그친다. 이 한 줄이 "오늘 이 소식이 투자 판단에 어떤 의미인가"라는 분석적 관점을 강제한다.

### 파라미터

| 파라미터 | 값 | 이유 |
|----------|----|------|
| `num_predict` | 1200 | 테마 그룹 + 시사점 5개 = 충분한 길이 |
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
