---
title: 임베딩 모델 교체 — nomic-embed-text → bge-m3
type: system-doc
created: 2026-05-15
---

# 임베딩 모델 교체: nomic-embed-text → bge-m3

## 배경

`nomic-embed-text`(768차원)는 한국 금융 뉴스 간 cosine distance 차이가 0.007 수준으로
관련/비관련 뉴스를 실질적으로 구분하지 못했다.
벡터 필터가 무력화되어 회사당 최대 79건 전량이 LLM 분석 대상으로 통과됐고,
이것이 2026-05-15 배치 hang의 간접 원인이었다.

---

## 변경 내용

| 항목 | 변경 전 | 변경 후 |
|------|---------|---------|
| 임베딩 모델 | `nomic-embed-text` | `bge-m3` |
| 벡터 차원 | 768 | 1024 |
| 유사도 임계값 | 0.50 | 0.55 |
| ChromaDB | 300청크 (`sample_vault/` 잔존 포함) | 256청크 (`agent_vault/`만) |

### 수정 파일

| 파일 | 변경 내용 |
|------|-----------|
| `src/obsidian/embedder.py:16` | `_EMBED_MODEL = "bge-m3"` |
| `src/llm/analyzer.py:18` | `_SIM_THRESHOLD = 0.55` |

---

## 교체 절차 (1회성)

```bash
# 1. 모델 다운로드 (~1.2GB)
ollama pull bge-m3

# 2. 기존 ChromaDB + 인덱스 초기화
rm -rf data/chroma
rm -f data/index_state.json

# 3. 전체 재인덱싱
python -c "
from src.obsidian.indexer import get_changed_files
from src.obsidian.embedder import index_files
changed = get_changed_files('./agent_vault')
n = index_files(changed)
print(f'{n}청크 임베딩 완료')
"
```

---

## 거리 분포 측정 결과 (bge-m3, 2026-05-15)

SK하이닉스 볼트 기준으로 측정:

| 뉴스 | 거리 | 판정 |
|------|------|------|
| SK하이닉스 2Q26 영업이익 20조원 전망 | 0.314 | 관련 ✅ |
| 삼성전자 HBM3E 수율 개선 양산 돌입 | 0.403 | 관련 ✅ |
| SK하이닉스 HBM4 NVIDIA 납품 계약 확대 | 0.407 | 관련 ✅ |
| NVIDIA Blackwell GB300 출하량 급증 | 0.502 | 관련 ✅ |
| TSMC CoWoS 패키징 생산능력 증설 | 0.532 | 관련 ✅ |
| 카카오 광고 매출 감소 우려 | 0.589 | 무관 ❌ |
| 현대차 노조 임금협상 타결 | 0.601 | 무관 ❌ |
| 코스피 외국인 순매도 3000억원 | 0.609 | 무관 ❌ |
| 서울 아파트 분양가 상한제 확대 | 0.626 | 무관 ❌ |
| 원달러 환율 1380원 돌파 | 0.666 | 무관 ❌ |

**관련 뉴스 최대 거리**: 0.532  
**무관 뉴스 최소 거리**: 0.589  
**갭**: 0.057 (nomic 대비 약 8배)

### 임계값 0.55 선정 근거

- 관련 뉴스 전부 포함 (≤ 0.532)
- 무관 뉴스 전부 차단 (≥ 0.589)
- 양쪽 경계로부터 약 0.02~0.04 여유

---

## nomic-embed-text 비교

| 항목 | nomic-embed-text | bge-m3 |
|------|-----------------|--------|
| 관련/무관 거리 차이 | ~0.007 | ~0.057 |
| 필터 실효성 | 사실상 없음 (전량 통과) | 명확한 구분 가능 |
| 한국어 지원 | 제한적 | 100개 이상 언어 특화 |
| 차원 | 768 | 1024 |

---

## 향후 모니터링

- 첫 `collect_news.py` 실행 후 회사당 통과 건수 확인
- 정상 범위: 수집 뉴스의 20~50% 통과 (이전 100% 대비)
- 임계값 추가 조정 필요 시 `src/llm/analyzer.py:18` 수정
