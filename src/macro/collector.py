"""
매크로 지표 수집

FRED API (금리·물가·고용·달러) + yfinance (시장·원자재·환율)
FRED_API_KEY 환경변수 없으면 yfinance 지표만 수집.
"""

import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta

_FRED_KEY = os.environ.get("FRED_API_KEY", "")

# yfinance 수집 대상
_YFINANCE_TARGETS = [
    ("^GSPC",  "S&P500",      "시장",   "pt"),
    ("^VIX",   "VIX",         "시장",   "pt"),
    ("CL=F",   "WTI 원유",    "원자재", "달러"),
    ("KRW=X",  "USD/KRW",     "달러",   "원"),
]

# FRED 수집 대상 (일별 시계열)
_FRED_DAILY = [
    ("DGS10",    "10년물 국채",  "금리", "%"),
    ("DGS2",     "2년물 국채",   "금리", "%"),
    ("DTWEXBGS", "달러인덱스",   "달러", "pt"),
]

# FRED 수집 대상 (월별 시계열 — 최신값만)
_FRED_MONTHLY = [
    ("FEDFUNDS",  "기준금리",   "금리", "%"),
    ("CPIAUCSL",  "CPI",        "물가", "pt"),
    ("PCEPI",     "PCE",        "물가", "pt"),
    ("UNRATE",    "실업률",     "고용", "%"),
    ("PAYEMS",    "비농업고용", "고용", "천명"),
    ("INTDSRKRM193N",   "한국 기준금리", "금리", "%"),
    ("IRLTLT01JPM156N", "일본 10년물",   "금리", "%"),
    ("ECBDFR",          "유럽 기준금리", "금리", "%"),
    ("INTDSRCNM193N",   "중국 기준금리", "금리", "%"),
]


@dataclass
class MacroItem:
    code: str
    name: str
    category: str
    value: float
    prev_value: float
    change: float
    change_pct: float
    unit: str
    as_of: date
    source: str


def _fetch_yfinance_all() -> list[MacroItem]:
    import yfinance as yf
    items = []
    for ticker, name, category, unit in _YFINANCE_TARGETS:
        try:
            hist = yf.Ticker(ticker).history(period="5d")
            if hist.empty or len(hist) < 2:
                continue
            cur = float(hist["Close"].iloc[-1])
            prev = float(hist["Close"].iloc[-2])
            change = round(cur - prev, 4)
            change_pct = round((change / prev) * 100, 2) if prev else 0.0
            items.append(MacroItem(
                code=ticker, name=name, category=category,
                value=round(cur, 2), prev_value=round(prev, 2),
                change=change, change_pct=change_pct,
                unit=unit, as_of=hist.index[-1].date(), source="yfinance",
            ))
        except Exception as e:
            print(f"  [macro] yfinance {ticker} 실패: {e}")
    return items


def _fetch_fred_all() -> list[MacroItem]:
    if not _FRED_KEY:
        return []
    try:
        from fredapi import Fred
        fred = Fred(api_key=_FRED_KEY)
    except Exception as e:
        print(f"  [macro] FRED 초기화 실패: {e}")
        return []

    items = []

    for code, name, category, unit in _FRED_DAILY:
        try:
            s = fred.get_series(code, observation_start=str(date.today() - timedelta(days=10)))
            s = s.dropna()
            if len(s) < 2:
                continue
            cur = round(float(s.iloc[-1]), 4)
            prev = round(float(s.iloc[-2]), 4)
            change = round(cur - prev, 4)
            change_pct = round((change / prev) * 100, 2) if prev else 0.0
            items.append(MacroItem(
                code=code, name=name, category=category,
                value=cur, prev_value=prev,
                change=change, change_pct=change_pct,
                unit=unit, as_of=s.index[-1].date(), source="FRED",
            ))
        except Exception as e:
            print(f"  [macro] FRED {code} 실패: {e}")

    for code, name, category, unit in _FRED_MONTHLY:
        try:
            s = fred.get_series(code, observation_start=str(date.today() - timedelta(days=400)))
            s = s.dropna()
            if len(s) < 2:
                continue
            cur = round(float(s.iloc[-1]), 4)
            prev = round(float(s.iloc[-2]), 4)
            change = round(cur - prev, 4)
            change_pct = round((change / prev) * 100, 2) if prev else 0.0
            items.append(MacroItem(
                code=code, name=name, category=category,
                value=cur, prev_value=prev,
                change=change, change_pct=change_pct,
                unit=unit, as_of=s.index[-1].date(), source="FRED",
            ))
        except Exception as e:
            print(f"  [macro] FRED {code} 실패: {e}")

    return items


def collect_all() -> list[MacroItem]:
    """전체 매크로 지표 수집. FRED 키 없으면 yfinance만."""
    items = _fetch_yfinance_all()
    items += _fetch_fred_all()
    if not _FRED_KEY:
        print("  [macro] FRED_API_KEY 없음 — yfinance 지표만 수집")
    print(f"  [macro] 수집 완료: {len(items)}개 지표")
    return items
