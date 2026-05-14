---
title: VaultPulse — 시스템 전체 개요
type: system-doc
created: 2026-05-14
---

# VaultPulse

> 내가 쌓은 투자 리서치를 필터 삼아, 매일 관련 뉴스를 자동으로 골라 Obsidian에 정리하는 개인 인텔리전스 파이프라인

---

## 시스템 이름 선정 배경

**VaultPulse** — Obsidian Vault(지식 저장소)에 뉴스가 심장 박동(Pulse)처럼 규칙적으로 유입된다는 의미.
단순 뉴스 알림이 아니라 **볼트에 축적된 나의 리서치**가 필터 기준이 된다는 점이 핵심 차별점이다.

- 일반 뉴스 알림: 키워드(삼성전자, NVDA)가 기준
- VaultPulse: **내가 볼트에 쓴 글**이 기준

HBM 경쟁력 분석을 써둔 사람에게는 HBM 뉴스가 높은 유사도로 선별된다.
같은 "삼성전자" 기사라도 노사 갈등 기사는 낮게, 메모리 공정 기사는 높게 잡힌다.

---

## 핵심 개념: RAG 역방향 응용

```
일반 RAG:    질문(Query) → 문서 검색 → 답변 생성
VaultPulse:  문서(볼트)  → 뉴스 필터링 → 인사이트 생성
```

볼트가 커질수록 필터가 정교해진다. 오늘의 뉴스 노트가 내일의 필터 재료가 된다.
**피드백 루프**가 내장된 자기 성장형 시스템이다.

---

## 전체 아키텍처

```
┌─────────────────────────────────────────────────────────┐
│                    run_daily.sh (LaunchAgent)            │
│                    매일 07:00 / 18:00 자동 실행           │
└──────────┬──────────────┬──────────────┬────────────────┘
           │              │              │
       Phase 1         Phase 2        Phase 3
      뉴스 수집        KRX 리서치     해외 리서치
           │
    collect_news.py
    ┌──────┴──────────────┐
    │                     │
  Phase A              Phase B+C
  볼트 인덱싱          뉴스 수집 & 분석
    │                     │
  ChromaDB           Daily 노트 저장
  (벡터 DB)          (Obsidian 볼트)
```

---

## 모듈별 상세 설명

### Phase A — 볼트 인덱싱 (`src/obsidian/`)

볼트 전체를 스캔하되 변경된 파일만 재임베딩하는 **증분 인덱싱** 시스템.

| 파일 | 역할 |
|------|------|
| `indexer.py` | `mtime + MD5` 해시로 변경 파일 감지, `data/index_state.json` 관리 |
| `embedder.py` | ChromaDB에 청크 임베딩. 손상 DB 자동 복구, 동시 실행 충돌 graceful fallback |
| `company_manager.py` | 기업 폴더 구조 동기화. `company_dir()` — 모든 경로의 단일 출처 |
| `templates.py` | 기업 프로필 마크다운 자동 생성 템플릿 |
| `writer.py` | Daily 노트 작성 (종합 분석 + 뉴스 목록 단일 파일) |

**설계 원칙**: 볼트가 수백 개 파일로 커져도 일일 실행 시간이 일정하다.
Daily 노트는 인덱싱에서 제외(`_SKIP_DIRS`)하여 자기 참조 루프를 방지한다.

---

### Phase B — 뉴스 수집 (`src/sources/`)

거래소별로 최적화된 8개 소스를 조합해 뉴스를 수집한다.

| 거래소 | 소스 조합 |
|--------|---------|
| KRX (한국) | Naver 뉴스 API + Naver Finance 메인 + DuckDuckGo |
| NASDAQ/NYSE (미국) | Yahoo Finance RSS(24h 캐시) + DuckDuckGo + Google News |
| HKEX (홍콩) | Yahoo Finance + HKEX 공시 → Google News 폴백 |
| SZSE (중국) | Yahoo Finance + Google News |
| TWSE (대만) | Yahoo Finance + MOPS 공시 → Google News 폴백 |
| TSE (일본) | Yahoo Finance + TDnet 공시 → Google News 폴백 |
| PRIVATE | DuckDuckGo + Google News |

**Yahoo Finance 429 대응**: 당일 첫 fetch 실패 시 캐시 없음 → 자동으로 DDG/Google News로 폴백.
다음 날 정상 실행 시 캐시 생성 후 안정화.

**소스 파일**:

| 파일 | 담당 소스 |
|------|---------|
| `naver.py` | Naver Search API (KRX 전용) |
| `naver_finance.py` | Naver Finance 메인 뉴스 (KRX 공통 배분) |
| `yahoo_finance.py` | Yahoo Finance RSS + 24h 파일 캐시 |
| `duckduckgo.py` | DuckDuckGo Search |
| `google_news.py` | Google News RSS (언어별: ko/en/zh/zh-TW/ja) |
| `hkex.py` | HKEX 공시 게시판 |
| `twse.py` | 대만 MOPS 공시 |
| `tse.py` | 일본 TDnet 공시 |
| `collector.py` | 위 소스들을 기업별로 조합·중복 제거 |
| `fetcher.py` (scraper) | BeautifulSoup 본문 추출 → Playwright 폴백 (고관련 기사 한정) |

---

### Phase C — 관련성 분석 & LLM 처리 (`src/llm/`)

2단계 필터로 비용과 속도를 최적화한다.

```
수집된 뉴스 전체
    │
    ▼
[1단계] 코사인 유사도 필터 (ChromaDB)
    • KRX 임계값: 0.75
    • 해외 임계값: 0.95
    │
    ├── 임계값 미달 → 제외
    │
    └── 통과
        ▼
    [2단계] LLM 근거 생성 (Ollama llama3.2)
        • "왜 내 볼트와 관련 있는가" 텍스트 생성
        │
        ▼
    [3단계] 종합 분석 합성 (curator)
        • 전체 뉴스 테마별 큐레이션 생성
        • Daily 노트 상단에 삽입
```

| 파일 | 역할 |
|------|------|
| `analyzer.py` | 벡터 유사도 필터 + LLM 근거 생성 (`AnalyzedItem` 반환) |
| `curator.py` | `synthesize()` — 종합 분석 텍스트 생성 (파일 쓰기 없음, writer에 위임) |

---

### 리서치 수집 (`src/research/`)

Daily 뉴스와 별개로 증권사 분석 리포트를 PDF로 수집해 Research 폴더에 저장한다.

| 파일 | 역할 |
|------|------|
| `naver_research.py` | KRX 기업 네이버 증권 리서치 PDF 수집 + LLM 요약 |
| `naver_industry.py` | 해외 기업 산업 분석 리포트 수집 |
| `register_pdf.py` | 로컬 PDF 수동 등록 (직접 지정 / 폴더 스캔 두 모드) |

---

### 볼트 구조 (`sample_vault/`)

38개 기업을 **거래소 지역별 하위폴더**로 관리한다.

```
sample_vault/
└── Companies/
    ├── KR/          삼성전자 · SK하이닉스 · 현대차 · LG에너지솔루션 · 포스코홀딩스
    ├── US/          Apple · NVIDIA · Microsoft · Alphabet · Google · Amazon
    │                Meta · Tesla · Broadcom · Micron · AMD · Intel
    │                ARM · ASML · Qualcomm · Super Micro · Berkshire Hathaway · Eli Lilly
    ├── CN/          Tencent · Alibaba · CATL · BYD · Xiaomi
    ├── TW/          TSMC · Delta Electronics · MediaTek · Nanya
    ├── JP/          SoftBank · Kioxia · Tokyo Electron
    └── Private/     OpenAI · Anthropic · SpaceX

    각 기업 폴더:
    ├── {기업명}.md    프로필 (자동 생성, 이후 덮어쓰지 않음)
    ├── Daily/         일일 뉴스 노트 — 배치 전용
    ├── Research/      증권사 리포트 요약 — 배치 전용
    └── Memos/         투자 메모 — 사용자 전용, 시스템 수정 불가
```

**Daily 노트 파일명 규칙**: `{날짜}{순서}.md` (예: `2026-05-14a.md`, `2026-05-14b.md`)
순서는 시간이 아닌 **실행 순서** 기준. 수동 실행 시 명시적으로 suffix 지정.

---

## 기업 레지스트리 (`companies.csv`)

38개사 등록. 컬럼: `name, region, ticker, exchange, sector, industry, active, keywords`

- `active: false` → 뉴스 수집 제외, 볼트 파일은 유지
- `keywords` → 뉴스 검색 쿼리에 추가 반영
- 기업 추가 시 CSV 편집 후 `python -m src.obsidian.company_manager --vault ./sample_vault` 실행

---

## 실행 스케줄

| 시간 | 배치 | 파일 suffix |
|------|------|-----------|
| 매일 07:00 | 1회차 (첫 실행) | `a` |
| 매일 18:00 | 2회차 (두 번째) | `b` |
| 수동 실행 | 필요 시 언제든 | 명시적 지정 |

macOS LaunchAgent (`com.boon.obs-news-update.plist`) 로 자동화.
로그: `logs/{날짜}{suffix}.log`, 30일 후 자동 삭제.

---

## 기술 스택

| 영역 | 선택 | 이유 |
|------|------|------|
| 임베딩 | `nomic-embed-text` (Ollama) | 로컬 무료, 한/영 모두 양호 |
| 벡터 DB | ChromaDB | 경량, 파일 기반 영구 저장 (`data/chroma/`) |
| LLM (분석) | `llama3.2` (Ollama) | 로컬 실행, API 비용 없음 |
| 본문 추출 | BeautifulSoup → Playwright 폴백 | 고관련 기사 전문 확보 |
| 뉴스 소스 | Naver API, DDG, Yahoo Finance, Google News RSS, HKEX/TWSE/TSE 공시 | 무료 공개 소스 |
| 스케줄러 | macOS LaunchAgent | 오전 7시 / 오후 6시 2회 실행 |
| 볼트 | Obsidian | 마크다운 기반, 로컬 저장 |
| 언어 | Python 3.13 | |

---

## 설계 원칙

- **증분 인덱싱**: `mtime + MD5`로 변경 파일만 재임베딩 → 볼트가 커져도 실행 시간 일정
- **2단계 필터**: 벡터 유사도 사전 필터 → 통과 기사만 LLM 처리 (비용·속도 절감)
- **비파괴 동기화**: 기존 프로필·메모 파일은 덮어쓰지 않음
- **부분 실패 허용**: 소스 하나 실패해도 전체 파이프라인 중단 없음
- **단일 경로 출처**: `company_dir()` 함수가 모든 파일 경로의 유일한 기준

---

## 현재 구현 상태

| 컴포넌트 | 파일 | 상태 |
|---------|------|------|
| 기업 레지스트리 | `companies.csv` (38개사) | 완료 |
| 볼트 동기화 | `src/obsidian/company_manager.py` | 완료 |
| 증분 인덱싱 | `src/obsidian/indexer.py` | 완료 |
| ChromaDB 임베딩 | `src/obsidian/embedder.py` | 완료 |
| 뉴스 수집 8종 | `src/sources/` | 완료 |
| 본문 추출 | `src/scraper/fetcher.py` | 완료 |
| 유사도 분석 + 근거 생성 | `src/llm/analyzer.py` | 완료 |
| 종합 분석 합성 | `src/llm/curator.py` | 완료 |
| Daily 노트 저장 | `src/obsidian/writer.py` | 완료 |
| KRX 리서치 PDF | `src/research/naver_research.py` | 완료 |
| 해외 리서치 PDF | `src/research/naver_industry.py` | 완료 |
| 로컬 PDF 수동 등록 | `src/research/register_pdf.py` | 완료 |
| 파이프라인 오케스트레이터 | `collect_news.py` | 완료 |
| 일일 배치 | `run_daily.sh` | 완료 |
| 볼트 마이그레이션 | `migrate_vault.py` | 완료 |
| 샘플 볼트 (38개사) | `sample_vault/` | 완료 |
| LaunchAgent (자동화) | `com.boon.obs-news-update.plist` | 완료 |
| **Commander Agent** | `src/commander/` | **미구현 (설계 완료)** |

총 코드: Python 3,461줄 + Shell 51줄

---

## 알려진 한계

| 항목 | 내용 |
|------|------|
| Yahoo Finance 429 | 당일 첫 실행 시 캐시 없어 해당 종목 뉴스 누락. 다음 날 자동 복구 |
| DuckDuckGo 불안정 | 타임아웃(20s) 또는 No results 시 조용히 건너뜀 |
| LLM 한국어 품질 | llama3.2 한국어 추론이 영어 대비 약함. Claude API로 교체 시 개선 가능 |
| 단일 머신 의존 | Mac이 꺼져 있으면 배치 누락 |
| ChromaDB 동시 실행 | 두 프로세스가 같은 DB 접근 시 충돌 가능. Graceful fallback 처리됨 |

---

## 로드맵

| 단계 | 내용 | 문서 |
|------|------|------|
| **현재** | 뉴스 수집 → 볼트 저장 자동화 | 이 문서 |
| **Phase 2** | Commander Agent — 시스템이 사용자에게 액션 지시 | `docs/commander-agent.md` |
| **Phase 3** | 포트폴리오 연동, 가격 이벤트 트리거 | 미정 |
| **Phase 4** | LLM 업그레이드 (Claude API 전면 전환) | 미정 |
