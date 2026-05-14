---
title: AgentVault — 에이전트 구조 개요
type: intro-doc
audience: 외부 설명용
created: 2026-05-14
---

# AgentVault

> 여러 AI 에이전트가 협력하여 매일 나 대신 뉴스를 읽고, 내 관심사에 맞는 것만 골라 Obsidian에 정리하고, 중요한 것은 나에게 직접 지시를 내리는 개인 투자 인텔리전스 시스템

---

## 한 줄로 설명하면

"내가 직접 뉴스를 찾아보는 게 아니라, 시스템이 내 리서치 노트를 읽고 무엇이 중요한지 판단해서 나에게 가져다준다."

---

## 일반 뉴스 알림과의 차이

| | 일반 뉴스 알림 | AgentVault |
|--|--------------|-----------|
| 필터 기준 | 키워드 ("삼성전자") | **내가 쓴 리서치 노트** |
| 결과 | 삼성전자 관련 기사 전부 | HBM·메모리 공정 기사만 선별 |
| 시간이 지나면 | 그대로 | 볼트가 쌓일수록 필터가 정교해짐 |
| 사용자 역할 | 매일 직접 읽고 판단 | 시스템이 판단, 중요한 것만 보고받음 |

HBM 경쟁력 분석을 써둔 사람에게는 HBM 뉴스가 높은 점수로 선별된다.
같은 삼성전자 기사라도 노사 갈등 기사는 낮게, 메모리 공정 기사는 높게 잡힌다.

---

## 전체 구조: 5개 에이전트의 협업

```
        [나의 Obsidian 볼트]
               │
               ▼
    ┌─── Memory Agent ───┐        매일 07:00 / 18:00 자동 실행
    │  내 노트를 읽고 기억  │
    └────────┬───────────┘
             │ (내 관심사 벡터화)
             ▼
    ┌─── Scout Agent ────┐
    │  8개 소스에서 뉴스   │        KRX · NASDAQ · HKEX · TSE 등
    │  매일 수집          │        38개 기업 × 평균 45건
    └────────┬───────────┘
             │ (수집된 뉴스 전체)
             ▼
    ┌─── Filter Agent ───┐
    │  내 노트와 유사한    │        유사도 낮은 기사는 제거
    │  뉴스만 선별        │        "왜 관련 있는가" 근거 생성
    └────────┬───────────┘
             │ (관련 뉴스만)
             ▼
    ┌─── Analyst Agent ──┐
    │  선별된 뉴스를 종합  │        로컬 LLM (Ollama llama3.2)
    │  분석·큐레이션      │        테마별 인사이트 생성
    └────────┬───────────┘
             │ (분석 완료)
             ▼
    ┌─── Scribe Agent ───┐
    │  Obsidian에 노트    │        Daily/2026-05-14a.md
    │  자동 저장          │        종합분석 + 뉴스목록 단일 파일
    └────────────────────┘

    (예정)
    ┌─── Commander Agent ┐
    │  중요한 것만 골라   │        Telegram 푸시
    │  나에게 직접 지시   │        "이거 봐라", "이거 분석해라"
    └────────────────────┘
```

---

## 에이전트별 역할 상세

### Agent 1 — Memory Agent (기억 에이전트)

**역할**: 내가 Obsidian에 쓴 글을 읽고, AI가 이해할 수 있는 형태(벡터)로 변환해 저장한다.

- 볼트 전체를 스캔하되 **변경된 파일만** 다시 처리 (시간 절약)
- 파일 수정 시각 + MD5 해시로 변경 여부 판단
- 결과물: ChromaDB (로컬 벡터 데이터베이스)

이 에이전트 덕분에 "나의 관심사"가 수치로 표현되고, 다른 에이전트들이 그 수치를 필터로 사용한다.

---

### Agent 2 — Scout Agent (정찰 에이전트)

**역할**: 매일 8개 뉴스 소스를 돌며 38개 기업의 뉴스를 수집한다.

| 지역 | 소스 |
|------|------|
| 한국 (KRX) | Naver 뉴스 API, Naver Finance, DuckDuckGo |
| 미국 (NASDAQ/NYSE) | Yahoo Finance RSS, DuckDuckGo, Google News |
| 홍콩 (HKEX) | Yahoo Finance, HKEX 공시, Google News |
| 대만 (TWSE) | Yahoo Finance, MOPS 공시, Google News |
| 일본 (TSE) | Yahoo Finance, TDnet 공시, Google News |
| 비상장 (Private) | DuckDuckGo, Google News |

하루 수집량: 38개사 × 평균 45건 = 약 1,700건
중복 제거 및 소스 장애 시 자동 폴백 처리.

---

### Agent 3 — Filter Agent (필터 에이전트)

**역할**: 수집된 뉴스 1,700건 중 내 볼트와 실제로 관련 있는 것만 남긴다.

**2단계 필터**로 속도와 비용을 최적화한다:

```
1단계 — 수학적 필터 (빠름, 무료)
  수집 뉴스 1,700건
       ↓
  내 볼트 벡터와 코사인 유사도 계산
  임계값 미달 → 제거
       ↓
  통과 뉴스 (훨씬 적음)

2단계 — LLM 필터 (정확, 유료 자원 사용)
  통과 뉴스에만 LLM 적용
  "왜 내 볼트와 관련 있는가?" 근거 텍스트 생성
```

LLM을 모든 뉴스에 적용하지 않기 때문에 비용과 시간이 절감된다.

---

### Agent 4 — Analyst Agent (분석 에이전트)

**역할**: 선별된 뉴스들을 종합해 오늘의 핵심 테마와 인사이트를 생성한다.

- 개별 뉴스의 근거를 모아 큰 그림을 그림
- "오늘 반도체 섹터에서 무슨 일이 있었는가" 수준의 종합 분석
- 로컬 LLM(Ollama)으로 실행 — API 비용 없음

---

### Agent 5 — Scribe Agent (기록 에이전트)

**역할**: 분석 결과를 Obsidian 노트 형식으로 저장한다.

파일 위치: `볼트/Companies/{지역}/{기업}/Daily/2026-05-14a.md`

```
파일 구조:
┌─────────────────────────────┐
│  ## 종합 분석               │  ← Analyst Agent 결과
│  오늘 HBM4 관련 뉴스가...   │
│  ─────────────────────────  │
│  ## 뉴스 목록 (42건)        │  ← Filter Agent 통과 목록
│  ### 1. SK하이닉스 HBM4...  │     각 뉴스에 근거 포함
│  ### 2. 삼성전자 메모리...   │
│  ...                        │
└─────────────────────────────┘
```

하루 2회 실행 (07:00 = `a`, 18:00 = `b`), 수동 실행 시 순서 자동 감지.

---

### Agent 6 — Research Agent (리서치 에이전트)

**역할**: 뉴스와 별개로 증권사 분석 리포트(PDF)를 자동 수집·요약한다.

- 네이버 증권에서 KRX 기업 리포트 PDF 자동 다운로드
- 해외 기업 산업 분석 리포트 수집
- LLM으로 핵심 내용 요약 후 `Research/` 폴더에 저장
- 로컬 PDF 수동 등록 지원 (Downloads 폴더 스캔 모드)

---

### Agent 7 — Commander Agent (지휘 에이전트) — 개발 예정

**역할**: 위 에이전트들의 결과를 감시하다가 중요한 것을 발견하면 나에게 직접 지시를 내린다.

지금까지의 에이전트들은 모두 **수집·저장** 역할이다.
Commander는 반대로 **판단·지시** 역할이다.

```
Scribe가 저장한 Daily 노트들
          ↓
  Commander가 패턴 감지
          ↓
  [Telegram] "삼성전자 HBM4 관련 기사 7건 집중.
              심층 분석 권장 — Claude에게 이렇게 물어봐:"
              → "HBM4 공급 확보가 엔비디아 GB300 로드맵에 미치는 영향은?"
```

사용하는 LLM:
- **로컬 LLM**: 빠른 1차 스크리닝 (비용 없음)
- **Cloud LLM (Claude API)**: 고품질 분석 명령 텍스트 생성 (중요 항목에만 적용)

---

## 볼트 구조

38개 기업을 지역별로 분류해 관리한다.

```
볼트/
└── Companies/
    ├── KR/       삼성전자 · SK하이닉스 · 현대차 · LG에너지솔루션 · 포스코홀딩스
    ├── US/       Apple · NVIDIA · Microsoft · Alphabet · Google · Amazon · Meta
    │             Tesla · Broadcom · Micron · AMD · Intel · ARM · ASML 외
    ├── CN/       Tencent · Alibaba · CATL · BYD · Xiaomi
    ├── TW/       TSMC · MediaTek · Delta Electronics · Nanya
    ├── JP/       SoftBank · Kioxia · Tokyo Electron
    └── Private/  OpenAI · Anthropic · SpaceX

    각 기업 폴더:
    ├── {기업명}.md    프로필 — 시스템 자동 생성
    ├── Daily/         일일 뉴스 노트 — 시스템 전용
    ├── Research/      증권사 리포트 요약 — 시스템 전용
    └── Memos/         투자 메모 — 나만 사용, 시스템 수정 불가
```

---

## 기술 스택

| 역할 | 기술 | 특징 |
|------|------|------|
| 에이전트 언어 | Python 3.13 | |
| 기억 저장소 | ChromaDB | 로컬 파일 기반, 영구 저장 |
| 임베딩 모델 | nomic-embed-text (Ollama) | 로컬 실행, 한/영 모두 지원 |
| 분석 LLM | llama3.2 (Ollama) | 로컬 실행, API 비용 없음 |
| 지시 LLM (예정) | Claude API | 고품질 한국어 분석 |
| 볼트 | Obsidian | 마크다운, 로컬 저장 |
| 자동화 | macOS LaunchAgent | 매일 07:00 / 18:00 |

**설계 원칙**: 일상 운영 비용 0원. 로컬 LLM만 사용.
Commander Agent 도입 시 중요 항목에만 Claude API 사용 (비용 최소화).

---

## 자동화 흐름 (매일)

```
07:00 LaunchAgent 자동 실행
    │
    ├── Memory Agent    볼트 변경 파일 재학습
    │
    ├── Scout Agent     38개 기업 뉴스 수집
    │
    ├── Filter Agent    관련 뉴스 선별 + 근거 생성
    │
    ├── Analyst Agent   종합 분석 작성
    │
    ├── Scribe Agent    Daily 노트 저장 (a)
    │
    ├── Research Agent  KRX 리서치 PDF 수집
    │
    └── Research Agent  해외 리서치 PDF 수집

18:00 동일 흐름 반복 (b)
```

---

## 현재 구현 상태

| 에이전트 | 상태 |
|---------|------|
| Memory Agent (볼트 인덱싱) | 완료 |
| Scout Agent (뉴스 수집 8종) | 완료 |
| Filter Agent (유사도 분석 + 근거 생성) | 완료 |
| Analyst Agent (종합 분석) | 완료 |
| Scribe Agent (Daily 노트 저장) | 완료 |
| Research Agent (PDF 수집·요약) | 완료 |
| 자동화 (LaunchAgent) | 완료 |
| **Commander Agent** | **설계 완료, 구현 예정** |

총 코드: Python 3,461줄 + Shell 51줄 / 추적 기업 38개사

---

## 로드맵

| 단계 | 내용 |
|------|------|
| **현재 (v1)** | 6개 에이전트 자동 운영, 매일 38개사 Daily 노트 생성 |
| **v2** | Commander Agent — 중요 신호 Telegram 푸시, 분석 지시 |
| **v3** | 포트폴리오 연동 — 보유 비중에 따라 우선순위 가중치 |
| **v4** | Cloud LLM 전환 — Claude API로 분석 품질 향상 |
