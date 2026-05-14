---
title: 주식투자용 테크니컬 리포트 — 요건정의서
type: requirements
created: 2026-05-14
status: draft
reference: https://blog.naver.com/ranto28
---

# 주식투자용 테크니컬 리포트 요건정의서

> 참조 모델: 메르의 블로그 (blog.naver.com/ranto28)
> 일 방문자 10만 명의 파워 경제 블로거. 복잡한 산업 구조를 번호 기반 스텝으로 해체하고,
> 기술적 사실에서 투자 시사점까지 연결하는 스타일.

---

## 1. 목적

**현재 시스템의 한계:**
AgentVault는 기업별 뉴스를 수집하고 "오늘 ASML 뉴스가 많다"를 알려준다.
하지만 "EUV 장비 수요가 왜 지금 중요한지", "HBM 공정에서 TSV 본딩 기술이 뭔지"같은
**배경 지식 없이는 뉴스의 의미를 제대로 해석할 수 없다.**

**목표:**
7개 섹터 각각에 대해 메르 스타일의 기술적 배경 리포트를 주기적으로 생성.
뉴스를 읽기 전에 먼저 알아야 할 구조적 지식을 제공.

---

## 2. 대상 섹터

| 섹터 | 핵심 관심사 | 주요 추적 기업 |
|------|------------|--------------|
| **AI** | LLM 인프라, 에이전트, 데이터센터 | NVIDIA, OpenAI, Anthropic, Microsoft, Google |
| **반도체** | 공정 기술, 장비, 패키징, 지정학 | TSMC, ASML, 삼성전자, SK하이닉스, Intel |
| **바이오** | 신약 파이프라인, 임상 단계, 플랫폼 기술 | Eli Lilly, 코오롱티슈진 |
| **헬스케어** | 의료기기, 디지털 헬스, 보험 | Berkshire Hathaway |
| **디스플레이** | OLED, MicroLED, QD 기술 | Samsung, LG |
| **2차전지** | 양극재, 음극재, 전해질, 셀 공정 | CATL, BYD, LG에너지솔루션, 포스코홀딩스 |
| **자동차** | 전동화, 자율주행, SDV, 수소 | 현대차, Tesla, BYD, Xiaomi |

---

## 3. 참조 모델 분석 — 메르 글쓰기 패턴

### 구조적 특징

```
[트리거] 최근 뉴스·데이터 포인트 1개 (후킹)
    ↓
[기술 해부] 번호 기반 스텝 (1. 2. 3. ...)
    - 배경 개념 설명 (중학생도 이해 가능한 수준)
    - 기술/산업 구조 상세
    - 핵심 플레이어와 역할 관계
    ↓
[변화 포인트] 지금 무엇이 달라지고 있는가
    - 수급 변화, 기술 전환, 규제 이슈
    ↓
[투자 시사점] 그래서 어떤 기업이 수혜/피해인가
    - 구체적 기업명 + 이유
    ↓
[A/S] 상황 변화 시 업데이트 (선택)
```

### 문체 특징

- 번호 매기기: `1. 2. 3.` 순차 전개 — 논리 흐름 추적 쉬움
- 짧은 문장: 한 번호에 한 문장 원칙
- 구어체: "~임", "~함", "~인 것임"
- 비유 사용: 어려운 개념을 일상 사례로 설명
- "A/S" 방식: 과거 글을 업데이트하며 연속성 유지

### 예시 구조 (메르 스타일 적용)

```
[트리거] 카자흐스탄 우라늄 공급 감산

1. 세계 최대 우라늄 생산국은 카자흐스탄임.
2. 국영기업 Kazatomprom이 전세계의 40%를 생산 중임.
3. 2026년 생산목표를 8,500만 파운드 → 7,700만 파운드로 하향함.
4. 추가 감산 시 6,200만 파운드까지 가능한 상황임.
...
투자 시사점: 우라늄 현물 가격 상승 → 한국 관련주 △△△ 수혜 예상
```

---

## 4. 리포트 종류

### 4-1. 섹터 기초 리포트 (온보딩용)
- **주기**: 섹터당 1회 생성 (신규 등록 시)
- **분량**: 20~30개 번호 포인트
- **내용**: 해당 섹터의 공급망 구조, 핵심 용어, 주요 플레이어 관계도
- **예시**: "HBM을 이해하려면 먼저 이것부터 — 메모리 계층 구조와 AI 수요"

### 4-2. 이슈 심층 리포트 (트리거 기반)
- **주기**: 섹터 관련 중요 뉴스 감지 시 자동 생성
- **분량**: 10~15개 번호 포인트
- **내용**: 특정 이슈의 기술적 배경 + 투자 임팩트
- **예시**: "TSMC CoWoS 캐파 부족이 투자에 미치는 의미"

### 4-3. 주간 섹터 업데이트 (정기 A/S)
- **주기**: 섹터당 주 1회
- **분량**: 5~8개 번호 포인트
- **내용**: 지난 주 주요 변화 + 다음 주 주목 포인트
- **예시**: "이번 주 반도체 섹터 변화 — 삼성 18A 수율 이슈 후속"

---

## 5. 지식 소스 (섹터별)

| 섹터 | 1차 소스 | 2차 소스 |
|------|---------|---------|
| AI | arXiv cs.LG, OpenAI blog, Anthropic blog | TechCrunch, The Verge |
| 반도체 | IEDM/ISSCC 논문, TSMC/삼성 IR, SemiAnalysis | IEEE Spectrum, AnandTech |
| 바이오 | PubMed, ClinicalTrials.gov, FDA 공시 | BioPharma Dive, STAT News |
| 헬스케어 | CMS 정책, WHO 보고서 | FierceHealthcare |
| 디스플레이 | DSCC 리포트, SID 학회 | Display Daily |
| 2차전지 | SNE Research, BloombergNEF, CATL IR | Benchmark Minerals |
| 자동차 | IEA EV Outlook, 각사 IR, ADAS 특허 | Electrek, InsideEVs |

---

## 6. 시스템 요건

### 6-1. 입력 (Input)

| 입력 | 설명 |
|------|------|
| 섹터 지정 | 7개 중 1개 (또는 전체) |
| 트리거 타입 | `onboarding` / `issue` / `weekly` |
| 이슈 키워드 | 심층 리포트 생성 시 (예: "CoWoS 캐파") |
| 볼트 컨텍스트 | 사용자의 현재 지식 수준 (ChromaDB 조회) |

### 6-2. 출력 (Output)

| 출력 | 포맷 | 저장 위치 |
|------|------|----------|
| 리포트 본문 | 메르 스타일 번호 마크다운 | `agent_vault/Reports/{섹터}/{날짜}.md` |
| Telegram 알림 | 핵심 3줄 + 전체 링크 | Telegram 봇 |
| Digest 기록 | `[!info]` callout | `Digest/{날짜}.md` |

### 6-3. 품질 기준

- **가독성**: 번호 포인트 15개 이하 (한 화면에 읽기 가능)
- **언어**: 한국어 전용, 영문 용어는 괄호 병기 (예: 패키징(CoWoS))
- **정확성**: 출처 URL 포함 의무화
- **투자 연결**: 마지막에 반드시 "투자 시사점" 섹션

---

## 7. LangGraph 연동 설계

이 리포트 시스템은 [langgraph-knowledge-agent.md](langgraph-knowledge-agent.md)의 Knowledge Agent 위에 구현된다.

```
TechReportAgent (신규)
    │
    ├─▶ SectorContextNode   ← 볼트에서 해당 섹터 기존 지식 조회
    ├─▶ SourceScoutNode     ← 섹터별 소스 크롤링 (arXiv, IR, 논문)
    ├─▶ GapAnalyzerNode     ← 사용자 지식 공백 식별
    ├─▶ ReportWriterNode    ← 메르 스타일 번호 리포트 생성 (Groq/Claude)
    ├─▶ FactCheckerNode     ← 주요 수치/사실 검증 (선택)
    └─▶ DeliveryNode        ← vault 저장 + Telegram 전송
```

### 트리거 연동

```python
# Commander가 특정 섹터 테마 급등 감지 시 자동 트리거
if theme_surge detected in ["HBM", "CoWoS", "GLP-1", ...]:
    TechReportAgent.run(sector=맵핑[theme], type="issue", keyword=theme)
```

---

## 8. 구현 우선순위

| 단계 | 내용 | 난이도 |
|------|------|--------|
| **Phase 1** | 수동 트리거 — CLI로 섹터 지정 시 리포트 생성 | 낮음 |
| **Phase 2** | Commander 테마 급등 감지 시 자동 트리거 | 중간 |
| **Phase 3** | 주간 스케줄 자동화 + A/S 업데이트 | 중간 |
| **Phase 4** | LangGraph 풀 에이전트 통합 | 높음 |

Phase 1부터 단계적으로 구현. 핵심 가치는 리포트 품질이지 자동화 수준이 아님.

---

## 9. 미결 사항

- [ ] 섹터별 소스 크롤링 권한/접근 가능 여부 확인 (arXiv는 자유, DSCC 등 유료 소스 대안)
- [ ] 기초 리포트 생성에 Claude API vs Groq 선택 (긴 문서 생성 품질 차이)
- [ ] Reports 폴더를 볼트 내 어디에 위치시킬지 (Companies 외부 vs 내부)
- [ ] 기존 Research/ 폴더와의 구분 (증권사 PDF vs 자체 생성 리포트)

---

## 관련 문서

- [langgraph-knowledge-agent.md](langgraph-knowledge-agent.md) — Knowledge Agent 전체 설계
- [system-overview.md](system-overview.md) — AgentVault 전체 구조
- [commander-telegram-flow.md](commander-telegram-flow.md) — 테마 급등 → 자동 트리거 연결점
