#!/bin/bash
# 일일 뉴스 수집 & 큐레이팅 자동 실행
# LaunchAgent에서 호출됨 — 매일 오전 7:00

PROJECT_DIR="/Users/boon/Dropbox/03_code/a_0512_obs_news_update"
PYTHON="/opt/anaconda3/bin/python"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/$(date +%Y-%m-%d).log"

mkdir -p "$LOG_DIR"

cd "$PROJECT_DIR" || exit 1

echo "=== $(date '+%Y-%m-%d %H:%M:%S') 시작 ===" >> "$LOG_FILE"

"$PYTHON" collect_news.py --all >> "$LOG_FILE" 2>&1
EXIT_CODE=$?

echo "=== $(date '+%Y-%m-%d %H:%M:%S') 종료 (exit: $EXIT_CODE) ===" >> "$LOG_FILE"

# 30일 이상 된 로그 삭제
find "$LOG_DIR" -name "*.log" -mtime +30 -delete
