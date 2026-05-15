---
title: Telegram vs Discord 연동 비교 — AgentVault
updated: 2026-05-16
---

# Telegram vs Discord 연동 비교

AgentVault는 현재 Telegram을 단방향 알림 + 양방향 봇으로 구현하고 있다.
Discord 전환 또는 병행 운영 가능성을 검토한다.

---

## 현재 Telegram 구현 현황

### 단방향 알림 (`src/telegram/sender.py`)

| 함수 | 용도 | 호출 위치 |
|------|------|-----------|
| `send()` | 범용 텍스트 전송 | 전체 |
| `send_commander()` | 액션 명령 | `notifier.py` |
| `send_alert()` | 레벨별 알림 (info/warning/error/success) | 배치, 매크로 신호 |

### 양방향 봇 (`src/telegram/bot.py`)

| 명령 | 기능 |
|------|------|
| `/status` | 오늘 Daily 노트 수집 현황 |
| `/batch` | 배치 실행 이력 + LaunchAgent 상태 |
| `/logs [n]` | 오늘 로그 마지막 n줄 |
| `/inbox [n]` | Inbox 최근 알림 |
| `/commander` | Commander Agent 즉시 실행 |
| `/analyze 기업명` | Gemini 2.5 Pro 심층 분석 |
| `/memo 기업명 텍스트` | 투자 코멘트 Memos 저장 |
| `/blog 기업명` | 블로그 초안 생성 |

---

## 기능 비교표

| 항목 | Telegram | Discord |
|------|----------|---------|
| **봇 생성** | BotFather — 1분 | Developer Portal — 5분 |
| **Python 라이브러리** | `python-telegram-bot` (현재 사용) | `discord.py` 또는 `py-cord` |
| **메시지 포맷** | Markdown / HTML | Embed (card UI) + Markdown |
| **문자 제한** | 4,096자 | 일반 2,000자 / Embed 6,000자 |
| **슬래시 명령** | `/command` (텍스트 기반) | `/command` (자동완성 UI) |
| **파일 전송** | 최대 50MB | 최대 25MB (Nitro 500MB) |
| **폴링 vs 웹훅** | 양쪽 지원 | 웹훅 전용 (Gateway) |
| **채널 구조** | 단일 채팅방 | 서버 → 채널 (카테고리 분리 가능) |
| **알림 제어** | 수신자가 음소거 | 채널별·역할별 알림 세밀 제어 |
| **스레드** | 없음 | 있음 (메시지별 토론 분리) |
| **역할/권한** | 없음 (개인 봇) | 역할 기반 접근 제어 |
| **API 비용** | 무료 | 무료 |
| **모바일 UX** | 매우 우수 | 보통 |
| **PC UX** | 보통 | 우수 (채널 구조) |

---

## AgentVault 관점 세부 비교

### 1. 알림 채널 분리

**Telegram**: 단일 채팅방 — 배치 완료·Commander 명령·매크로 신호가 모두 섞임

**Discord**: 채널별 분리 가능
```
AgentVault 서버
├── #배치-알림        → 시작/완료/오류
├── #commander       → 액션 명령 (★★★★★)
├── #매크로-신호      → FOMC·VIX·CPI 발동
├── #리서치          → 증권사 리포트 수집 완료
└── #브리핑          → 아침/저녁 브리핑
```
→ 알림 피로도 감소, 종류별 검색 가능

### 2. 메시지 표현력

**Telegram**: Markdown 텍스트만
```
*[★★★★★] SK하이닉스 — HBM4 양산 확정*

근거: 삼성전자와의 격차 확대 신호...
```

**Discord**: Embed 카드 (색상, 필드, 썸네일, 푸터)
```
┌────────────────────────────────┐
│ 🔵 SK하이닉스 — HBM4 양산 확정  │
│ ★★★★★  score: 0.92            │
├─────────────────┬──────────────┤
│ 근거            │ 테마         │
│ 삼성과 격차 확대 │ HBM·CoWoS   │
├─────────────────┴──────────────┤
│ 액션                            │
│ • 목표주가 상향 가능성 점검      │
│ • 패키징 경쟁사 동향 모니터링    │
└────────────────────────────────┘
```

### 3. 양방향 명령 UX

**Telegram**: 텍스트 직접 입력, 자동완성 없음
```
/analyze 삼성전자
```

**Discord**: 슬래시 명령 자동완성 + 파라미터 힌트
```
/analyze company: 삼성전자
           ↳ [자동완성 드롭다운]
```

### 4. 구현 전환 비용

| 항목 | 규모 |
|------|------|
| `sender.py` 재작성 | Discord Webhook URL 방식으로 교체 — 50줄 |
| `bot.py` 재작성 | `discord.py` Cog 구조로 전환 — 200~300줄 |
| 채널 ID 관리 | `.env`에 채널별 ID 추가 |
| 기존 Telegram 유지 | `.env`에 토큰 존재 여부로 자동 선택 가능 |

### 5. 단방향 알림 (Webhook)

Discord는 Webhook URL 하나로 채널에 즉시 전송 가능 — Bot 없이도 동작.

```python
# Discord Webhook 방식 (python-telegram-bot 불필요)
import requests

def send_discord(channel_url: str, content: str, embed: dict = None):
    payload = {"content": content}
    if embed:
        payload["embeds"] = [embed]
    requests.post(channel_url, json=payload)
```

Telegram `send_alert()` 대비 라이브러리 의존성 없음.

---

## 권장 방향

### 단기: Telegram 유지 + Discord 알림 병행

Telegram은 모바일 즉시성이 우수해 긴급 알림에 적합.  
Discord는 PC에서 채널별 리뷰에 적합.

`.env` 토큰 존재 여부로 자동 선택:

```python
# sender.py 확장 예시
def send_alert(title, body, level="warning"):
    if os.environ.get("TELEGRAM_BOT_TOKEN"):
        _telegram_send_alert(title, body, level)
    if os.environ.get("DISCORD_WEBHOOK_COMMANDER"):
        _discord_send_alert(title, body, level)
```

### 장기: Discord로 전환 검토 조건

- 여러 사람이 알림을 공유할 때 (서버 멤버)
- 채널별 알림 분리가 필요할 때
- Embed 카드 UI가 필요할 때

---

## 구현 시 필요한 것

### Telegram (현재)
```
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

### Discord (추가 시)
```
DISCORD_WEBHOOK_BATCH=https://discord.com/api/webhooks/...      # 배치 알림
DISCORD_WEBHOOK_COMMANDER=https://discord.com/api/webhooks/...  # 액션 명령
DISCORD_WEBHOOK_MACRO=https://discord.com/api/webhooks/...      # 매크로 신호
DISCORD_BOT_TOKEN=...                                            # 양방향 봇 (선택)
```

Webhook만 쓰면 Bot Token 없이도 단방향 알림 운영 가능.

---

## 결론

| 상황 | 권장 |
|------|------|
| 혼자 쓰는 개인 시스템, 모바일 중심 | Telegram 유지 |
| PC 중심, 알림 종류 분리 필요 | Discord 병행 또는 전환 |
| 팀/공유 운영 | Discord |
| 구현 비용 최소화 | Telegram 유지 + Discord Webhook만 추가 |
