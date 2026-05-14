---
title: 뉴스 수집 소스 설계 및 신규 기업 추가
date: 2026-05-14
tags:
  - news-sources
  - design
  - companies
---

# 뉴스 수집 소스 설계

## 기업 레지스트리 (companies.csv)

총 34개 기업 등록. 거래소별 분류:

| 거래소 | 기업 |
|--------|------|
| KRX    | 삼성전자, SK하이닉스, 현대차, LG에너지솔루션, 포스코홀딩스 |
| NASDAQ | Apple, Microsoft, NVIDIA, Alphabet, Google, Amazon, Meta, Broadcom, Micron, AMD, Intel, ARM, ASML, Qualcomm, Super Micro |
| NYSE   | Tesla, Berkshire Hathaway, Eli Lilly, TSMC |
| HKEX   | Tencent (0700.HK), Xiaomi (1810.HK) |
| SZSE   | CATL (300750.SZ), BYD (002594.SZ) |
| TWSE   | Delta Electronics (2308.TW), MediaTek (2454.TW), Nanya (2408.TW) |
| TSE    | SoftBank (9984.T), Kioxia (285A.T), Tokyo Electron (8035.T) |
| PRIVATE | OpenAI, Anthropic, SpaceX, Alibaba |

## 뉴스 소스 구성

### 거래소별 소스 라우팅

```
KRX/KOSDAQ  →  Naver News + Naver Finance + DuckDuckGo + Google News (KO)
NASDAQ/NYSE →  Yahoo Finance RSS + DuckDuckGo + Google News (EN)
HKEX        →  Yahoo Finance RSS + HKEX공시(Playwright) + DuckDuckGo + Google News (EN)
TWSE        →  Yahoo Finance RSS + TWSE MOPS(Playwright) + DuckDuckGo + Google News (EN)
TSE         →  Yahoo Finance RSS + TSE TDnet(Playwright) + DuckDuckGo + Google News (EN)
SZSE        →  Yahoo Finance RSS + DuckDuckGo + Google News (EN)
PRIVATE     →  DuckDuckGo + Google News (EN)
```

### 소스 파일 목록

| 파일 | 소스 | 대상 |
|------|------|------|
| `src/sources/naver.py` | Naver 뉴스 검색 API | KRX 기업 |
| `src/sources/naver_finance.py` | Naver 금융 메인 뉴스 | KRX 기업 |
| `src/sources/yahoo_finance.py` | Yahoo Finance RSS | 모든 해외 기업 (ticker 기반) |
| `src/sources/duckduckgo.py` | DuckDuckGo 뉴스 | 모든 기업 |
| `src/sources/google_news.py` | Google News RSS | 모든 기업 (언어 선택 가능) |
| `src/sources/hkex.py` | HKEX 기업 공시 | HKEX 상장사 (.HK 티커) |
| `src/sources/twse.py` | TWSE MOPS 중요공시 | TWSE 상장사 (.TW 티커) |
| `src/sources/tse.py` | TSE TDnet 공시 | TSE 상장사 (.T 티커) |
| `src/sources/collector.py` | 수집 오케스트레이터 | 전체 조율 |

### HKEX / TWSE / TSE 소스 동작 방식

1. **1차 시도**: Playwright로 공식 거래소 공시 시스템 렌더링
   - HKEX: `www.hkexnews.hk` 검색 결과
   - TWSE: `mops.twse.com.tw/mops/web/t91sb01` POST 폼
   - TSE: `www.release.tdnet.info` 날짜별 조회
2. **2차 폴백**: Playwright 미설치 또는 실패 시 Google News로 대체
   - HKEX → Google News (zh-HK)
   - TWSE → Google News (zh-TW)
   - TSE → Google News (ja-JP)

### Google News RSS

```python
# 언어별 인스턴스
gnews_ko = GoogleNewsSource(lang="ko", country="KR")  # 한국어
gnews_en = GoogleNewsSource(lang="en", country="US")  # 영어
gnews_zh = GoogleNewsSource(lang="zh", country="HK")  # 중국어 (홍콩)
gnews_ja = GoogleNewsSource(lang="ja", country="JP")  # 일본어
```

URL 형식: `https://news.google.com/rss/search?q={query}&hl={lang}-{country}&gl={country}&ceid={country}:{lang}`

## 실행 방법

```bash
# 전체 기업 뉴스 수집
/opt/anaconda3/bin/python collect_news.py --all --vault ./agent_vault

# 특정 기업만
/opt/anaconda3/bin/python collect_news.py --companies "CATL,BYD,Tencent" --vault ./agent_vault

# 신규 기업 그룹
/opt/anaconda3/bin/python collect_news.py \
  --companies "Tencent,Alibaba,CATL,BYD,Xiaomi,Delta Electronics,MediaTek,Nanya,SoftBank,Kioxia,Tokyo Electron" \
  --vault ./agent_vault
```

## 네이버금융 리서치 리포트 (별도 모듈)

뉴스와 별개로 네이버 금융에서 PDF 리서치 리포트를 수집하는 배치:

```bash
# 한국 기업 리서치 (KRX)
python -m src.research.naver_research --vault ./agent_vault --date today

# 해외 기업 리서치 (산업분석 리포트)
python -m src.research.naver_industry --vault ./agent_vault --date today

# 해당 기간 전체 실행
python -m src.research.naver_industry --vault ./agent_vault --from 2026-05-01 --to 2026-05-14
```

### 리서치 필터 설정 (naver_industry.py)

```python
_MIN_KW_COUNT = 3      # PDF 내 키워드 최소 출현 횟수
_WHOLE_WORD_KEYWORDS = frozenset(["ARM", "META", "AI", "애플"])  # 단어 경계 매칭
```

제외 패턴: 박제민의 QnA, 주간 뉴스레터, Preview, Memory Watch, 제약/바이오, 통신 Weekly 등

## 볼트 저장 경로

| 유형 | 경로 |
|------|------|
| 뉴스 노트 | `Companies/{기업명}/News/YYYY-MM-DD.md` |
| 리서치 리포트 | `Companies/{기업명}/Research/YYYYMMDD_{제목}.md` |
| 큐레이션 | `Companies/{기업명}/Curated/` |
