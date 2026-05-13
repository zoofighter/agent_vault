---
title: 리서치 리포트 수집 소스 설계
date: 2026-05-14
tags:
  - research
  - naver-finance
  - design
---

# 리서치 리포트 수집 소스 설계

## 소스 1 — 한국 종목: company_list

URL: https://finance.naver.com/research/company_list.naver  
대상: companies.csv 중 KRX/KOSDAQ 기업 (6자리 숫자 티커)  
방식: POST `searchType=itemCode&itemCode={ticker}` — 종목별 직접 검색  
구현: `src/research/naver_research.py`

```bash
# 날짜 지정 실행
python -m src.research.naver_research --vault ./sample_vault --date today
python -m src.research.naver_research --vault ./sample_vault --from 2026-05-01 --to 2026-05-14
python -m src.research.naver_research --vault ./sample_vault --date today --company 삼성전자
```

## 소스 2 — 미국 기업: industry_list 키워드 검색

URL: https://finance.naver.com/research/industry_list.naver  
대상: companies.csv 중 해외 기업 (비 6자리 티커: AAPL, NVDA, MSFT 등)  
방식: GET `searchType=keyword&keyword={기업명/한국명}` — 제목 포함 여부로 필터  
구현: `src/research/naver_industry.py`

```bash
# 날짜 지정 실행
python -m src.research.naver_industry --vault ./sample_vault --date today
python -m src.research.naver_industry --vault ./sample_vault --from 2026-05-01 --to 2026-05-14
python -m src.research.naver_industry --vault ./sample_vault --date today --company NVIDIA
```

### 검색 전략

각 US 기업에 대해 영문명 + 한국명 + 주요 키워드로 다중 검색:
- NVIDIA → "NVIDIA", "엔비디아"
- Apple → "Apple", "애플"
- Microsoft → "Microsoft", "마이크로소프트"
- Alphabet → "Alphabet", "구글", "Google"
- TSMC → "TSMC"

결과 필터: **제목에 검색어 포함** 여부로 관련 없는 리포트 배제

## 수동 등록

URL: 로컬 파일 (Downloads 등)  
구현: `src/research/register_pdf.py`

```bash
# 직접 지정
python -m src.research.register_pdf --vault ./sample_vault \
    --pdf ~/Downloads/report.pdf --company NVIDIA

# 폴더 스캔 후 대화식 선택
python -m src.research.register_pdf --vault ./sample_vault --scan
```

## 파일 저장 규칙

| 항목 | 규칙 |
|------|------|
| 경로 | `Companies/{기업명}/Research/{YYYYMMDD}_{제목}.md` |
| 중복 방지 | frontmatter `nid` 기준 — 이미 있으면 건너뜀 |
| 파일명 충돌 | `_b`, `_c`, `_d` 접미사 자동 부여 |
| 수동 등록 | `nid: manual-{해시}`, `source: 수동등록` |
| 자동 수집 | `nid: {Naver nid}`, `source: 네이버금융 리서치` |
