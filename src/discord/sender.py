"""
Discord Webhook 단방향 전송

채널별 Webhook URL을 .env에 설정:
  DISCORD_WEBHOOK_BATCH      — 배치 시작/완료/오류
  DISCORD_WEBHOOK_COMMANDER  — Commander 액션 명령
  DISCORD_WEBHOOK_MACRO      — 매크로 신호
  DISCORD_WEBHOOK_GENERAL    — 브리핑·리서치·기타

미설정 채널은 조용히 스킵.
"""

import os
import requests

_COLORS = {
    "success":   0x2ECC71,   # 초록
    "info":      0x3498DB,   # 파랑
    "warning":   0xF1C40F,   # 노랑
    "error":     0xE74C3C,   # 빨강
    "critical":  0xC0392B,   # 짙은 빨강
    "important": 0x9B59B6,   # 보라
}

# level → 자동 채널 매핑
_LEVEL_CHANNEL = {
    "info":      "BATCH",
    "success":   "BATCH",
    "error":     "BATCH",
    "warning":   "MACRO",
    "critical":  "MACRO",
    "important": "COMMANDER",
}


def _webhook(channel: str) -> str:
    return os.environ.get(f"DISCORD_WEBHOOK_{channel.upper()}", "")


def _post(url: str, payload: dict) -> bool:
    try:
        resp = requests.post(url, json=payload, timeout=10)
        return resp.status_code in (200, 204)
    except Exception:
        return False


def send(text: str, channel: str = "GENERAL") -> bool:
    url = _webhook(channel)
    if not url:
        return False
    # Discord content는 2000자 제한
    content = text[:2000] if len(text) > 2000 else text
    return _post(url, {"content": content})


def send_alert(title: str, body: str, level: str = "warning",
               channel: str = "") -> bool:
    if not channel:
        channel = _LEVEL_CHANNEL.get(level, "GENERAL")

    url = _webhook(channel)
    if not url:
        # 지정 채널 없으면 GENERAL로 폴백
        url = _webhook("GENERAL")
    if not url:
        return False

    color = _COLORS.get(level, 0x95A5A6)
    payload = {
        "embeds": [{
            "title": title,
            "description": body[:4000] if body else "",
            "color": color,
        }]
    }
    return _post(url, payload)


def send_commander(company: str, title: str, body: str, stars: str) -> bool:
    url = _webhook("COMMANDER")
    if not url:
        url = _webhook("GENERAL")
    if not url:
        return False

    # 본문에서 근거와 액션 분리
    lines = body.splitlines()
    reason_lines, action_lines = [], []
    in_actions = False
    for line in lines:
        if "권장 액션" in line:
            in_actions = True
            continue
        if in_actions:
            action_lines.append(line)
        else:
            reason_lines.append(line)

    fields = []
    if reason_lines:
        fields.append({
            "name": "근거",
            "value": "\n".join(reason_lines).strip()[:1024] or "-",
            "inline": False,
        })
    if action_lines:
        fields.append({
            "name": "권장 액션",
            "value": "\n".join(action_lines).strip()[:1024] or "-",
            "inline": False,
        })

    payload = {
        "embeds": [{
            "title": f"{stars}  {company} — {title}",
            "color": _COLORS["important"],
            "fields": fields,
        }]
    }
    return _post(url, payload)
