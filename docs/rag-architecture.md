---
title: AgentVault RAG 아키텍처
type: system-doc
created: 2026-05-15
related:
  - Docu-vault-relationship.md
---

# AgentVault RAG 아키텍처

---

## RAG인가

맞다. AgentVault의 뉴스 필터는 RAG(Retrieval-Augmented Generation)다.

`src/llm/analyzer.py`의 핵심 흐름:

```python
# 1. Retrieve — ChromaDB에서 가장 유사한 볼트 청크 조회
similar = query_similar(query_text, n_results=3, company_filter=company)

# 2. Augment — 조회된 청크를 LLM 프롬프트에 삽입
context = best["document"][:600]   # ← 볼트 문서 내용
prompt = _build_prompt(company, context, title, snippet)
# → "Reference document (investment memo excerpt):\n{context}\n\n"

# 3. Generate — LLM이 context를 참조해서 근거 생성
reason = ollama.generate(prompt)   # gemma4:e2b (로컬 Ollama)
```

---

## 일반 RAG와의 차이

| 구분 | 일반 RAG | AgentVault |
|------|----------|------------|
| 목적 | 질문에 답변 | 뉴스 관련성 판단 + 근거 생성 |
| Retrieve | 질문과 유사한 문서 | 뉴스와 유사한 볼트 문서 |
| Generate | 답변 | "왜 이 기업 투자자에게 관련 있는가" |
| 필터 역할 | 없음 | distance > 0.75면 LLM 호출 자체 안 함 |

정확히는 **"RAG-as-filter"** 패턴이다.

---

## 2단계 필터 구조

```
뉴스 수백 건
    │
    ▼
[1단계] 벡터 유사도 필터 (ChromaDB)
    distance ≤ 0.75 → 통과
    distance > 0.75 → 즉시 버림 (LLM 호출 없음)
    │
    ▼ (통과된 뉴스만)
[2단계] RAG — LLM 근거 생성
    Retrieve: 가장 유사한 볼트 청크 (context)
    Augment:  context + 뉴스 제목 + 본문 → LLM 프롬프트
    Generate: "왜 이 기업 투자자에게 관련 있는가" (한 문장)
    │
    ▼ LLM이 "무관" 판정 시 추가 제거
[결과] Daily 노트에 저장되는 뉴스
```

비용 절감 설계: 1단계 벡터 필터가 대부분을 걸러내서 LLM 호출 수를 최소화한다.

---

## ChromaDB 임베딩 대상

뉴스 필터의 기준이 되는 지식 소스.

| 소스 | 역할 |
|------|------|
| `Companies/{region}/{기업}.md` | 기업 프로필 — 내가 쓴 투자 개요 |
| `Companies/.../Research/` | 증권사·IR 분석 요약 |
| `Companies/.../Memos/` | 내 투자 판단 (가장 중요) |
| `Docu/` | 섹터 구조 지식 — 내용 채울수록 필터 정교화 |

**제외 대상** (`src/obsidian/indexer.py` `_SKIP_DIRS`):

```python
_SKIP_DIRS = {
    "Daily",    # 뉴스가 뉴스 필터 기준이 되면 순환
    "Digest",   # 에이전트 로그 — 지식 아님
    "Content",  # 블로그 초안 — 지식 아님
    "Archive",  "News", "Curated", ".obsidian", "__pycache__"
}
```

---

## Docu/가 필터에 미치는 영향

Docu에 내용을 채울수록 관련 뉴스 통과율이 높아진다.

예시:
```
Docu/반도체/반도체_TechDoc.md 에
"3.4.2 CoWoS — TSMC가 개발한 2.5D 패키징 기술. HBM과 GPU를 인터포저 위에 올림"
을 채워넣으면

→ "TSMC CoWoS 캐파 부족" 뉴스의 벡터 거리가 낮아짐
→ 1단계 필터 통과
→ LLM이 투자 근거 생성
→ Daily 노트에 ★★★★ 등급으로 저장
```

Memos에 내 판단을 쓰는 것도 동일한 효과다.
내가 더 많이 쓸수록 필터가 내 관심사에 맞게 정교해진다.

---

## 관련 코드

| 파일 | 역할 |
|------|------|
| `src/obsidian/indexer.py` | 변경된 볼트 파일 감지 (mtime+MD5) |
| `src/obsidian/embedder.py` | ChromaDB 증분 임베딩 (nomic-embed-text) |
| `src/llm/analyzer.py` | RAG 필터 + LLM 근거 생성 (gemma4:e2b) |
| `collect_news.py` Phase A | 볼트 인덱싱 실행 진입점 |

---

## 관련 문서

- [Docu-vault-relationship.md](../agent_vault/Docu/Docu-vault-relationship.md)
