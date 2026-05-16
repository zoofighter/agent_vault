"""
AgentVault Telegram Bot — 양방향 인터페이스

지원 명령:
  /status          오늘 Daily 노트 현황 요약
  /batch           배치 실행 이력 + 성공/실패 요약
  /logs [n]        오늘 로그 마지막 n줄 (기본 30)
  /inbox [n]       Inbox.md 최근 n개 알림 (기본 5)
  /commander       Commander Agent 즉시 실행
  /analyze 기업명  심층 투자 분석 (멀티소스 + Gemini 2.5 Pro)
  /memo 기업명 텍스트  분석 코멘트를 Memos에 저장
  /blog 기업명     특정 기업 블로그 초안 생성
  /help            명령 목록
"""

import asyncio
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters


# ── 경로 기준 ─────────────────────────────────────────────────────────────────

PROJECT = Path(__file__).resolve().parents[2]
DEFAULT_VAULT = Path("/Users/boon/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent_vault")


def _vault() -> Path:
    v = os.environ.get("VAULT_PATH", str(DEFAULT_VAULT))
    return Path(v)


# ── 핸들러 ────────────────────────────────────────────────────────────────────

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "*AgentVault Bot 명령 목록*\n\n"
        "/status (s) — 오늘 Daily 노트 수집 현황\n"
        "/batch (bt) — 배치 실행 이력 + 성공/실패 요약\n"
        "/logs (l) [n] — 오늘 로그 마지막 n줄 (기본 30)\n"
        "/inbox (i) [n] — Inbox 최근 알림 (기본 5개)\n"
        "/commander (c) — Commander Agent 즉시 실행\n"
        "/analyze (a) 삼성전자 — 심층 투자 분석 (Gemini 2.5 Pro)\n"
        "/memo (m) 삼성전자 [코멘트] — 분석 코멘트를 Memos에 저장\n"
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


async def cmd_logs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """오늘 로그 파일 마지막 n줄 + 종료 요약 라인."""
    n = 30
    if context.args:
        try:
            n = max(1, min(int(context.args[0]), 200))
        except ValueError:
            pass

    logs_dir = PROJECT / "logs"
    today = datetime.now().strftime("%Y-%m-%d")

    # a → b → c 순으로 가장 최근 파일 탐색
    log_file = None
    for suffix in ("c", "b", "a"):
        candidate = logs_dir / f"{today}{suffix}.log"
        if candidate.exists():
            log_file = candidate
            break

    if log_file is None:
        await update.message.reply_text(f"오늘({today}) 로그 파일 없음")
        return

    lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
    tail = lines[-n:] if len(lines) >= n else lines

    # 종료 요약 라인 추출 (파일 전체에서 마지막 "=== ... 종료" 라인)
    summary_line = ""
    for line in reversed(lines):
        if "종료" in line and line.startswith("==="):
            summary_line = line.strip()
            break

    header = f"*{log_file.name}* (마지막 {len(tail)}줄)\n"
    if summary_line:
        header += f"`{summary_line}`\n"
    header += "\n"

    body = "\n".join(tail)
    msg = header + f"```\n{body}\n```"
    if len(msg) > 4000:
        # 앞부분 잘라냄 — 뒷부분(최신) 유지
        overflow = len(msg) - 4000
        body = body[overflow:]
        msg = header + f"```\n...{body}\n```"

    await update.message.reply_text(msg, parse_mode="Markdown")


def _parse_log_summary(log_path: Path) -> dict:
    """로그 파일에서 시작 시각, 종료 라인, 성공 여부 파싱."""
    info = {"start": None, "end": None, "summary": None, "ok": None}
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        for line in lines:
            if info["start"] is None and "시작" in line and line.startswith("==="):
                info["start"] = line.strip()
            if "종료" in line and line.startswith("==="):
                info["end"] = line.strip()
                info["summary"] = line.strip()
        if info["end"]:
            # "종료" 라인이 있으면 정상 완료로 판단
            info["ok"] = True
        elif info["start"]:
            # 시작만 있고 종료 없으면 실행 중이거나 hang
            info["ok"] = False
    except Exception:
        pass
    return info


async def cmd_batch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """배치 실행 이력 요약 — 오늘/어제 로그 파일 기반."""
    logs_dir = PROJECT / "logs"
    today = datetime.now().strftime("%Y-%m-%d")

    lines = ["*배치 실행 이력*\n"]

    # 일일 배치 (obs-news-update): 오늘 a/b/c 로그
    lines.append("*일일 뉴스 배치 (07:00 / 18:00)*")
    found_any = False
    for suffix in ("a", "b", "c"):
        lf = logs_dir / f"{today}{suffix}.log"
        if not lf.exists():
            continue
        found_any = True
        info = _parse_log_summary(lf)
        status = "완료" if info["ok"] else ("실행 중 / 비정상 종료" if info["start"] else "빈 파일")
        start_time = ""
        if info["start"]:
            m = re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", info["start"])
            start_time = f" ({m.group(0)})" if m else ""
        lines.append(f"  {lf.name}: {status}{start_time}")
        if info["summary"]:
            lines.append(f"  `{info['summary']}`")
    if not found_any:
        lines.append("  오늘 로그 없음")

    # 브리핑 로그
    lines.append("\n*브리핑 (07:30 / 18:xx)*")
    briefing_log = logs_dir / "briefing.log"
    if briefing_log.exists():
        bl_text = briefing_log.read_text(encoding="utf-8", errors="replace")
        # 형식: "=== Briefing Agent [YYYY-MM-DD] ==="
        today_blocks = re.findall(
            rf"=== Briefing Agent \[{re.escape(today)}\] ===.*?(?====|\Z)",
            bl_text, re.DOTALL
        )
        if today_blocks:
            last_block_lines = today_blocks[-1].strip().splitlines()
            lines.append(f"  오늘 {len(today_blocks)}회 실행")
            lines.append(f"  마지막: `{last_block_lines[-1][:100]}`")
        else:
            lines.append("  오늘 실행 없음")
    else:
        lines.append("  로그 파일 없음")

    # Telegram 봇 로그 — 날짜 없는 포맷이므로 파일 수정 시각으로 표시
    lines.append("\n*Telegram 봇 (상시)*")
    bot_log = logs_dir / "telegram_bot.log"
    if bot_log.exists():
        import os
        mtime = datetime.fromtimestamp(os.path.getmtime(bot_log)).strftime("%m-%d %H:%M")
        total_lines = bot_log.read_text(encoding="utf-8", errors="replace").count("\n")
        lines.append(f"  마지막 갱신: {mtime} / 누적 {total_lines:,}줄")
    else:
        lines.append("  로그 파일 없음")

    # LaunchAgent 상태 (launchctl)
    lines.append("\n*LaunchAgent 상태*")
    import subprocess
    try:
        lc = subprocess.run(
            ["launchctl", "list"],
            capture_output=True, text=True, timeout=5,
        )
        boon_jobs = [l for l in lc.stdout.splitlines() if "boon" in l]
        if boon_jobs:
            for job in boon_jobs:
                parts = job.split()
                pid = parts[0] if parts else "-"
                name = parts[2] if len(parts) > 2 else job
                running = "실행 중" if pid not in ("-", "0") else "대기/중단"
                lines.append(f"  {name.split('.')[-1]}: {running} (PID={pid})")
        else:
            lines.append("  등록된 배치 없음")
    except Exception as e:
        lines.append(f"  launchctl 조회 실패: {e}")

    msg = "\n".join(lines)
    if len(msg) > 4000:
        msg = msg[:4000] + "\n...(이하 생략)"
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
    await update.message.reply_text(f"*{company}* 심층 분석 중... (약 2~3분 소요)")
    vault = _vault()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    try:
        from src.analysis.deep_analyzer import analyze, save_memo
        draft, sources = await asyncio.get_event_loop().run_in_executor(
            None, analyze, vault, company
        )
    except Exception as e:
        await update.message.reply_text(f"분석 실패: {e}")
        return

    header = f"*[{company}] 심층 투자 분석 초안*\n소스: {sources}\n\n"
    footer = f"\n\n코멘트를 저장하려면:\n`/memo {company} [코멘트 내용]`"

    msg = header + draft + footer
    if len(msg) > 4000:
        # 초안 저장 후 파일 경로 안내
        path = save_memo(vault, company, draft, today)
        rel = "/".join(path.parts[-4:])
        await update.message.reply_text(
            f"{header}(분석 내용이 길어 파일로 저장됨)\n`{rel}`{footer}",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_memo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("사용법: /memo 삼성전자 [코멘트 내용]")
        return

    company = context.args[0]
    comment = " ".join(context.args[1:])
    vault = _vault()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    try:
        from src.analysis.deep_analyzer import save_memo
        content = f"## 투자 코멘트\n\n{comment}\n"
        path = save_memo(vault, company, content, today)
        rel = "/".join(path.parts[-4:])
        await update.message.reply_text(
            f"저장됨: `{rel}`\n(다음 임베딩 사이클에서 RAG에 반영됩니다)",
            parse_mode="Markdown",
        )
    except Exception as e:
        await update.message.reply_text(f"저장 실패: {e}")


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
    app.add_handler(CommandHandler(["batch",     "bt"],          cmd_batch))
    app.add_handler(CommandHandler(["logs",      "l"],           cmd_logs))
    app.add_handler(CommandHandler(["inbox",     "i"],           cmd_inbox))
    app.add_handler(CommandHandler(["commander", "c"],           cmd_commander))
    app.add_handler(CommandHandler(["analyze",   "a"],           cmd_analyze))
    app.add_handler(CommandHandler(["memo",      "m"],           cmd_memo))
    app.add_handler(CommandHandler(["blog",      "b"],           cmd_blog))
    app.add_handler(MessageHandler(filters.COMMAND, unknown))
    print("AgentVault Bot 시작됨 (Ctrl+C로 종료)")
    app.run_polling(drop_pending_updates=True)
