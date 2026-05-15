"""
매크로 지표 신호 감지 + LLM 해석
"""

import json
import re
from dataclasses import dataclass

import ollama

from src.macro.collector import MacroItem

_LLM_MODEL = "gemma4:e2b"

_TRIGGERS = [
    {
        "code": "FEDFUNDS", "signal_type": "rate_move",
        "condition": lambda i: abs(i.change) >= 0.25,
        "alert_level": "critical",
        "action_hint": "금리 변동 — 성장주 PER·채권 영향 점검 필요",
    },
    {
        "code": "CPIAUCSL", "signal_type": "inflation_surge",
        "condition": lambda i: i.change_pct > 0.4,
        "alert_level": "warning",
        "action_hint": "물가 가속 — 원자재·에너지주 및 금리 인상 시나리오 검토",
    },
    {
        "code": "^VIX", "signal_type": "vix_surge",
        "condition": lambda i: i.value > 25,
        "alert_level": "warning",
        "action_hint": "공포지수 급등 — 포트폴리오 방어 자산 비중 점검",
    },
    {
        "code": "KRW=X", "signal_type": "dollar_surge",
        "condition": lambda i: i.change > 20,
        "alert_level": "warning",
        "action_hint": "달러 강세 — 신흥국 자본 유출·수출주 유불리 점검",
    },
    {
        "code": "INTDSRKRM193N", "signal_type": "kr_rate_move",
        "condition": lambda i: abs(i.change) >= 0.25,
        "alert_level": "warning",
        "action_hint": "한국 기준금리 변동 — KRX 금융주·성장주 영향 점검",
    },
    {
        "code": "IRLTLT01JPM156N", "signal_type": "jp_rate_move",
        "condition": lambda i: abs(i.change) >= 0.10,
        "alert_level": "warning",
        "action_hint": "일본 기준금리 변동 — 엔화·일본 수출주 영향 점검",
    },
    {
        "code": "ECBDFR", "signal_type": "eu_rate_move",
        "condition": lambda i: abs(i.change) >= 0.25,
        "alert_level": "warning",
        "action_hint": "ECB 기준금리 변동 — 유럽 금융주·달러 강세 점검",
    },
    {
        "code": "INTDSRCNM193N", "signal_type": "cn_rate_move",
        "condition": lambda i: abs(i.change) >= 0.10,
        "alert_level": "warning",
        "action_hint": "중국 기준금리 변동 — 홍콩·소비·부동산주 영향 점검",
    },
]


@dataclass
class MacroSignal:
    indicator: str
    signal_type: str
    value: float
    threshold_desc: str
    alert_level: str
    description: str
    action_hint: str


def detect_signals(items: list[MacroItem]) -> list[MacroSignal]:
    item_map = {i.code: i for i in items}
    signals = []
    for t in _TRIGGERS:
        item = item_map.get(t["code"])
        if item and t["condition"](item):
            signals.append(MacroSignal(
                indicator=item.name,
                signal_type=t["signal_type"],
                value=item.value,
                threshold_desc=f"변화 {item.change:+.2f} ({item.change_pct:+.2f}%)",
                alert_level=t["alert_level"],
                description=f"{item.name} {item.value}{item.unit} — {item.change:+.4f}",
                action_hint=t["action_hint"],
            ))
    return signals


def build_summary(items: list[MacroItem], signals: list[MacroSignal]) -> str:
    lines = [f"- {i.name}: {i.value}{i.unit} ({i.change_pct:+.2f}%)" for i in items]
    signal_lines = [f"- [{s.alert_level.upper()}] {s.action_hint}" for s in signals]

    prompt = (
        "다음은 오늘 매크로 지표 현황이다. 투자자 관점에서 2~3문장으로 핵심 시사점을 요약해라.\n\n"
        f"지표:\n" + "\n".join(lines) +
        (f"\n\n발동 신호:\n" + "\n".join(signal_lines) if signal_lines else "") +
        "\n\n한국어로, 구체적 수치를 포함해서 작성."
    )
    try:
        resp = ollama.generate(model=_LLM_MODEL, prompt=prompt,
                               options={"num_predict": 200}, think=False)
        return resp.response.strip()
    except Exception:
        return " | ".join(f"{i.name} {i.value}{i.unit}" for i in items[:5])


def build_indicator_interpretation(item: MacroItem) -> str:
    prompt = (
        f"{item.name}({item.code})이 현재 {item.value}{item.unit}이고 "
        f"전 대비 {item.change:+.4f} ({item.change_pct:+.2f}%) 변화했다.\n"
        "주식 투자자 관점에서 이 수치가 의미하는 것을 한 문장으로 설명해라."
    )
    try:
        resp = ollama.generate(model=_LLM_MODEL, prompt=prompt,
                               options={"num_predict": 100}, think=False)
        return resp.response.strip()
    except Exception:
        return f"{item.change_pct:+.2f}% 변화"
