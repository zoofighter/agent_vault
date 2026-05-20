# AgentVault

여러 AI 에이전트가 협력하여 매일 뉴스를 읽고, Obsidian 볼트에 쌓인 내 리서치를 필터 삼아 관련 뉴스만 골라 Daily 노트로 저장하는 개인 투자 인텔리전스 시스템.

- 단순 키워드 필터가 아닌 **볼트에 직접 쓴 글**이 필터 기준
- 선택된 뉴스마다 "왜 관련 있는지" 근거 텍스트 자동 생성
- mtime + MD5로 **변경된 파일만 증분 임베딩** → 매일 실행 시간 일정 유지

---

## 에이전트 구성

```
Memory Agent   → 볼트 변경 파일 ChromaDB 임베딩
Scout Agent    → 8개 소스에서 38개사 뉴스 수집
Filter Agent   → 벡터 유사도 필터 + LLM 근거 생성
Analyst Agent  → 종합 분석 합성
Scribe Agent   → Daily 노트 저장
Research Agent → 증권사 PDF 수집·요약
Commander      → Daily 분석 → Telegram 액션 명령 + 신규 편입 후보 추천
Briefing       → 대화체 브리핑 → Telegram 전송
Content Writer → Daily 노트 → 블로그/유튜브 초안
Telegram Bot   → 양방향 명령 인터페이스
```

---

## 요구사항

### 런타임

- Python 3.10+
- [Ollama](https://ollama.com) — 로컬 LLM/임베딩

```bash
# Ollama 모델 설치
ollama pull nomic-embed-text   # 임베딩
ollama pull llama3.2           # 분석 LLM (로컬)
```

### Python 패키지

```bash
pip install chromadb requests beautifulsoup4 feedparser playwright
pip install duckduckgo-search python-dotenv groq
playwright install chromium
```

### API 키 (`.env` 파일)

프로젝트 루트에 `.env` 파일을 생성하고 아래 값을 설정한다.

```env
# 네이버 검색 API (뉴스 수집)
NAVER_CLIENT_ID=your_naver_client_id
NAVER_CLIENT_SECRET=your_naver_client_secret

# Groq API (LLM — 브리핑/Commander)
GROQ_API_KEY=your_groq_api_key

# Telegram (알림/봇)
TELEGRAM_BOT_TOKEN=1234567890:AAF...
TELEGRAM_CHAT_ID=123456789

# FRED API (거시경제 지표)
FRED_API_KEY=your_fred_api_key

# Discord Webhook (선택 — 배치/Commander 로그)
DISCORD_WEBHOOK_BATCH=https://discord.com/api/webhooks/...
DISCORD_WEBHOOK_COMMANDER=https://discord.com/api/webhooks/...
DISCORD_WEBHOOK_MACRO=https://discord.com/api/webhooks/...
DISCORD_WEBHOOK_GENERAL=https://discord.com/api/webhooks/...
```

- Naver API: [developers.naver.com](https://developers.naver.com) → 검색 앱 등록
- Groq API: [console.groq.com](https://console.groq.com)
- FRED API: [fred.stlouisfed.org/docs/api/api_key.html](https://fred.stlouisfed.org/docs/api/api_key.html)
- Telegram Bot: @BotFather → `/newbot`

---

## 초기 설정

### 1. 볼트 경로 확인

기본 볼트 경로는 `collect_news.py` 상단 `DEFAULT_VAULT`에 고정되어 있다.  
다른 경로를 사용한다면 실행 시 `--vault` 옵션으로 지정하거나 파일을 직접 수정한다.

```python
# collect_news.py
DEFAULT_VAULT = Path("/Users/boon/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent_vault")
```

### 2. 기업 목록 확인

`companies.csv`에 38개사가 사전 등록되어 있다.

```bash
cat companies.csv | head -5
```

### 3. 볼트 폴더 구조 생성

```bash
python -m src.obsidian.company_manager --vault "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent_vault"
```

### 4. 볼트 초기 임베딩

뉴스 수집 첫 실행 시 자동으로 임베딩된다. 수동으로 먼저 실행하려면:

```bash
python collect_news.py --all --vault "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent_vault" --skip-news
```

---

## 실행 방법

> Python 경로 예시: `/opt/anaconda3/bin/python`  
> 아래 명령은 프로젝트 루트에서 실행한다.

---

### 뉴스 수집 (`collect_news.py`)

```bash
# 전체 기업 수집 (companies.csv active=true 항목)
python collect_news.py --all --vault "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent_vault"

# 특정 기업만
python collect_news.py --companies "삼성전자,NVIDIA,Apple" --vault "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent_vault"

# 수집 기간 변경 (기본 7일)
python collect_news.py --all --days 3 --vault "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent_vault"

# 볼트 재인덱싱 생략 (볼트 파일이 바뀌지 않았을 때 — 빠른 재실행)
python collect_news.py --all --skip-index --vault "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent_vault"

# 실제 저장 없이 미리보기
python collect_news.py --all --dry-run --vault "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent_vault"
```

출력 위치:
- `agent_vault/Companies/{기업명}/Daily/` — Daily 뉴스 노트

---

### KRX 리서치 리포트 (`naver_research.py`)

네이버 금융에서 한국 기업 증권사 PDF를 수집해 LLM 요약 후 저장.

```bash
# 오늘 리포트
python -m src.research.naver_research --vault "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent_vault" --date today

# 특정 날짜
python -m src.research.naver_research --vault "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent_vault" --date 2026-05-13

# 날짜 범위
python -m src.research.naver_research --vault "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent_vault" --from 2026-05-01 --to 2026-05-14

# 특정 기업만
python -m src.research.naver_research --vault "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent_vault" --date today --company 삼성전자
```

출력 위치: `agent_vault/Companies/{기업명}/Research/YYYYMMDD_{제목}.md`

---

### 해외 기업 리서치 (`naver_industry.py`)

네이버 금융 산업분석 리포트에서 해외 기업 관련 리포트를 키워드 필터링 후 저장.

```bash
# 오늘 리포트
python -m src.research.naver_industry --vault "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent_vault" --date today

# 날짜 범위
python -m src.research.naver_industry --vault "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent_vault" --from 2026-05-01 --to 2026-05-14

# 특정 기업만
python -m src.research.naver_industry --vault "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent_vault" --date today --company NVIDIA
```

필터 임계값 (`src/research/naver_industry.py`):
- `_MIN_KW_COUNT = 3` — PDF 내 키워드 최소 출현 횟수

---

### PDF 수동 등록 (`register_pdf.py`)

로컬 PDF를 특정 기업의 Research 폴더에 직접 등록.

```bash
# 파일 직접 지정
python -m src.research.register_pdf \
  --vault "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent_vault" --pdf ~/Downloads/samsung_report.pdf --company 삼성전자

# Downloads 폴더 스캔 후 대화식 선택
python -m src.research.register_pdf --vault "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent_vault" --scan

# 특정 폴더 스캔
python -m src.research.register_pdf --vault "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent_vault" --scan --dir ~/Downloads
```

---

### Commander Agent (`run_commander.py`)

Daily 노트를 분석해 Inbox.md에 액션 명령을 작성하고 신규 편입 후보를 추천.

```bash
# 오늘 날짜 기준 실행
python run_commander.py --vault "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent_vault"

# 특정 날짜
python run_commander.py --vault "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent_vault" --date 2026-05-14

# LLM 없이 휴리스틱만
python run_commander.py --vault "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent_vault" --no-llm

# 분석 대상 기업 수 제한
python run_commander.py --vault "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent_vault" --max 5
```

---

### Briefing Agent (`run_briefing.py`)

Digest를 요약해 대화체 브리핑을 생성하고 Telegram으로 전송.

```bash
python run_briefing.py --vault "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent_vault"

# 특정 날짜
python run_briefing.py --vault "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent_vault" --date 2026-05-14

# 실제 전송 없이 미리보기
python run_briefing.py --vault "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent_vault" --dry-run
```

---

### Content Writer (`run_content.py`)

Daily 노트를 블로그 포스트 또는 유튜브 스크립트 초안으로 변환.

```bash
# 블로그 + 유튜브 둘 다
python run_content.py --vault "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent_vault"

# 블로그만
python run_content.py --vault "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent_vault" --mode blog

# 유튜브만
python run_content.py --vault "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent_vault" --mode youtube

# 특정 기업
python run_content.py --vault "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent_vault" --company 삼성전자

# 특정 날짜
python run_content.py --vault "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent_vault" --date 2026-05-14

# 미리보기
python run_content.py --vault "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent_vault" --dry-run
```

---

### Telegram Bot (`run_telegram_bot.py`)

Telegram에서 명령을 입력해 실시간으로 수집/조회를 실행.

```bash
python run_telegram_bot.py
```

`.env`에 `TELEGRAM_BOT_TOKEN`과 `TELEGRAM_CHAT_ID`가 설정되어 있어야 한다.

---

### 기업 볼트 동기화 (`company_manager.py`)

`companies.csv`를 수정한 뒤 볼트 폴더 구조를 동기화한다.

```bash
# 동기화 실행 (신규 기업 폴더·파일 생성, 기존 파일 보호)
python -m src.obsidian.company_manager --vault "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent_vault"

# 현황 확인
python -m src.obsidian.company_manager --vault "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent_vault" --status

# 변경 없이 미리보기
python -m src.obsidian.company_manager --vault "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent_vault" --dry-run
```

---

## 자동화 (macOS LaunchAgent)

`run_daily.sh`가 4단계를 순서대로 실행한다:

1. 뉴스 수집 (`collect_news.py --all`)
2. KRX 리서치 (`naver_research.py`)
3. 해외 리서치 (`naver_industry.py`)
4. Commander (`run_commander.py`)

등록된 LaunchAgent:

| Plist | 실행 내용 | 시각 |
|---|---|---|
| `com.boon.obs-news-update.plist` | `run_daily.sh` — 뉴스 수집 전체 | 07:00, 18:00 |
| `com.boon.agentvault-briefing.plist` | `run_briefing.py` — Telegram 브리핑 | 별도 설정 |
| `com.boon.agentvault-telegram-bot.plist` | `run_telegram_bot.py` — 봇 상시 실행 | 부팅 시 |
| `com.boon.agent-vault-archive.plist` | `archive_daily.sh` — 30일+ 노트 아카이브 | 별도 설정 |

```bash
# LaunchAgent 등록
launchctl load ~/Library/LaunchAgents/com.boon.obs-news-update.plist

# 해제
launchctl unload ~/Library/LaunchAgents/com.boon.obs-news-update.plist

# 상태 확인
launchctl list | grep boon.obs-news

# 즉시 수동 실행
launchctl start com.boon.obs-news-update
```

---

## 신규 기업 추가

```bash
# 1. companies.csv에 행 추가
#    name,region,ticker,exchange,sector,industry,active,keywords

# 2. 볼트 폴더 생성
python -m src.obsidian.company_manager --vault "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent_vault"

# 3. 첫 뉴스 수집
python collect_news.py --companies "신규기업명" --vault "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent_vault"
```

`active: false`로 설정하면 뉴스 수집에서 제외되지만 볼트 파일은 유지된다.

---

## 볼트 구조

```
agent_vault/
└── Companies/
    ├── KR/      삼성전자 · SK하이닉스 · 현대차 · LG에너지솔루션 · 포스코홀딩스
    ├── US/      Apple · NVIDIA · Microsoft · Alphabet · Amazon 외 12개
    ├── CN/      Tencent · Alibaba · CATL · BYD · Xiaomi
    ├── TW/      TSMC · MediaTek · Delta Electronics · Nanya
    ├── JP/      SoftBank · Kioxia · Tokyo Electron
    └── Private/ OpenAI · Anthropic · SpaceX

    각 기업 폴더:
    ├── {기업명}.md   프로필 (시스템 생성, 이후 덮어쓰지 않음)
    ├── Daily/        일일 뉴스 노트 (시스템 전용)
    ├── Research/     증권사 리포트 요약 (시스템 전용)
    └── Memos/        투자 메모 (사용자 전용, 시스템 수정 불가)
```

Daily 파일명: `{날짜}{순서}.md` (예: `2026-05-14a.md`, `2026-05-14b.md`)

---

## 로그

```bash
# 오늘 수집 로그 실시간
tail -f logs/$(date +%Y-%m-%d)a.log

# 에러만 필터
grep -i "error\|오류\|traceback" logs/$(date +%Y-%m-%d)a.log

# LaunchAgent 실행 로그
tail -f logs/launchagent.log
```

로그 파일: `logs/YYYY-MM-DDa.log`, `...b.log`, `...c.log` (하루 최대 3회)  
30일 이상 된 로그는 자동 삭제된다.

---

## 기술 스택

| 영역 | 선택 |
|---|---|
| 임베딩 | `nomic-embed-text` (Ollama, 로컬) |
| 벡터 DB | ChromaDB (`data/chroma/`) |
| 분석 LLM | `llama3.2` (Ollama, 로컬) |
| 브리핑 LLM | `llama-3.3-70b-versatile` (Groq API) |
| 뉴스 소스 | Naver API · DuckDuckGo · Yahoo Finance · Google News RSS · HKEX · TWSE · TSE |
| 본문 추출 | BeautifulSoup → Playwright 폴백 |
| 자동화 | macOS LaunchAgent |
| 알림 | Telegram Bot API · Discord Webhook |
