# CLAUDE.md — Obsidian 뉴스 수집 시스템

## 프로젝트 개요

Obsidian 볼트에 저장된 **회사별 리포트·메모를 기준 문서**로 삼아,
매일 관련 뉴스를 자동 수집·분석한 뒤 Obsidian 노트로 저장하는 시스템.

- 단순 키워드 필터가 아닌 **벡터 유사도 기반** 뉴스 선별
- 선택된 뉴스마다 "왜 관련 있는지" 근거 텍스트 자동 생성
- 볼트가 커져도 **변경된 파일만 증분 임베딩** → 일일 실행 시간 일정 유지

## 아키텍처 (두 단계)

```
Phase A — 인덱스 빌드 (변경 파일만)
  볼트 스캔 → mtime+MD5 비교 → 변경 파일만 임베딩 → ChromaDB 저장

Phase B — 일일 뉴스 검색
  ChromaDB 로드 → 뉴스 수집 → 벡터 유사도 검색 → LLM 근거 생성 → Obsidian 저장
```

설계 상세: [docs/incremental-indexing-design.md](docs/incremental-indexing-design.md)  
전체 요건: [docs/requirements.md](docs/requirements.md)

## 현재 구현 상태

| 파일 | 역할 | 상태 |
|------|------|------|
| `companies.csv` | 기업 레지스트리 38개사 | ✅ 완료 |
| `src/obsidian/company_manager.py` | 볼트 폴더/파일 동기화 | ✅ 완료 |
| `src/obsidian/templates.py` | 회사 노트 마크다운 템플릿 | ✅ 완료 |
| `src/obsidian/indexer.py` | 파일 변경 감지 + index_state.json | ✅ 완료 |
| `src/obsidian/embedder.py` | ChromaDB 증분 임베딩 + 손상 자동 복구 | ✅ 완료 |
| `src/sources/` | 뉴스 소스 8종 (Naver/DDG/Yahoo캐시/GoogleNews/HKEX/TWSE/TSE) | ✅ 완료 |
| `src/scraper/fetcher.py` | BeautifulSoup 본문 추출 (고관련 기사 한정) | ✅ 완료 |
| `src/llm/analyzer.py` | 벡터 유사도 필터 + LLM 근거 생성 | ✅ 완료 |
| `src/llm/curator.py` | 테마별 종합 분석 (Curated 노트) | ✅ 완료 |
| `src/obsidian/writer.py` | Obsidian 뉴스 노트 저장 | ✅ 완료 |
| `src/research/naver_research.py` | KRX 기업 리서치 PDF 수집 + LLM 요약 | ✅ 완료 |
| `src/research/naver_industry.py` | 해외 기업 산업분석 리포트 수집 | ✅ 완료 |
| `src/research/register_pdf.py` | 로컬 PDF 수동 등록 | ✅ 완료 |
| `collect_news.py` | 전체 파이프라인 오케스트레이터 | ✅ 완료 |
| `run_daily.sh` | 일일 배치 (뉴스 + KRX리서치 + 해외리서치) | ✅ 완료 |
| `sample_vault/` | 38개사 볼트 구조 | ✅ 완료 |

## 기업 관리

기업 추가/수정은 `companies.csv`를 직접 편집 후 동기화 명령 실행.

```bash
# 현황 확인
python -m src.obsidian.company_manager --vault ./sample_vault --status

# 볼트 동기화 (새 기업 파일 자동 생성, 기존 파일 보호)
python -m src.obsidian.company_manager --vault ./sample_vault

# 변경 없이 미리보기
python -m src.obsidian.company_manager --vault ./sample_vault --dry-run
```

`active: false` 설정 시 뉴스 수집에서 제외 (볼트 파일은 유지).

## 볼트 구조

회사가 많아질 것을 대비해 **회사별 폴더**로 관리한다.

```
sample_vault/
├── Companies/
│   ├── 삼성전자/
│   │   ├── 삼성전자.md      ← 회사 프로필 (company_manager 자동 생성)
│   │   ├── Research/        ← 실적·기술 분석 (AI 자동 생성)
│   │   ├── Memos/           ← 투자 메모 (사용자 직접 작성, 시스템 수정 불가)
│   │   └── News/            ← 뉴스 노트 (시스템 자동 저장)
│   └── SK하이닉스/
│       └── ...
└── Digest/                  ← 전사 일일 요약 노트
```

## 기술 스택

| 영역 | 선택 |
|------|------|
| 임베딩 모델 | `nomic-embed-text` via Ollama (로컬 무료) |
| 벡터 DB | ChromaDB (`data/chroma/` 영구 저장) |
| 로컬 LLM | Ollama `llama3.2` (또는 LM Studio) |
| 뉴스 소스 | Naver API, DuckDuckGo, Yahoo Finance(24h캐시), Google News RSS, HKEX/TWSE/TSE 공시 |
| 본문 추출 | BeautifulSoup → Playwright 폴백 |
| 설정 | `config.yaml` + `.env` (API 키) |

## 설계 원칙

- **증분 인덱싱**: 볼트 파일 중 변경된 것만 재임베딩 (mtime + MD5 해시 추적)
- **2단계 필터링**: 벡터 유사도 사전 필터 → 통과한 기사만 LLM 분석 (비용 절감)
- **비파괴 동기화**: 이미 존재하는 볼트 파일은 덮어쓰지 않음
- **부분 실패 허용**: 소스 하나 실패해도 전체 실행 중단 없음
