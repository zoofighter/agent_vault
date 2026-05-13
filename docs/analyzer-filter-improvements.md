---
title: Analyzer 필터 개선 — 버그 수정 & 품질 향상
tags:
  - system
  - analyzer
  - bugfix
created: 2026-05-13
---

# Analyzer 필터 개선 — 버그 수정 & 품질 향상

현대차 Curated 결과물에서 발견된 품질 문제를 진단하고 수정한 내용을 기록한다.

---

## 발견된 문제 (현대차 사례)

현대차 큐레이팅에 반도체(HBM) 내용이 혼입되고, 자동차와 무관한 기사가 필터를 통과하는 현상이 관찰됐다. 원인을 추적하니 세 가지 버그가 발견됐다.

---

## Bug 1 — LLM 거절 표현 다양성

### 문제

`analyzer.py`에서 LLM이 "관련 없다"고 판단할 때 정확히 `무관`을 반환하도록 지시했지만, `gemma4:e2b`는 다양한 한국어 표현으로 거절했다.

```
# 필터를 통과해버린 거절 표현들
"관련 없음"
"관련성 없음"
"관련 정보 없음"
"관련성이 없습니다"
"연관성은 없습니다"
"직접적인 영향은 없습니다"
"영향을 주지 않습니다"
"정보 없음"
```

기존 필터: `if "무관" in reason` — 하나만 잡고 나머지는 모두 통과.

### 수정

`_REJECT_PHRASES` 튜플을 정의하고 `any(p in reason for p in _REJECT_PHRASES)`로 교체.

```python
_REJECT_PHRASES = (
    "무관", "관련 없음", "관련성 없음", "해당 없음",
    "관련 정보 없음", "관련된 정보 없음", "직접적인 관련 없음", "직접 관련 없음", "정보 없음",
    "연관성은 없", "관련성은 없", "관련성이 없", "영향을 주지 않", "영향은 없", "영향이 없",
    "not relevant", "irrelevant", "no relevance", "no direct relevance",
)
```

### 결과

현대차 77건 수집 → 이전: 76건 통과 / 이후: 52건 통과 (25건 추가 필터링)

---

## Bug 2 — ChromaDB 한글 경로 NFC/NFD 불일치

### 문제

`company_filter` 기능이 한국어 회사명(현대차, SK하이닉스 등)에서 작동하지 않았다.

```python
# query_similar() 내부
if company_filter in meta["source"]:  # ← 항상 False
```

원인은 macOS 파일 시스템의 Unicode 정규화 방식이다.

| | 형태 | 예시 |
|--|------|------|
| Python 문자열 | NFC (합성형) | `현대차` |
| macOS 파일 경로 | NFD (분해형) | `현대차` (ᄒ+ᅧ+ᆫ+ᄃ+ᅢ+ᄎ+ᅡ) |

`Path.read_text()`로 파일 내용은 정상이지만, `str(Path)` 경로 자체가 NFD로 저장된다. 그래서 `"현대차" in "/…/현대차/…"` 비교가 실패한다.

ChromaDB에 경로가 NFD로 저장된 상태에서, Python 문자열 `"현대차"`(NFC)로 검색하면 매칭이 안 된다. 결과: **모든 뉴스가 `company_filter=None`처럼 동작 → 회사 구분 없이 전체 ChromaDB를 검색** → 현대차 뉴스에 반도체 청크가 매칭됨.

### 수정

`embedder.py`에서 저장 시와 검색 시 모두 NFC 정규화를 적용.

```python
import unicodedata

# 저장 시 (index_files)
source_str = unicodedata.normalize("NFC", str(md_file))
metas = [{"source": source_str, ...}]

# 검색 시 (query_similar)
nfc_filter = unicodedata.normalize("NFC", company_filter)
if nfc_filter in unicodedata.normalize("NFC", meta["source"]):
    ...
```

### 결과

한글 회사명 필터가 정상 작동. 현대차 뉴스는 현대차 볼트 문서하고만 유사도를 비교한다.

> [!warning] ChromaDB 재구축 필요
> 기존에 NFD로 저장된 경로가 있으면 필터가 여전히 실패한다.
> `data/chroma/`와 `data/index_state.json`을 삭제 후 재실행하면 NFC 경로로 새로 저장된다.

---

## Bug 3 — 자회사명 기사 혼입

### 문제

`"현대차"` 키워드 검색 결과에 `"현대차증권"` 기사가 포함됐다. Naver 뉴스는 부분 문자열로 검색하기 때문에, 검색어 `"현대차"`가 `"현대차증권"`, `"현대차그룹"`, `"현대차모비스"` 등의 기사도 가져온다.

### 수정

`analyzer.py`에 `_is_subsidiary_article()` 함수 추가. 기사 제목에 `회사명 + 접미사` 형태의 다른 법인명이 포함되면 사전 제외한다.

```python
_SUBSIDIARY_SUFFIXES = ("증권", "금융", "보험", "캐피탈", "자산운용", "저축은행")

def _is_subsidiary_article(title: str, company: str) -> bool:
    for suffix in _SUBSIDIARY_SUFFIXES:
        if (company + suffix) in title and not company.endswith(suffix):
            return True
    return False
```

적용 위치: LLM 호출 전 사전 필터링. LLM 비용 절감 + 오판 방지.

---

## 개선 전후 비교 (현대차 기준)

| 항목 | 개선 전 | 개선 후 |
|------|---------|---------|
| 수집 건수 | 76건 | 77건 |
| 통과 건수 | 76건 (100%) | 52건 (67%) |
| `인덱스 없음` 처리 | 76건 (100%) | 0건 |
| 현대차증권 기사 | 포함 | 제외 |
| Curated 내용 | HBM/반도체 혼입 | EV/제네시스/수소차 집중 |

---

## 관련 파일

- `src/llm/analyzer.py` — Bug 1, Bug 3 수정
- `src/obsidian/embedder.py` — Bug 2 수정
- [[prompt-design]] — 프롬프트 설계 상세
- [[curation-design]] — 큐레이팅 구조 설명
