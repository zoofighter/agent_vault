---
title: 섹터별 데이터 소스 상세 가이드
type: system-doc
created: 2026-05-14
related: technical-report-requirements.md
---

# 섹터별 데이터 소스 상세 가이드

> 테크니컬 리포트 생성에 사용할 소스 목록.
> **무료/유료 구분**, API 접근 방법, Python 예시까지 포함.

---

## 요약 — 무료로 쓸 수 있는 핵심 스택

```
AI·반도체  →  arXiv + Semantic Scholar + IEEE Spectrum RSS
바이오     →  PubMed + bioRxiv/medRxiv + ClinicalTrials.gov
헬스케어   →  ClinicalTrials.gov + PubMed + SEC EDGAR
디스플레이 →  arXiv + IEEE Spectrum RSS (유료 대체 불가)
2차전지    →  arXiv + IEA API + SEC EDGAR + DART
자동차     →  IEA API + SEC EDGAR + Electrek RSS
공통       →  SEC EDGAR (미국 공시) + DART (한국 공시)

총 비용: 0원
```

---

## 1. arXiv

**제공**: AI·반도체·물리·화학 최신 논문 프리프린트 (동료 심사 전 공개)

| 항목 | 내용 |
|------|------|
| 무료 여부 | 완전 무료 |
| API | `export.arxiv.org/api/query` |
| 형식 | Atom XML |
| 속도 제한 | 3초당 1건 (준수 필수) |
| Python 라이브러리 | `pip install arxiv` |

**주요 카테고리**:

| 카테고리 | 내용 |
|----------|------|
| `cs.AI` | 인공지능 |
| `cs.LG` | 머신러닝 |
| `cs.AR` | 하드웨어 아키텍처 |
| `eess.SP` | 신호처리·센서 |
| `cond-mat.mtrl-sci` | 소재과학 (배터리·반도체 소재) |
| `physics.app-ph` | 응용물리 (디스플레이·반도체) |

**Python 예시**:

```python
import arxiv

client = arxiv.Client()
results = client.results(arxiv.Search(
    query="HBM high bandwidth memory packaging",
    max_results=10,
    sort_by=arxiv.SortCriterion.SubmittedDate,
))
for r in results:
    print(r.title, r.published, r.entry_id)
```

**활용 포인트**: NVIDIA·TSMC·삼성이 출판한 논문 저자 소속으로 필터링 가능.

---

## 2. Semantic Scholar

**제공**: arXiv 포함 2억 개 이상 논문 메타데이터 + 인용 그래프

| 항목 | 내용 |
|------|------|
| 무료 여부 | 무료 (API 키 필요) |
| API | `api.semanticscholar.org/graph/v1` |
| 형식 | JSON |
| 속도 제한 | 공유 풀 1,000 req/초 (키 없이도 접근 가능) |
| API 키 발급 | semanticscholar.org/product/api 에서 무료 신청 |

**arXiv 대비 장점**: 피인용수·영향력 지수로 중요 논문 필터링 가능.

```python
import requests

resp = requests.get(
    "https://api.semanticscholar.org/graph/v1/paper/search",
    params={
        "query": "CoWoS advanced packaging TSMC",
        "fields": "title,year,citationCount,authors,externalIds",
        "limit": 10,
    },
    headers={"x-api-key": "YOUR_KEY"},
)
papers = resp.json()["data"]
```

---

## 3. PubMed (NCBI E-utilities)

**제공**: 바이오·의학 문헌 3,500만 건

| 항목 | 내용 |
|------|------|
| 무료 여부 | 완전 무료 |
| API | `eutils.ncbi.nlm.nih.gov/entrez/eutils/` |
| 형식 | XML / JSON |
| 속도 제한 | 키 없이 3 req/초, 무료 키 등록 시 10 req/초 |
| 키 발급 | ncbi.nlm.nih.gov/account 에서 무료 |

**바이오 투자 활용 예시**:

```python
import requests

# GLP-1 관련 최신 임상 논문 검색
resp = requests.get(
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
    params={
        "db": "pubmed",
        "term": "semaglutide obesity clinical trial 2025",
        "retmax": 10,
        "sort": "pub+date",
        "retmode": "json",
        "api_key": "YOUR_KEY",
    },
)
ids = resp.json()["esearchresult"]["idlist"]
```

---

## 4. ClinicalTrials.gov API v2

**제공**: 미국 등록 임상시험 50만 건 전체 (Phase 1~4, 결과 포함)

| 항목 | 내용 |
|------|------|
| 무료 여부 | 완전 무료, 인증 불필요 |
| API | `clinicaltrials.gov/api/v2/studies` |
| 형식 | JSON |
| 속도 제한 | 명시 없음 |

**바이오 투자 핵심 지표**: 특정 기업의 임상 파이프라인 단계, 예상 완료일, 1차 평가변수

```python
import requests

resp = requests.get(
    "https://clinicaltrials.gov/api/v2/studies",
    params={
        "query.spons": "Eli Lilly",        # 스폰서 기업
        "filter.overallStatus": "RECRUITING",
        "fields": "NCTId,BriefTitle,Phase,StartDate,CompletionDate",
        "pageSize": 20,
    },
)
studies = resp.json()["studies"]
```

---

## 5. bioRxiv / medRxiv

**제공**: 생물학·의학 프리프린트 (임상 결과 사전 공개 포함)

| 항목 | 내용 |
|------|------|
| 무료 여부 | 완전 무료 |
| API | `api.medrxiv.org/details/{server}/{date_from}/{date_to}` |
| 형식 | JSON |
| 속도 제한 | 명시 없음 |

```python
import requests

resp = requests.get(
    "https://api.medrxiv.org/details/medrxiv/2026-05-01/2026-05-14/0/json"
)
papers = resp.json()["collection"]
# title, authors, abstract, doi 포함
```

---

## 6. SEC EDGAR

**제공**: 미국 상장기업 전체 공시 (10-K 연간보고서, 10-Q 분기, 8-K 수시, S-1 IPO)

| 항목 | 내용 |
|------|------|
| 무료 여부 | 완전 무료 |
| API | `data.sec.gov/submissions/{CIK}.json` |
| 전문 검색 | `efts.sec.gov/LATEST/search-index?q=...` |
| 형식 | JSON |
| 속도 제한 | 10 req/초, User-Agent 헤더 필수 |
| Python 라이브러리 | `pip install edgartools` |

**투자 활용**: 기업 IR에서 직접 언급하는 기술 키워드, R&D 지출, 리스크 요인

```python
import edgar

# edgartools 사용
company = edgar.Company("NVIDIA")
filings = company.get_filings(form="10-K").latest(1)
doc = filings.obj()  # 구조화된 10-K 객체
print(doc.business)  # 사업 개요 텍스트
```

---

## 7. DART (금융감독원 전자공시)

**제공**: 한국 상장기업 전체 공시 (사업보고서, 반기보고서, 주요사항보고)

| 항목 | 내용 |
|------|------|
| 무료 여부 | 완전 무료 |
| API | `opendart.fss.or.kr/api/` |
| 형식 | XML / JSON |
| 속도 제한 | 일 10,000건 |
| API 키 발급 | opendart.fss.or.kr 에서 무료 회원가입 |

```python
import requests

resp = requests.get(
    "https://opendart.fss.or.kr/api/list.json",
    params={
        "crtfc_key": "YOUR_DART_KEY",
        "corp_code": "00126380",   # 삼성전자 법인코드
        "bgn_de": "20260101",
        "end_de": "20260514",
        "pblntf_ty": "A",          # A=정기공시
    },
)
filings = resp.json()["list"]
```

**법인코드 조회**: `opendart.fss.or.kr/api/corpCode.xml` 에서 전체 목록 다운로드

---

## 8. IEA (국제에너지기구) API

**제공**: 전 세계 에너지 통계 (전기차 판매량, 배터리 수요, 재생에너지)

| 항목 | 내용 |
|------|------|
| 무료 여부 | 무료 (무료 계정 필요) |
| API | `api.iea.org/evs` (전기차), `api.iea.org/renewables` |
| 형식 | JSON |
| 등록 | iea.org/data-and-statistics 에서 계정 생성 |

**2차전지·자동차 투자 핵심 지표**: 국가별 EV 침투율, 배터리 용량 수요 전망

---

## 9. IEEE Spectrum RSS

**제공**: 반도체·AI·전기차 기술 뉴스 (편집부 큐레이션)

| 항목 | 내용 |
|------|------|
| 무료 여부 | 완전 무료 |
| 형식 | RSS/Atom |
| 인증 | 불필요 |

**주요 RSS 피드**:

```
반도체: https://spectrum.ieee.org/feeds/topic/semiconductors.rss
AI:    https://spectrum.ieee.org/feeds/topic/artificial-intelligence.rss
전기차: https://spectrum.ieee.org/feeds/topic/transportation.rss
```

---

## 10. 유료 소스 — 대안 접근법

아래 소스는 유료지만 무료로 부분 접근 가능한 방법이 있다.

| 유료 소스 | 무료 대안 |
|----------|-----------|
| **BloombergNEF** (배터리·에너지) | IEA API + Benchmark Minerals 무료 지수 |
| **DSCC** (디스플레이) | IEEE Xplore 논문 + 삼성/LG IR 직접 분석 |
| **SNE Research** (배터리 시장) | DART 기업 공시 + IEA 통계 |
| **SemiAnalysis** (반도체 딥다이브) | arXiv + IEDM 공개 요약 + IEEE Spectrum |
| **Benchmark Minerals** (양극재) | 무료 가격 지수 페이지 스크래핑 가능 |

---

## 섹터별 소스 매핑

| 섹터 | 주 소스 | 보조 소스 |
|------|---------|----------|
| **AI** | arXiv (cs.AI/LG), Semantic Scholar | SEC EDGAR (MS·Google·NVIDIA 10-K) |
| **반도체** | arXiv (cs.AR), Semantic Scholar | SEC EDGAR, DART, IEEE Spectrum RSS |
| **바이오** | PubMed, ClinicalTrials.gov, bioRxiv | SEC EDGAR (10-K 파이프라인 섹션) |
| **헬스케어** | PubMed, ClinicalTrials.gov | SEC EDGAR |
| **디스플레이** | arXiv (physics.app-ph) | DART (삼성·LG), IEEE Spectrum RSS |
| **2차전지** | arXiv (cond-mat.mtrl-sci), IEA API | DART, SEC EDGAR |
| **자동차** | IEA API (EV 통계) | SEC EDGAR (Tesla), DART (현대차) |

---

## 시스템 통합 구조

```
TechReportAgent
    ├─▶ AcademicScout  → arXiv API + Semantic Scholar API
    ├─▶ ClinicalScout  → PubMed API + ClinicalTrials.gov API
    ├─▶ DisclosureScout→ SEC EDGAR API + DART API
    ├─▶ EnergyScout    → IEA API
    └─▶ NewsScout      → IEEE Spectrum RSS + bioRxiv RSS

각 Scout 노드는 src/sources/ 패턴으로 구현
결과는 Synthesizer → 메르 스타일 번호 리포트 생성
```

**구현 참조**: 기존 `src/sources/` 폴더의 뉴스 소스 패턴을 그대로 재사용.
각 소스를 `fetch(query, max_results) -> list[dict]` 인터페이스로 구현.

---

## 환경변수 (.env에 추가 필요)

```
NCBI_API_KEY=...       # PubMed 속도 향상 (무료 발급)
DART_API_KEY=...       # 한국 공시 (무료 발급)
SEMANTIC_SCHOLAR_KEY=... # 선택 (없어도 작동)
```

---

## 관련 문서

- [technical-report-requirements.md](technical-report-requirements.md) — 리포트 요건정의서
- [technical-report-concept.md](technical-report-concept.md) — 개념 및 배경
