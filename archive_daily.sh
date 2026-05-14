#!/bin/bash
# Daily 파일 아카이브
# 30일 이상 된 Daily 노트를 Archive/{YYYY-MM}/ 폴더로 이동
#
# 사용법:
#   ./archive_daily.sh              # 실제 실행
#   ./archive_daily.sh --dry-run    # 시뮬레이션만

PROJECT_DIR="/Users/boon/Dropbox/03_code/a_0512_obs_news_update"
VAULT="$PROJECT_DIR/agent_vault"
LOG_DIR="$PROJECT_DIR/logs"
DRY_RUN="${1:-}"

mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/archive_$(date +%Y-%m-%d).log"

# 30일 전 날짜 (macOS)
CUTOFF=$(date -v-30d +%Y-%m-%d)

moved=0
skipped=0

log() { echo "$1" | tee -a "$LOG_FILE"; }

log "=== $(date '+%Y-%m-%d %H:%M:%S') 아카이브 시작 (기준: $CUTOFF 이전) ==="
[[ -n "$DRY_RUN" ]] && log "[dry-run 모드]"

while IFS= read -r -d '' file; do
    filename=$(basename "$file")

    # 파일명에서 날짜 추출: 2026-05-14a.md → 2026-05-14
    filedate="${filename:0:10}"

    # 날짜 형식 검증 (YYYY-MM-DD)
    if ! [[ "$filedate" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
        continue
    fi

    # 30일 이전 파일만 이동
    if [[ "$filedate" < "$CUTOFF" ]]; then
        yearmonth="${filedate:0:7}"       # 2026-05
        daily_dir=$(dirname "$file")      # .../Daily
        company_dir=$(dirname "$daily_dir")  # .../삼성전자
        archive_dir="$company_dir/Archive/$yearmonth"

        if [[ -n "$DRY_RUN" ]]; then
            log "  [이동 예정] $filename → $(basename "$company_dir")/Archive/$yearmonth/"
        else
            mkdir -p "$archive_dir"
            mv "$file" "$archive_dir/$filename"
            log "  이동: $(basename "$company_dir")/$filename → Archive/$yearmonth/"
        fi
        ((moved++))
    else
        ((skipped++))
    fi
done < <(find "$VAULT/Companies" -path "*/Daily/*.md" -print0 | sort -z)

prefix="[dry-run] "
[[ -z "$DRY_RUN" ]] && prefix=""
log "${prefix}완료: 이동 ${moved}개 / 유지 ${skipped}개"
log "=== 종료 ==="
