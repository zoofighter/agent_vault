"""
AgentVault Telegram Bot — 양방향 인터페이스

지원 명령:
  /status          오늘 Daily 노트 현황 요약
  /inbox [n]       Inbox.md 최근 n개 알림 (기본 5)
  /commander       Commander Agent 즉시 실행
  /analyze 기업명  특정 기업 뉴스 수집 + 분석
  /blog 기업명     특정 기업 블로그 초안 생성
  /help            명령 목록
"""

import os
import re
from datetime import datetime, timezone
from pathlib import Path

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters


# ── 경로 기준 ─────────────────────────────────────────────────────────────────

PROJECT = Path(__file__).resolve().parents[2]
DEFAULT_VAULT = PROJECT / "agent_vault"


def _vault() -> Path:
    v = os.environ.get("VAULT_PATH", str(DEFAULT_VAULT))
    return Path(v)


# ── 핸들러 ────────────────────────────────────────────────────────────────────

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "*AgentVault Bot 명령 목록*\n\n"
        "/status (s) — 오늘 Daily 노트 수집 현황\n"
        "/inbox (i) [n] — Inbox 최근 알림 (기본 5개)\n"
        "/commander (c) — Commander Agent 즉시 실행\n"
        "/analyze (a) 삼성전자 — 기업 즉시 분석\n"
        "/blog (b) 삼성전자 — 블로그 초안 생성\n"
        "/help (h) — 이 목록\n"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    vault = _vault()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    notes = list(vault.glob(f"Companies/*/*/Daily/{today}*.md"))
    if not notes:
        await update.message.reply_text(f"오늘({today}) Daily 노트 없음")
        return

    lines = [f"*오늘 Daily 노트 현황 ({today})*\n"]
    total_news = 0
    for note in sorted(notes):
        company = note.parent.parent.name
        text = note.read_text(encoding="utf-8")
        m = re.search(r"^news_count:\s*(\d+)", text, re.MULTILINE)
        nc = int(m.group(1)) if m else 0
        total_news += nc
        lines.append(f"  {company}: {nc}건")

    lines.append(f"\n총 {len(notes)}개사 / {total_news}건")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_inbox(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    vault = _vault()
    inbox_path = vault / "Inbox.md"

    if not inbox_path.exists():
        await update.message.reply_text("Inbox.md 없음")
        return

    # 개수 파싱
    n = 5
    if context.args:
        try:
            n = int(context.args[0])
        except ValueError:
            pass

    text = inbox_path.read_text(encoding="utf-8")

    # callout 블록 추출
    blocks = re.findall(r"> \[!\w+\] .+?(?=\n> \[!|\Z)", text, re.DOTALL)
    if not blocks:
        await update.message.reply_text("알림 없음")
        return

    selected = blocks[:n]
    result = []
    for block in selected:
        # callout → plain text 변환
        lines = [l.lstrip("> ").strip() for l in block.strip().splitlines()]
        result.append("\n".join(l for l in lines if l))

    msg = f"*Inbox 최근 {len(selected)}개*\n\n" + "\n\n─────\n\n".join(result)
    # Telegram 메시지 4096자 제한
    if len(msg) > 4000:
        msg = msg[:4000] + "\n\n...(이하 생략)"
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_commander(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Commander Agent 실행 중... (약 30초 소요)")
    vault = _vault()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    import subprocess
    result = subprocess.run(
        ["python", str(PROJECT / "run_commander.py"),
         "--vault", str(vault), "--no-llm", "--max", "3"],
        capture_output=True, text=True, cwd=str(PROJECT), timeout=120,
    )
    output = result.stdout[-2000:] if result.stdout else result.stderr[-1000:]
    await update.message.reply_text(f"```\n{output}\n```", parse_mode="Markdown")


async def cmd_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("사용법: /analyze 삼성전자")
        return

    company = " ".join(context.args)
    await update.message.reply_text(f"*{company}* 분석 중... (약 1~2분 소요)")
    vault = _vault()

    import subprocess
    result = subprocess.run(
        ["python", str(PROJECT / "collect_news.py"),
         "--vault", str(vault),
         "--companies", company,
         "--skip-index"],
        capture_output=True, text=True, cwd=str(PROJECT), timeout=300,
    )
    output = (result.stdout or result.stderr)[-2000:]
    await update.message.reply_text(f"```\n{output}\n```", parse_mode="Markdown")


async def cmd_blog(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("사용법: /blog 삼성전자")
        return

    company = " ".join(context.args)
    await update.message.reply_text(f"*{company}* 블로그 초안 생성 중...")
    vault = _vault()

    import subprocess
    result = subprocess.run(
        ["python", str(PROJECT / "run_content.py"),
         "--vault", str(vault),
         "--mode", "blog",
         "--company", company,
         "--min-score", "0.0"],
        capture_output=True, text=True, cwd=str(PROJECT), timeout=120,
    )
    output = (result.stdout or result.stderr)[-1500:]

    # 생성된 파일 경로 추출
    m = re.search(r"저장: (.+\.md)", result.stdout or "")
    if m:
        note_path = vault / m.group(1)
        if note_path.exists():
            content = note_path.read_text(encoding="utf-8")
            # 프론트매터 제거 후 앞부분만
            body = re.sub(r"^---.*?---\n", "", content, flags=re.DOTALL)
            preview = body[:2000] + ("\n...(이하 vault에서 확인)" if len(body) > 2000 else "")
            await update.message.reply_text(preview)
            return

    await update.message.reply_text(f"```\n{output}\n```", parse_mode="Markdown")


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("알 수 없는 명령. /help 로 목록 확인")


# ── 봇 실행 ───────────────────────────────────────────────────────────────────

def run_bot(token: str) -> None:
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler(["help",      "h"],           cmd_help))
    app.add_handler(CommandHandler("start",                      cmd_help))
    app.add_handler(CommandHandler(["status",    "s"],           cmd_status))
    app.add_handler(CommandHandler(["inbox",     "i"],           cmd_inbox))
    app.add_handler(CommandHandler(["commander", "c"],           cmd_commander))
    app.add_handler(CommandHandler(["analyze",   "a"],           cmd_analyze))
    app.add_handler(CommandHandler(["blog",      "b"],           cmd_blog))
    app.add_handler(MessageHandler(filters.COMMAND, unknown))
    print("AgentVault Bot 시작됨 (Ctrl+C로 종료)")
    app.run_polling(drop_pending_updates=True)
