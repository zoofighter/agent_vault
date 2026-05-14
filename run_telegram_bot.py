#!/usr/bin/env python3
"""
AgentVault Telegram Bot 실행

설정 (.env):
  TELEGRAM_BOT_TOKEN=1234567890:AAF...
  TELEGRAM_CHAT_ID=123456789
  VAULT_PATH=/path/to/agent_vault   (선택, 기본: ./agent_vault)

사용:
  python run_telegram_bot.py
"""

import os
import sys
from pathlib import Path

_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
if not token:
    print("오류: .env에 TELEGRAM_BOT_TOKEN 없음")
    print("  @BotFather 에서 봇 생성 후 토큰을 .env에 추가하세요")
    sys.exit(1)

chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
if not chat_id:
    print("경고: TELEGRAM_CHAT_ID 없음 — 알림 전송 불가 (명령 수신은 가능)")

from src.telegram.bot import run_bot
run_bot(token)
