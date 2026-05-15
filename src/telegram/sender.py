"""
Telegram 메시지 전송 (단방향)

Commander, 에러 리포트, Research 알림 등 모든 에이전트가 공유.
"""

import os
import requests


def _token() -> str:
    return os.environ.get("TELEGRAM_BOT_TOKEN", "")


def _chat_id() -> str:
    return os.environ.get("TELEGRAM_CHAT_ID", "")


def send(text: str, parse_mode: str = "Markdown") -> bool:
    """Telegram으로 텍스트 전송. 성공 여부 반환."""
    token = _token()
    chat_id = _chat_id()
    if not token or not chat_id:
        return False

    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": parse_mode},
            timeout=10,
        )
        ok = resp.status_code == 200
    except Exception:
        ok = False

    try:
        from src.discord import sender as _discord
        _discord.send(text, channel="GENERAL")
    except Exception:
        pass

    return ok


def send_commander(company: str, title: str, body: str, stars: str) -> bool:
    text = (
        f"*[{stars}] {company} — {title}*\n\n"
        f"{body}"
    )
    ok = send(text)

    try:
        from src.discord import sender as _discord
        _discord.send_commander(company, title, body, stars)
    except Exception:
        pass

    return ok


def send_alert(title: str, body: str, level: str = "warning") -> bool:
    icons = {"info": "ℹ️", "warning": "⚠️", "important": "🔔", "error": "🚨", "success": "✅"}
    icon = icons.get(level, "📌")
    text = f"{icon} *{title}*\n\n{body}"
    ok = send(text)

    try:
        from src.discord import sender as _discord
        _discord.send_alert(title, body, level)
    except Exception:
        pass

    return ok
