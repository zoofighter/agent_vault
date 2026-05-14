---
title: 섹터 테크니컬 다큐멘트 생성 에이전트 — 요건정의서
type: requirements
created: 2026-05-14
status: draft
related:
  - technical-report-concept.md
  - tech-report-implementation.md
  - sector-deep-analysis.md
---

# 섹터 테크니컬 다큐멘트 생성 에이전트 요건정의서

---

## 1. 목적

AgentVault의 TechReport(단편 번호 리포트)와 별개로,
섹터당 **전문 서적 수준**의 장기 참조 문서를 생성·유지한다.

| 구분 | TechReport | TechDoc (이번 시스템) |
|------|-----------|----------------------|
| 분량 | 1~3페이지 | 50~150페이지 수준 |
| 주기 | 이슈 발생 시 / 주간 | 섹터당 최초 1회 + 대형 변화 시 개정 |
| 목적 | 오늘의 뉴스 해석 | 섹터 완전 이해 (영구 참조) |
| 문체 | 메르 블로그 구어체 | 전문 기술 문서 (책 수준) |
| 독자 | 투자자 일반 | 심층 분석 수행자 (본인) |

---

## 2. 출력 문서 스펙

### 2-1. 형식

- Obsidian 마크다운 (`.md`)
- 저장 경로: `agent_vault/Docs/{섹터}/{섹터}_TechDoc_{YYYY-MM-DD}.md`
- 목차 기반 헤딩 구조 (`#`, `##`, `###`)
- Mermaid 다이어그램 포함 (공급망, 가치사슬, 기술 로드맵)
- 각 챕터 끝: 투자 시사점 요약 박스

### 2-2. 목표 분량

| 섹터 특성 | 챕터 수 | 예상 분량 |
|----------|---------|---------|
| AI / 반도체 (복잡) | 6~8개 | 80~120페이지 |
| 바이오 / 헬스케어 | 5~7개 | 70~100페이지 |
| 나머지 9개 섹터 | 4~6개 | 50~80페이지 |

### 2-3. 챕터 공통 구조

```
## {챕터명}

### 개요
### 핵심 기술 / 메커니즘
### 시장 구조와 플레이어
### 변화 동인 (Catalysts)
### 투자 시사점

> [!important] 이 챕터의 핵심
> - 핵심 포인트 1
> - 핵심 포인트 2
```

---

## 3. 에이전트 아키텍처

### 3-1. 전체 흐름

```
DocumentOrchestrator
        │
        ├─[1] ResearchAgent      ← 멀티소스 리서치 (병렬)
        │       ├─ NewsScout     ← 기존 Google News / TheElec / 전자신문
        │       ├─ AcademicScout ← arXiv / Semantic Scholar
        │       └─ DisclosureScout ← SEC EDGAR / DART / 기업 IR
        │
        ├─[2] OutlineAgent       ← 목차 초안 생성
        │       └─ [HITL]        ← Telegram으로 사용자 승인/수정
        │
        ├─[3] ChapterAgents      ← 챕터별 병렬 생성
        │       ├─ ChapterAgent(1)
        │       ├─ ChapterAgent(2)
        │       └─ ChapterAgent(N)
        │
        ├─[4] EditorAgent        ← 일관성 검토 + 교차 참조 연결
        │
        └─[5] PublisherAgent     ← vault 저장 + Telegram 완료 알림
```

### 3-2. 각 에이전트 역할

#### ResearchAgent
- 입력: 섹터명
- 동작: 멀티소스 동시 수집 (최대 50건)
- 출력: `ResearchPackage` (기사 목록 + 논문 요약 + 기업 공시 발췌)
- 병렬 실행: 3개 Scout를 `asyncio.gather()` 또는 `ThreadPoolExecutor`로 동시 실행

#### OutlineAgent
- 입력: 섹터명 + ResearchPackage 요약
- 동작: LLM으로 목차 초안 생성 (챕터 제목 + 각 챕터 2줄 설명)
- 출력: YAML 구조의 `Outline` 객체

```yaml
# Outline 예시
sector: 반도체
chapters:
  - id: 1
    title: "반도체 산업의 구조 이해"
    sections: ["반도체란", "가치사슬", "주요 플레이어"]
    focus: "공급망 전체 그림"
  - id: 2
    title: "선단 공정 기술"
    sections: ["EUV 리소그래피", "GAA vs FinFET", "3nm/2nm 경쟁"]
    focus: "TSMC vs 삼성 기술 격차"
  ...
```

#### HITL (Human-in-the-Loop) 목차 승인
→ 별도 섹션 [4] 상세 기술

#### ChapterAgent
- 입력: 챕터 메타(제목/섹션) + ResearchPackage + 전체 Outline 컨텍스트
- 동작:
  1. 리서치 자료에서 챕터 관련 내용 추출
  2. LLM 1차 초안 생성
  3. LLM 자기 검토 ("이 챕터에 빠진 내용은?")
  4. 보완 후 최종 마크다운 출력
- LLM: **Claude API** (claude-sonnet-4-6) — 책 수준 품질 필요
- 출력: 챕터 마크다운 문자열

#### EditorAgent
- 입력: 전체 챕터 목록
- 동작:
  1. 챕터 간 용어 통일 확인 (예: "패키징(CoWoS)" 표기 일관성)
  2. 교차 참조 자동 삽입 (`[[챕터명]]` Obsidian 링크)
  3. 전체 목차 + 색인 생성
- LLM: Groq (가벼운 편집 작업)

#### PublisherAgent
- vault 저장
- 목차 파일 업데이트 (`agent_vault/Docs/INDEX.md`)
- Telegram 완료 알림 (문서 경로 + 챕터 수 + 총 분량)

---

## 4. HITL 목차 승인 설계

### 4-1. 흐름

```
OutlineAgent → 목차 초안 생성
     │
     ▼
Telegram 전송:
  "[반도체] 목차 초안입니다. 수정 후 /approve 로 승인해주세요."
  1. 반도체 산업의 구조 이해
  2. 선단 공정 기술 (EUV, GAA)
  3. HBM과 차세대 메모리
  ...
     │
     ▼
사용자 응답 대기 (타임아웃: 24시간)
     │
     ├─ /approve                 → 원안 그대로 챕터 생성 시작
     ├─ /edit "3번 삭제, 7번 추가: 지정학 리스크" → 수정 후 재전송
     ├─ /regen                   → 목차 재생성 (다른 각도로)
     └─ 타임아웃                  → 원안으로 자동 진행 (선택 설정)
```

### 4-2. Telegram 명령 확장 (run_telegram_bot.py)

| 명령 | 동작 |
|------|------|
| `/approve` | 현재 대기 중인 목차 승인 → 생성 시작 |
| `/edit {내용}` | 목차 수정 지시 → OutlineAgent 재실행 |
| `/regen` | 목차 완전 재생성 |
| `/status` | 현재 문서 생성 진행 상황 |
| `/abort` | 현재 생성 중단 |

### 4-3. 대기 메커니즘

```python
# 비동기 HITL 대기 패턴
class HitlApprovalGate:
    def __init__(self, session_id: str, timeout_hours: int = 24):
        self.session_id = session_id
        self.timeout = timeout_hours * 3600
        self._event = asyncio.Event()  # Telegram 봇이 set()
        self._result: str = "timeout"  # "approved" | "edited:{내용}" | "timeout"

    async def wait(self) -> str:
        try:
            await asyncio.wait_for(self._event.wait(), self.timeout)
        except asyncio.TimeoutError:
            self._result = "timeout"
        return self._result
```

---

## 5. LLM 전략

| 단계 | 모델 | 이유 |
|------|------|------|
| ResearchAgent 요약 | Groq `llama-3.3-70b` | 빠른 처리, 저비용 |
| OutlineAgent 목차 생성 | Groq `llama-3.3-70b` | 구조화 작업, JSON 출력 |
| ChapterAgent 본문 생성 | **Claude API** `claude-sonnet-4-6` | 책 수준 품질 필수 |
| EditorAgent 교정 | Groq `llama-3.3-70b` | 반복 편집 작업 |

**왜 Claude인가:**
- 한 챕터당 3,000~8,000 토큰 출력 필요
- 전문 기술 문서 일관성, 논리 흐름, 한국어 품질 모두 요구
- Groq llama-3.3-70b는 긴 문서에서 반복·품질 저하 발생

**비용 추산 (claude-sonnet-4-6):**
- 챕터당 평균 8,000 토큰 출력 × 6챕터 = 48,000 토큰
- 섹터당 ≈ $0.10~0.20 (input 포함)
- 11개 섹터 전체 ≈ $1.5~2.5

---

## 6. 데이터 소스 전략

### 6-1. 섹터별 소스 우선순위

| 섹터 | 1순위 | 2순위 | 3순위 |
|------|------|------|------|
| AI / 반도체 | arXiv + Semantic Scholar | Google News | SEC EDGAR (NVIDIA/TSMC) |
| 바이오 | PubMed + ClinicalTrials.gov | Google News | SEC EDGAR (파이프라인) |
| 2차전지 | arXiv (소재과학) + IEA API | 전자신문 RSS | DART (한국 기업) |
| 에너지 | IEA API | Google News | SEC EDGAR |
| 나머지 | Google News + 전자신문 RSS | arXiv | DART / SEC |

### 6-2. 리서치 깊이 목표

- 소스 수: 섹터당 30~80건 (현재 TechReport는 5~20건)
- 기간: 최근 2년 (주간 리포트의 7일 대비)
- 논문: 상위 인용 논문 10~20편 요약 포함

---

## 7. 구현 단계

| Phase | 내용 | 우선순위 |
|-------|------|---------|
| **A** | CLI 수동 실행 — `python run_docgen.py --sector 반도체` | 1순위 |
| **B** | HITL Telegram 목차 승인 루프 | 2순위 |
| **C** | ChapterAgent 병렬 생성 (asyncio) | 3순위 |
| **D** | EditorAgent + 교차 참조 | 4순위 |
| **E** | 문서 개정판 생성 (기존 문서 비교 + 변경 섹션만 재생성) | 5순위 |

**Phase A만으로도 핵심 가치 달성 가능.** B~E는 점진적 자동화.

---

## 8. 파일 구조 (신규)

```
run_docgen.py                      CLI 진입점
src/docgen/
    __init__.py
    orchestrator.py                DocumentOrchestrator 메인 루프
    research.py                    ResearchAgent (멀티소스 수집)
    outline.py                     OutlineAgent (목차 생성 + HITL)
    chapter.py                     ChapterAgent (Claude API 본문 생성)
    editor.py                      EditorAgent (일관성 교정)
    publisher.py                   vault 저장 + 알림
    hitl.py                        HITL 게이트 (Telegram 승인 대기)
    models.py                      ResearchPackage, Outline, Chapter 데이터클래스

agent_vault/Docs/
    INDEX.md                       전체 문서 목록
    반도체/
        반도체_TechDoc_2026-05-14.md
    AI/
        AI_TechDoc_2026-05-14.md
    ...
```

---

## 9. CLI 사용법 (Phase A 기준)

```bash
# 반도체 전체 문서 생성 (목차 자동, HITL 없음)
python run_docgen.py --sector 반도체 --vault ./agent_vault

# HITL 목차 승인 포함
python run_docgen.py --sector AI --vault ./agent_vault --hitl

# 특정 챕터만 재생성
python run_docgen.py --sector 반도체 --vault ./agent_vault --chapter 3

# 기존 문서 개정 (변경 섹션만)
python run_docgen.py --sector 반도체 --vault ./agent_vault --revise

# 목차만 생성 후 중단 (검토용)
python run_docgen.py --sector 바이오 --vault ./agent_vault --outline-only
```

---

## 10. 미결 사항

- [ ] Claude API 키 `.env` 추가 필요 (`ANTHROPIC_API_KEY`)
- [ ] HITL 승인 후 챕터 생성 시작 — 동기/비동기 방식 결정 (Telegram 봇 재활용 vs 별도 프로세스)
- [ ] 챕터 병렬 생성 시 API 레이트리밋 처리 (Claude: 분당 요청 수 제한)
- [ ] 문서 개정판 전략 — 전체 재생성 vs 변경 챕터만 재생성
- [ ] 다이어그램 자동 생성 — Mermaid 코드 LLM 생성 vs 수동 삽입

---

## 관련 문서

- [technical-report-concept.md](technical-report-concept.md) — 단편 리포트 개념
- [tech-report-implementation.md](tech-report-implementation.md) — Phase 1 구현
- [sector-deep-analysis.md](sector-deep-analysis.md) — 11개 섹터 심층 분석
- [sector-sources-accessible.md](sector-sources-accessible.md) — 데이터 소스 목록
- [sector-data-sources.md](sector-data-sources.md) — 학술 소스 상세
