---
title: LangGraph 기반 Knowledge Agent — 설계 구상
type: system-doc
created: 2026-05-14
status: draft
---

# LangGraph 기반 Knowledge Agent

> 현재의 뉴스 수집 파이프라인을 LangGraph 에이전트 그래프로 전환하고,
> 단순 뉴스 필터링 대신 **볼트의 지식 공백을 찾아 전문 문서를 전달**하는 시스템으로 발전시키는 구상.

---

## 현재 vs 전환 후

| | 현재 | LangGraph 전환 후 |
|--|------|-----------------|
| 시작점 | 38개사 뉴스 수집 | 내 볼트의 **지식 공백**에서 출발 |
| 목표 | 관련 뉴스 필터링 | 몰라야 할 것을 찾아서 채워줌 |
| 소스 | Naver·Yahoo·DDG 뉴스 | arXiv·SEC·GitHub·기술 블로그·산업 리포트 |
| 흐름 | 선형 파이프라인 | 그래프 — 조건 분기·루프·병렬 실행 |
| Telegram | 단방향 푸시 | 양방향 — 답장으로 검색 방향 조정 |

---

## 핵심 전환 포인트

**지금:**
> "TSMC 뉴스가 있다 → 관련 있다 → 전달"

**전환 후:**
> "볼트에 TSMC 파운드리 메모가 있는데 CoWoS 패키징 내용이 없다
> → arXiv·TSMC 기술 블로그·Samsung LSI IR에서 CoWoS 문서 탐색
> → 핵심 요약 + 원문 링크 전달"

볼트가 커질수록 에이전트가 더 정교하게 공백을 찾는다.

---

## LangGraph 그래프 구조

```
                 ┌──────────────────┐
                 │  VaultReader     │  ← ChromaDB로 현재 관심사 파악
                 └────────┬─────────┘
                          │ user_context
                 ┌────────▼─────────┐
                 │  GapAnalyzer     │  ← 볼트에 없는 지식 공백 식별
                 └────────┬─────────┘
                          │ knowledge_queries
          ┌───────────────┼────────────────┐
          ▼               ▼                ▼
   ┌──────────┐   ┌──────────────┐  ┌──────────────┐
   │PaperScout│   │  DocScout    │  │  TechScout   │
   │ (arXiv)  │   │(SEC/IR/PDF)  │  │(GitHub/Docs) │
   └──────┬───┘   └──────┬───────┘  └──────┬───────┘
          └──────────────┼──────────────────┘
                         │ raw_findings
                ┌────────▼─────────┐
                │  RelevanceJudge  │  ← 볼트 유사도 + LLM 평가
                └────────┬─────────┘
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
       [관련성 충분]           [부족 → 재검색]
              │                     │
     ┌────────▼─────────┐           └──▶ GapAnalyzer (루프)
     │   Synthesizer    │  ← 왜 알아야 하는지 설명 생성
     └────────┬─────────┘
              │
     ┌────────▼─────────┐
     │ TelegramDelivery │  → 문서 링크 + 핵심 요약 전송
     └────────┬─────────┘
              │
    (사용자 Telegram 답장 도착 시)
              │
     ┌────────▼─────────┐
     │  HumanFeedback   │  ← "더 깊이 파줘" / "다른 방향으로"
     └──────────────────┘
```

---

## 노드별 역할

### VaultReader
- ChromaDB에서 최근 활성화된 주제 벡터 추출
- 어떤 기업·기술·개념에 대한 메모가 가장 많은지 파악
- 출력: `user_context` — 관심 주제 리스트 + 각 주제의 현재 이해 수준

### GapAnalyzer
- `user_context`를 LLM에 전달해 "이 사람이 아직 모르는 것"을 추론
- 볼트에 TSMC 메모가 있지만 CoWoS·SoIC 패키징 내용이 없으면 → 탐색 쿼리 생성
- 출력: `knowledge_queries` — 검색할 키워드·개념 목록

### Scout 노드들 (병렬 실행)
| 노드 | 소스 | 탐색 대상 |
|------|------|-----------|
| PaperScout | arXiv, Semantic Scholar | 기술 논문, 연구 결과 |
| DocScout | SEC EDGAR, DART, 증권사 | 공시, IR 자료, 산업 리포트 |
| TechScout | GitHub, 공식 문서, 기술 블로그 | 기술 문서, 오픈소스 동향 |

### RelevanceJudge
- 수집된 문서를 볼트 벡터와 유사도 비교
- LLM으로 "이게 실제로 투자 판단에 도움이 되는가" 평가
- 기준 미달 시 GapAnalyzer로 되돌아가 다른 쿼리 생성 (최대 3회 루프)

### Synthesizer
- 선별된 문서에서 핵심만 추출
- "왜 지금 이걸 알아야 하는가"를 볼트 맥락과 연결해서 설명
- 원문 링크 보존

### TelegramDelivery
- 요약 + 원문 링크 전송
- Digest/{date}.md에도 기록

### HumanFeedback (양방향)
- 사용자 Telegram 답장 수신
- "더 깊이", "다른 방향", "이건 필요 없어" 등 지시 처리
- 그래프 상태를 업데이트해 다음 루프에 반영

---

## LangGraph 선택 이유

| 기능 | 현재 (선형 파이프라인) | LangGraph |
|------|----------------------|-----------|
| 조건 분기 | 불가 (if/else 하드코딩) | 엣지 조건으로 동적 라우팅 |
| 루프 | 불가 | 내장 지원 (RelevanceJudge → GapAnalyzer) |
| 병렬 실행 | 불가 | 노드 병렬 실행 내장 |
| 상태 관리 | 없음 | `TypedDict` State로 전 노드 공유 |
| Human-in-the-loop | 없음 | `interrupt()` 내장 |
| 체크포인트 | 없음 | SQLite/Redis 저장 → 중단 후 재개 |

---

## 구현 시 기술 스택

```
langgraph          → 그래프 오케스트레이션
langchain-core     → 공통 인터페이스 (LLM, Tool, Message)
anthropic / groq   → LLM 노드 (Synthesizer, GapAnalyzer)
chromadb           → VaultReader 벡터 검색
arxiv              → PaperScout
sec-edgar-downloader → DocScout
requests / bs4     → TechScout 웹 크롤링
python-telegram-bot → TelegramDelivery + HumanFeedback
```

---

## 마이그레이션 전략 (미결)

현재 뉴스 파이프라인과의 관계를 결정해야 함:

**Option A — 완전 대체**
뉴스 수집 파이프라인을 LangGraph로 전면 교체.
구현 기간 길고 리스크 있음.

**Option B — 병행 추가**
기존 뉴스 파이프라인 유지 + Knowledge Agent를 별도 스케줄로 추가.
빠르게 시작 가능, 점진적 전환.

**Option C — 뉴스를 소스 중 하나로 편입**
LangGraph 그래프 내에 NewsScout 노드를 추가해서
기존 뉴스 수집 로직을 Scout 노드 중 하나로 흡수.

---

## 미결 질문

설계 확정 전에 답이 필요한 항목들:

1. **"전문 지식"의 범위** — 반도체 공정 같은 딥테크인가, 기업 전략·산업 구조 같은 투자 맥락인가?
2. **소스 우선순위** — arXiv 논문 / SEC·DART 공시 / 회사 기술 블로그 / YouTube 강의 중 어느 것이 가장 유용한가?
3. **뉴스 파이프라인** — 완전 대체 vs 병행 (Option A/B/C)?
4. **Telegram 양방향** — 답장으로 검색 방향 조정하는 흐름이 필요한가?

---

## 관련 문서

- [proactive-telegram.md](proactive-telegram.md) — 현재 Commander + Briefing 설계
- [commander-telegram-flow.md](commander-telegram-flow.md) — Commander 메시지 흐름 상세
- [system-overview.md](system-overview.md) — 전체 시스템 개요


주식투자를 위한 테크니컬 보고서 (ai, 반도체, 바이오, 헬스케어, 디스플레이, 2차전지, 자동차)