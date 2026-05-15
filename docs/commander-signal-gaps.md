# Commander Agent — 현황 vs 참조 설계 비교 및 개선 포인트

참조: `a_0504_hanky/docs/requirements_personal_llm_trader.md`

---

## 현재 Commander 구현 현황

| 파일 | 역할 |
|------|------|
| `scanner.py` | Daily 노트 읽기 → 휴리스틱 + LLM 중요도 점수 (0~1) |
| `dispatcher.py` | 상위 스코어 기업 → Groq LLM → 액션 명령 (TYPE/TITLE/BODY/ACTIONS) |
| `watchlist_recommender.py` | Daily 노트 분석 → 신규 편입 후보 5개 추천 |
| `notifier.py` | 결과 → Inbox.md + Telegram 전송 |

### scanner.py 점수 계산 방식

```
휴리스틱 score = news_count(0.35) + star_avg(0.45) + keyword_hits(0.20)
LLM refine    = (휴리스틱 + LLM score) / 2  ← score ≥ 0.3 이고 synthesis 있을 때만
```

키워드 목록: 급등/급락/실적/계약/인수/합병/파산/제재/어닝/가이던스 등 30개

---

## 참조 설계(personal_llm_trader)에서 가져올 것

### 1. 수치 기반 트리거 7가지 — 현재 없음

`requirements_personal_llm_trader.md`의 Signal Detector 정의:

| 트리거 | 조건 | 현재 구현 |
|--------|------|-----------|
| 가격 알림 | 목표가 / 손절가 도달 | ❌ |
| 변동성 급증 | 일일 수익률 > 30일 평균 2σ | ❌ |
| 거래량 급증 | 거래량 > 20일 평균 3배 | ❌ |
| 공시 발생 | 보유·관심 종목 신규 공시 | ❌ |
| 실적 발표 | D-3 / 당일 / 결과 | ❌ |
| **뉴스 급증** | 24시간 내 종목 관련 뉴스 5건 초과 | △ (news_count로 간접 반영) |
| 커뮤니티 화제 | 언급 빈도 전주 대비 3배 초과 | ❌ |

현재 scanner.py는 뉴스 수 + 별점 + 키워드 기반 **상대 중요도** 평가이고,
**절대 기준 수치 트리거**는 없다. 가격/거래량 데이터를 수집하지 않기 때문.

**구현 방향**: yfinance로 일별 가격·거래량 수집 → `data/prices.db`(SQLite) 저장
→ 매 실행 시 트리거 조건 체크 → 발화 시 scanner 결과에 신호 플래그 추가.

```python
# 추가할 신호 구조 (scanner.py ScanResult에 병합)
@dataclass
class PriceSignal:
    ticker: str
    signal_type: str   # "volume_surge" | "volatility" | "earnings_due"
    value: float       # 실제 수치 (배율, σ 등)
    threshold: float   # 기준값
    description: str   # "거래량 3.8배 (20일 평균 대비)"
```

---

### 2. ticker_extractor의 STOP_WORDS — 현재 없음

`a_0504_hanky/analyst/ticker_extractor.py`:

```python
STOP_WORDS = {"USD", "KRW", "ETF", "GDP", "CEO", "CFO", "PER", "EPS", "AI", "API"}
```

현재 `src/llm/company_index.py`의 `_stage1_ticker_match()`가 뉴스 제목에서
티커 문자열을 단순 substring 검색하는데, "AI", "EPS", "CEO" 같은 약어가
오탐을 일으킬 수 있다.

**적용 위치**: `src/llm/analyzer.py`의 `_stage1_ticker_match()`

```python
_TICKER_STOP_WORDS = {"USD", "KRW", "ETF", "GDP", "CEO", "CFO",
                      "PER", "EPS", "AI", "API", "IPO", "ROE", "ROA"}

def _stage1_ticker_match(item: NewsItem, company: str) -> bool:
    ticker = TICKER_INDEX.get(company, "")
    if not ticker or ticker in _TICKER_STOP_WORDS:
        return False
    text = f"{item.title} {item.snippet or ''}"
    return ticker in text
```

---

### 3. Pre-Trade Checklist / Devil's Advocate — 현재 없음

Commander가 액션 명령(ACTIONS)을 생성하지만,
사용자가 실제 매매 결정 전에 **반론을 강제로 보는 구조**가 없다.

`requirements_personal_llm_trader.md` 설계:
```
매매 의도 입력 → LLM이 5단계 질문 강제
→ "데블스 어드보킷" 모드로 반론 3가지 생성
→ 인간이 그래도 진행/취소
→ 모든 답변 trade_log 기록
```

**구현 방향**: Telegram Bot 명령어로 구현.

```
/trade buy NVDA → 체크리스트 5단계 대화
                → LLM 반론 3가지
                → /confirm or /cancel
                → trade_log.json 기록
```

`run_telegram_bot.py`에 `/trade` 핸들러 추가. trade_log는 `data/trade_log.json` 또는
`agent_vault/Trade Log/` Obsidian 노트로 저장 가능.

---

### 4. 자동 복기 (30/90/180일) — 현재 없음

`requirements_personal_llm_trader.md`:
```
trade_review: 30 | 90 | 180일 후 LLM이 자동 검토
  - "당시 가설이 맞았는가" (yes / partial / no)
  - 실제 주가 변화와 대조
  - 텔레그램 알림
```

**구현 방향**: `run_daily.sh` 실행 시 trade_log 날짜 체크
→ 30/90/180일 경과 항목 발견 시 yfinance로 현재가 조회
→ LLM이 가설 적중 여부 평가 → Telegram 전송.

---

### 5. API 비용 상한 알림 — 현재 없음

`requirements_personal_llm_trader.md`:
```
LLM API 비용 월 $20 초과 시 알림 (의도치 않은 폭증 방지)
```

현재 dispatcher.py가 Groq API를 하루 최대 3회 호출하는 상한(`_MAX_COMMANDS=3`)만 있고,
누적 비용 추적은 없다.

**구현 방향**: `data/api_usage.json`에 일별 LLM 호출 횟수 기록
→ 월간 추정 비용 계산 → 임계값 초과 시 Telegram 경고.

---

## 우선순위 정리

| 항목 | 임팩트 | 난이도 | 우선순위 |
|------|--------|--------|----------|
| STOP_WORDS 추가 | 오탐 방지 | 낮음 | **즉시** |
| 뉴스 급증 트리거 수치화 | 정확도 향상 | 낮음 | **즉시** — news_count 임계값 5건으로 절대화 |
| 가격/거래량 트리거 | 신호 다양화 | 중간 | Phase 2 |
| Pre-Trade Checklist | 의사결정 품질 | 중간 | Phase 2 |
| 자동 복기 | 학습 루프 | 높음 | Phase 3 |
| API 비용 알림 | 비용 제어 | 낮음 | Phase 2 |

---

## 즉시 적용 가능한 것 (코드 변경 최소)

### 뉴스 급증 트리거 수치화

현재 scanner.py의 `_heuristic_score()`에서 `news_count / 15.0`으로 정규화하는데,
절대 기준 트리거를 별도로 추가:

```python
# scanner.py ScanResult에 필드 추가
news_surge: bool = False   # news_count >= 5이면 True

# _parse_daily_note() 이후
if parsed["news_count"] >= 5:
    result.news_surge = True
```

dispatcher.py 프롬프트에 `news_surge=True` 시 "🔴 뉴스 급증" 태그 추가.

### STOP_WORDS — analyzer.py에 즉시 추가 가능

위 섹션 2 참조.
