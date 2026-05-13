"""
로컬 PDF를 Obsidian Research 폴더에 수동 등록

모드:
  1. 직접 지정: --pdf <파일> --company <기업명>
  2. 폴더 스캔:  --scan [--dir ~/Downloads]  (PDF 목록 보여주고 대화식 선택)

사용:
  python -m src.research.register_pdf --vault ./sample_vault \\
      --pdf ~/Downloads/samsung_report.pdf --company 삼성전자

  python -m src.research.register_pdf --vault ./sample_vault --scan

  python -m src.research.register_pdf --vault ./sample_vault --scan --dir ~/Downloads
"""

import argparse
import hashlib
import re
import sys
from datetime import datetime
from pathlib import Path

# naver_research에서 PDF 분석·저장 함수 재사용
from src.research.naver_research import (
    analyze_pdf_bytes,
    load_naver_companies,
    save_research_note,
)

COMPANIES_CSV = Path(__file__).resolve().parents[2] / "companies.csv"
DEFAULT_SCAN_DIR = Path.home() / "Downloads"
_SCAN_DAYS = 30  # 스캔 시 최근 N일 내 파일만 표시


# ── 유틸 ──────────────────────────────────────────────────────────────────────

def _load_all_companies(csv_path: Path = COMPANIES_CSV) -> dict[str, str]:
    """name → ticker (전체 활성 기업)"""
    import csv
    mapping: dict[str, str] = {}
    with open(csv_path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            name = row.get("name", "").strip()
            ticker = row.get("ticker", "").strip()
            active = row.get("active", "true").strip().lower()
            if name and active not in ("false", "0", "no"):
                mapping[name] = ticker
    return mapping


def _make_manual_nid(pdf_path: Path) -> str:
    """파일 경로 해시로 고유 nid 생성 (중복 등록 방지용)"""
    h = hashlib.md5(str(pdf_path.resolve()).encode()).hexdigest()[:8]
    return f"manual-{h}"


def _guess_company(filename: str, companies: dict[str, str]) -> str | None:
    """파일명에서 기업명 추정"""
    for name in sorted(companies, key=len, reverse=True):  # 긴 이름 우선
        if name in filename:
            return name
    return None


def _clean_title(stem: str) -> str:
    """파일명 스템에서 날짜 접두사·하이픈 등 정리"""
    # YYYYMMDD_ 또는 YYMMDD_ 형태 접두사 제거
    stem = re.sub(r"^\d{6,8}[_\-\s]+", "", stem)
    # 괄호 안 티커 코드 정리: (GOOGL US_매수) → 매수
    stem = re.sub(r"\(\s*[A-Z]{1,5}\s*[A-Z]{0,2}\s*[_\s]", "(", stem)
    return stem.strip()


def _file_mtime_date(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d")


def _scan_pdfs(scan_dir: Path, days: int = _SCAN_DAYS) -> list[Path]:
    """디렉토리에서 최근 N일 내 PDF 목록 (최신순)"""
    from datetime import timedelta
    cutoff = (datetime.now() - timedelta(days=days)).timestamp()
    pdfs = [
        p for p in scan_dir.glob("*.pdf")
        if p.stat().st_mtime >= cutoff
    ]
    return sorted(pdfs, key=lambda p: p.stat().st_mtime, reverse=True)


# ── 등록 핵심 로직 ────────────────────────────────────────────────────────────

def register_one(
    vault_path: Path,
    pdf_path: Path,
    company_name: str,
    companies: dict[str, str],
    title: str | None = None,
    date: str | None = None,
    broker: str = "자체수집",
) -> Path | None:
    ticker = companies.get(company_name, "")
    report_title = title or _clean_title(pdf_path.stem)
    report_date  = date  or _file_mtime_date(pdf_path)
    nid          = _make_manual_nid(pdf_path)

    # 이미 등록된 파일 확인 (같은 nid)
    from src.research.naver_research import _find_existing_nid
    research_dir = vault_path / "Companies" / company_name / "Research"
    existing = _find_existing_nid(research_dir, nid)
    if existing:
        print(f"  이미 등록됨: {existing.name}")
        return existing

    print(f"  PDF 읽는 중...", end=" ", flush=True)
    pdf_bytes = pdf_path.read_bytes()
    print(f"{len(pdf_bytes)//1024}KB")

    print(f"  LLM 분석 중...", end=" ", flush=True)
    try:
        analysis = analyze_pdf_bytes(pdf_bytes, company_name, report_title)
        print("완료")
    except Exception as e:
        print(f"실패: {e}")
        return None

    report = {
        "ticker":  ticker,
        "nid":     nid,
        "title":   report_title,
        "date":    report_date,
        "broker":  broker,
        "pdf_url": str(pdf_path.resolve()),
        "source":  "수동등록",
    }

    saved = save_research_note(vault_path, company_name, report, analysis)
    print(f"  저장: {saved.relative_to(vault_path)}")
    return saved


# ── 스캔 모드 ─────────────────────────────────────────────────────────────────

def run_scan(vault_path: Path, scan_dir: Path) -> None:
    companies = _load_all_companies()
    names = list(companies.keys())

    pdfs = _scan_pdfs(scan_dir)
    if not pdfs:
        print(f"PDF 없음: {scan_dir} (최근 {_SCAN_DAYS}일)")
        return

    print(f"\n{scan_dir} 최근 {_SCAN_DAYS}일 PDF ({len(pdfs)}개)\n")
    for i, p in enumerate(pdfs, 1):
        mdate = _file_mtime_date(p)
        guessed = _guess_company(p.name, companies)
        guess_str = f"  → {guessed} 추정" if guessed else ""
        print(f"  [{i:2d}] {mdate}  {p.name[:60]}{guess_str}")

    print("\n처리할 번호 입력 (쉼표 구분, 전체=all, 건너뜀=엔터): ", end="")
    try:
        sel = input().strip()
    except (EOFError, KeyboardInterrupt):
        print("\n취소")
        return

    if not sel:
        return

    if sel.lower() == "all":
        selected = list(range(len(pdfs)))
    else:
        try:
            selected = [int(x.strip()) - 1 for x in sel.split(",")]
        except ValueError:
            print("잘못된 입력")
            return

    for idx in selected:
        if idx < 0 or idx >= len(pdfs):
            continue
        pdf_path = pdfs[idx]
        guessed  = _guess_company(pdf_path.name, companies)

        print(f"\n── {pdf_path.name}")
        if guessed:
            print(f"  기업명 [{guessed}] (엔터=사용, 다른 이름 입력): ", end="")
        else:
            print(f"  기업명 입력 ({', '.join(names[:8])}...): ", end="")

        try:
            ans = input().strip()
        except (EOFError, KeyboardInterrupt):
            break

        company = ans if ans else guessed
        if not company or company not in companies:
            print(f"  미등록 기업: '{company}' — 건너뜀")
            continue

        print(f"  제목 [{pdf_path.stem[:40]}] (엔터=파일명 사용): ", end="")
        try:
            title_ans = input().strip()
        except (EOFError, KeyboardInterrupt):
            break
        title = title_ans or None

        register_one(vault_path, pdf_path, company, companies, title=title)


# ── 직접 지정 모드 ────────────────────────────────────────────────────────────

def run_direct(
    vault_path: Path,
    pdf_path: Path,
    company_name: str,
    title: str | None,
    date: str | None,
    broker: str,
) -> None:
    companies = _load_all_companies()
    if company_name not in companies:
        close = [n for n in companies if company_name in n or n in company_name]
        hint = f"  비슷한 이름: {close}" if close else ""
        print(f"오류: '{company_name}' 은 companies.csv에 없습니다.{hint}", file=sys.stderr)
        sys.exit(1)

    if not pdf_path.exists():
        print(f"오류: 파일 없음 — {pdf_path}", file=sys.stderr)
        sys.exit(1)

    print(f"기업: {company_name}  |  파일: {pdf_path.name}")
    register_one(vault_path, pdf_path, company_name, companies, title=title, date=date, broker=broker)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="로컬 PDF를 Obsidian Research 폴더에 등록",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  --pdf ~/Downloads/report.pdf --company 삼성전자
  --pdf ~/Downloads/report.pdf --company 삼성전자 --title "2Q26 실적" --date 2026-05-13
  --scan
  --scan --dir ~/Desktop
        """,
    )
    parser.add_argument("--vault",   required=True, help="Obsidian 볼트 경로")
    parser.add_argument("--pdf",     default=None,  help="등록할 PDF 파일 경로")
    parser.add_argument("--company", default=None,  help="기업명 (companies.csv 기준)")
    parser.add_argument("--title",   default=None,  help="리포트 제목 (기본: 파일명)")
    parser.add_argument("--date",    default=None,  help="리포트 날짜 YYYY-MM-DD (기본: 파일 수정일)")
    parser.add_argument("--broker",  default="자체수집", help="증권사/출처 (기본: 자체수집)")
    parser.add_argument("--scan",    action="store_true", help="Downloads 폴더 스캔 모드")
    parser.add_argument("--dir",     default=str(DEFAULT_SCAN_DIR),
                        help=f"스캔 대상 폴더 (기본: {DEFAULT_SCAN_DIR})")
    args = parser.parse_args()

    vault_path = Path(args.vault).resolve()
    if not vault_path.exists():
        print(f"오류: 볼트 경로 없음 — {vault_path}", file=sys.stderr)
        sys.exit(1)

    if args.scan:
        run_scan(vault_path, Path(args.dir).expanduser())
    elif args.pdf and args.company:
        run_direct(
            vault_path,
            Path(args.pdf).expanduser(),
            args.company,
            args.title,
            args.date,
            args.broker,
        )
    else:
        parser.error("--pdf + --company 또는 --scan 중 하나 필요")


if __name__ == "__main__":
    main()
