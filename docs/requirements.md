# 요건정의서: Obsidian 연동 뉴스 수집 및 분석 시스템

## 1. 프로젝트 개요

### 1.1 목적
Obsidian 볼트에 저장된 회사별 리포트 및 수동 정리 파일을 기반으로, 관련 뉴스를 자동으로 수집·분석하여 Obsidian 노트 형식으로 저장하는 시스템 구축

### 1.2 핵심 가치
- 기존 Obsidian 리서치 자료와 맥락이 맞는 뉴스만 선별
- 뉴스 수집 근거(출처, 유사도 이유)를 함께 기록
- 분석 결과를 Obsidian 표준 양식으로 자동 저장

### 1.3 볼트 폴더별 작성 주체

회사 폴더 내 하위 폴더는 **작성 주체**에 따라 역할을 명확히 구분한다.

| 폴더 | 작성 주체 | 용도 |
|------|---------|------|
| `Research/` | **AI 자동 생성** | 실적 분석, 기술 동향, 경쟁사 비교 등 구조화된 리서치 문서 |
| `Memos/` | **사용자 직접 작성** | 투자 메모, 개인 판단, 아이디어 등 주관적 기록 |
| `News/` | **시스템 자동 저장** | 매일 수집된 뉴스 노트 (본 시스템 산출물) |

- `Research/`는 AI가 볼트 내 컨텍스트 + 외부 데이터를 참조해 자동 작성할 계획
- `Memos/`는 시스템이 읽기만 하며, 절대 자동 생성·덮어쓰기하지 않는다

---

## 2. 시스템 아키텍처

볼트 규모 확장에 대비해 **인덱스 빌드**와 **일일 검색**을 분리한다.
인덱스는 변경된 파일만 증분 업데이트하므로 볼트가 수천 개로 늘어나도 일일 실행 시간은 일정하게 유지된다.

### Phase A — 인덱스 빌드 (변경 파일만 처리)

```
[Obsidian 볼트]
  └─ .md 파일 전체 목록
          ↓ mtime + MD5 비교
[인덱스 관리 모듈]  ←── index_state.json
  └─ 변경된 파일만 선별
          ↓ 변경 파일 본문 + frontmatter
[임베딩 모듈]
          ↓ 벡터
[ChromaDB]  ←── data/chroma/ (영구 저장)
```

### Phase B — 일일 뉴스 검색 (매일 실행)

```
[ChromaDB]  ←── 이미 빌드된 인덱스 (즉시 로드)
          ↓ 벡터 유사도 검색 (< 0.5초)
[뉴스 수집 모듈]  ←── 복수 소스
          ↓ 원문 수집
[본문 추출 모듈]  ←── BeautifulSoup / Playwright
          ↓ 정제된 본문
[로컬 LLM 분석 모듈]  ←── 유사도 상위 N건만
          ↓ 분석 결과 + 근거
[Obsidian 노트 생성 모듈]
          ↓
[Obsidian 볼트]  ←── 뉴스 노트 저장
```

---

## 3. 기능 요건

### 3.1 Obsidian 컨텍스트 추출 모듈

| ID | 요건 | 우선순위 |
|----|------|---------|
| F-01 | 지정된 Obsidian 볼트 경로에서 마크다운 파일 읽기 | 필수 |
| F-02 | 회사별 폴더/태그 기반 파일 분류 | 필수 |
| F-03 | 파일 내 핵심 키워드 추출 (회사명, 업종, 관심 이슈) | 필수 |
| F-04 | 최근 수정된 파일 우선 처리 | 선택 |
| F-05 | Obsidian frontmatter(YAML) 파싱 (tags, company, sector 등) | 필수 |

**입력**: Obsidian `.md` 파일 경로  
**출력**: `{company: str, keywords: list, context_summary: str, file_path: str}`

---

### 3.2 뉴스 수집 모듈

#### 3.2.1 지원 소스

| 소스 | 라이브러리/방식 | 용도 | 비고 |
|------|---------------|------|------|
| 네이버 뉴스 | Naver Search API | 국내 뉴스 | API 키 필요 |
| DuckDuckGo | `duckduckgo-search` | 범용 검색 | 무료 |
| Yahoo Finance News | RSS / 스크래핑 | 글로벌 금융 뉴스 | - |
| SearXNG | REST API | 무료 통합 검색 | 자체 인스턴스 권장 |
| OrioSearch | API | 최신 구조 기반 검색 | - |

#### 3.2.2 수집 요건

| ID | 요건 | 우선순위 |
|----|------|---------|
| F-10 | 각 소스별 검색어 자동 생성 (회사명 + 키워드 조합) | 필수 |
| F-11 | 중복 뉴스 제거 (URL 기준 dedup) | 필수 |
| F-12 | 수집 날짜 범위 설정 가능 (기본: 최근 7일) | 필수 |
| F-13 | 소스별 결과 수 제한 설정 | 선택 |
| F-14 | 수집 실패 시 다음 소스로 폴백 | 필수 |
| F-15 | Rate limit 준수 (소스별 딜레이 설정) | 필수 |

---

### 3.3 본문 추출 모듈

| ID | 요건 | 우선순위 |
|----|------|---------|
| F-20 | BeautifulSoup으로 정적 페이지 본문 추출 | 필수 |
| F-21 | JavaScript 렌더링 필요 페이지는 Playwright로 처리 | 필수 |
| F-22 | 광고, 메뉴, 푸터 등 불필요한 요소 제거 | 필수 |
| F-23 | 추출 실패 시 snippet(요약문) 대체 사용 | 필수 |
| F-24 | 본문 최대 길이 제한 설정 (LLM 컨텍스트 고려) | 필수 |

---

### 3.4 로컬 LLM 분석 모듈

| ID | 요건 | 우선순위 |
|----|------|---------|
| F-30 | Obsidian 파일 컨텍스트와 뉴스 본문 유사도 분석 | 필수 |
| F-31 | 유사도 점수 및 관련 근거 텍스트 추출 | 필수 |
| F-32 | 뉴스 요약문 생성 (3~5줄) | 필수 |
| F-33 | 관련 회사 파일에 미치는 영향 분석 | 선택 |
| F-34 | 유사도 임계값 미만 뉴스 필터링 | 필수 |
| F-35 | 분석에 사용한 모델명 및 버전 기록 | 선택 |

**지원 로컬 LLM 백엔드**: Ollama, LM Studio (OpenAI 호환 API)

---

### 3.5 Obsidian 노트 생성 모듈

| ID | 요건 | 우선순위 |
|----|------|---------|
| F-40 | 수집된 뉴스를 Obsidian 마크다운 형식으로 저장 | 필수 |
| F-41 | 노트 파일명: `YYYY-MM-DD_회사명_뉴스제목.md` | 필수 |
| F-42 | 저장 경로: 볼트 내 `News/` 또는 설정 가능한 경로 | 필수 |
| F-43 | 회사 노트에 백링크(`[[회사명]]`) 자동 삽입 | 필수 |
| F-44 | 수집 완료 후 일일 요약 노트 생성 | 선택 |

---

### 3.6 인덱스 관리 모듈 (증분 임베딩)

볼트 파일 수가 증가해도 일일 실행 시간이 늘어나지 않도록, **변경된 파일만** 임베딩을 재생성한다.

| ID | 요건 | 우선순위 |
|----|------|---------|
| F-50 | 파일별 mtime + MD5 해시로 변경 감지 | 필수 |
| F-51 | 변경된 파일만 임베딩 재생성 (전체 재빌드 없음) | 필수 |
| F-52 | ChromaDB `persistent_directory` 설정으로 영구 저장 | 필수 |
| F-53 | `data/index_state.json`에 파일별 `{mtime, hash, embedded_at}` 기록 | 필수 |
| F-54 | 볼트 파일 삭제 시 ChromaDB에서 해당 임베딩도 제거 | 필수 |
| F-55 | 강제 전체 재인덱스 옵션 (`--reindex-all` 플래그) | 선택 |

**처리 흐름**:
```
볼트 스캔 → 파일별 (mtime, hash) 계산
    → index_state.json 과 비교
        신규/변경 파일 → 임베딩 생성 → ChromaDB upsert → state 갱신
        삭제된 파일   → ChromaDB delete → state에서 제거
        미변경 파일   → 스킵 (0ms)
```

**index_state.json 구조**:
```json
{
  "Companies/삼성전자.md": {
    "mtime": 1747036800.0,
    "hash": "a3f2c1...",
    "embedded_at": "2026-05-12T08:00:00"
  }
}
```

---

## 4. Obsidian 노트 양식

### 4.1 개별 뉴스 노트 템플릿

```markdown
---
type: news
company: "{{회사명}}"
source: "{{출처 URL}}"
published: {{기사 발행일}}
collected: {{수집일시}}
relevance_score: {{0.0 ~ 1.0}}
tags:
  - news
  - {{회사명}}
  - {{섹터/업종}}
---

# {{기사 제목}}

## 요약
{{LLM 생성 요약 (3~5줄)}}

## 관련 근거
> {{기존 Obsidian 파일과 연결된 핵심 문장}}
> — [[{{연결된 Obsidian 파일명}}]]

**유사도**: {{relevance_score}} | **분석 이유**: {{근거 설명}}

## 원문 본문
{{추출된 본문 또는 snippet}}

## 출처
- **URL**: {{source_url}}
- **소스**: {{수집 소스명 (Naver / DuckDuckGo / Yahoo 등)}}
- **수집 쿼리**: `{{사용된 검색 쿼리}}`
```

### 4.2 일일 요약 노트 템플릿

```markdown
---
type: news-digest
date: {{YYYY-MM-DD}}
total_collected: {{총 수집 기사 수}}
tags:
  - digest
  - news
---

# 뉴스 다이제스트 — {{YYYY-MM-DD}}

## 회사별 요약

### [[{{회사명1}}]]
- [[{{뉴스 노트 링크1}}]] — {{한줄 요약}}
- [[{{뉴스 노트 링크2}}]] — {{한줄 요약}}

### [[{{회사명2}}]]
- ...

## 오늘의 주요 이슈
{{LLM 생성 전체 요약}}
```

---

## 5. 비기능 요건

| ID | 요건 | 기준 |
|----|------|------|
| NF-01 | 뉴스 수집 처리 시간 | 회사 1개당 60초 이내 |
| NF-02 | 로컬 LLM 응답 시간 | 기사 1건당 30초 이내 |
| NF-03 | 수집 로그 저장 | `logs/YYYY-MM-DD.log` |
| NF-04 | 설정 파일 기반 운영 | `config.yaml` |
| NF-05 | API 키 환경변수 관리 | `.env` 파일 사용 |
| NF-06 | 오류 발생 시 부분 실패 허용 (전체 중단 없음) | - |
| NF-10 | 초기 인덱스 빌드 시간 | 100개 파일 기준 3분 이내 |
| NF-11 | 일일 인덱스 업데이트 시간 | 변경 파일 10개 이하 기준 10초 이내 |
| NF-12 | ChromaDB 벡터 유사도 검색 | 10,000 문서 기준 0.5초 이내 |

---

## 6. 설정 파일 구조 (`config.yaml`)

```yaml
obsidian:
  vault_path: "/path/to/obsidian/vault"
  company_folders:
    - "Companies/"
    - "Research/"
  news_output_folder: "News/"
  digest_folder: "Digest/"

sources:
  naver:
    enabled: true
    api_key: "${NAVER_CLIENT_ID}"
    api_secret: "${NAVER_CLIENT_SECRET}"
    results_per_query: 10
  duckduckgo:
    enabled: true
    results_per_query: 10
    delay_seconds: 2
  yahoo_finance:
    enabled: true
    results_per_query: 5
  searxng:
    enabled: false
    base_url: "http://localhost:8080"
  oriosearch:
    enabled: false
    api_key: "${ORIOSEARCH_API_KEY}"

scraping:
  use_playwright: true
  max_content_length: 3000
  timeout_seconds: 15

embedding:
  backend: "ollama"                 # ollama | openai | gemini
  model: "nomic-embed-text"         # 로컬 무료 (Ollama)
  # model: "text-embedding-3-small" # OpenAI API ($0.02/1M tokens)
  batch_size: 20                    # 한 번에 처리할 파일 수

llm:
  backend: "ollama"           # ollama | lmstudio
  model: "llama3.2"
  base_url: "http://localhost:11434"
  relevance_threshold: 0.6    # 이 점수 미만 기사 필터링

schedule:
  run_time: "08:00"           # 매일 실행 시각
  lookback_days: 7
```

---

## 7. 데이터 흐름 상세

#### Phase A — 인덱스 업데이트 (볼트 변경 시마다 / 또는 일일 실행 전 자동)

```
1. config.yaml 로드
2. 볼트 전체 .md 파일 목록 수집
3. 파일별 (mtime, MD5) 계산 → index_state.json 비교
4. 변경/신규 파일만:
   a. frontmatter + 본문 파싱
   b. 임베딩 생성 (embedding.model)
   c. ChromaDB upsert (company, file_path 메타데이터 포함)
   d. index_state.json 갱신
5. 삭제된 파일: ChromaDB delete + state 제거
6. 미변경 파일: 스킵
```

#### Phase B — 일일 뉴스 검색

```
1. ChromaDB 로드 (이미 빌드됨, 즉시)
2. 활성 회사 목록 수집 (ChromaDB 메타데이터 기반)
3. 회사별 반복:
   a. 검색 쿼리 생성 (회사명 + 키워드)
   b. 활성화된 소스에서 뉴스 URL 수집
   c. 중복 제거
   d. 각 URL 본문 추출 (BS4 → Playwright 폴백)
   e. ChromaDB 벡터 유사도 검색 → 관련 기준 문서 top-K 반환
   f. 유사도 threshold 미만 기사 사전 필터링
   g. 통과한 기사만 LLM으로 근거 생성 + 요약
   h. Obsidian 노트로 저장
4. 일일 다이제스트 노트 생성
5. 실행 로그 저장
```

---

## 8. 파일/폴더 구조 (구현)

```
project/
├── config.yaml
├── .env
├── main.py                  # 진입점 (--index-only / --search-only 플래그 지원)
├── src/
│   ├── obsidian/
│   │   ├── reader.py        # 볼트 파일 읽기 / 키워드 추출
│   │   ├── indexer.py       # 파일 변경 감지 + index_state.json 관리
│   │   ├── embedder.py      # ChromaDB 증분 임베딩 업데이트
│   │   └── writer.py        # 뉴스 노트 생성
│   ├── sources/
│   │   ├── naver.py
│   │   ├── duckduckgo.py
│   │   ├── yahoo_finance.py
│   │   ├── searxng.py
│   │   └── oriosearch.py
│   ├── scraper/
│   │   ├── bs4_scraper.py
│   │   └── playwright_scraper.py
│   └── llm/
│       └── analyzer.py      # 근거 생성 + 요약 (유사도는 ChromaDB가 담당)
├── data/
│   ├── chroma/              # ChromaDB 영구 저장소
│   └── index_state.json     # 파일별 변경 추적 상태
├── templates/
│   ├── news_note.md
│   └── digest_note.md
└── logs/
```

---

## 9. 구현 단계 (Phase)

| Phase | 내용 | 산출물 |
|-------|------|--------|
| Phase 1-A | 볼트 파일 읽기 + 변경 감지 | `obsidian/reader.py`, `obsidian/indexer.py` |
| Phase 1-B | ChromaDB 증분 임베딩 빌드 | `obsidian/embedder.py`, `data/chroma/` |
| Phase 2 | 뉴스 소스 1개 연동 (DuckDuckGo 우선) | `sources/duckduckgo.py` |
| Phase 3 | BS4 본문 추출 | `scraper/bs4_scraper.py` |
| Phase 4 | ChromaDB 유사도 검색 + LLM 근거 생성 | `llm/analyzer.py` |
| Phase 5 | Obsidian 노트 저장 | `obsidian/writer.py` |
| Phase 6 | 나머지 소스 추가 + Playwright 추가 | - |
| Phase 7 | 일일 다이제스트 + 스케줄러 | - |
