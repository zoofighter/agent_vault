#!/bin/bash
# 일일 뉴스 수집 & 큐레이팅 자동 실행
# LaunchAgent에서 호출됨 — 매일 오전 7:00

PROJECT_DIR="/Users/boon/Dropbox/03_code/a_0512_obs_news_update"
PYTHON="/opt/anaconda3/bin/python"
VAULT="$PROJECT_DIR/agent_vault"
LOG_DIR="$PROJECT_DIR/logs"

# 실행 순서 suffix: 오늘 로그가 없으면 a, a 있으면 b, 둘 다 있으면 c
TODAY=$(date +%Y-%m-%d)
if [ ! -f "$LOG_DIR/${TODAY}a.log" ]; then
    DATE_SUFFIX="a"
elif [ ! -f "$LOG_DIR/${TODAY}b.log" ]; then
    DATE_SUFFIX="b"
else
    DATE_SUFFIX="c"
fi

LOG_FILE="$LOG_DIR/${TODAY}${DATE_SUFFIX}.log"

mkdir -p "$LOG_DIR"

cd "$PROJECT_DIR" || exit 1

START_TIME=$(date +%s)
echo "=== $(date '+%Y-%m-%d %H:%M:%S') 시작 ===" >> "$LOG_FILE"

# 배치 시작 알림
PYTHONUNBUFFERED=1 "$PYTHON" -c "
import os, sys
sys.path.insert(0, '.')
for line in open('.env').read().splitlines():
    line=line.strip()
    if line and not line.startswith('#') and '=' in line:
        k,v=line.split('=',1); os.environ.setdefault(k.strip(),v.strip())
from src.telegram.sender import send_alert
send_alert('배치 시작 — $TODAY ($DATE_SUFFIX)', '뉴스 수집 · 리서치 · Commander 순으로 실행합니다.', level='info')
" >> "$LOG_FILE" 2>&1

# Phase 1: 뉴스 수집 (전 종목)
echo "--- [뉴스 수집] $(date '+%H:%M:%S') ---" >> "$LOG_FILE"
PYTHONUNBUFFERED=1 "$PYTHON" collect_news.py --all --vault "$VAULT" --date-suffix "$DATE_SUFFIX" >> "$LOG_FILE" 2>&1
NEWS_EXIT=$?
echo "--- [뉴스 수집 완료] exit: $NEWS_EXIT ---" >> "$LOG_FILE"

# Phase 2: 한국 기업 리서치 리포트 (오늘 날짜)
echo "--- [KRX 리서치] $(date '+%H:%M:%S') ---" >> "$LOG_FILE"
PYTHONUNBUFFERED=1 "$PYTHON" -m src.research.naver_research \
    --vault "$VAULT" --date today >> "$LOG_FILE" 2>&1
RESEARCH_EXIT=$?
echo "--- [KRX 리서치 완료] exit: $RESEARCH_EXIT ---" >> "$LOG_FILE"

# Phase 3: 해외 기업 리서치 리포트 (오늘 날짜)
echo "--- [해외 리서치] $(date '+%H:%M:%S') ---" >> "$LOG_FILE"
PYTHONUNBUFFERED=1 "$PYTHON" -m src.research.naver_industry \
    --vault "$VAULT" --date today >> "$LOG_FILE" 2>&1
INDUSTRY_EXIT=$?
echo "--- [해외 리서치 완료] exit: $INDUSTRY_EXIT ---" >> "$LOG_FILE"

# Phase 4: Commander Agent (Daily 분석 → Telegram 액션 명령)
echo "--- [Commander] $(date '+%H:%M:%S') ---" >> "$LOG_FILE"
PYTHONUNBUFFERED=1 "$PYTHON" run_commander.py \
    --vault "$VAULT" --date "$TODAY" --max 3 >> "$LOG_FILE" 2>&1
COMMANDER_EXIT=$?
echo "--- [Commander 완료] exit: $COMMANDER_EXIT ---" >> "$LOG_FILE"

ELAPSED=$(( $(date +%s) - START_TIME ))
echo "=== $(date '+%Y-%m-%d %H:%M:%S') 종료 (뉴스: $NEWS_EXIT / KRX리서치: $RESEARCH_EXIT / 해외리서치: $INDUSTRY_EXIT / Commander: $COMMANDER_EXIT) ===" >> "$LOG_FILE"

# 배치 종료 알림
TOTAL_ERRORS=$(( NEWS_EXIT + RESEARCH_EXIT + INDUSTRY_EXIT + COMMANDER_EXIT ))
PYTHONUNBUFFERED=1 "$PYTHON" -c "
import os, sys
sys.path.insert(0, '.')
for line in open('.env').read().splitlines():
    line=line.strip()
    if line and not line.startswith('#') and '=' in line:
        k,v=line.split('=',1); os.environ.setdefault(k.strip(),v.strip())
from src.telegram.sender import send_alert
errors = $TOTAL_ERRORS
elapsed = $ELAPSED
mins, secs = divmod(elapsed, 60)
duration = f'{mins}분 {secs}초'
exits = '뉴스 $NEWS_EXIT / KRX리서치 $RESEARCH_EXIT / 해외리서치 $INDUSTRY_EXIT / Commander $COMMANDER_EXIT'
if errors == 0:
    send_alert('배치 완료 — $TODAY ($DATE_SUFFIX)', f'소요: {duration}\n{exits}', level='success')
else:
    send_alert('배치 오류 — $TODAY ($DATE_SUFFIX)', f'소요: {duration}\n{exits}\n오류 {errors}건 — 로그 확인 필요', level='error')
" >> "$LOG_FILE" 2>&1

# 30일 이상 된 로그 삭제
find "$LOG_DIR" -name "*.log" -mtime +30 -delete
