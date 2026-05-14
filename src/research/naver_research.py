"""
네이버 금융 기업분석 리포트 수집 + 로컬 LLM 요약 → Obsidian Research 폴더 저장

사용:
  # 오늘 리포트
  python -m src.research.naver_research --vault ./agent_vault --date today

  # 특정 날짜
  python -m src.research.naver_research --vault ./agent_vault --date 2026-05-13

  # 날짜 범위
  python -m src.research.naver_research --vault ./agent_vault --from 2026-05-01 --to 2026-05-13

  # 특정 기업만
  python -m src.research.naver_research --vault ./agent_vault --date today --company 삼성전자
"""

import argparse
import csv
import re
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

import fitz   # PyMuPDF

from src.obsidian.company_manager import company_dir as _vault_company_dir
import ollama

_RESEARCH_URL = "https://finance.naver.com/research/company_list.naver"
_GET_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
}
_POST_HEADERS = {**_GET_HEADERS, "Content-Type": "application/x-www-form-urlencoded"}
_MODEL = "gemma4:26b"
_MAX_SCAN_PAGES = 30  # 날짜 범위 내 리포트를 찾기 위한 최대 스캔 페이지

COMPANIES_CSV = Path(__file__).resolve().parents[2] / "companies.csv"


# ── 날짜 파싱 헬퍼 ────────────────────────────────────────────────────────────

def _parse_date_arg(s: str) -> str:
    """'today', 'yesterday', 'YYYY-MM-DD' → 'YYYY-MM-DD'"""
    today = datetime.now().strftime("%Y-%m-%d")
    if s in ("today", "오늘"):
        return today
    if s in ("yesterday", "어제"):
        return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    # YYYY-MM-DD 또는 YYYYMMDD
    s = s.replace("/", "-")
    if re.fullmatch(r"\d{8}", s):
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s
    raise ValueError(f"날짜 형식 오류: {s}  (YYYY-MM-DD 또는 today/yesterday)")


# ── 기업 로드 ─────────────────────────────────────────────────────────────────

def load_naver_companies(csv_path: Path = COMPANIES_CSV) -> dict[str, str]:
    """ticker → name (네이버 금융 검색 가능한 기업: 6자리 숫자 ticker 보유)"""
    mapping: dict[str, str] = {}
    with open(csv_path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            ticker = row.get("ticker", "").strip()
            name = row.get("name", "").strip()
            active = row.get("active", "true").strip().lower()
            # 6자리 숫자 ticker = 한국 상장 종목 (KRX/KOSDAQ/KONEX)
            if re.fullmatch(r"\d{6}", ticker) and name and active not in ("false", "0", "no"):
                mapping[ticker] = name
    return mapping


# ── 리스트 페이지 스크래핑 ────────────────────────────────────────────────────

def _fetch_post(ticker: str, name: str, page: int) -> str:
    data = urllib.parse.urlencode({
        "searchType": "itemCode",
        "itemCode": ticker,
        "itemName": name,
        "page": page,
    }).encode()
    req = urllib.request.Request(_RESEARCH_URL, data=data, headers=_POST_HEADERS)
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode("euc-kr", errors="replace")


def _parse_page(html: str, ticker: str) -> list[dict]:
    rows = []
    for tr in re.findall(r"<tr>(.*?)</tr>", html, re.DOTALL):
        if "company_read" not in tr:
            continue
        nid_m    = re.search(r"nid=(\d+)", tr)
        title_m  = re.search(r"nid=\d+[^>]*>([^<]+)", tr)
        pdf_m    = re.search(r"(https://stock\.pstatic\.net/[^\"]+\.pdf)", tr)
        date_m   = re.search(r'class="date"[^>]*>(\d{2}\.\d{2}\.\d{2})', tr)
        broker_m = re.search(r"</td>\s*<td>([^<]+)</td>\s*<td class=\"file\"", tr)
        if not (nid_m and title_m and pdf_m and date_m):
            continue
        rows.append({
            "ticker":  ticker,
            "nid":     nid_m.group(1),
            "title":   title_m.group(1).strip(),
            "pdf_url": pdf_m.group(1),
            "date":    "20" + date_m.group(1).replace(".", "-"),
            "broker":  broker_m.group(1).strip() if broker_m else "",
        })
    return rows


def fetch_reports_in_range(
    ticker: str,
    name: str,
    date_from: str,
    date_to: str,
    max_pages: int = _MAX_SCAN_PAGES,
) -> list[dict]:
    """date_from ~ date_to 범위의 리포트를 반환. 범위를 벗어나면 스캔 중단."""
    result = []
    for page in range(1, max_pages + 1):
        try:
            html = _fetch_post(ticker, name, page)
        except Exception as e:
            print(f"    [{name} p{page}] 네트워크 오류: {e}")
            break

        rows = _parse_page(html, ticker)
        if not rows:
            break

        for row in rows:
            d = row["date"]
            if d > date_to:
                continue        # 아직 범위 이전 — 다음 row
            if d < date_from:
                return result   # 범위보다 오래됨 — 이 페이지부터는 불필요
            result.append(row)

        # 페이지 마지막 항목이 date_from 이전이면 더 볼 필요 없음
        if rows[-1]["date"] < date_from:
            break

        time.sleep(0.3)
    return result


# ── PDF 분석 ─────────────────────────────────────────────────────────────────

def _pdf_to_text(pdf_bytes: bytes) -> str:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name
    doc = fitz.open(tmp_path)
    text = "\n".join(p.get_text() for p in doc)
    doc.close()
    Path(tmp_path).unlink(missing_ok=True)
    return text


def _pdf_to_images(pdf_bytes: bytes, dpi: int = 120) -> list[tuple[int, bytes]]:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name
    doc = fitz.open(tmp_path)
    images = [(i + 1, p.get_pixmap(dpi=dpi).tobytes("png")) for i, p in enumerate(doc)]
    doc.close()
    Path(tmp_path).unlink(missing_ok=True)
    return images


def analyze_pdf_bytes(pdf_bytes: bytes, company: str, title: str) -> str:
    text = _pdf_to_text(pdf_bytes)
    if len(text.strip()) >= 300:
        return _analyze_text(text, company, title)
    return _analyze_vision(pdf_bytes, company, title)


def _analyze_text(text: str, company: str, title: str) -> str:
    prompt = (
        f"아래는 {company}에 대한 증권사 리서치 리포트 '{title}'의 본문이다.\n\n"
        f"{text[:6000]}\n\n"
        "이 리포트를 다음 형식으로 한국어로 요약해줘:\n"
        "## 핵심 주장\n"
        "## 투자 포인트 (3개)\n"
        "## 주요 수치/목표주가\n"
        "## 리스크 요인\n"
        "## 결론"
    )
    resp = ollama.chat(model=_MODEL, messages=[{"role": "user", "content": prompt}])
    return resp["message"]["content"].strip()


def _analyze_vision(pdf_bytes: bytes, company: str, title: str) -> str:
    import base64
    summaries = []
    for page_num, img_bytes in _pdf_to_images(pdf_bytes)[:8]:
        prompt = (
            f"{company} 리서치 리포트 p{page_num} 핵심 내용을 "
            "한국어로 간결히 요약해줘. 수치·목표주가 포함."
        )
        resp = ollama.chat(
            model=_MODEL,
            messages=[{"role": "user", "content": prompt,
                       "images": [base64.b64encode(img_bytes).decode()]}],
        )
        summaries.append(f"[p{page_num}] {resp['message']['content'].strip()}")

    prompt2 = (
        f"{company} 리포트 '{title}' 페이지별 요약:\n\n"
        + "\n\n".join(summaries)
        + "\n\n전체를 다음 형식으로 종합:\n"
        "## 핵심 주장\n## 투자 포인트\n## 주요 수치/목표주가\n## 리스크\n## 결론"
    )
    resp2 = ollama.chat(model=_MODEL, messages=[{"role": "user", "content": prompt2}])
    return resp2["message"]["content"].strip()


# ── Obsidian 노트 저장 ────────────────────────────────────────────────────────

_SUFFIXES = ["", "_b", "_c", "_d", "_e", "_f", "_g", "_h"]


def _safe(s: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", s)


def _find_existing_nid(research_dir: Path, nid: str) -> Path | None:
    """nid가 frontmatter에 있는 기존 파일을 찾는다."""
    if not research_dir.exists():
        return None
    for md in research_dir.glob("*.md"):
        try:
            text = md.read_text(encoding="utf-8")
            if f"nid: \"{nid}\"" in text or f"nid: {nid}" in text:
                return md
        except OSError:
            pass
    return None


def _resolve_note_path(research_dir: Path, date_str: str, safe_title: str) -> Path:
    """파일명 충돌 시 _b, _c … 접미사를 붙여 사용 가능한 경로를 반환."""
    for suffix in _SUFFIXES:
        candidate = research_dir / f"{date_str}_{safe_title}{suffix}.md"
        if not candidate.exists():
            return candidate
    # 모두 찼으면 타임스탬프 사용 (극히 드문 경우)
    ts = datetime.now().strftime("%H%M%S")
    return research_dir / f"{date_str}_{safe_title}_{ts}.md"


def save_research_note(vault_path: Path, company: str, report: dict, analysis: str) -> Path:
    research_dir = _vault_company_dir(vault_path, company) / "Research"
    research_dir.mkdir(parents=True, exist_ok=True)

    date_str   = report["date"].replace("-", "")
    safe_title = _safe(report["title"])[:50]
    path       = _resolve_note_path(research_dir, date_str, safe_title)

    broker_line = f"> - **증권사**: {report['broker']}\n" if report.get("broker") else ""
    source = report.get("source", "네이버금융 리서치")
    content = (
        f"---\n"
        f"title: \"{report['title']}\"\n"
        f"company: {company}\n"
        f"date: {report['date']}\n"
        f"nid: \"{report['nid']}\"\n"
        f"broker: {report.get('broker', '')}\n"
        f"source: {source}\n"
        f"pdf: {report['pdf_url']}\n"
        f"tags:\n"
        f"  - research\n"
        f"  - {company}\n"
        f"---\n\n"
        f"# {report['title']}\n\n"
        f"> [!info] 리포트 정보\n"
        f"> - **종목**: {company} ({report['ticker']})\n"
        f"> - **날짜**: {report['date']}\n"
        f"{broker_line}"
        f"> - **원문**: [PDF]({report['pdf_url']})\n\n"
        f"---\n\n"
        f"{analysis}\n"
    )
    path.write_text(content, encoding="utf-8")
    return path


# ── 배치 실행 ─────────────────────────────────────────────────────────────────

def run_batch(
    vault_path: Path,
    date_from: str,
    date_to: str,
    filter_company: str | None = None,
) -> None:
    companies = load_naver_companies()
    targets = {t: n for t, n in companies.items() if filter_company is None or n == filter_company}

    if not targets:
        msg = f"'{filter_company}' 없음 (companies.csv의 6자리 티커 기업만 지원)"
        print(f"대상 기업 없음: {msg}")
        return

    date_label = date_from if date_from == date_to else f"{date_from} ~ {date_to}"
    print(f"기간: {date_label}")
    print(f"대상 ({len(targets)}개): {', '.join(targets.values())}\n")

    # 기업별 리포트 수집
    all_reports: list[tuple[str, dict]] = []  # (company_name, report)
    for ticker, name in targets.items():
        print(f"  [{name}] 수집 중...", end=" ", flush=True)
        reports = fetch_reports_in_range(ticker, name, date_from, date_to)
        print(f"{len(reports)}건")
        for r in reports:
            all_reports.append((name, r))

    if not all_reports:
        print("\n해당 기간 리포트 없음.")
        return

    print(f"\n처리 대상: {len(all_reports)}건")
    for company, r in all_reports:
        print(f"  {company} | {r['date']} | {r.get('broker','?'):12s} | {r['title']}")

    # PDF 분석 및 저장
    print()
    done, skipped, failed = 0, 0, 0
    for i, (company, report) in enumerate(all_reports, 1):
        print(f"[{i}/{len(all_reports)}] {company} — {report['title']}")

        # nid 기반 중복 체크 (같은 nid → 파일명이 달라도 건너뜀)
        research_dir = _vault_company_dir(vault_path, company) / "Research"
        existing = _find_existing_nid(research_dir, report["nid"])
        if existing:
            print(f"  건너뜀 (이미 존재: {existing.name})")
            skipped += 1
            continue

        # PDF 다운로드
        print(f"  PDF...", end=" ", flush=True)
        try:
            req = urllib.request.Request(report["pdf_url"], headers=_GET_HEADERS)
            with urllib.request.urlopen(req, timeout=30) as resp:
                pdf_bytes = resp.read()
            print(f"{len(pdf_bytes)//1024}KB", end="  ", flush=True)
        except Exception as e:
            print(f"다운로드 실패: {e}")
            failed += 1
            continue

        # LLM 분석
        print(f"LLM...", end=" ", flush=True)
        try:
            analysis = analyze_pdf_bytes(pdf_bytes, company, report["title"])
            print("완료")
        except Exception as e:
            print(f"분석 실패: {e}")
            failed += 1
            continue

        # 저장 (파일명 충돌 시 _b/_c 자동 처리)
        saved = save_research_note(vault_path, company, report, analysis)
        print(f"  저장: {saved.relative_to(vault_path)}")
        done += 1
        time.sleep(0.3)

    print(f"\n완료 — 저장 {done}건 / 건너뜀 {skipped}건 / 실패 {failed}건")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="네이버 금융 리서치 리포트 배치 수집",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  --date today                   오늘 발간 리포트
  --date 2026-05-13              특정 날짜
  --from 2026-05-01 --to 2026-05-13   날짜 범위
  --date today --company 삼성전자     단일 기업
        """,
    )
    parser.add_argument("--vault",    required=True, help="Obsidian 볼트 경로")
    parser.add_argument("--date",     default=None,  help="수집 날짜 (today / YYYY-MM-DD)")
    parser.add_argument("--from",     dest="date_from", default=None, help="시작 날짜")
    parser.add_argument("--to",       dest="date_to",   default=None, help="종료 날짜")
    parser.add_argument("--company",  default=None,  help="특정 기업만 (예: 삼성전자)")
    args = parser.parse_args()

    vault_path = Path(args.vault).resolve()
    if not vault_path.exists():
        print(f"오류: 볼트 경로 없음 — {vault_path}", file=sys.stderr)
        sys.exit(1)

    # 날짜 해석
    try:
        if args.date:
            date_from = date_to = _parse_date_arg(args.date)
        elif args.date_from or args.date_to:
            today = datetime.now().strftime("%Y-%m-%d")
            date_from = _parse_date_arg(args.date_from) if args.date_from else today
            date_to   = _parse_date_arg(args.date_to)   if args.date_to   else today
            if date_from > date_to:
                date_from, date_to = date_to, date_from
        else:
            # 기본값: 오늘
            date_from = date_to = datetime.now().strftime("%Y-%m-%d")
    except ValueError as e:
        print(f"오류: {e}", file=sys.stderr)
        sys.exit(1)

    run_batch(vault_path, date_from, date_to, args.company)


if __name__ == "__main__":
    main()
