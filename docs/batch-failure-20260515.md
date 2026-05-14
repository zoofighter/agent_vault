---
title: 2026-05-15 배치 실패 원인 분석 및 수정
type: system-doc
created: 2026-05-15
related:
  - system-overview.md
---

# 2026-05-15 배치 실패 원인 및 수정

---

## 증상

- `run_daily.sh` 07:00:05 시작
- Phase A (임베딩), Phase B (뉴스 수집) 정상 완료
- Phase C (LLM 분석) — LG에너지솔루션 64건 처리 중 로그 중단
- Daily 노트 생성 0건

---

## 원인 1 — Ollama hang (주원인)

`src/llm/analyzer.py`와 `src/llm/curator.py`의 `ollama.generate()` 스트리밍 호출에 타임아웃이 없었음.

```python
# 수정 전 — 무한 대기 가능
for chunk in ollama.generate(model=..., stream=True):
    parts.append(chunk.response)
```

LG에너지솔루션 분석 중 Ollama가 느려지거나 멈추면 프로세스가 영원히 대기.
LaunchAgent에도 `MaxRunTimeSeconds` 설정이 없어 강제 종료 불가.

**수정**: `threading.Thread`로 감싸 타임아웃 적용

```python
# analyzer.py — 개별 기사 LLM 호출
_LLM_TIMEOUT = 30   # 30초 초과 시 "(타임아웃)" 반환

# curator.py — 합성 LLM 호출
_CURATOR_TIMEOUT = 120  # 120초 초과 시 None 반환 → 합성 스킵
```

---

## 원인 2 — 벡터 필터 미작동 (과부하 원인)

벡터 필터 임계값 0.75가 너무 넓어 수집된 뉴스의 100%가 LLM 분석 대상으로 통과됨.

```
삼성전자:       79건 수집 → 79건 LLM 호출 (100%)
SK하이닉스:     41건 수집 → 41건 LLM 호출 (100%)
현대차:         58건 수집 → 58건 LLM 호출 (100%)
LG에너지솔루션: 64건 수집 → 처리 중 hang
```

원인: `nomic-embed-text`의 한국 금융 뉴스 임베딩은 기사 간 cosine distance 차이가 0.007 수준으로 미미함. 임계값으로 관련/비관련 구분 불가.

```
삼성전자 HBM 뉴스: distance=0.273  (관련)
서울 아파트 뉴스:  distance=0.280  (무관) ← 구분 불가
```

**수정**:
- 임계값 0.75 → 0.50 (보수적 조정, 근본 해결은 아님)
- 회사당 LLM 호출 상한 `_MAX_LLM_ITEMS = 25` 추가
- 2단계 구조로 변경: 벡터 필터 전수 적용 → 거리 오름차순 상위 25건에만 LLM 호출

---

## 수정된 흐름 (analyzer.py)

```
수집된 뉴스 (평균 50건)
    │
    ▼
[1단계] 벡터 필터 (LLM 없음, 전수)
    distance ≤ 0.50 통과
    거리 오름차순 정렬
    │
    ▼ 상위 25건만
[2단계] LLM 근거 생성 (타임아웃 30초/건)
    "무관" 판정 시 제외
    │
    ▼
Daily 노트 저장
```

---

## 수정 후 예상 소요 시간

| 구분 | 수정 전 | 수정 후 |
|------|---------|---------|
| 회사당 최대 LLM 호출 | 무제한 (79건 관측) | 25건 |
| 전체 최대 호출 수 | ~1,900회 | 950회 |
| hang 발생 시 | 무한 대기 | 30초 후 "(타임아웃)" 처리 |
| 예상 소요 (평균) | 알 수 없음 | 약 90~100분 |

---

## 수정된 파일

| 파일 | 변경 내용 |
|------|-----------|
| `src/llm/analyzer.py` | threading 타임아웃 30초, 2단계 구조, 상한 25건, 임계값 0.50 |
| `src/llm/curator.py` | threading 타임아웃 120초 |

---

## 추가 확인 사항 (미해결)

- ChromaDB에 `sample_vault/` 경로 잔존 (vault 이름 변경 전 데이터)
  - `agent_vault/` 경로와 혼재 중 (총 275청크)
  - 기능에는 영향 없으나 정리 필요
- 벡터 필터의 근본적 개선 필요
  - `nomic-embed-text` 대신 한국어 특화 임베딩 모델 검토
  - 또는 회사 프로필 대신 투자 테제 핵심 문장만 임베딩 기준으로 사용
