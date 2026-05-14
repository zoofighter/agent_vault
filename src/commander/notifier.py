"""
Commander 명령 → Inbox.md 기록

테마 급등 감지(여러 기업에서 동일 키워드 클러스터)도 처리한다.
"""

from collections import Counter
from pathlib import Path

from src.commander.dispatcher import Command
from src.commander.scanner import ScanResult
from src.obsidian.digest import append_record
from src.telegram.sender import send_commander, send_alert


def _format_command_body(cmd: Command) -> str:
    lines = [
        f"**근거**: {cmd.body}",
        "",
        "**권장 액션**:",
    ]
    for line in cmd.actions.strip().splitlines():
        lines.append(line if line.startswith("-") else f"- {line}")
    return "\n".join(lines)


def push_commands(commands: list[Command], vault_path: Path) -> None:
    """Commander 명령을 Digest + Telegram에 기록."""
    for cmd in commands:
        title = f"{cmd.company} — {cmd.title} ({cmd.stars})"
        body = _format_command_body(cmd)
        append_record(vault_path, title, body, level="important")
        send_commander(cmd.company, cmd.title, body, cmd.stars)
        print(f"  [digest+tg] 기록: {title}")


def detect_theme_surge(
    results: list[ScanResult],
    min_companies: int = 3,
) -> list[tuple[str, list[str]]]:
    """N개 이상 기업에서 공통 테마 키워드 감지 → (테마, 기업 목록) 반환."""
    theme_companies: dict[str, list[str]] = {}
    for r in results:
        for theme in r.key_themes:
            theme_companies.setdefault(theme, []).append(r.company)

    surges = [
        (theme, companies)
        for theme, companies in theme_companies.items()
        if len(companies) >= min_companies
    ]
    return sorted(surges, key=lambda x: len(x[1]), reverse=True)


def push_theme_surges(
    results: list[ScanResult],
    vault_path: Path,
    min_companies: int = 3,
) -> None:
    """테마 급등을 Inbox.md에 기록."""
    surges = detect_theme_surge(results, min_companies)
    for theme, companies in surges:
        title = f"테마 급등 — {theme} ({len(companies)}개사 동시 언급)"
        body = (
            f"**감지 기업**: {', '.join(companies)}\n\n"
            f"**권장 액션**:\n"
            f"- 섹터 전반 영향 분석 수행\n"
            f"- 포트폴리오 비중 점검"
        )
        append_record(vault_path, title, body, level="warning")
        send_alert(title, f"감지 기업: {', '.join(companies)}", level="warning")
        print(f"  [digest+tg] 테마 급등: {theme}")
