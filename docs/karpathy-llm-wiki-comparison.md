---
title: Karpathy LLM Wiki vs AgentVault 비교
type: system-doc
created: 2026-05-15
related:
  - system-overview.md
  - batch-schedule.md
  - deep-analysis-pipeline.md
source: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
---

# Karpathy LLM Wiki vs AgentVault 비교

> "Obsidian is the IDE; the LLM is the programmer; the wiki is the codebase."
> — Andrej Karpathy, LLM Wiki gist

---

## 1. 핵심 철학 비교

### Karpathy LLM Wiki

매 쿼리마다 RAG로 문서를 재검색하지 않는다. 대신 LLM이 **점진적으로 누적되는(persistent, compounding) 마크다운 위키**를 직접 작성·유지보수한다.
- 이미 cross-reference가 걸려 있고
- 모순은 이미 플래그되어 있고
- 합성(synthesis)은 이미 끝나 있다

→ "지루한 부분(bookkeeping)을 LLM에게 맡기고, 인간은 큐레이션과 질문에 집중한다."

### AgentVault

매일 38개 기업의 뉴스를 8개 소스에서 자동 수집하고, **볼트에 쓴 내 글이 필터 기준**이 되어 관련 뉴스만 골라 Daily 노트로 저장한다.
- 키워드 매칭이 아닌 의미 기반 필터링
- 선택된 뉴스마다 "왜 관련 있는지" 근거 텍스트 자동 생성
- 변경된 파일만 증분 임베딩 → 일일 실행 시간 일정 유지

→ **공통점**: 인간은 큐레이션(투자 메모 작성), LLM은 반복 작업(매일 뉴스 읽기).
→ **차이점**: Karpathy는 *지식 누적*, AgentVault는 *지식 기반 필터링 + 실시간 의사결정 지원*.

---

## 2. 3-Layer 아키텍처 매핑

| Karpathy LLM Wiki | AgentVault | 일치도 |
|-------------------|------------|--------|
| **Raw Sources** (immutable) | `agent_vault/Companies/*/Research/` (증권사 PDF 요약), `Memos/` (사용자 메모) | 부분 일치 — Research는 LLM 요약본이라 완전한 immutable은 아님 |
| **The Wiki** (LLM-owned) | `Daily/` (LLM 합성 + 뉴스 목록), `Inbox.md` (Commander 액션), `Reports/` (TechReport) | 일치 |
| **The Schema** (config) | `CLAUDE.md`, `companies.csv`, `docs/system-overview.md` | 일치 |

**평가**: AgentVault는 Karpathy의 3-layer를 자연스럽게 따르고 있다. 단, "Wiki" 레이어가 단일 디렉토리가 아니라 여러 폴더(Daily/Inbox/Reports/Docu)로 분리되어 있다는 차이가 있다.

---

## 3. Key Operations 매핑

### Karpathy: Ingest

> "When adding a new source, the LLM reads it, extracts key information, updates entity pages, notes contradictions, strengthens synthesis."

### AgentVault: Memory Agent + Scout Agent

```
변경된 .md 파일 감지 (mtime + MD5)
    ↓
nomic-embed-text로 청크 임베딩
    ↓
ChromaDB에 누적 저장
```

**일치점**: 둘 다 증분(incremental) 방식.
**미달점**: AgentVault는 단순 임베딩만 한다. 모순 플래그·entity page 업데이트·synthesis 강화는 없음.

---

### Karpathy: Query

> "Ask questions against the wiki; answers cite specific pages and can be filed back as new wiki pages."

### AgentVault: Filter Agent + Analyst Agent

```
뉴스 1건 → 회사 프로필과 벡터 유사도 비교 → LLM 근거 생성
    ↓
30건 모음 → curator.py가 합성 → Daily 노트 저장
```

**일치점**: 답변이 새로운 wiki 페이지(=Daily 노트)로 다시 저장됨 → "explorations compound."
**차이점**: Karpathy는 *사용자 질문 답변* 중심, AgentVault는 *자동 트리거 분석* 중심.
→ `/analyze` Telegram 명령(deep_analyzer.py)이 Karpathy의 Query에 가장 가까움.

---

### Karpathy: Lint

> "Periodic health checks for contradictions, stale claims, orphan pages, missing cross-references."

### AgentVault: ❌ **미구현**

이 부분이 가장 큰 미스매치다. AgentVault에 있는 것:
- `archive_daily.sh` (30일 이상 Daily 노트 이동) ← 단순 archival
- ChromaDB 손상 자동 복구 ← 인프라 레벨

**없는 것**:
- 투자 논거 모순 감지 (예: Memos에 "TSMC 독점 수혜" vs 신규 Daily에 "삼성 HBM4 양산 시작" 충돌)
- 오래된 주장 stale 플래그 (예: 6개월 전 매수 근거 vs 현재 시장 상황)
- Orphan 페이지 감지 (어떤 회사 폴더에서도 참조되지 않는 메모)
- Cross-reference 누락 (Daily에서 다른 Daily/Memos로의 wikilink 부재)

**→ Phase 2 작업 후보**: `linter.py` 에이전트 추가.

---

## 4. Navigation Tools 비교

| 역할 | Karpathy | AgentVault |
|------|----------|------------|
| **카탈로그** | `index.md` (content-oriented, 카테고리별) | ❌ 없음. `companies.csv`만 있음 (메타데이터 only) |
| **연대기 로그** | `log.md` (append-only) | `Digest/{date}.md` (배치 실행 기록), `Inbox.md` (Commander 알림) |
| **시스템 가이드** | `CLAUDE.md` 또는 schema 파일 | `CLAUDE.md`, `docs/system-overview.md`, `docs/batch-schedule.md` |

**갭**: AgentVault에는 **content-oriented `index.md`가 없다**. 즉, "지금 볼트에 어떤 주제·테마·논거가 축적되어 있는가"를 한눈에 보는 카탈로그가 부재.

**→ Phase 2 작업 후보**: `agent_vault/index.md` 자동 생성기.
- 입력: 모든 Memos, Daily의 핵심 테마, TechReport 토픽
- 출력: 카테고리(섹터/논거/리스크) → 페이지 링크 목록

---

## 5. 패턴 일치 점수 (주관적)

| 항목 | 일치도 | 비고 |
|------|--------|------|
| 점진적 누적 (compounding) | ✅ 90% | Daily 노트가 매일 쌓임 |
| LLM-owned wiki layer | ✅ 80% | 자동 생성 + 사용자 보호 영역(Memos) 명확 분리 |
| Raw / Wiki / Schema 3계층 | ✅ 75% | Research가 완전 immutable이 아님 |
| Ingest (entity 업데이트) | 🟡 50% | 임베딩은 있으나 entity-level synthesis 없음 |
| Query (답변→새 페이지) | ✅ 70% | `/analyze` 흐름이 정확히 이 패턴 |
| Lint | ❌ 5% | 거의 미구현 |
| index.md | ❌ 10% | companies.csv 외 카탈로그 없음 |
| log.md | ✅ 80% | Digest + Inbox로 분산 구현 |

**총평**: AgentVault는 Karpathy 패턴의 약 **60~65%**를 무의식적으로 구현하고 있다.
가장 큰 차이는 **Lint 부재**와 **index.md 부재** — 둘 다 "지식 누적의 품질"을 담보하는 장치.

---

## 6. AgentVault만의 차별점

Karpathy LLM Wiki에 없는 것이 AgentVault에는 있다:

| AgentVault 고유 | 설명 |
|----------------|------|
| **자동 트리거 파이프라인** | LaunchAgent로 매일 07:00/18:00 무인 실행. Karpathy 패턴은 인간 트리거 가정. |
| **외부 데이터 수집기** | 8개 뉴스 소스 + 증권사 PDF 크롤러. Karpathy는 "Raw sources는 인간이 큐레이션." |
| **다중 에이전트 분업** | Memory/Scout/Filter/Analyst/Scribe/Commander/Briefing. Karpathy는 단일 LLM 가정. |
| **양방향 인터페이스** | Telegram bot으로 모바일 query/memo. Karpathy는 Claude Code/Obsidian IDE 가정. |
| **시간 민감 의사결정** | Commander가 "지금 매수 후보" 추천. Karpathy 패턴은 시간 무관 지식 베이스. |

**해석**: Karpathy는 *일반 지식 관리* 패턴, AgentVault는 *시간 민감 도메인(투자) 특화*. 같은 뼈대 위에 다른 살을 붙인 셈.

---

## 7. Phase 2 작업 제안 (Karpathy 패턴으로의 정렬)

우선순위 순:

### A. `linter.py` — 모순/스테일 감지 (우선순위 1)

```python
# src/agents/linter.py
def lint_company(vault: Path, company: str) -> list[LintFinding]:
    """
    1. Memos의 투자 논거를 추출 (LLM)
    2. 최근 7일 Daily 노트와 대조
    3. 모순 감지: "독점 수혜" 논거 vs "경쟁사 진입" 뉴스
    4. Stale 감지: 30일 이상 업데이트 없는 논거
    5. 결과를 Inbox.md에 callout으로 push
    """
```

### B. `index_builder.py` — content-oriented 카탈로그 (우선순위 2)

```python
# agent_vault/index.md 자동 생성
# 카테고리:
#   - 섹터별 (반도체/AI/바이오/...)
#   - 논거별 (HBM 독점/EUV 병목/...)
#   - 리스크별 (중국 제재/금리/...)
# 각 항목에서 관련 Memos·Daily·Reports 페이지로 wikilink
```

### C. Wikilink 자동 삽입 (우선순위 3)

현재 Daily 노트는 다른 노트를 참조하지 않음. Karpathy 패턴의 핵심인 "interlinked pages"를 위해:
- writer.py에서 합성 시 관련 Memos 페이지 wikilink 자동 삽입
- 예: `[[삼성전자/Memos/2025-03-12_HBM4_논거]]`

### D. Query→Wiki 자동 저장 강화 (우선순위 4)

`/analyze` 결과를 Memos가 아닌 별도 `Queries/` 폴더에 저장하고, index.md에서 카탈로그화.
- Karpathy: "answers can be filed back as new wiki pages"
- 현재: `/memo`로 사용자가 명시적으로 저장 필요 → 자동화 여지

---

## 8. 결론

AgentVault는 **Karpathy의 LLM Wiki 패턴을 우연히 70% 가까이 구현한 도메인 특화 시스템**이다.

가장 핵심적인 차이 두 가지:

1. **Lint 부재** → 지식이 쌓일수록 모순과 stale이 증가하는데 감지 메커니즘이 없음.
2. **Index 부재** → 38개사 × 수개월의 Daily/Memos가 쌓여도 "전체 지도"가 없음.

이 두 가지를 보완하면 Karpathy 패턴에 거의 완전히 부합하면서도, 시간 민감 의사결정이라는 **AgentVault 고유 가치**는 그대로 유지할 수 있다.

---

## 참고 자료

- **Karpathy LLM Wiki gist**: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
- **lucasastorian 오픈소스 구현**: https://github.com/lucasastorian/llmwiki
- **LLM Wiki v2 확장 (rohitg00)**: https://gist.github.com/rohitg00/2067ab416f7bbe447c1977edaaa681e2
- **Medium 분석**: https://medium.com/@urvvil08/andrej-karpathys-llm-wiki-create-your-own-knowledge-base-8779014accd5
- **Towards AI 분석**: https://pub.towardsai.net/andrej-karpathy-killed-rag-or-did-he-the-llm-wiki-pattern-7824d876e790
