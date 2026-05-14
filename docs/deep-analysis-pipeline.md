---
title: 심층분석 → 투자 연결 파이프라인 설계
type: system-doc
created: 2026-05-15
related:
  - system-overview.md
  - techreport-phase2-design.md
  - naver-research-batch.md
---

# 심층분석 → 투자 연결 파이프라인

> asking.md 마지막 항목: "심층분석을 → 분석 결과 + 커멘트 → 투자로 이어지게 → 리포트"
> 가장 큰 설계 작업. 현재 미구현.

---

## 현재 파이프라인의 단절점

```
뉴스 수집 → RAG 필터 → Daily 노트
                            ↓
                       Commander → "SK하이닉스 HBM 매수 검토" (Inbox)
                            ↓
                       TechReport → 섹터 기술 분석 (자동)
                            ↓
                          ★ 여기서 끊김 ★
                     투자 결정은 사람이 처음부터 다시 해야 함
```

뉴스·리서치 리포트·테크리포트가 쌓이지만, 이것들을 종합해서
"이 기업 지금 사야 하나 말아야 하나"까지 이어주는 링크가 없다.

---

## 전체 파이프라인 (4단계)

```
[1단계] 트리거
    Commander buy 명령 / 리포트 N건 누적 / Telegram 수동
                ↓
[2단계] 멀티소스 수집
    최근 뉴스 + 증권사 리포트 + 내 메모 + TechDoc + TechReport
                ↓
[3단계] LLM 투자 판단 초안 (Gemini 2.5 Pro)
    매수 근거 / 리스크 / 포지션 제안
                ↓
[4단계] 사람 확인 + 코멘트 → Memo 저장
    Telegram 양방향 → 내 코멘트 → 다음 RAG의 기준이 됨
```

---

## 1단계 — 트리거

분석을 언제 시작하는가.

| 트리거 | 조건 | 우선순위 |
|--------|------|----------|
| Commander 자동 | `command_type=buy` 생성 시 | 높음 |
| 리포트 누적 | 5일 내 같은 기업 증권사 리포트 3건 이상 | 중간 |
| Telegram 수동 | `/analyze 삼성전자` 명령 | 즉시 |

---

## 2단계 — 멀티소스 수집

기업에 대해 쌓인 모든 정보를 한 곳으로 끌어모음.

```
Companies/{기업}/Daily/    → 최근 14일 뉴스 요약 (Scout·Scribe 결과)
Companies/{기업}/Research/ → 증권사 리포트 요약 (naver_research 결과)
Companies/{기업}/Memos/    → 내 과거 투자 판단 (직접 쓴 글)
Docu/{섹터}/               → 섹터 배경 지식 (TechDoc)
Reports/{섹터}/            → 최신 TechReport 테마 분석
```

ChromaDB RAG로 관련 청크 조회 + 파일 직접 읽기 혼합.
Gemini 2.5 Pro (1M 토큰 컨텍스트) → 모든 소스를 하나의 프롬프트에 담아 전송.

---

## 3단계 — LLM 투자 판단 초안

Gemini 2.5 Pro가 출력하는 포맷:

```markdown
## [SK하이닉스] 투자 판단 초안 — 2026-05-15

### 매수 근거
1. HBM3E 독점 공급 → NVIDIA 물량 확보됨
2. 증권사 5곳 중 4곳 목표주가 상향 (컨센서스 230,000원)
3. 재고 DSI 정상화 — 공급 병목 구조 재진입

### 리스크
1. TSMC CoWoS 병목 완화 시 HBM 수요 감소 가능성
2. 중국 CXMT 추격 — 3~4년 후 위협
3. 메모리 가격 하락 사이클 진입 여부 불확실

### 포지션 제안
단기: 매수 우호 (현재 185,000원 → 목표 230,000원, +24%)
장기: 불확실성 존재, 분할 매수 권장

### 근거 출처
- [증권사] 2026-05-13 키움증권 HBM3E 공급 타이트 유지
- [TechReport] 2026-05-14 HBM 공급 병목 심화
- [내 메모] 2026-04-20 "2분기 재고 정상화 확인 후 매수"
```

---

## 4단계 — 사람 확인 + Memo 저장 (핵심)

```
Telegram 전송: "[SK하이닉스] 투자 초안 전송. 코멘트 입력 또는 /confirm"
         ↓
사용자 응답: "HBM 단가 협상이 변수. 3분기 실적 보고 판단"
         ↓
자동 저장: Companies/KR/SK하이닉스/Memos/2026-05-15_투자판단.md
         ↓
이 메모 → 다음 RAG 분석의 기준이 됨 (ChromaDB 재임베딩)
```

이 단계가 "자동화"가 아니라 "보조"로 만드는 핵심 설계다.
AI가 판단하고 사람이 코멘트를 더해 최종 결정 — LLM이 실수해도 사람이 잡음.

---

## 왜 가장 큰 설계 작업인가

| 과제 | 내용 |
|------|------|
| 데이터 통합 | 5개 소스를 시간·기업 기준으로 조합 |
| LLM 선택 | 긴 컨텍스트 + 투자 판단 → Gemini 2.5 Pro 필수 |
| Human-in-the-Loop | Telegram 봇이 양방향 대화 지원 필요 (기존은 단방향) |
| 피드백 루프 | 사용자 코멘트가 Memo에 쌓여 다음 RAG에 반영됨 |
| 투자 결과 추적 | 실제 수익률과 비교하는 피드백 시스템 (Phase 2+) |

---

## 구현 순서 (권장)

```
Phase 1 (수동 트리거)
    Telegram /analyze {기업} 명령 수신
    → 멀티소스 수집
    → Gemini Pro 분석 초안 전송
    → 사용자 코멘트 → Memo 저장

Phase 2 (자동 트리거)
    Commander buy 명령 → 자동 심층분석 시작
    리포트 N건 누적 감지 → 트리거

Phase 3 (투자 결과 추적)
    실제 매수/매도 기록 → 결과 수익률 추적
    → AI 판단 정확도 피드백 루프
```

---

## 관련 파일 (현재 존재)

| 파일 | 역할 | 심층분석에서의 역할 |
|------|------|---------------------|
| `run_telegram_bot.py` | Telegram 봇 | `/analyze` 명령 수신 |
| `src/telegram/sender.py` | Telegram 전송 | 초안 전송 |
| `src/commander/scanner.py` | 기업 스코어링 | 트리거 판단 기준 |
| `src/tech_report/reporter.py` | Gemini CLI 호출 | LLM 초안 생성 재활용 |
| `src/obsidian/digest.py` | Memo 기록 | 판단 저장 |
| `src/llm/analyzer.py` | RAG 조회 | 멀티소스 수집 |
