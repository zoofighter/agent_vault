# 요건정의서 — 매크로/금리 모듈

**버전** 0.1 · **작성일** 2026-05-15

---

## 1. 배경 및 목적

### 1-1. 현재 시스템의 공백

AgentVault는 38개 기업의 뉴스를 수집·분석하지만,
이 기업들의 밸류에이션과 섹터 흐름을 결정하는 **매크로 컨텍스트**가 없다.

| 매크로 변화 | 종목 영향 | 현재 시스템 |
|------------|----------|------------|
| 금리 +25bp | 성장주 PER 압축, 채권 약세 | 감지 불가 |
| CPI 상승 | 원자재·에너지주 강세 | 감지 불가 |
| VIX 급등 | 전체 리스크 오프 | 감지 불가 |
| 달러 강세 | 신흥국 자본 유출, 수출주 유리 | 감지 불가 |

### 1-2. 목표

- 금리·물가·달러·시장변동성 등 핵심 매크로 지표를 **일 1회 자동 수집**
- Obsidian 볼트 `Macro/` 폴더에 지표 히스토리 + LLM 해석 저장
- 임계값 초과 시 **Commander 신호** 발동 → Telegram 알림
- 기업 Daily 노트 생성 시 매크로 컨텍스트를 프롬프트에 자동 주입

### 1-3. 비목표

- 자동 매매 신호 생성 (X)
- 금리/환율 예측 모델 (X)
- 실시간 틱 데이터 (X) — 일 1회 수집으로 충분
- 선물·옵션 데이터 (X)

---

## 2. 추적 대상 지표 (12개)

| 카테고리 | 지표명 | 코드 | 소스 | 수집 빈도 |
|----------|--------|------|------|----------|
| **금리** | 미국 기준금리 | FED_FUNDS | FRED | 일 1회 |
| | 10년물 국채수익률 | DGS10 | FRED | 일 1회 |
| | 2년물 국채수익률 | DGS2 | FRED | 일 1회 |
| **물가** | 소비자물가지수 | CPIAUCSL | FRED | 월 1회 (발표일) |
| | PCE 물가 | PCEPI | FRED | 월 1회 (발표일) |
| **고용** | 실업률 | UNRATE | FRED | 월 1회 (발표일) |
| | 비농업 고용 | PAYEMS | FRED | 월 1회 (발표일) |
| **달러** | 달러인덱스 | DTWEXBGS | FRED | 일 1회 |
| | USD/KRW 환율 | KRW=X | yfinance | 일 1회 |
| **시장** | S&P500 | ^GSPC | yfinance | 일 1회 |
| | VIX (공포지수) | ^VIX | yfinance | 일 1회 |
| **원자재** | WTI 원유 | CL=F | yfinance | 일 1회 |

> FRED API 키 없이도 yfinance 지표(VIX, S&P500, USD/KRW, WTI)만으로 Phase 1 시작 가능.
> FRED 지표는 Phase 2에서 추가.

---

## 3. 볼트 구조 추가

```
agent_vault/
└── Macro/
    ├── Indicators/
    │   ├── 금리.md        # FED_FUNDS, DGS10, DGS2, 장단기 스프레드
    │   ├── 물가.md        # CPI, PCE — 월별 갱신
    │   ├── 고용.md        # UNRATE, PAYEMS — 월별 갱신
    │   ├── 달러.md        # DTWEXBGS, USD/KRW
    │   └── 시장.md        # S&P500, VIX, WTI
    ├── Daily/             # 매크로 일일 요약 노트 — 시스템 전용
    │   └── {YYYY-MM-DD}.md
    └── Memos/             # 사용자 투자 메모 — 시스템 수정 불가
```

### Indicators/*.md 파일 구조

```markdown
---
updated: 2026-05-15
category: 금리
---

## 현재 수치

| 지표 | 현재값 | 전일 대비 | 전월 대비 |
|------|--------|----------|----------|
| 기준금리 (FED_FUNDS) | 5.25% | - | - |
| 10년물 (DGS10) | 4.42% | -0.03%p | +0.12%p |
| 2년물 (DGS2) | 4.89% | -0.01%p | +0.08%p |
| 장단기 스프레드 | -0.47%p | - | - |

## LLM 해석

{gemma4:e2b가 생성한 2~3문장 시장 해석}

## 투자 시사점

{성장주/가치주/채권 관점 시사점 1~2문장}

## 히스토리 (최근 10일)

| 날짜 | FED_FUNDS | DGS10 | DGS2 |
|------|-----------|-------|------|
| ... | ... | ... | ... |
```

### Macro/Daily/{date}.md 파일 구조

```markdown
---
date: 2026-05-15
type: macro_daily
---

## 오늘의 매크로 요약

{전체 지표를 종합한 LLM 2~3문장 요약}

## 주요 지표

| 지표 | 값 | 변화 | 신호 |
|------|-----|------|------|
| VIX | 18.4 | +2.1 | ⚠️ |
| S&P500 | 5,312 | -0.8% | - |
| WTI | $78.2 | +1.2% | - |
| USD/KRW | 1,352 | +3 | - |

## 신호 발동

{트리거 발동 시 내용, 없으면 "이상 신호 없음"}

## 매크로 뉴스

{Google News에서 수집한 FOMC/CPI 관련 뉴스 3~5개}
```

---

## 4. 데이터 수집 모듈

### 4-1. 신규 파일: `src/macro/collector.py`

```python
from dataclasses import dataclass
from datetime import date

@dataclass
class MacroItem:
    code: str           # "FED_FUNDS", "^VIX" 등
    name: str           # "미국 기준금리"
    category: str       # "금리" | "물가" | "고용" | "달러" | "시장" | "원자재"
    value: float
    prev_value: float   # 전일/전월 값
    change: float       # 절대 변화
    change_pct: float   # % 변화
    unit: str           # "%" | "pt" | "원" | "달러"
    as_of: date
    source: str         # "FRED" | "yfinance"

def fetch_fred(indicator: str) -> MacroItem:
    """FRED API로 단일 지표 수집. FRED_API_KEY 환경변수 필요."""

def fetch_yfinance(ticker: str, name: str, category: str, unit: str) -> MacroItem:
    """yfinance로 시장 지표 수집. API 키 불필요."""

def collect_all() -> list[MacroItem]:
    """전체 지표 수집. FRED 키 없으면 yfinance 지표만 수집."""
```

**환경변수**: `FRED_API_KEY` (없으면 FRED 지표 건너뜀, yfinance만 동작)

### 4-2. 신규 파일: `src/macro/analyzer.py`

```python
def detect_signals(items: list[MacroItem]) -> list[MacroSignal]:
    """임계값 초과 지표 → MacroSignal 반환."""

def build_summary(items: list[MacroItem]) -> str:
    """전체 지표 → LLM 2~3문장 요약 (gemma4:e2b)."""

def build_indicator_interpretation(item: MacroItem) -> str:
    """단일 지표 → LLM 투자 시사점 1~2문장."""
```

### 4-3. 신규 파일: `src/macro/writer.py`

```python
def write_indicators(items: list[MacroItem], vault_path: Path):
    """Macro/Indicators/*.md 갱신. 히스토리 최대 30일 유지."""

def write_daily(items: list[MacroItem], signals: list[MacroSignal],
                news: list[str], vault_path: Path, date_str: str):
    """Macro/Daily/{date}.md 생성."""
```

### 4-4. 신규 파일 (선택): `src/sources/macro_news.py`

기존 `google_news.py` 패턴 재사용:

```python
_MACRO_QUERIES = [
    "Federal Reserve interest rate",
    "FOMC meeting decision",
    "CPI inflation report",
    "US dollar index",
    "VIX volatility",
]

def fetch_macro_news(days: int = 1) -> list[NewsItem]:
    """Google News RSS로 매크로 뉴스 수집."""
```

---

## 5. 신호 트리거 (4개)

```python
@dataclass
class MacroSignal:
    indicator: str      # "VIX"
    signal_type: str    # "vix_surge"
    value: float        # 실제 값 (26.3)
    threshold: float    # 임계값 (25.0)
    alert_level: str    # "warning" | "critical"
    description: str    # "공포지수 26.3 — 임계값(25) 초과"
    action_hint: str    # Commander 프롬프트에 주입할 힌트
```

| 신호 | 조건 | alert_level | Commander 힌트 |
|------|------|-------------|----------------|
| `rate_move` | FED_FUNDS 전월 대비 ±25bp 이상 | critical | "금리 변동 — 성장주 PER·채권 영향 점검 필요" |
| `inflation_surge` | CPI MoM > 0.4% | warning | "물가 가속 — 원자재·에너지주 및 금리 인상 시나리오 검토" |
| `vix_surge` | VIX > 25 | warning | "공포지수 급등 — 포트폴리오 방어 자산 비중 점검" |
| `dollar_surge` | USD/KRW 주간 변화 > +20원 | warning | "달러 강세 — 신흥국 자본 유출·수출주 유불리 점검" |

---

## 6. 기존 파이프라인 연계

### 6-1. `collect_news.py` 수집 흐름 앞단 추가

```python
# collect_news.py main() 상단에 추가
from src.macro.collector import collect_all as collect_macro
from src.macro.analyzer import detect_signals, build_summary
from src.macro.writer import write_indicators, write_daily

macro_items = collect_macro()
macro_signals = detect_signals(macro_items)
write_indicators(macro_items, VAULT_PATH)
write_daily(macro_items, macro_signals, [], VAULT_PATH, date_str)

# 이후 기존 기업 수집 흐름 그대로
```

### 6-2. `src/commander/dispatcher.py` 매크로 컨텍스트 주입

```python
# _build_prompt() 내부에 추가
macro_daily = _read_macro_daily(vault_path, date_str)  # Macro/Daily/{date}.md 첫 500자
macro_signals_str = _format_signals(macro_signals)

prompt = f"""...
매크로 환경 ({date_str}):
{macro_daily[:400]}

발동된 매크로 신호:
{macro_signals_str or "없음"}
...
"""
```

### 6-3. `run_briefing.py` 매크로 요약 섹션 추가

브리핑 앞부분에 "오늘의 매크로" 섹션 삽입:

```
📊 오늘의 매크로
VIX 18.4 (+2.1) | S&P500 5,312 (-0.8%) | WTI $78.2 (+1.2%) | USD/KRW 1,352
→ {LLM 한 줄 요약}
```

### 6-4. ChromaDB 매크로 컬렉션 (선택, Phase 3)

기존 `src/obsidian/embedder.py`의 `embed_files()` 재사용:

```python
# Macro/Indicators/*.md + Macro/Daily/*.md 임베딩
# 컬렉션명: "macro" (기존 "vault"와 분리)
```

Commander가 기업 분석 시 매크로 컬렉션도 조회 → 관련 지표 컨텍스트 자동 포함.

---

## 7. 기술 스택

| 역할 | 선택 | 비고 |
|------|------|------|
| 금리/거시지표 | `fredapi` | FRED API 키 필요 (무료, [fred.stlouisfed.org](https://fred.stlouisfed.org/docs/api/api_key.html)) |
| 시장 지표 | `yfinance` | 이미 사용 중, 키 불필요 |
| LLM 해석 | `gemma4:e2b` (Ollama) | 기존 analyzer.py와 동일 |
| 저장 | Obsidian Markdown | 기존 볼트 구조 확장 |
| 임베딩 | ChromaDB `macro` 컬렉션 | Phase 3, 기존 embedder.py 재사용 |
| 매크로 뉴스 | Google News RSS | Phase 4, 기존 google_news.py 패턴 |

---

## 8. 구현 순서 (Phase)

### Phase 1 — 수집 + 볼트 저장 (yfinance만, FRED 없이 동작)

| 순서 | 작업 | 산출물 |
|------|------|--------|
| 1 | `src/macro/` 패키지 생성 | `__init__.py` |
| 2 | yfinance 지표 수집 | `collector.py` — `fetch_yfinance()` |
| 3 | Indicators/*.md 갱신 | `writer.py` — `write_indicators()` |
| 4 | Macro/Daily/{date}.md 생성 | `writer.py` — `write_daily()` |
| 5 | `collect_news.py` 앞단 연결 | 기존 파일 수정 |

**검증**: `python -c "from src.macro.collector import collect_all; print(collect_all())"` 실행 후 `agent_vault/Macro/` 폴더 생성 확인.

### Phase 2 — 신호 트리거 + Commander 연계

| 순서 | 작업 | 산출물 |
|------|------|--------|
| 1 | 신호 감지 로직 | `analyzer.py` — `detect_signals()` |
| 2 | LLM 해석 생성 | `analyzer.py` — `build_summary()` |
| 3 | FRED API 연동 | `collector.py` — `fetch_fred()` |
| 4 | dispatcher.py 프롬프트 주입 | 기존 파일 수정 |

### Phase 3 — Briefing 연계 + ChromaDB 임베딩

| 순서 | 작업 | 산출물 |
|------|------|--------|
| 1 | run_briefing.py 매크로 섹션 | 기존 파일 수정 |
| 2 | ChromaDB macro 컬렉션 구축 | embedder.py 재사용 |

### Phase 4 — 매크로 뉴스 수집 (선택)

| 순서 | 작업 | 산출물 |
|------|------|--------|
| 1 | Google News RSS 매크로 쿼리 | `src/sources/macro_news.py` |
| 2 | Macro/Daily/ 노트 하단 뉴스 추가 | `writer.py` 수정 |

---

## 9. 환경변수

```bash
# .env 또는 LaunchAgent plist에 추가
FRED_API_KEY=your_key_here   # 없으면 yfinance만 동작 (Phase 1은 불필요)
```

FRED API 키 발급: https://fred.stlouisfed.org/docs/api/api_key.html (무료, 즉시 발급)

---

## 10. 기존 구조와의 충돌 없음 확인

| 확인 항목 | 상태 |
|----------|------|
| `company_dir()` 경로 규칙 | `Macro/`는 `Companies/` 외부 → 충돌 없음 |
| ChromaDB 컬렉션 | 신규 `macro` 컬렉션 분리 → 기존 `vault` 컬렉션 영향 없음 |
| `companies.csv` | 수정 없음 — 매크로는 별도 설정 파일 또는 하드코딩 |
| `collect_news.py` | 앞단에 3줄 추가만 — 기존 기업 수집 흐름 그대로 |
| `run_daily.sh` | 수정 없음 — collect_news.py가 자동으로 매크로 포함 |

---

## 참조

- `a_0504_hanky/docs/requirements_personal_llm_trader.md` — FRED 지표 목록, macro_indicators 스키마
- `a_0504_hanky/docs/requirements_market_intelligence_x.md` — 매크로 이벤트 캘린더, Investing.com
- `src/sources/google_news.py` — 뉴스 수집 패턴 (macro_news.py 작성 시 재사용)
- `src/obsidian/embedder.py` — ChromaDB 임베딩 (Phase 3 재사용)
