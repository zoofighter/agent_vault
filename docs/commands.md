---
title: 실행 명령 정리
date: 2026-05-14
---

# 실행 명령 정리

> Python 경로: `/opt/anaconda3/bin/python`
> 작업 디렉토리: `/Users/boon/Dropbox/03_code/a_0512_obs_news_update`

---

## 데몬 (자동 실행)

### LaunchAgent — 매일 오전 7시 뉴스 수집

macOS LaunchAgent로 등록되어 있으며 매일 오전 7시에 자동 실행된다.

```
Plist:  ~/Library/LaunchAgents/com.boon.obs-news-update.plist
Script: run_daily.sh
Log:    logs/YYYY-MM-DD.log
        logs/launchagent.log (stdout)
        logs/launchagent-error.log (stderr)
```

**데몬 제어 명령**

```bash
# 등록 (처음 또는 plist 변경 후)
launchctl load ~/Library/LaunchAgents/com.boon.obs-news-update.plist

# 해제
launchctl unload ~/Library/LaunchAgents/com.boon.obs-news-update.plist

# 현재 상태 확인
launchctl list | grep obs-news

# 즉시 수동 실행 (스케줄 무관)
launchctl start com.boon.obs-news-update

# 실시간 로그 확인
tail -f logs/$(date +%Y-%m-%d).log
```

`run_daily.sh`가 실행하는 내용:

```bash
/opt/anaconda3/bin/python collect_news.py --all --vault ./agent_vault
```

---

## 일시 실행

### 1. 뉴스 수집 (`collect_news.py`)

```bash
# 전체 기업 수집 (companies.csv의 active=true 항목)
PYTHONUNBUFFERED=1 /opt/anaconda3/bin/python collect_news.py --all --vault ./agent_vault

# 특정 기업만
/opt/anaconda3/bin/python collect_news.py \
  --companies "삼성전자,NVIDIA,Apple" \
  --vault ./agent_vault

# 신규 기업 그룹 (처음 추가한 11개 기업)
/opt/anaconda3/bin/python collect_news.py \
  --companies "Tencent,Alibaba,CATL,BYD,Xiaomi,Delta Electronics,MediaTek,Nanya,SoftBank,Kioxia,Tokyo Electron" \
  --vault ./agent_vault

# 수집 기간 변경 (기본 7일)
/opt/anaconda3/bin/python collect_news.py --all --days 3 --vault ./agent_vault

# 볼트 재인덱싱 건너뜀 (빠른 재실행, 볼트 파일이 바뀌지 않았을 때)
/opt/anaconda3/bin/python collect_news.py --all --skip-index --vault ./agent_vault

# 실제 저장 없이 미리보기
/opt/anaconda3/bin/python collect_news.py --all --dry-run --vault ./agent_vault
```

출력 파일:
- `agent_vault/Companies/{기업명}/News/YYYY-MM-DD.md` — 수집된 뉴스 목록
- `agent_vault/Companies/{기업명}/Curated/YYYY-MM-DD.md` — LLM 테마 분석

---

### 2. 리서치 리포트 수집 — 한국 기업 (`naver_research.py`)

네이버 금융에서 KRX 기업 분석 리포트(PDF)를 수집해 LLM 요약 후 저장.

```bash
# 오늘 리포트
/opt/anaconda3/bin/python -m src.research.naver_research \
  --vault ./agent_vault --date today

# 특정 날짜
/opt/anaconda3/bin/python -m src.research.naver_research \
  --vault ./agent_vault --date 2026-05-13

# 날짜 범위
/opt/anaconda3/bin/python -m src.research.naver_research \
  --vault ./agent_vault --from 2026-05-01 --to 2026-05-14

# 특정 기업만
/opt/anaconda3/bin/python -m src.research.naver_research \
  --vault ./agent_vault --date today --company 삼성전자
```

출력 파일: `agent_vault/Companies/{기업명}/Research/YYYYMMDD_{제목}.md`

---

### 3. 리서치 리포트 수집 — 해외 기업 (`naver_industry.py`)

네이버 금융 산업분석 리포트에서 해외 기업 관련 리포트를 키워드로 필터링 후 저장.

```bash
# 오늘 리포트
/opt/anaconda3/bin/python -m src.research.naver_industry \
  --vault ./agent_vault --date today

# 날짜 범위
/opt/anaconda3/bin/python -m src.research.naver_industry \
  --vault ./agent_vault --from 2026-05-01 --to 2026-05-14

# 특정 기업만
/opt/anaconda3/bin/python -m src.research.naver_industry \
  --vault ./agent_vault --date today --company NVIDIA
```

필터 설정 (`src/research/naver_industry.py`):
- `_MIN_KW_COUNT = 3` — PDF 내 키워드 최소 출현 횟수
- `_WHOLE_WORD_KEYWORDS` — 단어 경계 매칭 적용 대상: `ARM, META, AI, 애플`

출력 파일: `agent_vault/Companies/{기업명}/Research/YYYYMMDD_{제목}.md`

---

### 4. PDF 수동 등록 (`register_pdf.py`)

로컬 PDF를 특정 기업의 Research 폴더에 직접 등록.

```bash
# 파일 직접 지정
/opt/anaconda3/bin/python -m src.research.register_pdf \
  --vault ./agent_vault \
  --pdf ~/Downloads/samsung_report.pdf \
  --company 삼성전자

# Downloads 폴더 스캔 (대화식 선택)
/opt/anaconda3/bin/python -m src.research.register_pdf \
  --vault ./agent_vault --scan

# 특정 폴더 스캔
/opt/anaconda3/bin/python -m src.research.register_pdf \
  --vault ./agent_vault --scan --dir ~/Downloads
```

---

### 5. 볼트 기업 동기화 (`company_manager.py`)

`companies.csv`에 기업을 추가한 뒤 볼트 폴더 구조를 생성.

```bash
# 동기화 실행 (신규 기업 폴더/파일 자동 생성, 기존 파일 보호)
/opt/anaconda3/bin/python -m src.obsidian.company_manager --vault ./agent_vault

# 현황 확인
/opt/anaconda3/bin/python -m src.obsidian.company_manager --vault ./agent_vault --status

# 변경 없이 미리보기
/opt/anaconda3/bin/python -m src.obsidian.company_manager --vault ./agent_vault --dry-run
```

---

## 기업 추가 워크플로

신규 기업을 추가할 때의 순서:

```bash
# 1. companies.csv 편집 (name, exchange, ticker, keywords 추가)

# 2. 볼트 폴더 생성
/opt/anaconda3/bin/python -m src.obsidian.company_manager --vault ./agent_vault

# 3. 뉴스 수집
/opt/anaconda3/bin/python collect_news.py \
  --companies "신규기업1,신규기업2" \
  --vault ./agent_vault --skip-index
```

---

## 로그 확인

```bash
# 오늘 수집 로그
tail -f logs/$(date +%Y-%m-%d).log

# LaunchAgent 실행 로그
tail -f logs/launchagent.log

# 에러만
grep -i "error\|오류\|traceback" logs/$(date +%Y-%m-%d).log
```
