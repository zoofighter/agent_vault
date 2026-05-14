"""
agent_vault/Inbox.md 에 callout 블록으로 알림 추가 (최신이 위)

모든 에이전트가 공유하는 단일 Inbox 채널.
"""

from datetime import datetime, timezone
from pathlib import Path

_INBOX_FILENAME = "Inbox.md"

_HEADER = """---
title: Inbox
type: inbox
tags:
  - inbox
---

# AgentVault Inbox

"""

_CALLOUT_LEVELS = {
    "info":      "note",
    "warning":   "warning",
    "important": "important",
    "error":     "danger",
    "success":   "success",
}


def _ensure_inbox(inbox_path: Path) -> str:
    if inbox_path.exists():
        return inbox_path.read_text(encoding="utf-8")
    inbox_path.parent.mkdir(parents=True, exist_ok=True)
    inbox_path.write_text(_HEADER, encoding="utf-8")
    return _HEADER


def append_alert(
    vault_path: Path,
    title: str,
    body: str,
    level: str = "warning",
    timestamp: str | None = None,
) -> Path:
    """Inbox.md 상단에 callout 블록 추가 (최신이 위에 쌓임)."""
    inbox_path = vault_path / _INBOX_FILENAME
    content = _ensure_inbox(inbox_path)

    ts = timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    callout_type = _CALLOUT_LEVELS.get(level, "note")

    lines = body.strip().splitlines()
    body_quoted = "\n".join(f"> {ln}" if ln.strip() else ">" for ln in lines)

    block = f"""> [!{callout_type}] {title}
> *{ts}*
>
{body_quoted}

"""

    marker = "# AgentVault Inbox\n\n"
    idx = content.find(marker)
    if idx == -1:
        new_content = content + block
    else:
        insert_at = idx + len(marker)
        new_content = content[:insert_at] + block + content[insert_at:]

    inbox_path.write_text(new_content, encoding="utf-8")
    return inbox_path
