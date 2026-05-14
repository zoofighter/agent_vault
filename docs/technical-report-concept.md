---
title: 테크니컬 리포트 시스템 — 개념 및 배경
type: concept-doc
created: 2026-05-14
related:
  - technical-report-requirements.md
  - langgraph-knowledge-agent.md
---

# 테크니컬 리포트 시스템 — 개념 및 배경

---

## 왜 만드는가

현재 AgentVault는 기업별 뉴스를 수집·필터링해서 "오늘 ASML 뉴스가 많다"를 알려준다.
그런데 **뉴스를 제대로 해석하려면 기술적 배경 지식이 먼저 있어야 한다.**

- "TSMC CoWoS 캐파 부족" — CoWoS가 뭔지 모르면 임팩트를 가늠할 수 없다
- "카자흐스탄 우라늄 감산" — 공급망 구조를 모르면 어느 기업이 영향받는지 모른다
- "GLP-1 시장 경쟁 심화" — 약물 메커니즘과 파이프라인 구조를 알아야 수혜주를 찾는다

뉴스보다 먼저, **섹터 구조와 핵심 기술을 이해하는 것**이 더 중요하다.

---

## 참조 모델 — 메르의 블로그 (blog.naver.com/ranto28)

### 누구인가

- 필명 "메르(Mer)" — 경제 파워 블로거
- 매일 10만 명 이상 방문, 여의도 증권가 애널리스트·PB들이 정독
- 연합뉴스 인터뷰: "여의도가 매일 기다리는 남자"

### 글쓰기 방식

번호 기반 스텝 전개가 핵심이다.

```
1. 세계 최대 우라늄 생산국은 카자흐스탄임.
2. 국영기업 Kazatomprom이 전세계의 40%를 생산 중임.
3. 2026년 생산목표를 8,500만 파운드 → 7,700만 파운드로 하향함.
4. 추가 감산 시 6,200만 파운드까지 가능한 상황임.
...
투자 시사점: 우라늄 현물 가격 상승 → 관련주 수혜 예상
```

### 패턴 구조

```
[트리거]      최근 뉴스·데이터 포인트 1개 (후킹)
    ↓
[기술 해부]   번호 기반 스텝 (배경 → 구조 → 플레이어 관계)
    ↓
[변화 포인트] 지금 무엇이 달라지고 있는가
    ↓
[투자 시사점] 어떤 기업이 수혜/피해인가
    ↓
[A/S]         상황 변화 시 업데이트 포스팅
```

### 문체 특징

- 짧은 문장, 한 번호에 한 사실
- "~임", "~함", "~인 것임" 구어체
- 어려운 개념을 일상 비유로 설명
- 과거 글을 A/S(업데이트)하며 지식을 쌓아나감

---

## 대상 7개 섹터

| 섹터 | 핵심 질문 |
|------|-----------|
| **AI** | 어떤 인프라가 AI를 돌리는가, 병목은 어디인가 |
| **반도체** | 공정·장비·패키징 구조, 지정학 리스크 |
| **바이오** | 신약 개발 단계, 플랫폼 기술, 임상 구조 |
| **헬스케어** | 의료기기, 디지털 헬스, 보험·수가 구조 |
| **디스플레이** | OLED·MicroLED·QD 기술 경쟁 구도 |
| **2차전지** | 양극재·음극재·전해질 소재, 셀 공정, 수급 |
| **자동차** | 전동화, 자율주행(ADAS/FSD), SDV, 수소 |

---

## 리포트 3종

### 1. 섹터 기초 리포트
- 섹터를 처음 공부할 때 읽는 입문서
- 공급망 구조, 핵심 용어, 주요 플레이어 관계도
- 20~30개 번호 포인트

### 2. 이슈 심층 리포트
- 특정 이슈 발생 시 자동 생성 (Commander 테마 급등 연동)
- 기술적 배경 + 투자 임팩트
- 10~15개 번호 포인트

### 3. 주간 A/S
- 주 1회, 지난 주 변화 + 다음 주 주목 포인트
- 5~8개 번호 포인트

---

## AgentVault 시스템 내 위치

```
현재 시스템
────────────
뉴스 수집 → 유사도 필터 → Daily 노트 → Commander → Telegram

추가되는 레이어
──────────────
섹터 이슈 감지 (Commander)
    └─▶ TechReportAgent
            ├─▶ 소스 탐색 (arXiv, IR, 논문, 전문 블로그)
            ├─▶ 메르 스타일 리포트 생성 (LLM)
            ├─▶ vault 저장 (Reports/{섹터}/{날짜}.md)
            └─▶ Telegram 전송 ("이걸 먼저 읽어야 오늘 뉴스가 보입니다")
```

뉴스 → 지식 순서가 아니라, **지식 → 뉴스 해석** 순서로 전환.

---

## LangGraph 연동 방향

[langgraph-knowledge-agent.md](langgraph-knowledge-agent.md)의 Knowledge Agent 그래프에서
`TechScout` + `Synthesizer` 노드 조합으로 구현된다.

트리거 연결:

```python
# Commander가 테마 급등 감지 시
if "HBM" in theme_surge:
    → TechReportAgent(sector="반도체", keyword="HBM")

if "GLP-1" in theme_surge:
    → TechReportAgent(sector="바이오", keyword="GLP-1")
```

---

## 구현 단계

| Phase | 내용 | 상태 |
|-------|------|------|
| 1 | CLI 수동 트리거 — `python run_tech_report.py --sector 반도체 --topic CoWoS` | 미착수 |
| 2 | Commander 테마 급등 → 자동 트리거 | 미착수 |
| 3 | 주간 자동 스케줄 | 미착수 |
| 4 | LangGraph 풀 에이전트 통합 | 미착수 |

---

## 관련 문서

- [technical-report-requirements.md](technical-report-requirements.md) — 상세 요건정의서
- [langgraph-knowledge-agent.md](langgraph-knowledge-agent.md) — LangGraph 설계
- [proactive-telegram.md](proactive-telegram.md) — Telegram 전송 설계
