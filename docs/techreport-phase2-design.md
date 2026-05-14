---
title: TechReport Phase 2 — Commander 테마 급등 자동 트리거 설계
type: system-doc
created: 2026-05-15
related:
  - tech-report-implementation.md
  - commander-agent.md
---

# TechReport Phase 2 — Commander 테마 급등 자동 트리거

---

## 현재 Commander 흐름

```
scanner.py      ScanResult[]
                company="SK하이닉스"
                key_themes=["HBM", "AI 반도체"]
                score=0.82
                     │
                     ▼
dispatcher.py   Groq LLM 호출
                → command_type="theme_surge"   ← 이미 감지됨
                → title="HBM 공급 병목 심화"
                     │
                     ▼
notifier.py     Inbox + Telegram 전송
```

`dispatcher.py`의 `_parse_response()`가 LLM 출력에서 `command_type`을 이미 추출하고 있음.
`theme_surge`가 감지되면 `run_tech_report.py`를 subprocess로 호출하면 됨.

---

## 추가할 코드 (run_commander.py)

Phase 3(명령 생성) 직후에 삽입:

```python
import subprocess

# 테마 → 섹터 매핑
_THEME_SECTOR_MAP = {
    # 반도체
    "HBM": "반도체", "CoWoS": "반도체", "EUV": "반도체",
    "GAA": "반도체", "HBM3E": "반도체", "패키징": "반도체",
    # AI
    "AI 반도체": "AI", "LLM": "AI", "MoE": "AI", "추론": "AI",
    # 바이오
    "GLP-1": "바이오", "임상": "바이오", "ADC": "바이오",
    # 2차전지
    "전고체": "2차전지", "양극재": "2차전지", "리튬": "2차전지",
    # 자동차
    "FSD": "자동차", "자율주행": "자동차", "전기차": "자동차",
    # 디스플레이
    "OLED": "디스플레이", "MicroLED": "디스플레이",
    # 에너지
    "SMR": "에너지", "원전": "에너지", "ESS": "에너지",
    # 우주방산
    "Starlink": "우주방산", "LEO": "우주방산", "드론": "우주방산",
    # 양자컴퓨팅
    "큐비트": "양자컴퓨팅", "양자": "양자컴퓨팅",
    # 로보틱스
    "휴머노이드": "로보틱스", "로봇": "로보틱스",
}

# Phase 3.5: theme_surge → TechReport 자동 트리거
triggered = set()  # 중복 방지
for cmd, scan in zip(commands, candidates):
    if cmd.command_type == "theme_surge":
        for theme in scan.key_themes:
            sector = _THEME_SECTOR_MAP.get(theme)
            if sector and (sector, theme) not in triggered:
                triggered.add((sector, theme))
                print(f"  [phase3.5] theme_surge → TechReport: {sector}/{theme}")
                if not args.dry_run:
                    subprocess.run([
                        "python", "run_tech_report.py",
                        "--sector", sector,
                        "--topic",  theme,
                        "--vault",  str(vault),
                    ])
```

---

## 전체 실행 경로

```
run_daily.sh (07:00)
    └─ collect_news.py        뉴스 수집·RAG 필터
    └─ run_commander.py
          Phase 1: scan       → ScanResult[]
          Phase 2: dispatch   → Command[type="theme_surge", themes=["HBM"]]
          Phase 3: notify     → Inbox + Telegram
          Phase 3.5: ★신규★
                theme_surge 감지
                → subprocess: run_tech_report.py --sector 반도체 --topic HBM
                → Gemini CLI gemini-2.5-pro로 리포트 생성
                → agent_vault/Reports/반도체/2026-05-15_HBM.md
                → Telegram 전송
          Phase 4: watchlist  → 편입 후보 추천
```

---

## 조건 처리

| 상황 | 처리 |
|------|------|
| 같은 날 같은 테마 중복 | `triggered` set으로 1회만 실행 |
| Reports/ 파일 이미 존재 | 덮어쓰기 (날짜가 같으면 재생성) |
| `--dry-run` | subprocess 호출 생략, 로그만 출력 |
| 테마가 매핑 없음 | 스킵 (로그 없음) |

---

## 관련 파일

| 파일 | 역할 |
|------|------|
| `run_commander.py` | Phase 3.5 코드 삽입 위치 |
| `src/commander/dispatcher.py` | `command_type="theme_surge"` 감지 |
| `src/commander/scanner.py` | `key_themes` 추출 |
| `run_tech_report.py` | subprocess 타깃 |
