---
title: TechReportAgent Phase 1 — 구현 상세
type: system-doc
created: 2026-05-14
related:
  - technical-report-concept.md
  - technical-report-requirements.md
---

# TechReportAgent Phase 1 — 구현 상세

---

## 개요

섹터 키워드를 입력받아 뉴스를 수집하고, LLM이 메르 스타일 번호 리포트를 생성해서
볼트에 저장하고 Telegram으로 전송하는 CLI 도구.

```bash
python run_tech_report.py --sector 반도체 --topic CoWoS --vault ./agent_vault
```

---

## 사용 LLM

| 구분 | 모델 | 용도 |
|------|------|------|
| **리포트 생성** | `llama-3.3-70b-versatile` (Groq Cloud) | 메르 스타일 번호 리포트 전문 생성 |

- Groq API 엔드포인트: `https://api.groq.com/openai/v1`
- OpenAI 호환 인터페이스 (`openai` 패키지) 사용
- temperature: 0.4 (창의성 최소화, 사실 기반 작성)
- max_tokens: issue 2000 / onboarding 3500 / weekly 800

**왜 Groq인가:**
- Commander, Briefing, Watchlist 등 기존 구성요소와 동일한 Groq 스택 통일
- 로컬 LLM(Ollama) 대비 긴 리포트 생성 품질이 높음
- llama-3.3-70b는 한국어 투자 글쓰기에 충분한 수준

---

## 파일 구조

```
run_tech_report.py              CLI 진입점
src/tech_report/
    __init__.py
    collector.py                섹터 뉴스 수집
    reporter.py                 LLM 리포트 생성 + vault 저장 + 알림
```

---

## 실행 흐름

```
[1] 뉴스 수집 (collector.py)
    GoogleNewsSource(한국어) + GoogleNewsSource(영어)
    각 섹터별 쿼리 템플릿 적용 (예: "CoWoS 반도체 공정 패키징")
    중복 제거 후 최대 20건
         ↓
[2] 리포트 생성 (reporter.py → Groq)
    System Prompt: 메르 스타일 작성 규칙
    User Prompt: 섹터 + 토픽 + 수집 기사 목록
    결과물: 트리거 → 기술해부 → 변화포인트 → 투자시사점
    CJK/Cyrillic 오염 문자 제거 (_sanitize)
         ↓
[3] 저장 + 알림
    agent_vault/Reports/{섹터}/{날짜}_{토픽}.md
    Telegram: 첫 5줄 미리보기 + 파일 경로
    Digest: [!note] callout 기록
```

---

## 리포트 유형

| 유형 | 번호 포인트 수 | max_tokens | 사용 시점 |
|------|--------------|------------|---------|
| `issue` (기본) | 12개 내외 | 2,000 | 특정 이슈 발생 시 |
| `onboarding` | 25개 내외 | 3,500 | 섹터 처음 공부할 때 |
| `weekly` | 6개 내외 | 800 | 주간 업데이트 |

---

## 지원 섹터 (11개)

| 섹터 | 한국어 쿼리 예시 | 영어 쿼리 예시 |
|------|---------------|--------------|
| AI | `{topic} AI 인공지능 최신 동향` | `{topic} artificial intelligence` |
| 반도체 | `{topic} 반도체 공정 패키징 기술` | `{topic} semiconductor chip packaging` |
| 바이오 | `{topic} 바이오 임상 신약 파이프라인` | `{topic} biotech clinical trial` |
| 헬스케어 | `{topic} 헬스케어 의료기기 디지털헬스` | `{topic} healthcare medical device` |
| 디스플레이 | `{topic} 디스플레이 OLED 패널 기술` | `{topic} display OLED panel` |
| 2차전지 | `{topic} 배터리 양극재 음극재 소재` | `{topic} battery cathode anode material` |
| 자동차 | `{topic} 전기차 자율주행 자동차` | `{topic} electric vehicle autonomous driving` |
| 에너지 | `{topic} 에너지 전력 원전 ESS 그리드` | `{topic} energy power nuclear grid` |
| 우주방산 | `{topic} 우주 위성 방산 무기체계` | `{topic} space satellite defense weapon` |
| 양자컴퓨팅 | `{topic} 양자컴퓨팅 큐비트` | `{topic} quantum computing qubit error` |
| 로보틱스 | `{topic} 로보틱스 휴머노이드 로봇 액추에이터` | `{topic} robotics humanoid actuator` |

---

## 출력 파일 구조

```
agent_vault/Reports/
└── {섹터}/
    └── {YYYY-MM-DD}_{토픽}.md
```

**frontmatter:**
```yaml
---
type: tech-report
sector: 반도체
topic: CoWoS
date: 2026-05-14
report_type: issue
created: 2026-05-14T14:37:38Z
tags:
  - tech-report
  - 반도체
---
```

**본문 구조 (메르 스타일):**
```
## 트리거
최근 이슈 한 가지 (1~2문장)

## 기술 해부
1. ~임.
2. ~함.
3. ~인 것임.
...

## 변화 포인트
N. ...

## 투자 시사점
N. ...

**참고 기사**
* URL 1
* URL 2
```

---

## System Prompt (LLM에 전달)

```
당신은 "메르(Mer)" 스타일의 한국어 투자 리포트 작성 전문가다.

[작성 규칙]
- 반드시 한국어로만 작성한다. 영문 기술 용어는 한국어 옆 괄호로 병기한다.
- 문장은 짧게. 한 번호에 한 사실.
- 구어체 사용: "~임", "~함", "~인 것임", "~할 것임".
- 어려운 기술 개념은 일상 비유로 설명한다.
- 절대로 영어, 중국어, 러시아어 등 다른 언어를 섞지 않는다.

[리포트 구조]
## 트리거 / ## 기술 해부 / ## 변화 포인트 / ## 투자 시사점
```

---

## CLI 사용법

```bash
# issue 리포트 (기본)
python run_tech_report.py --sector 반도체 --topic CoWoS --vault ./agent_vault

# 저장·전송 없이 미리보기
python run_tech_report.py --sector 바이오 --topic GLP-1 --vault ./agent_vault --dry-run

# 섹터 입문 리포트 (25개 포인트)
python run_tech_report.py --sector AI --topic MoE --vault ./agent_vault --type onboarding

# 주간 업데이트
python run_tech_report.py --sector 2차전지 --topic 리튬가격 --vault ./agent_vault --type weekly

# 뉴스 수집 범위 조정 (14일)
python run_tech_report.py --sector 로보틱스 --topic 휴머노이드 --vault ./agent_vault --days 14
```

---

## Telegram 출력 형식

```
*[반도체] CoWoS 기술 리포트*

## 트리거
최근 CoWoS(패키징 기술) 관련 수혜 기대감이 폭발하고 있음.

## 기술 해부
1. CoWoS(패키징 기술)는 반도체 칩을 더 빠르고 효율적으로 연결하는 기술임.
...

📄 전체 리포트: `Reports/반도체/2026-05-14_CoWoS.md`
```

---

## 향후 연결 포인트 (Phase 2+)

| Phase | 내용 |
|-------|------|
| Phase 2 | Commander 테마 급등 감지 → `TechReportAgent` 자동 트리거 |
| Phase 3 | LaunchAgent 주간 스케줄 (월요일 08:00) — 전 섹터 weekly 리포트 |
| Phase 4 | LangGraph 통합 — AcademicScout + ClinicalScout + NewsScout 노드 |

Phase 2 연결 예시:
```python
# src/commander/dispatcher.py 에서
if "HBM" in theme_surge:
    subprocess.run(["python", "run_tech_report.py",
                    "--sector", "반도체", "--topic", "HBM",
                    "--vault", str(vault_path)])
```

---

## 관련 문서

- [technical-report-concept.md](technical-report-concept.md) — 개념 및 배경
- [technical-report-requirements.md](technical-report-requirements.md) — 요건정의서
- [sector-deep-analysis.md](sector-deep-analysis.md) — 11개 섹터 심층 분석
- [sector-sources-accessible.md](sector-sources-accessible.md) — 데이터 소스 가이드
