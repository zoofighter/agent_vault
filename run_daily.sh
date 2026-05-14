#!/bin/bash
# 일일 뉴스 수집 & 큐레이팅 자동 실행
# LaunchAgent에서 호출됨 — 매일 오전 7:00

PROJECT_DIR="/Users/boon/Dropbox/03_code/a_0512_obs_news_update"
PYTHON="/opt/anaconda3/bin/python"
VAULT="$PROJECT_DIR/sample_vault"
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

echo "=== $(date '+%Y-%m-%d %H:%M:%S') 시작 ===" >> "$LOG_FILE"

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

echo "=== $(date '+%Y-%m-%d %H:%M:%S') 종료 (뉴스: $NEWS_EXIT / KRX리서치: $RESEARCH_EXIT / 해외리서치: $INDUSTRY_EXIT) ===" >> "$LOG_FILE"

# 30일 이상 된 로그 삭제
find "$LOG_DIR" -name "*.log" -mtime +30 -delete
