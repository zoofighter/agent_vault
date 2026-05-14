---
title: AgentVault 배치 실행 목록
type: system-doc
created: 2026-05-15
related:
  - system-overview.md
  - batch-failure-20260515.md
---

# AgentVault 배치 실행 목록

---

## 자동 실행 배치 (LaunchAgent)

| 배치 | plist | 스케줄 | 스크립트 | 로그 |
|------|-------|--------|----------|------|
| 일일 뉴스 수집 | `com.boon.obs-news-update` | 매일 **07:00**, **18:00** | `run_daily.sh` | `logs/YYYY-MM-DD{a\|b}.log` |
| 브리핑 | `com.boon.agentvault-briefing` | 매일 **07:30**, **18:xx** | `run_briefing.py` | `logs/briefing.log` |
| 주간 TechReport | `com.boon.agentvault-techreport-weekly` | **매주 월요일 08:30** | `run_tech_report_weekly.py` | stdout/stderr → plist 지정 경로 |
| Telegram 봇 | `com.boon.agentvault-telegram-bot` | **상시 실행** | `run_telegram_bot.py` | `logs/telegram_bot.log` |

---

## 일일 배치 내부 단계 (`run_daily.sh`)

```
Phase 1  뉴스 수집        collect_news.py --all         07:00 시작
Phase 2  KRX 리서치       naver_research --date today
Phase 3  해외 리서치       naver_industry --date today
Phase 4  Commander        run_commander.py --max 3
  └─ Phase 3.5  theme_surge → TechReport 자동 트리거
```

로그 파일: `logs/{YYYY-MM-DD}{a|b|c}.log`
- `a`: 07:00 실행분
- `b`: 18:00 실행분
- `c`: 추가 실행분

종료 라인 예시:
```
=== 2026-05-15 09:12:33 종료 (뉴스: 0 / KRX리서치: 0 / 해외리서치: 0 / Commander: 0) ===
```

---

## 수동 실행 CLI

| 명령 | 용도 |
|------|------|
| `python run_commander.py --vault ./agent_vault` | Commander 즉시 실행 |
| `python run_tech_report.py --sector 반도체 --topic HBM --vault ./agent_vault` | 섹터 TechReport 즉시 생성 |
| `python run_briefing.py --vault ./agent_vault` | 브리핑 즉시 생성 |
| `python -m src.research.naver_research --vault ./agent_vault --date today` | KRX 리서치 즉시 수집 |
| `python -m src.research.naver_industry --vault ./agent_vault --date today` | 해외 리서치 즉시 수집 |

---

## Telegram 봇 명령 (실시간 모니터링)

| 명령 | 기능 |
|------|------|
| `/status` (s) | 오늘 Daily 노트 수집 현황 |
| `/batch` (bt) | 배치 실행 이력 + 성공/실패 요약 |
| `/logs [n]` (l) | 오늘 로그 마지막 n줄 (기본 30) |
| `/inbox [n]` (i) | Inbox.md 최근 알림 |
| `/commander` (c) | Commander 즉시 실행 |
| `/analyze 기업` (a) | 심층 투자 분석 |
| `/memo 기업 텍스트` (m) | 코멘트 Memo 저장 |
| `/blog 기업` (b) | 블로그 초안 생성 |

---

## 로그 파일 위치

```
logs/
├── 2026-05-15a.log      ← 오늘 07:00 실행 (뉴스+리서치+Commander)
├── 2026-05-15b.log      ← 오늘 18:00 실행
├── briefing.log         ← 브리핑 실행 로그 (append 방식)
├── telegram_bot.log     ← Telegram 봇 실행 로그
├── launchagent.log      ← LaunchAgent stdout
└── launchagent-error.log ← LaunchAgent stderr
```

---

## LaunchAgent 상태 확인 (터미널)

```bash
# 실행 중인 배치 확인
launchctl list | grep boon

# 특정 배치 상태
launchctl list com.boon.obs-news-update

# 오늘 로그 실시간 확인
tail -f logs/$(date +%Y-%m-%d)a.log

# 배치 수동 트리거
launchctl kickstart -k gui/$(id -u)/com.boon.obs-news-update
```
