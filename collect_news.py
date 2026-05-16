#!/usr/bin/env python3
"""
뉴스 수집 CLI

사용법:
    python collect_news.py
    python collect_news.py --companies "삼성전자,현대차" --days 3
    python collect_news.py --vault ./agent_vault --dry-run
"""

import argparse
import csv
import os
from pathlib import Path

_env_file = Path(__file__).parent / '.env'
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip())

from src.obsidian.indexer import get_changed_files
from src.obsidian.embedder import index_files
from src.obsidian.company_manager import company_dir as _company_dir
from src.sources.collector import collect
from src.sources.naver_finance import NaverFinanceSource
from src.sources.base import NewsItem
from src.llm.analyzer import analyze
from src.llm.curator import synthesize
from src.obsidian.writer import write_daily
from src.macro.collector import collect_all as _collect_macro
from src.macro.analyzer import detect_signals, build_summary
from src.macro.writer import write_indicators, write_daily as write_macro_daily

DEFAULT_COMPANIES = "삼성전자,Google,현대차,SK하이닉스"
DEFAULT_VAULT = Path("/Users/boon/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent_vault")
CHROMA_PATH = "data/chroma"
COMPANIES_CSV = Path(__file__).parent / "companies.csv"


def _all_active_companies() -> list[str]:
    with open(COMPANIES_CSV, encoding="utf-8") as f:
        return [r["name"] for r in csv.DictReader(f) if r.get("active", "true").lower() == "true"]


def _exchange_map() -> dict[str, str]:
    with open(COMPANIES_CSV, encoding="utf-8") as f:
        return {r["name"]: r.get("exchange", "") for r in csv.DictReader(f)}


def _keywords_map() -> dict[str, str]:
    """name → keywords (companies.csv의 keywords 컬럼)"""
    with open(COMPANIES_CSV, encoding="utf-8") as f:
        return {r["name"]: r.get("keywords", "") for r in csv.DictReader(f)}


def main():
    parser = argparse.ArgumentParser(description="Obsidian 뉴스 수집기")
    parser.add_argument('--companies', default=DEFAULT_COMPANIES)
    parser.add_argument('--all', action='store_true',
                        help='companies.csv의 모든 활성 기업 대상')
    parser.add_argument('--days', type=int, default=7)
    parser.add_argument('--vault', default=str(DEFAULT_VAULT))
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--skip-index', action='store_true',
                        help='볼트 재인덱싱 건너뜀 (빠른 재실행용)')
    parser.add_argument('--date-suffix', default='',
                        help='파일명 날짜 suffix (a, b, c). 미지정 시 순서 기반 자동 설정')
    args = parser.parse_args()

    # names, vault 먼저 확정 (suffix 자동감지에 필요)
    names = _all_active_companies() if args.all else [n.strip() for n in args.companies.split(',') if n.strip()]
    vault = Path(args.vault)

    from datetime import datetime as _dt, timezone as _tz, timedelta as _td
    _today = _dt.now(_tz(_td(hours=9))).strftime("%Y-%m-%d")  # KST

    if not args.date_suffix:
        _sample = names[0] if names else None
        args.date_suffix = "a"

        if _sample:
            for _s in ["a", "b", "c", "d"]:
                try:
                    _p = _company_dir(vault, _sample) / "Daily" / f"{_today}{_s}.md"
                except ValueError:
                    _p = None
                if _p is None or not _p.exists():
                    args.date_suffix = _s
                    break

    # ── ChromaDB 상태 검증 ────────────────────────────────────────────
    if not args.skip_index:
        try:
            import chromadb as _cdb
            _client = _cdb.PersistentClient(path=CHROMA_PATH)
            _col = _client.get_or_create_collection("vault_docs")
            if _col.count() > 0:
                _col.get(limit=1)
        except Exception as _e:
            print(f"[warn] ChromaDB 손상 감지 ({_e}) — 재초기화")
            import shutil
            shutil.rmtree(CHROMA_PATH, ignore_errors=True)

    # ── Phase 0: 매크로 지표 수집 ─────────────────────────────────────
    print("=== Phase 0: 매크로 지표 수집 ===")
    try:
        macro_items   = _collect_macro()
        macro_signals = detect_signals(macro_items)
        macro_summary = build_summary(macro_items, macro_signals)
        write_indicators(macro_items, vault)
        write_macro_daily(macro_items, macro_signals, macro_summary, vault, _today)
        if macro_signals:
            print(f"  신호 {len(macro_signals)}개 발동: {[s.signal_type for s in macro_signals]}")
            from src.commander.notifier import push_macro_signals
            push_macro_signals(macro_signals, vault)
    except Exception as _me:
        print(f"  [warn] 매크로 수집 실패 (파이프라인 계속): {_me}")
        macro_signals = []

    # ── Phase A: 볼트 증분 인덱싱 ──────────────────────────────────────
    if not args.skip_index:
        print("=== Phase A: 볼트 인덱싱 ===")
        changed = get_changed_files(vault)
        if changed:
            print(f"변경 파일 {len(changed)}개 임베딩 중...")
            total = index_files(changed, chroma_path=CHROMA_PATH)
            print(f"임베딩 완료: {total}청크")
        else:
            print("변경된 볼트 파일 없음 — 인덱스 최신 상태")
    else:
        print("=== Phase A: 인덱싱 건너뜀 ===")

    # ── Phase B: 뉴스 수집 ────────────────────────────────────────────
    print(f"\n=== Phase B: 뉴스 수집 (대상: {names}) ===")

    print("\n[NaverFinance] 메인 뉴스 수집 중...")
    nf_items_raw = NaverFinanceSource().fetch_all()
    print(f"  수집: {len(nf_items_raw)}건 (KRX 기업에만 배분)")

    all_items: list[NewsItem] = collect(names, days=args.days, naver_finance_items=nf_items_raw)

    _total_news = 0
    for name in names:
        cnt = sum(1 for i in all_items if i.company == name)
        _total_news += cnt
        print(f"  {name}: {cnt}건")

    # Phase B 완료 알림
    if not args.dry_run:
        try:
            from src.telegram.sender import send as _tg_send
            _tg_send(
                f"[Phase B] {_today}{args.date_suffix} 수집 완료\n"
                f"{len(names)}개사 / 총 {_total_news}건\n"
                f"Phase C 분석 시작..."
            )
        except Exception:
            pass

    # ── Phase C: 벡터 유사도 필터 + LLM 분석 + Daily 저장 ──────────────
    print(f"\n=== Phase C: 관련성 분석 ===")
    written_paths = []
    ex_map = _exchange_map()

    errors: list[str] = []        # (company, reason)
    zero_news: list[str] = []     # 뉴스 0건 기업
    kw_map = _keywords_map()
    _total = len(names)
    _MILESTONES = {25, 50, 75}

    for _idx, name in enumerate(names, 1):
        items_for = [i for i in all_items if i.company == name]
        print(f"\n[{name}] {len(items_for)}건 분석 중...")

        if not items_for:
            zero_news.append(name)

        # bge-m3 기준: KRX 0.55 / 비KRX 0.60 (nomic 시절 0.75/0.95에서 조정)
        threshold = 0.55 if ex_map.get(name) == "KRX" else 0.60
        analyzed = analyze(items_for, company=name,
                           sim_threshold=threshold, chroma_path=CHROMA_PATH,
                           company_keywords=kw_map.get(name, ""))
        print(f"  → 관련 뉴스 {len(analyzed)}건 선별")

        # LLM 종합 분석 (실패 시 None → 뉴스 목록만 저장)
        synthesis_text = synthesize(
            company=name,
            analyzed=analyzed,
            chroma_path=CHROMA_PATH,
        )
        if analyzed and synthesis_text is None:
            errors.append(f"{name}: LLM 합성 실패")

        # Daily/ 단일 파일로 저장 (종합분석 + 뉴스목록)
        daily_path = write_daily(
            company=name,
            analyzed=analyzed,
            vault_path=vault,
            date_suffix=args.date_suffix,
            synthesis=synthesis_text,
            dry_run=args.dry_run,
        )
        if daily_path:
            written_paths.append(daily_path)
        elif not args.dry_run:
            errors.append(f"{name}: Daily 노트 저장 실패")

        # 25% / 50% / 75% 구간 통과 시 Telegram 진행률 전송
        if not args.dry_run:
            _pct = (_idx * 100) // _total
            _prev_pct = ((_idx - 1) * 100) // _total
            if any(_prev_pct < m <= _pct for m in _MILESTONES):
                try:
                    from src.telegram.sender import send as _tg_send
                    _tg_send(
                        f"[진행] {_today}{args.date_suffix} — "
                        f"{_idx}/{_total} ({_pct}%) {name} 완료"
                    )
                except Exception:
                    pass

    # ── 결과 요약 ─────────────────────────────────────────────────────
    print(f"\n{'='*50}")
    if args.dry_run:
        print(f"[dry-run] 저장 예정: {len(written_paths)}개 파일")
    else:
        print(f"완료: {len(written_paths)}개 파일 저장")
        for p in written_paths:
            print(f"  {p.relative_to(vault)}")

    # ── Inbox 에러 리포트 ──────────────────────────────────────────────
    if not args.dry_run and (errors or zero_news):
        try:
            from src.obsidian.digest import append_record
            from datetime import datetime as _dt, timezone as _tz
            date_label = _dt.now(_tz.utc).strftime("%Y-%m-%d")
            body_lines = []
            if errors:
                body_lines.append("**오류 항목**:")
                body_lines.extend(f"- {e}" for e in errors)
            if zero_news:
                body_lines.append("")
                body_lines.append(f"**뉴스 0건 기업**: {', '.join(zero_news)}")
            body_lines.append("")
            body_lines.append(f"**정상 저장**: {len(written_paths)}/{len(names)}개")
            alert_title = f"파이프라인 경고 — {date_label} ({len(errors)}건 오류)"
            alert_body = "\n".join(body_lines)
            alert_level = "error" if errors else "warning"
            append_record(vault, alert_title, alert_body, level=alert_level)
            from src.telegram.sender import send_alert
            send_alert(alert_title, alert_body, level=alert_level)
            print(f"  [digest+tg] 에러 리포트 기록 완료")
        except Exception as e:
            print(f"  [digest] 기록 실패: {e}")


if __name__ == '__main__':
    main()
