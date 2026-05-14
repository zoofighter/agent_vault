---
title: Watchlist Recommender — 신규 편입 후보 추천 로직
type: system-doc
created: 2026-05-14
---

# Watchlist Recommender

> Commander Agent의 Phase 4. 하루 Daily 노트를 분석해서 현재 추적 목록(38개사)에
> 없지만 추가할 만한 기업을 매일 추천하는 기능.

---

## 왜 필요한가

현재 38개사는 처음에 수동으로 선정한 목록이다.  
시장은 매일 변하고, 오늘 CATL 뉴스에 등장한 공급업체나 NVIDIA 뉴스에 나온 AI 클라우드 기업이
내일 더 중요해질 수 있다. 수동으로 계속 목록을 업데이트하는 것은 비효율적이다.

Recommender는 **뉴스가 자연스럽게 언급하는 기업들**을 자동으로 포착해서
"이 기업 추가하는 게 어때요?"라고 먼저 말해준다.

---

## 5가지 신호

| 신호 | 설명 | 점수 기여 |
|------|------|-----------|
| **뉴스 제목 직접 언급** | 추적 기업 Daily 노트의 뉴스 제목에 타사 이름/ticker 등장 | 높음 |
| **종합분석 텍스트 언급** | `## 종합 분석` 블록에서 언급된 기업 (맥락 포함) | 높음 |
| **볼트 Memo 언급** | 사용자가 `Memos/*.md`에 직접 언급한 기업 | 매우 높음 |
| **테마 섹터 동반자** | 오늘 강세 테마에서 핵심적이지만 미추적 기업 | 중간 |
| **공급망·경쟁사 관계** | 추적 기업의 고객사·공급업체·경쟁사로 자주 등장 | 중간 |

---

## 처리 흐름

```
① _collect_daily_content()
   agent_vault/Companies/*/*/Daily/{date}*.md 전체 읽기
   → 기업명, 뉴스 제목 15개, 종합분석 800자 추출

② _collect_memo_text()
   */Memos/*.md 전체 읽기 (최대 3000자)
   → 사용자가 직접 쓴 메모에서 기업 언급 수집

③ _load_existing(companies.csv)
   현재 추적 중인 기업명 + ticker 집합 로드
   → 추천 결과에서 이미 추적 중인 기업 제거용

④ _build_prompt()
   ① + ② + ③ 를 Groq LLM 프롬프트로 조합
   → "이 뉴스들에서 추적 목록에 없는 중요 기업을 찾아라"

⑤ _call_groq()
   llama-3.3-70b-versatile 호출
   → JSON 형식: {candidates: [{name, ticker, region, reason, signals, score, source_companies}]}

⑥ _parse_candidates()
   JSON 파싱 → WatchlistCandidate 리스트
   → 이미 추적 중인 기업 재필터링 (LLM 실수 방지)
   → score 내림차순 정렬, 최대 5개

⑦ push_watchlist_recs()
   → Digest/{date}.md 에 [!info] callout 추가
   → Telegram 전송
```

---

## WatchlistCandidate 데이터 구조

```python
@dataclass
class WatchlistCandidate:
    name: str              # 기업명 (영문)
    ticker: str            # 티커 또는 "없음"
    region: str            # US/KR/CN/TW/JP/EU
    reason: str            # 한 줄 추천 이유
    signals: list[str]     # 어떤 신호에서 잡혔는지 (최대 2개)
    score: float           # 0~10 (LLM이 판단)
    source_companies: list[str]  # 언급 출처 기업 목록
```

---

## 점수 기준

LLM이 0~10점으로 직접 평가. 기준 예시:

| 점수 | 해석 |
|------|------|
| 9~10 | 오늘 여러 기업에서 반복 언급, 핵심 공급망 관계 |
| 7~8  | 1~2개 기업에서 구체적 관계로 언급 |
| 5~6  | 섹터 동반자, 간접 언급 |
| 4 미만 | 일회성 언급, 낮은 관련성 |

---

## 출력 형식

**Digest/{date}.md** (`[!info]` callout):

```
> [!info] 신규 편입 후보 — 2026-05-14
>
> 오늘 활동 기반으로 추적 목록에 추가할 만한 기업 4개:
>
> **1. Stellantis (STLA)** [EU] 8.0점 · 출처: BYD
> → BYD와의 협상을 통해 유럽 시장 공급망을 확대하면서 전기차 성장 동력에 기여
> → 신호: BYD 협상 / 유럽 시장 진출
>
> **2. CoreWeave** [US] 7.5점 · 출처: NVIDIA
> → NVIDIA의 Vera CPU를 도입함으로써 AI 컴퓨팅 성능을 향상
> → 신호: NVIDIA와 협력
```

**Telegram 메시지**:

```
📋 신규 편입 후보 — 2026-05-14

1. Stellantis (STLA) [EU] 8.0점
   BYD와의 협상을 통해 유럽 시장 공급망 확대...

2. CoreWeave [US] 7.5점
   NVIDIA의 Vera CPU 도입으로 AI 컴퓨팅 성능 향상...
```

---

## 실행 위치

`run_commander.py`의 Phase 4에 통합됨.
Commander 실행 시 자동으로 함께 실행된다.

```
[Phase 1] Daily 노트 스캔
[Phase 2] 액션 명령 생성
[Phase 3] Inbox.md 기록
[Phase 4] 신규 편입 후보 탐색  ← 여기
```

수동 실행도 가능:

```python
from src.commander.watchlist_recommender import recommend
candidates = recommend(vault_path, "2026-05-14")
```

---

## 추천 후 실제 추가 방법

Recommender는 추천만 한다. 실제 편입은 수동으로:

1. Telegram에서 추천 목록 확인
2. 관심 기업이 있으면 `companies.csv`에 행 추가
3. 볼트 동기화 실행:

```bash
python -m src.obsidian.company_manager --vault ./agent_vault
```

자동 편입 기능은 의도적으로 제외했다.
잘못된 기업이 자동 추가되는 것보다 사용자가 최종 판단하는 게 낫다.

---

## 제약 사항

- 하루 최대 추천 5개 (Groq API 비용 및 노이즈 제어)
- LLM 특성상 가끔 이미 추적 중인 기업을 추천하는 경우가 있음 → 코드에서 후필터링으로 제거
- 언어 혼용(한자·일문 등)이 간헐적으로 발생할 수 있음 → 결과 확인 후 판단

---

## 관련 파일

| 파일 | 역할 |
|------|------|
| `src/commander/watchlist_recommender.py` | 추천 로직 핵심 |
| `src/commander/notifier.py` | `push_watchlist_recs()` — Digest + Telegram 기록 |
| `run_commander.py` | Phase 4에서 호출 |
| `companies.csv` | 현재 추적 기업 목록 (추천 제외 기준) |

---

## 관련 문서

- [commander-telegram-flow.md](commander-telegram-flow.md) — Commander 전체 흐름
- [proactive-telegram.md](proactive-telegram.md) — Telegram 메시징 설계
