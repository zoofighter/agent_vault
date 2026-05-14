---
title: 프로액티브 Telegram 메시징 — 설계 문서
type: system-doc
created: 2026-05-14
---

# 프로액티브 Telegram 메시징

> LLM이 사용자에게 먼저 말을 거는 시스템. 사용자가 명령을 보내길 기다리는 것이 아니라,
> 에이전트가 스스로 판단해서 중요한 정보를 텔레그램으로 먼저 전송한다.

---

## 전체 구조

```
07:00  run_daily.sh Phase 1~3
       뉴스 수집 → KRX 리서치 → 해외 리서치

       Phase 4 (신규)
       Commander Agent 자동 실행
       → 중요 기업 Top 3 액션 명령 생성
       → Telegram 전송 (send_commander)

07:30  run_briefing.py (별도 LaunchAgent)
       Digest/{today}.md 읽기
       → Groq LLM으로 대화체 브리핑 생성
       → Telegram 전송 ("오늘 주목할 내용은...")

18:00  run_daily.sh (2회차)
       동일한 Phase 1~4 반복
```

---

## A. Commander Phase (run_daily.sh Phase 4)

### 역할

뉴스 수집이 끝난 직후 Commander Agent를 자동 실행해서 중요 기업의 액션 명령을
Telegram으로 전송한다.

### 전송 형식

```
[★★★★★] ASML — ASML 투자 기회 증가

**근거**: ASML의 AI 반도체 수요 병목 역할이 지속되며...

**권장 액션**:
- ASML 주가 저항선 확인
- 반도체 장비 섹터 전반 포지션 검토
```

### 특징

- 하루 최대 3개 기업만 (비용 제어)
- 점수 0.45 미만은 무시 (노이즈 제거)
- 여러 기업에서 동일 테마 감지 시 "테마 급등" 알림 추가
- `--no-llm` 플래그로 Groq API 호출 없이 휴리스틱만 사용 가능

### 관련 코드

| 파일 | 역할 |
|------|------|
| `src/commander/scanner.py` | Daily 노트 스캔 + LLM 중요도 점수 |
| `src/commander/dispatcher.py` | Groq API로 액션 명령 텍스트 생성 |
| `src/commander/notifier.py` | Digest 기록 + Telegram 전송 |
| `src/telegram/sender.py` | 단방향 Telegram HTTP 전송 |
| `run_commander.py` | CLI 진입점 |

---

## B. 대화체 브리핑 (run_briefing.py)

### 역할

Commander가 구조화된 "액션 명령"을 보내는 것과 달리, Briefing은 LLM이 오늘의
분석 결과를 읽고 자연어로 짧은 대화를 시작한다.

### 전송 형식 (예시)

```
오늘 아침 브리핑이에요.

반도체 섹터가 전반적으로 강세입니다. ASML, TSMC, NVIDIA 모두
AI 인프라 수요 관련 뉴스가 집중됐고, 특히 ASML은 EUV 수주 확대
소식이 눈에 띄었습니다.

LG에너지솔루션은 ESS 관련 공급 계약 뉴스가 있었는데 볼트 메모와
연결해보면 지켜볼 만합니다.

오늘 주목할 기업 3개: ASML ★★★★★ / TSMC ★★★★★ / NVIDIA ★★★★★
```

### 구현 흐름

```
1. 오늘 Digest/{date}.md 읽기
   → 오늘 Commander가 기록한 모든 callout 블록 수집

2. Daily 노트 스캔 결과 (상위 5개 기업 summary)

3. Groq LLM에 전달
   → 3~5문장 대화체 브리핑 생성 (한국어)
   → 형식 없이 자연스럽게

4. src/telegram/sender.send() 로 전송
```

### 스케줄

- LaunchAgent: `com.boon.agentvault-briefing`
- 실행 시각: 매일 07:30 (Phase 4 Commander 완료 후 30분)
- 18:30도 추가 가능 (저녁 브리핑)

### 관련 코드

| 파일 | 역할 |
|------|------|
| `run_briefing.py` | CLI 진입점 + Groq 브리핑 생성 |
| `src/obsidian/digest.py` | Digest 파일 읽기/쓰기 |
| `src/telegram/sender.py` | Telegram 전송 |
| LaunchAgent plist | 07:30 자동 실행 |

---

## 전체 일일 Telegram 흐름

| 시각 | 발신자 | 내용 |
|------|--------|------|
| 07:05~20 | Commander | 액션 명령 1~3개 (구조화) |
| 07:30 | Briefing | 대화체 아침 브리핑 1건 |
| 18:05~20 | Commander | 저녁 액션 명령 1~3개 |
| 18:30 | Briefing | 저녁 브리핑 1건 |
| 수시 | Telegram Bot | 사용자 명령(/status, /inbox 등)에 응답 |

---

## 단방향 vs 양방향

현재 시스템은 **단방향 푸시** 방식이다.

- LLM → 사용자: `sender.py`의 `requests.post()` 직접 호출
- 사용자 → LLM: Telegram Bot polling (`run_telegram_bot.py`)

양방향 대화(LLM이 질문하고 사용자 답변을 기다림)는 현재 구현되지 않았다.
구현하려면 Bot webhook + 대화 상태 저장이 필요하다.

---

## 환경 변수 (.env)

```
TELEGRAM_BOT_TOKEN=...   # BotFather에서 발급
TELEGRAM_CHAT_ID=...     # 자신의 채팅 ID
GROQ_API_KEY=...         # dispatcher, briefing LLM 호출
```
