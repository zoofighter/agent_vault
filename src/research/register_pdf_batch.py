"""
report_download/*.pdf → Obsidian Research 폴더 배치 등록

기업 식별 순서:
  1. 파일명에서 티커 추출 (AAPL, NVDA, ...)
  2. 파일명에서 한국어 기업명 매칭
  3. LLM으로 PDF 텍스트 분석

사용:
  python -m src.research.register_pdf_batch --vault ./agent_vault
  python -m src.research.register_pdf_batch --vault ./agent_vault --dir ./report_download
  python -m src.research.register_pdf_batch --vault ./agent_vault --file "report.pdf" --company NVIDIA
"""

import argparse
import csv
import re
import sys
from datetime import datetime
from pathlib import Path

import fitz  # PyMuPDF
import ollama

from src.obsidian.company_manager import company_dir as _vault_company_dir
from src.research.naver_research import (
    analyze_pdf_bytes,
    save_research_note,
    _find_existing_nid,
)
from src.research.register_pdf import (
    _make_manual_nid,
    _clean_title,
    _file_mtime_date,
)

COMPANIES_CSV = Path(__file__).resolve().parents[2] / "companies.csv"
REPORT_DOWNLOAD_DIR = Path(__file__).resolve().parents[2] / "report_download"
_MODEL = "gemma4:26b"


# ── 기업 목록 ──────────────────────────────────────────────────────────────────

def _load_companies(csv_path: Path = COMPANIES_CSV) -> dict[str, str]:
    """name → ticker"""
    mapping: dict[str, str] = {}
    with open(csv_path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            name = row.get("name", "").strip()
            ticker = row.get("ticker", "").strip()
            active = row.get("active", "true").strip().lower()
            if name and active not in ("false", "0", "no"):
                mapping[name] = ticker
    return mapping


def _ticker_to_company(companies: dict[str, str]) -> dict[str, str]:
    """ticker → name (역방향 조회)"""
    return {v.upper(): k for k, v in companies.items() if v}


# ── 기업 식별 ──────────────────────────────────────────────────────────────────

# 파일명 한국어 별칭 → companies.csv name 매핑
_KR_ALIAS: dict[str, str] = {
    "애플": "Apple",
    "아마존": "Amazon",
    "알파벳": "Alphabet",
    "구글": "Alphabet",
    "퀄컴": "Qualcomm",
    "엔비디아": "NVIDIA",
    "마이크로소프트": "Microsoft",
    "테슬라": "Tesla",
    "메타": "Meta",
    "삼성": "삼성전자",
    "하이닉스": "SK하이닉스",
    "마이크론": "Micron",
    "인텔": "Intel",
    "브로드컴": "Broadcom",
    "TSMC": "TSMC",
    "소프트뱅크": "SoftBank",
    "암": "ARM",
    "ARM": "ARM",
    "ASML": "ASML",
}


def _identify_from_filename(stem: str, companies: dict[str, str]) -> str | None:
    """파일명 스템에서 기업 추출 (티커 → 한국어 별칭 순)"""
    ticker_map = _ticker_to_company(companies)

    # 1) 괄호 안 티커: "애플 (AAPL US_...)" → AAPL
    m = re.search(r"\(([A-Z]{2,5})\s+[A-Z]{2}", stem)
    if m:
        ticker = m.group(1).upper()
        if ticker in ticker_map:
            return ticker_map[ticker]

    # 2) 한국어 별칭
    for alias, name in _KR_ALIAS.items():
        if alias in stem and name in companies:
            return name

    # 3) 영문 회사명 직접 매칭
    stem_upper = stem.upper()
    for name in sorted(companies, key=len, reverse=True):
        if name.upper() in stem_upper:
            return name

    return None


def _extract_pdf_text(pdf_path: Path, max_chars: int = 4000) -> str:
    doc = fitz.open(str(pdf_path))
    text = "\n".join(p.get_text() for p in doc).strip()
    doc.close()
    return text[:max_chars]


def _identify_from_llm(text: str, filename: str, companies: dict[str, str]) -> list[str]:
    """LLM으로 관련 기업 최대 3개 식별"""
    company_list = ", ".join(companies.keys())
    prompt = (
        f"파일명: {filename}\n\n"
        f"PDF 본문(일부):\n{text}\n\n"
        f"위 리포트에서 가장 관련 있는 기업을 아래 목록에서 골라줘.\n"
        f"목록: {company_list}\n\n"
        "규칙:\n"
        "- 목록에 있는 기업명만 정확히 사용\n"
        "- 최대 3개\n"
        "- 쉼표로 구분해서 기업명만 출력 (설명 없이)\n"
        "- 없으면 '없음'\n"
        "예: NVIDIA, SK하이닉스"
    )
    resp = ollama.chat(model=_MODEL, messages=[{"role": "user", "content": prompt}])
    raw = resp["message"]["content"].strip()
    if "없음" in raw:
        return []

    found = []
    for part in re.split(r"[,，\n]", raw):
        name = part.strip().strip("•-").strip()
        if name in companies:
            found.append(name)
        else:
            for cname in companies:
                if cname in name or name in cname:
                    if cname not in found:
                        found.append(cname)
                    break
        if len(found) >= 3:
            break
    return found


def _detect_broker(text: str, filename: str) -> str:
    """PDF 텍스트/파일명에서 증권사 추출 시도"""
    brokers = [
        "미래에셋", "Mirae Asset", "NH투자", "한국투자", "삼성증권", "KB증권",
        "신한투자", "하나증권", "메리츠", "키움", "대신증권", "유안타",
        "이베스트", "DB금융", "교보증권",
    ]
    combined = text[:2000] + " " + filename
    for broker in brokers:
        if broker in combined:
            return broker
    return "자체수집"


def _archive_pdf(pdf_path: Path, date_str: str) -> Path:
    yearmonth = date_str[:7]
    archive_dir = REPORT_DOWNLOAD_DIR / "Archive" / yearmonth
    archive_dir.mkdir(parents=True, exist_ok=True)
    dest = archive_dir / pdf_path.name
    if dest.exists():
        ts = datetime.now().strftime("%H%M%S")
        dest = archive_dir / f"{pdf_path.stem}_{ts}{pdf_path.suffix}"
    pdf_path.rename(dest)
    return dest


def _parse_filename_date(stem: str) -> str | None:
    """파일명 YYYYMMDD 접두사 → 'YYYY-MM-DD'"""
    m = re.match(r"(\d{8})[_\-\s]", stem)
    if m:
        d = m.group(1)
        return f"{d[:4]}-{d[4:6]}-{d[6:]}"
    return None


# ── 등록 ──────────────────────────────────────────────────────────────────────

def register_one_batch(
    vault_path: Path,
    pdf_path: Path,
    companies: dict[str, str],
    forced_company: str | None = None,
    archive_after: bool = True,
) -> list[Path]:
    """PDF 1개 처리 → 저장된 노트 경로 목록 반환"""
    nid = _make_manual_nid(pdf_path)
    print(f"\n── {pdf_path.name}")

    report_date = _parse_filename_date(pdf_path.stem) or _file_mtime_date(pdf_path)
    report_title = _clean_title(pdf_path.stem)
    print(f"  제목: {report_title}  |  날짜: {report_date}")

    # 기업 식별
    if forced_company:
        target_companies = [forced_company] if forced_company in companies else []
        if not target_companies:
            print(f"  오류: '{forced_company}' 는 companies.csv에 없음")
            return []
    else:
        guessed = _identify_from_filename(pdf_path.stem, companies)
        if guessed:
            target_companies = [guessed]
            print(f"  기업 (파일명): {target_companies}")
        else:
            print("  LLM 기업 식별 중...", end=" ", flush=True)
            text = _extract_pdf_text(pdf_path)
            target_companies = _identify_from_llm(text, pdf_path.name, companies)
            print(f"→ {target_companies or '없음'}")

    if not target_companies:
        print("  관련 기업 없음 — 건너뜀")
        return []

    # 중복 확인 (첫 기업 기준)
    primary = target_companies[0]
    research_dir = _vault_company_dir(vault_path, primary) / "Research"
    existing = _find_existing_nid(research_dir, nid)
    if existing:
        print(f"  이미 등록됨: {existing.name}")
        return [existing]

    # PDF 분석
    print("  LLM 분석 중...", end=" ", flush=True)
    try:
        pdf_bytes = pdf_path.read_bytes()
        analysis = analyze_pdf_bytes(pdf_bytes, primary, report_title)
        print("완료")
    except Exception as e:
        print(f"실패: {e}")
        return []

    broker = _detect_broker(_extract_pdf_text(pdf_path, 2000), pdf_path.name)

    saved_paths = []
    for company in target_companies:
        report = {
            "ticker":  companies.get(company, ""),
            "nid":     nid,
            "title":   report_title,
            "date":    report_date,
            "broker":  broker,
            "pdf_url": str(pdf_path.resolve()),
            "source":  "로컬 PDF",
        }
        saved = save_research_note(vault_path, company, report, analysis)
        print(f"  저장: {saved.relative_to(vault_path)}")
        saved_paths.append(saved)

    if archive_after and pdf_path.exists():
        archived = _archive_pdf(pdf_path, report_date)
        print(f"  아카이브: Archive/{archived.parent.name}/{archived.name[:40]}")

    return saved_paths


# ── 배치 실행 ──────────────────────────────────────────────────────────────────

def run_batch(vault_path: Path, scan_dir: Path) -> None:
    companies = _load_companies()
    pdf_files = sorted(scan_dir.glob("*.pdf"), key=lambda p: p.stat().st_mtime)

    if not pdf_files:
        print(f"PDF 파일 없음: {scan_dir}")
        return

    print(f"PDF {len(pdf_files)}개 발견 — 처리 시작\n")
    total_saved = 0
    for pdf_path in pdf_files:
        saved = register_one_batch(vault_path, pdf_path, companies)
        total_saved += len(saved)

    print(f"\n완료: 노트 {total_saved}개 저장")


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="report_download PDF → Obsidian Research 폴더 배치 등록",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  --vault ./agent_vault
  --vault ./agent_vault --dir ./report_download
  --vault ./agent_vault --file "20260226_엔비디아.pdf" --company NVIDIA
        """,
    )
    parser.add_argument("--vault",      required=True, help="Obsidian 볼트 경로")
    parser.add_argument("--dir",        default=str(REPORT_DOWNLOAD_DIR),
                        help=f"PDF 스캔 폴더 (기본: report_download/)")
    parser.add_argument("--file",       default=None, help="처리할 PDF 파일 (단일)")
    parser.add_argument("--company",    default=None, help="강제 지정 기업명")
    parser.add_argument("--no-archive", action="store_true", help="처리 후 아카이브 안 함")
    args = parser.parse_args()

    vault_path = Path(args.vault).resolve()
    if not vault_path.exists():
        print(f"오류: 볼트 경로 없음 — {vault_path}", file=sys.stderr)
        sys.exit(1)

    if args.file:
        pdf_path = Path(args.file).expanduser()
        if not pdf_path.is_absolute():
            pdf_path = Path(args.dir) / args.file
        if not pdf_path.exists():
            print(f"오류: 파일 없음 — {pdf_path}", file=sys.stderr)
            sys.exit(1)
        companies = _load_companies()
        register_one_batch(vault_path, pdf_path, companies,
                           forced_company=args.company,
                           archive_after=not args.no_archive)
    else:
        run_batch(vault_path, Path(args.dir))


if __name__ == "__main__":
    main()
