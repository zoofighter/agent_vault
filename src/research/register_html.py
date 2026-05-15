"""
report_download/*.html → Obsidian Research 폴더 배치 등록

Clien 등 커뮤니티에서 저장한 HTML 투자 분석 글을 파싱해
관련 기업 Research 폴더에 노트로 저장한다.

사용:
  python -m src.research.register_html --vault ./agent_vault
  python -m src.research.register_html --vault ./agent_vault --dir ./report_download
  python -m src.research.register_html --vault ./agent_vault --file "HBM분석.html" --company SK하이닉스
"""

import argparse
import csv
import hashlib
import re
import sys
from datetime import datetime
from pathlib import Path

import ollama
from bs4 import BeautifulSoup

from src.obsidian.company_manager import company_dir as _vault_company_dir
from src.research.naver_research import _find_existing_nid, save_research_note

COMPANIES_CSV = Path(__file__).resolve().parents[2] / "companies.csv"
REPORT_DOWNLOAD_DIR = Path(__file__).resolve().parents[2] / "report_download"
_MODEL = "gemma4:26b"
_MAX_TEXT_CHARS = 8000


# ── 기업 로드 ──────────────────────────────────────────────────────────────────

def _load_all_companies(csv_path: Path = COMPANIES_CSV) -> dict[str, str]:
    """name → ticker (전체 활성 기업)"""
    mapping: dict[str, str] = {}
    with open(csv_path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            name = row.get("name", "").strip()
            ticker = row.get("ticker", "").strip()
            active = row.get("active", "true").strip().lower()
            if name and active not in ("false", "0", "no"):
                mapping[name] = ticker
    return mapping


# ── HTML 파싱 ──────────────────────────────────────────────────────────────────

def _parse_savepage_date(html: str) -> str | None:
    """savepage-date 메타 태그에서 날짜 추출 (SingleFile/SavePage 확장)"""
    m = re.search(r'savepage-date["\s]+content="([^"]+)"', html)
    if not m:
        soup = BeautifulSoup(html[:4096], "html.parser")
        tag = soup.find("meta", attrs={"name": "savepage-date"})
        if tag:
            m_val = tag.get("content", "")
            m = re.match(r".+?(\d{4})", m_val)
            if m:
                try:
                    dt = datetime.strptime(m_val[:24].strip(), "%a %b %d %Y %H:%M:%S")
                    return dt.strftime("%Y-%m-%d")
                except ValueError:
                    pass
        return None
    raw = m.group(1)
    # "Fri May 15 2026 21:51:50 GMT+0900 ..."
    try:
        dt = datetime.strptime(raw[:15].strip(), "%a %b %d %Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        pass
    year_m = re.search(r"\d{4}", raw)
    if year_m:
        return raw[year_m.start():year_m.start() + 4] + "-01-01"
    return None


def extract_html_content(html_path: Path) -> tuple[str, str, str]:
    """(title, body_text, date_str) 반환"""
    raw = html_path.read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(raw, "html.parser")

    # 제목
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else html_path.stem
    # " : 클리앙" 같은 사이트명 접미사 제거
    title = re.sub(r"\s*[:|·]\s*클리앙$", "", title).strip()
    title = re.sub(r"\s*[:|·]\s*[A-Za-z가-힣]+$", "", title).strip() if not title else title

    # 본문
    article = soup.find("article")
    if article:
        text = article.get_text(separator="\n", strip=True)
    else:
        for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)

    # 빈 줄 정리
    lines = [l for l in text.splitlines() if l.strip()]
    text = "\n".join(lines)

    # 날짜: savepage-date → 파일 mtime
    date_str = _parse_savepage_date(raw)
    if not date_str:
        date_str = datetime.fromtimestamp(html_path.stat().st_mtime).strftime("%Y-%m-%d")

    return title, text[:_MAX_TEXT_CHARS], date_str


# ── LLM 분석 ──────────────────────────────────────────────────────────────────

def _company_list_str(companies: dict[str, str]) -> str:
    return ", ".join(companies.keys())


def identify_companies(text: str, title: str, companies: dict[str, str]) -> list[str]:
    """텍스트에서 관련 기업 최대 3개 추출 (companies 중에서만)"""
    company_list = _company_list_str(companies)
    prompt = (
        f"다음 텍스트(제목: {title})에서 가장 관련 있는 기업을 아래 목록에서 골라줘.\n"
        f"목록: {company_list}\n\n"
        f"텍스트:\n{text[:3000]}\n\n"
        "규칙:\n"
        "- 목록에 있는 기업명만 정확히 사용\n"
        "- 최대 3개까지\n"
        "- 쉼표로 구분해서 기업명만 나열 (설명 없이)\n"
        "- 관련 기업이 없으면 '없음' 출력\n"
        "예: SK하이닉스, NVIDIA, 삼성전자"
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
            # 부분 일치 시도
            for cname in companies:
                if cname in name or name in cname:
                    if cname not in found:
                        found.append(cname)
                    break
        if len(found) >= 3:
            break
    return found


def analyze_html_content(text: str, title: str, companies: list[str]) -> str:
    company_str = ", ".join(companies) if companies else "관련 기업"
    prompt = (
        f"아래는 {company_str}에 관한 투자 분석 글 '{title}'이다.\n\n"
        f"{text}\n\n"
        "이 글을 다음 형식으로 한국어로 요약해줘:\n"
        "## 핵심 주제\n"
        "## 주요 분석 포인트 (3~5개)\n"
        "## 언급된 기업 및 시사점\n"
        "## 주요 수치/데이터\n"
        "## 결론 및 투자 시사점"
    )
    resp = ollama.chat(model=_MODEL, messages=[{"role": "user", "content": prompt}])
    return resp["message"]["content"].strip()


# ── 등록·아카이브 ──────────────────────────────────────────────────────────────

def _make_nid(html_path: Path) -> str:
    h = hashlib.md5(str(html_path.resolve()).encode()).hexdigest()[:8]
    return f"html-{h}"


def _archive_html(html_path: Path, date_str: str) -> Path:
    yearmonth = date_str[:7]
    archive_dir = REPORT_DOWNLOAD_DIR / "Archive" / yearmonth
    archive_dir.mkdir(parents=True, exist_ok=True)
    dest = archive_dir / html_path.name
    if dest.exists():
        ts = datetime.now().strftime("%H%M%S")
        dest = archive_dir / f"{html_path.stem}_{ts}{html_path.suffix}"
    html_path.rename(dest)
    return dest


def register_one(
    vault_path: Path,
    html_path: Path,
    companies: dict[str, str],
    forced_company: str | None = None,
    archive_after: bool = True,
) -> list[Path]:
    """HTML 1개 처리 → 저장된 노트 경로 목록 반환"""
    nid = _make_nid(html_path)

    print(f"\n── {html_path.name}")

    title, text, date_str = extract_html_content(html_path)
    print(f"  제목: {title}")
    print(f"  날짜: {date_str}  |  본문: {len(text)}자")

    if forced_company:
        target_companies = [forced_company] if forced_company in companies else []
        if not target_companies:
            print(f"  오류: '{forced_company}' 는 companies.csv에 없음")
            return []
    else:
        print("  관련 기업 탐색 중...", end=" ", flush=True)
        target_companies = identify_companies(text, title, companies)
        print(f"→ {target_companies or '없음'}")

    if not target_companies:
        print("  관련 기업 없음 — 건너뜀")
        return []

    # 이미 등록됐는지 확인 (첫 번째 기업 폴더 기준)
    primary = target_companies[0]
    research_dir = _vault_company_dir(vault_path, primary) / "Research"
    existing = _find_existing_nid(research_dir, nid)
    if existing:
        print(f"  이미 등록됨: {existing.name}")
        return [existing]

    print("  LLM 분석 중...", end=" ", flush=True)
    analysis = analyze_html_content(text, title, target_companies)
    print("완료")

    saved_paths = []
    for company in target_companies:
        report = {
            "ticker":  companies.get(company, ""),
            "nid":     nid,
            "title":   title,
            "date":    date_str,
            "broker":  "커뮤니티 분석",
            "pdf_url": str(html_path.resolve()),
            "source":  "HTML 수집",
        }
        saved = save_research_note(vault_path, company, report, analysis)
        print(f"  저장: {saved.relative_to(vault_path)}")
        saved_paths.append(saved)

    if archive_after and html_path.exists():
        archived = _archive_html(html_path, date_str)
        print(f"  아카이브: Archive/{archived.parent.name}/{archived.name[:40]}")

    return saved_paths


# ── 배치 스캔 ──────────────────────────────────────────────────────────────────

def run_batch(vault_path: Path, scan_dir: Path) -> None:
    companies = _load_all_companies()
    html_files = sorted(scan_dir.glob("*.html"), key=lambda p: p.stat().st_mtime)

    if not html_files:
        print(f"HTML 파일 없음: {scan_dir}")
        return

    print(f"HTML {len(html_files)}개 발견 — 처리 시작\n")
    total_saved = 0
    for html_path in html_files:
        saved = register_one(vault_path, html_path, companies)
        total_saved += len(saved)

    print(f"\n완료: 노트 {total_saved}개 저장")


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="HTML 투자 분석 글을 Obsidian Research 폴더에 등록",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  --vault ./agent_vault
  --vault ./agent_vault --dir ./report_download
  --vault ./agent_vault --file "삼성전자 분석.html" --company 삼성전자
        """,
    )
    parser.add_argument("--vault",   required=True, help="Obsidian 볼트 경로")
    parser.add_argument("--dir",     default=str(REPORT_DOWNLOAD_DIR),
                        help=f"HTML 스캔 폴더 (기본: {REPORT_DOWNLOAD_DIR})")
    parser.add_argument("--file",    default=None, help="처리할 HTML 파일 (단일)")
    parser.add_argument("--company", default=None, help="강제 지정 기업명")
    parser.add_argument("--no-archive", action="store_true", help="처리 후 아카이브 안 함")
    args = parser.parse_args()

    vault_path = Path(args.vault).resolve()
    if not vault_path.exists():
        print(f"오류: 볼트 경로 없음 — {vault_path}", file=sys.stderr)
        sys.exit(1)

    if args.file:
        html_path = Path(args.file).expanduser()
        if not html_path.is_absolute():
            html_path = Path(args.dir) / args.file
        if not html_path.exists():
            print(f"오류: 파일 없음 — {html_path}", file=sys.stderr)
            sys.exit(1)
        companies = _load_all_companies()
        register_one(vault_path, html_path, companies,
                     forced_company=args.company,
                     archive_after=not args.no_archive)
    else:
        run_batch(vault_path, Path(args.dir))


if __name__ == "__main__":
    main()
