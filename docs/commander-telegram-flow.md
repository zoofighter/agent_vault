---
title: Commander → Telegram 메시지 흐름
type: system-doc
created: 2026-05-14
---

# Commander → Telegram 메시지 흐름

> Commander Agent가 Daily 노트를 분석하고 Telegram으로 액션 명령을 전송하기까지의 전체 과정.

---

## 전체 체인

```
run_daily.sh (Phase 4)
    └─▶ run_commander.py
            ├─▶ src/commander/scanner.py      → Daily 노트 읽기 + 점수 계산
            ├─▶ src/commander/dispatcher.py   → Groq API로 액션 텍스트 생성
            └─▶ src/commander/notifier.py
                    ├─▶ src/obsidian/digest.py    → Digest/{date}.md 기록
                    └─▶ src/telegram/sender.py    → Telegram HTTP 전송
```

---

## 단계별 설명

### 1단계 — 트리거 (`run_daily.sh` Phase 4)

```bash
python run_commander.py --vault ./agent_vault --date $TODAY --max 3
```

뉴스 수집(Phase 1~3)이 끝난 직후 자동 실행된다.
`--max 3`은 하루 최대 3개 기업에만 메시지를 생성하도록 제한 (Groq API 비용 제어).

---

### 2단계 — 스캔 (`src/commander/scanner.py`)

`scan_daily_notes(vault, date_str)` 함수:

- `agent_vault/Companies/*/*/Daily/2026-05-14*.md` 전체를 읽음
- 각 노트에서 `news_count`, `## 종합 분석` 블록, 뉴스 제목 목록 파싱
- **휴리스틱 점수** 계산:

  | 항목 | 가중치 |
  |------|--------|
  | 뉴스 수 (최대 15건 기준) | 35% |
  | 별점 평균 (★ 기준 0~1) | 45% |
  | 중요 키워드 히트 수 | 20% |

- 점수 0.3 이상이면 로컬 Ollama(`gemma4:e2b`)로 추가 정제 (LLM 점수와 평균)
- 결과를 점수 내림차순으로 정렬한 `ScanResult` 리스트 반환

중요 키워드 예시: `급등`, `급락`, `실적`, `계약`, `인수`, `가이던스`, `surge`, `acquisition` 등 24개.

---

### 3단계 — 명령 생성 (`src/commander/dispatcher.py`)

`generate_commands(results, max=3, threshold=0.45)`:

1. 점수 **0.45 이상**인 상위 3개 기업만 선택
2. 각 기업마다 Groq API(`llama-3.3-70b-versatile`)에 프롬프트 전송:

```
Company: ASML
Daily synthesis: ...종합분석 1200자...

→ TYPE / TITLE / BODY / ACTIONS 형식으로 출력 요구
```

3. 응답을 파싱해서 `Command` 객체 생성:

```python
@dataclass
class Command:
    company: str       # 기업명
    title: str         # 한 줄 제목
    body: str          # 2~3문장 근거
    actions: str       # 권장 액션 목록
    stars: str         # ★★★★★ ~ ★☆☆☆☆
    score: float       # 0.0 ~ 1.0
    command_type: str  # report_found | theme_surge | thesis_conflict | deep_analysis
```

점수 구간별 별점:

| 점수 범위 | 별점 |
|-----------|------|
| 0.85 이상 | ★★★★★ |
| 0.70~0.85 | ★★★★☆ |
| 0.55~0.70 | ★★★☆☆ |
| 0.40~0.55 | ★★☆☆☆ |
| 미만 | ★☆☆☆☆ |

---

### 4단계 — 전송 (`src/commander/notifier.py` → `src/telegram/sender.py`)

`push_commands(commands, vault_path)`:

```python
for cmd in commands:
    append_record(vault_path, title, body)          # Digest/{date}.md 기록
    send_commander(cmd.company, cmd.title, body, cmd.stars)  # Telegram 전송
```

`send_commander()` → `send()`:

```python
requests.post(
    f"https://api.telegram.org/bot{token}/sendMessage",
    json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
    timeout=10,
)
```

`.env`의 `TELEGRAM_BOT_TOKEN`과 `TELEGRAM_CHAT_ID`를 읽어 직접 HTTP 요청.
봇 폴링 없이 **단방향 푸시** 방식이므로 봇이 꺼져 있어도 전송 가능.

---

### 5단계 — 테마 급등 감지 (부가, `src/commander/notifier.py`)

`push_theme_surges(results, vault, min_companies=3)`:

- 3개 이상 기업의 종합분석에서 동일 키워드가 감지되면 별도 알림 전송
- 예: NVIDIA·TSMC·ASML 모두 "AI 인프라" 언급 → "테마 급등 — AI 인프라 (3개사 동시 언급)"

---

## 실제 수신되는 메시지 형태

**액션 명령 (Commander):**

```
[★★★★★] ASML — ASML 투자 기회 증가

**근거**: ASML의 EUV 장비 수주 확대가 AI 반도체 공급망의 핵심 병목을 강화합니다.
향후 반도체 장비 수요는 지속적으로 증가할 것으로 예상됩니다.

**권장 액션**:
- ASML 주가 저항선 215유로 확인
- 반도체 장비 섹터 포지션 점검
```

**테마 급등 알림:**

```
⚠️ 테마 급등 — AI 인프라 (3개사 동시 언급)

감지 기업: NVIDIA, TSMC, ASML

권장 액션:
- 섹터 전반 영향 분석 수행
- 포트폴리오 비중 점검
```

---

## 저장 위치

전송과 동시에 `agent_vault/Digest/2026-05-14.md`에도 동일 내용이 Obsidian callout 블록으로 기록된다.

```
agent_vault/
└── Digest/
    └── 2026-05-14.md   ← Commander 명령 + 테마 급등 + Briefing 모두 기록
```

---

## 환경 변수 의존성

| 변수 | 용도 |
|------|------|
| `TELEGRAM_BOT_TOKEN` | Telegram API 인증 |
| `TELEGRAM_CHAT_ID` | 수신자 채팅 ID |
| `GROQ_API_KEY` | dispatcher 액션 생성 LLM |

---

## 관련 문서

- [proactive-telegram.md](proactive-telegram.md) — 전체 프로액티브 메시징 설계 (Commander + Briefing)
- [commander-agent.md](commander-agent.md) — Commander Agent 상세 설계
