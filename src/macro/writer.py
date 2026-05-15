"""
매크로 지표 → Obsidian 볼트 저장

Macro/Indicators/*.md  — 카테고리별 지표 히스토리 (최대 30일)
Macro/Daily/{date}.md  — 일일 매크로 요약
"""

import re
from datetime import datetime
from pathlib import Path

from src.macro.collector import MacroItem
from src.macro.analyzer import MacroSignal

_CATEGORY_FILES = {
    "금리":   "금리.md",
    "물가":   "물가.md",
    "고용":   "고용.md",
    "달러":   "달러.md",
    "시장":   "시장.md",
    "원자재": "시장.md",  # 원자재는 시장.md에 합산
}

_ALERT_EMOJI = {"critical": "🔴", "warning": "⚠️"}


def _macro_root(vault_path: Path) -> Path:
    root = vault_path / "Macro"
    (root / "Indicators").mkdir(parents=True, exist_ok=True)
    (root / "Daily").mkdir(parents=True, exist_ok=True)
    (root / "Memos").mkdir(parents=True, exist_ok=True)
    return root


def _sign(v: float) -> str:
    return f"+{v}" if v >= 0 else str(v)


def _update_history_table(existing: str, new_row: str, header: str, max_rows: int = 30) -> str:
    """기존 히스토리 테이블에 새 행 추가, max_rows 초과 시 오래된 행 제거."""
    if header not in existing:
        return existing + f"\n{header}\n|------|------|\n{new_row}\n"

    lines = existing.split("\n")
    insert_idx = None
    data_rows = []
    in_table = False
    result = []

    for i, line in enumerate(lines):
        if header in line:
            in_table = True
            result.append(line)
            insert_idx = len(result)
            continue
        if in_table:
            if line.startswith("|---"):
                result.append(line)
                continue
            if line.startswith("|"):
                data_rows.append(line)
                continue
            else:
                in_table = False
                # 새 행 맨 앞에 추가, max_rows 제한
                kept = ([new_row] + data_rows)[:max_rows]
                result.extend(kept)
                result.append(line)
                continue
        result.append(line)

    if in_table:
        kept = ([new_row] + data_rows)[:max_rows]
        result.extend(kept)

    return "\n".join(result)


def write_indicators(items: list[MacroItem], vault_path: Path) -> None:
    """Macro/Indicators/*.md 갱신."""
    root = _macro_root(vault_path)
    ind_dir = root / "Indicators"

    # 카테고리별 그룹
    by_cat: dict[str, list[MacroItem]] = {}
    for item in items:
        fname = _CATEGORY_FILES.get(item.category)
        if not fname:
            continue
        by_cat.setdefault(fname, []).append(item)

    for fname, cat_items in by_cat.items():
        path = ind_dir / fname
        existing = path.read_text(encoding="utf-8") if path.exists() else ""

        # 현재 수치 섹션 재생성
        table_rows = []
        for i in cat_items:
            chg = f"{i.change:+.4f}" if abs(i.change) < 100 else f"{i.change:+.2f}"
            chg_pct = f"{i.change_pct:+.2f}%"
            table_rows.append(f"| {i.name} ({i.code}) | {i.value}{i.unit} | {chg} | {chg_pct} | {i.as_of} |")

        current_block = (
            "## 현재 수치\n\n"
            "| 지표 | 현재값 | 전일/전월 대비 | 변화율 | 기준일 |\n"
            "|------|--------|--------------|--------|--------|\n"
            + "\n".join(table_rows)
        )

        # 기존 파일에서 현재 수치 섹션 교체
        if "## 현재 수치" in existing:
            existing = re.sub(
                r"## 현재 수치\n.*?(?=\n## |\Z)", current_block, existing, flags=re.DOTALL
            )
        else:
            category = cat_items[0].category
            frontmatter = f"---\nupdated: {datetime.now().strftime('%Y-%m-%d')}\ncategory: {category}\n---\n\n"
            existing = frontmatter + current_block + "\n\n## 히스토리 (최근 30일)\n"

        # 히스토리 행 추가
        for i in cat_items:
            date_str = str(i.as_of)
            new_row = f"| {date_str} | {i.value}{i.unit} | {i.change:+.4f} |"
            hist_header = f"### {i.name} 히스토리"
            existing = _update_history_table(existing, new_row, hist_header)

        # updated 갱신
        existing = re.sub(r"updated: \S+", f"updated: {datetime.now().strftime('%Y-%m-%d')}", existing)
        path.write_text(existing, encoding="utf-8")

    print(f"  [macro] Indicators 갱신: {len(by_cat)}개 파일")


def write_daily(
    items: list[MacroItem],
    signals: list[MacroSignal],
    summary: str,
    vault_path: Path,
    date_str: str,
) -> Path:
    """Macro/Daily/{date}.md 생성 (기존 파일 덮어씀)."""
    root = _macro_root(vault_path)
    path = root / "Daily" / f"{date_str}.md"

    # 지표 테이블
    rows = []
    for i in items:
        emoji = "🔴" if abs(i.change_pct) >= 2 else ("⚠️" if abs(i.change_pct) >= 1 else "")
        rows.append(f"| {i.name} | {i.value}{i.unit} | {i.change_pct:+.2f}% | {emoji} |")

    table = (
        "| 지표 | 값 | 변화율 | 신호 |\n"
        "|------|-----|--------|------|\n"
        + "\n".join(rows)
    )

    # 신호 블록
    if signals:
        signal_lines = "\n".join(
            f"- {_ALERT_EMOJI.get(s.alert_level, '')} **{s.indicator}** ({s.description})\n  → {s.action_hint}"
            for s in signals
        )
    else:
        signal_lines = "이상 신호 없음"

    content = (
        f"---\n"
        f"date: {date_str}\n"
        f"type: macro_daily\n"
        f"signals: {len(signals)}\n"
        f"---\n\n"
        f"## 오늘의 매크로 요약\n\n{summary}\n\n"
        f"## 주요 지표\n\n{table}\n\n"
        f"## 신호\n\n{signal_lines}\n"
    )

    path.write_text(content, encoding="utf-8")
    print(f"  [macro] Daily 노트 저장: {path}")
    return path
