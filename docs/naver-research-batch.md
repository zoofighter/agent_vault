---
title: 네이버 리서치 배치 — 기업분석 + 산업분석
type: system-doc
created: 2026-05-15
related:
  - system-overview.md
---

# 네이버 리서치 배치

> asking.md 3번·4번 항목. **두 모듈 모두 완성된 상태.**

---

## 구현 현황

| 모듈 | URL | 대상 | 상태 |
|------|-----|------|------|
| `src/research/naver_research.py` | company_list.naver | 한국 종목 (6자리 ticker) | 완성 |
| `src/research/naver_industry.py` | industry_list.naver | 미국/해외 기업 | 완성 |

---

## 1. 기업분석 리포트 — `naver_research.py`

### 대상

`companies.csv`에서 **6자리 숫자 ticker를 가진 기업** (KRX·KOSDAQ 상장사)

```
삼성전자(005930), SK하이닉스(000660), 현대차(005380), LG에너지솔루션(373220) 등
```

### 파이프라인

```
Naver company_list.naver
  POST searchType=itemCode&itemCode={ticker}
       │
       ▼
  페이지 스캔 (최대 30페이지)
  날짜 범위 내 리포트만 추출 (nid, 제목, PDF URL, 날짜, 증권사)
       │
       ▼
  nid 중복 체크 → 이미 저장된 파일이면 건너뜀
       │
       ▼
  PDF 다운로드 (pstatic.net)
       │
       ▼
  PyMuPDF 텍스트 추출 (텍스트 ≥300자)
  텍스트 부족 시 → 이미지 변환 후 Vision LLM (Ollama gemma4:26b)
       │
       ▼
  로컬 LLM 요약 (Ollama gemma4:26b)
  [핵심 주장 / 투자 포인트 / 수치·목표주가 / 리스크 / 결론]
       │
       ▼
  agent_vault/Companies/KR/{기업}/Research/{YYYYMMDD}_{제목}.md
```

### CLI 사용법

```bash
# 오늘 리포트
python -m src.research.naver_research --vault ./agent_vault --date today

# 특정 날짜
python -m src.research.naver_research --vault ./agent_vault --date 2026-05-13

# 날짜 범위
python -m src.research.naver_research --vault ./agent_vault --from 2026-05-01 --to 2026-05-13

# 단일 기업
python -m src.research.naver_research --vault ./agent_vault --date today --company 삼성전자
```

### 저장 위치

```
agent_vault/Companies/KR/삼성전자/Research/
└── 20260514_삼성전자_목표주가_상향_AI_서버_수요_호조.md
```

---

## 2. 산업분석 리포트 — `naver_industry.py`

### 대상

`companies.csv`에서 **6자리 숫자 ticker가 없는 기업** (미국·중국·대만·일본 기업)

```
NVIDIA, Apple, Microsoft, TSMC, ASML, Tencent, CATL 등
```

### 파이프라인 (3단계 필터)

```
Naver industry_list.naver
  GET searchType=keyword&keyword={한글/영문 키워드}
  (각 기업별 키워드: "엔비디아", "NVIDIA", "엔비디아" 등)
       │
       ▼
[1단계] 제목 제외 필터 (PDF 다운로드 전, 빠름)
  → 주간 뉴스레터, Preview, Weekly 계열 제거
  → "박제민의 QnA", "Memory Watch", "IBKS Daily" 등
       │
       ▼
[2단계] PDF 텍스트 키워드 빈도 스캔 (LLM 없음)
  → PDF 다운로드 → PyMuPDF 전체 텍스트 추출
  → 기업 키워드가 3회 이상 등장해야 통과
  → 오매칭 방지: ARM(\b), 애플(앞뒤 한글 경계) 처리
       │
       ▼
[3단계] LLM 분석 (통과한 것만)
  → Ollama gemma4:26b 요약
       │
       ▼
  agent_vault/Companies/{US|CN|TW|JP}/{기업}/Research/{YYYYMMDD}_{제목}.md
```

### CLI 사용법

```bash
# 오늘 리포트
python -m src.research.naver_industry --vault ./agent_vault --date today

# 날짜 범위
python -m src.research.naver_industry --vault ./agent_vault --from 2026-04-14 --to 2026-05-14

# 단일 기업
python -m src.research.naver_industry --vault ./agent_vault --date today --company NVIDIA
```

### 저장 위치

```
agent_vault/Companies/US/NVIDIA/Research/
└── 20260514_HBM3E_공급_타이트_지속_엔비디아_수혜.md
```

---

## 비교: company_list vs industry_list

| 구분 | company_list (기업분석) | industry_list (산업분석) |
|------|-------------------------|--------------------------|
| 리포트 성격 | 특정 종목 직접 분석 | 산업 전반 → 기업 언급 포함 |
| 검색 방식 | POST + ticker (정확) | GET + 키워드 (간접, 후보 많음) |
| 필터 필요성 | 낮음 (ticker 직접 매칭) | 높음 (2단계 필터 필수) |
| 오매칭 위험 | 거의 없음 | 있음 (키워드 부분 일치) |
| 커버리지 | 한국 상장사만 | 미국·해외 기업 |

---

## run_daily.sh 연동

현재 `run_daily.sh`에 포함되지 않은 상태. 아래처럼 추가하면 됨:

```bash
# run_daily.sh 07:00 블록에 추가
echo "[Research] 기업분석 리포트..."
python -m src.research.naver_research --vault "$VAULT" --date today

echo "[Research] 산업분석 리포트..."
python -m src.research.naver_industry --vault "$VAULT" --date today
```

단, 리포트 없는 날(주말 포함)에는 실행해도 "해당 기간 리포트 없음"으로 조용히 종료됨.

---

## 한계 및 확장 여지

| 항목 | 현재 | 확장 방향 |
|------|------|-----------|
| LLM | Ollama gemma4:26b (로컬) | Gemini CLI fallback 추가 가능 |
| 요약 포맷 | 5개 섹션 고정 | 기업 유형별 포맷 분기 (바이오↔반도체) |
| 저장 후 알림 | Digest 기록만 | Telegram 알림 추가 가능 |
| 주간 배치 | 없음 | --from/--to로 주간 실행 가능 |
| 증권사 필터 | 없음 | 특정 증권사(삼성·미래 등)만 수집 옵션 |
