"""
agent_vault/Digest/{YYYY-MM-DD}.md 에 에이전트 실행 기록 추가

Inbox.md  → 사용자 인터랙션 (Telegram 봇 응답 등)
Digest/   → 시스템 자동 기록 (Commander 명령, 에러 리포트, Research 알림)
"""

from datetime import datetime, timezone
from pathlib import Path

_DIGEST_DIR = "Digest"

_CALLOUT_LEVELS = {
    "info":      "note",
    "warning":   "warning",
    "important": "important",
    "error":     "danger",
    "success":   "success",
}


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _digest_path(vault_path: Path, date: str | None = None) -> Path:
    date = date or _today()
    digest_dir = vault_path / _DIGEST_DIR
    digest_dir.mkdir(exist_ok=True)
    return digest_dir / f"{date}.md"


def _ensure_header(path: Path, date: str) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    header = (
        f"---\n"
        f"title: Digest {date}\n"
        f"type: digest\n"
        f"date: {date}\n"
        f"tags:\n"
        f"  - digest\n"
        f"---\n\n"
        f"# AgentVault Digest — {date}\n\n"
    )
    path.write_text(header, encoding="utf-8")
    return header


def append_record(
    vault_path: Path,
    title: str,
    body: str,
    level: str = "info",
    date: str | None = None,
    timestamp: str | None = None,
) -> Path:
    """Digest/{date}.md 하단에 callout 블록 추가 (오래된 것이 위, 최신이 아래)."""
    date = date or _today()
    path = _digest_path(vault_path, date)
    content = _ensure_header(path, date)

    ts = timestamp or datetime.now(timezone.utc).strftime("%H:%M UTC")
    callout_type = _CALLOUT_LEVELS.get(level, "note")

    lines = body.strip().splitlines()
    body_quoted = "\n".join(f"> {ln}" if ln.strip() else ">" for ln in lines)

    block = f"""> [!{callout_type}] {title}
> *{ts}*
>
{body_quoted}

"""
    path.write_text(content + block, encoding="utf-8")
    return path
