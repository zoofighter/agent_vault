"""
네이버 금융 산업분석 리포트에서 미국/해외 기업 리포트 수집 + 로컬 LLM 요약

파이프라인 (빠른 검색):
  1. Naver 키워드 검색 → 후보 리포트 목록
  2. PDF 다운로드 → PyMuPDF 텍스트 스캔 (LLM 없음, 빠름)
  3. 기업 키워드 포함 확인된 것만 → LLM 요약 → 저장

사용:
  python -m src.research.naver_industry --vault ./sample_vault --date today
  python -m src.research.naver_industry --vault ./sample_vault --from 2026-05-01 --to 2026-05-14
  python -m src.research.naver_industry --vault ./sample_vault --date today --company NVIDIA
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

import fitz  # PyMuPDF

from src.obsidian.company_manager import company_dir as _vault_company_dir

from src.research.naver_research import (
    _find_existing_nid,
    _parse_date_arg,
    analyze_pdf_bytes,
    save_research_note,
)

_INDUSTRY_URL = "https://finance.naver.com/research/industry_list.naver"
_GET_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
}
_MAX_SCAN_PAGES = 10   # 검색어당 최대 스캔 페이지
_MIN_KW_COUNT   = 3    # PDF 텍스트 내 키워드 최소 출현 횟수

COMPANIES_CSV = Path(__file__).resolve().parents[2] / "companies.csv"

# 제목에 이 패턴이 포함된 리포트는 수집하지 않음 (뉴스레터·주간지 등 범용 보고서)
_EXCLUDE_TITLE_PATTERNS: list[re.Pattern] = [p for p in map(re.compile, [
    r"박제민의\s*QnA",              # 주간 AI 뉴스레터 (모든 기업 언급)
    r"QnA\.I",
    r"Weekly\s*(?:리포트|뉴스|뷰|전망)?(?:\s|$)",  # "XXX Weekly" 계열
    r"Weekly\s+\w+\s+Check",       # "Weekly Amazon Beauty Check" 류
    r"Preview\s*[:：_]",            # "2026년 X월 Preview: ..." 또는 "Preview_"
    r"Re-NEWable\s*Weekly",
    r"IBKS\s*Daily",
    r"밸류업의\s*위대한\s*여정",
    r"Memory\s*Watch\s*[-–—]",     # "Memory Watch - ..." 반도체 업종 전반 주간지
    r"제약[\s/]?바이오",            # 제약/바이오 섹터 리포트
    r"통신\s+Weekly",               # 통신 주간지
    r"MLCC\s+산업",                 # MLCC 전자부품 업종 리포트
], )]

# 단어/형태소 경계 매칭이 필요한 키워드
# 영문: ARM → pharmaceutical 오매칭 방지 (\b)
# 한글: 애플 → 애플리케이션 오매칭 방지 (앞뒤 문자 클래스로 분리)
_WHOLE_WORD_KEYWORDS: frozenset[str] = frozenset(["ARM", "META", "AI", "애플"])

# 영문명 → 기본 검색어 (CSV 로드 전 fallback)
_KR_ALIAS: dict[str, list[str]] = {
    "NVIDIA":             ["엔비디아", "NVIDIA"],
    "Apple":              ["애플", "Apple"],
    "Microsoft":          ["마이크로소프트", "Microsoft"],
    "Alphabet":           ["구글", "Google", "Alphabet"],
    "Google":             ["구글", "Google"],
    "Amazon":             ["아마존", "Amazon", "AWS"],
    "Meta":               ["메타", "Meta", "페이스북"],
    "Tesla":              ["테슬라", "Tesla"],
    "Berkshire Hathaway": ["버크셔", "Berkshire"],
    "Eli Lilly":          ["일라이릴리", "Eli Lilly"],
    "Broadcom":           ["브로드컴", "Broadcom"],
    "Micron":             ["마이크론", "Micron"],
    "AMD":                ["AMD"],
    "Intel":              ["인텔", "Intel"],
    "ARM":                ["ARM"],
    "TSMC":               ["TSMC"],
    "ASML":               ["ASML"],
    "Qualcomm":           ["퀄컴", "Qualcomm"],
    "Super Micro":        ["슈퍼마이크로", "Super Micro", "SMCI"],
    "OpenAI":             ["OpenAI", "ChatGPT"],
    "Anthropic":          ["Anthropic", "Claude"],
    "SpaceX":             ["SpaceX", "스타링크", "Starlink"],
    "Tencent":            ["텐센트", "Tencent", "위챗"],
    "Alibaba":            ["알리바바", "Alibaba"],
    "CATL":               ["CATL", "닝더시대"],
    "BYD":                ["BYD", "비야디"],
    "Xiaomi":             ["샤오미", "Xiaomi"],
    "Delta Electronics":  ["델타전자", "Delta Electronics"],
    "MediaTek":           ["미디어텍", "MediaTek", "Dimensity"],
    "Nanya":              ["난야", "Nanya"],
    "SoftBank":           ["소프트뱅크", "SoftBank"],
    "Kioxia":             ["키옥시아", "Kioxia"],
    "Tokyo Electron":     ["도쿄일렉트론", "Tokyo Electron", "TEL"],
}


# ── 기업 로드 ─────────────────────────────────────────────────────────────────

def load_overseas_companies(csv_path: Path = COMPANIES_CSV) -> list[dict]:
    """비-KRX 활성 기업 (ticker, name, confirm_keywords)"""
    companies = []
    with open(csv_path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            ticker = row.get("ticker", "").strip()
            name   = row.get("name", "").strip()
            active = row.get("active", "true").strip().lower()
            if re.fullmatch(r"\d{6}", ticker) or not name or active in ("false", "0", "no"):
                continue
            kw_raw = row.get("keywords", "").strip()
            csv_kws = [k.strip() for k in kw_raw.split(",") if k.strip()]
            # 확인 키워드 = 별칭 + CSV 키워드 (PDF 텍스트 스캔용)
            alias = _KR_ALIAS.get(name, [name])
            confirm_kws = list(dict.fromkeys(alias + [name] + csv_kws))
            companies.append({
                "ticker": ticker,
                "name":   name,
                "search_terms":    alias,          # Naver 검색어
                "confirm_keywords": confirm_kws,   # PDF 텍스트 확인용
            })
    return companies


# ── 리스트 스크래핑 ───────────────────────────────────────────────────────────

def _fetch_page(keyword: str, page: int) -> str:
    url = _INDUSTRY_URL + "?" + urllib.parse.urlencode({
        "searchType": "keyword",
        "keyword":    keyword,
        "page":       page,
    })
    req = urllib.request.Request(url, headers=_GET_HEADERS)
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode("euc-kr", errors="replace")


def _parse_page(html: str) -> list[dict]:
    """날짜/nid/pdf 정보만 추출 (제목 필터 없음)"""
    rows = []
    for tr in re.findall(r"<tr>(.*?)</tr>", html, re.DOTALL):
        if "read.naver" not in tr:
            continue
        nid_m    = re.search(r"nid=(\d+)", tr)
        title_m  = re.search(r"nid=\d+[^>]*>([^<]+)", tr)
        pdf_m    = re.search(r"(https://stock\.pstatic\.net/[^\"]+\.pdf)", tr)
        date_m   = re.search(r'class="date"[^>]*>(\d{2}\.\d{2}\.\d{2})', tr)
        broker_m = re.search(r'</td>\s*<td>([^<]{2,20})</td>\s*<td class="file"', tr)
        if not (nid_m and title_m and pdf_m and date_m):
            continue
        rows.append({
            "nid":     nid_m.group(1),
            "title":   title_m.group(1).strip(),
            "pdf_url": pdf_m.group(1),
            "date":    "20" + date_m.group(1).replace(".", "-"),
            "broker":  broker_m.group(1).strip() if broker_m else "",
        })
    return rows


def _oldest_date(html: str) -> str | None:
    dates = re.findall(r'class="date"[^>]*>(\d{2}\.\d{2}\.\d{2})', html)
    if not dates:
        return None
    return "20" + min(dates).replace(".", "-")


def fetch_candidates(
    search_terms: list[str],
    date_from: str,
    date_to: str,
) -> list[dict]:
    """검색어로 후보 리포트 목록 수집 (날짜 범위 내, nid 중복 제거)"""
    seen: dict[str, dict] = {}

    for term in search_terms:
        for page in range(1, _MAX_SCAN_PAGES + 1):
            try:
                html = _fetch_page(term, page)
            except Exception as e:
                print(f"    [{term} p{page}] 오류: {e}")
                break

            rows = _parse_page(html)
            for r in rows:
                d = r["date"]
                if date_from <= d <= date_to and r["nid"] not in seen:
                    seen[r["nid"]] = r

            oldest = _oldest_date(html)
            if not rows or (oldest and oldest < date_from):
                break
            time.sleep(0.2)

    return list(seen.values())


# ── 제목 제외 필터 ────────────────────────────────────────────────────────────

def _is_excluded_title(title: str) -> bool:
    """뉴스레터·주간지 등 범용 보고서 제목이면 True"""
    return any(p.search(title) for p in _EXCLUDE_TITLE_PATTERNS)


# ── PDF 빠른 키워드 스캔 ──────────────────────────────────────────────────────

def _count_keyword_in_text(text: str, keyword: str) -> int:
    """텍스트 내 keyword 출현 횟수.
    _WHOLE_WORD_KEYWORDS: 한글/영문 문자가 앞뒤에 붙으면 매칭 제외 (부분 일치 방지).
      영문 \b 기반, 한글은 앞뒤 문자 클래스로 분리.
    """
    kw_lower = keyword.lower()
    if keyword.upper() in _WHOLE_WORD_KEYWORDS or keyword in _WHOLE_WORD_KEYWORDS:
        pattern = rf"(?<![가-힣a-zA-Z]){re.escape(kw_lower)}(?![가-힣a-zA-Z])"
        return len(re.findall(pattern, text))
    return text.count(kw_lower)


def _keyword_in_pdf(pdf_bytes: bytes, keywords: list[str], min_count: int = _MIN_KW_COUNT) -> tuple[bool, str]:
    """PDF 텍스트에서 키워드 출현 횟수 확인.
    Returns (통과여부, 매칭된 키워드 정보 문자열)
    """
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name
    try:
        doc = fitz.open(tmp_path)
        text = " ".join(p.get_text() for p in doc).lower()
        doc.close()
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    hits = []
    for kw in keywords:
        cnt = _count_keyword_in_text(text, kw)
        if cnt >= min_count:
            hits.append(f"{kw}×{cnt}")

    if hits:
        return True, ", ".join(hits[:3])
    return False, ""


# ── 배치 실행 ─────────────────────────────────────────────────────────────────

def run_batch(
    vault_path: Path,
    date_from: str,
    date_to: str,
    filter_company: str | None = None,
) -> None:
    overseas = load_overseas_companies()
    if filter_company:
        overseas = [c for c in overseas if c["name"] == filter_company]
    if not overseas:
        print(f"대상 기업 없음: '{filter_company}'")
        return

    date_label = date_from if date_from == date_to else f"{date_from} ~ {date_to}"
    print(f"기간: {date_label}")
    print(f"대상 ({len(overseas)}개): {', '.join(c['name'] for c in overseas)}\n")

    # 1단계: 후보 수집
    print("── 1단계: 후보 리포트 수집 ──")
    company_candidates: list[tuple[dict, dict]] = []
    for company in overseas:
        candidates = fetch_candidates(company["search_terms"], date_from, date_to)
        if candidates:
            print(f"  [{company['name']:15}] 후보 {len(candidates):2d}건")
        for r in candidates:
            r["ticker"] = company["ticker"]
            company_candidates.append((company, r))

    if not company_candidates:
        print("후보 없음.")
        return

    # 2단계: 제목 제외 필터 + PDF 텍스트 스캔
    print(f"\n── 2단계: 필터링 ({len(company_candidates)}건) ──")
    confirmed: list[tuple[dict, dict, bytes]] = []
    scanned = excluded_title = already = 0

    for company, report in company_candidates:
        # ① 제목 제외 필터 (PDF 다운로드 전)
        if _is_excluded_title(report["title"]):
            excluded_title += 1
            print(f"  제외(제목) {company['name']:12} | {report['title'][:50]}")
            continue

        research_dir = _vault_company_dir(vault_path, company["name"]) / "Research"
        if _find_existing_nid(research_dir, report["nid"]):
            already += 1
            continue

        # ② PDF 다운로드
        try:
            req = urllib.request.Request(report["pdf_url"], headers=_GET_HEADERS)
            with urllib.request.urlopen(req, timeout=30) as resp:
                pdf_bytes = resp.read()
        except Exception as e:
            print(f"  [{company['name']}] PDF 오류: {e}")
            continue

        scanned += 1
        # ③ 키워드 빈도 스캔 (최소 {_MIN_KW_COUNT}회)
        passed, hit_info = _keyword_in_pdf(pdf_bytes, company["confirm_keywords"])
        if passed:
            confirmed.append((company, report, pdf_bytes))
            print(f"  ✓ {company['name']:12} | {report['date']} | {report['title'][:40]}  [{hit_info}]")
        else:
            print(f"  ✗ {company['name']:12} | {report['date']} | {report['title'][:40]}")

        time.sleep(0.15)

    print(f"\n  제목제외 {excluded_title}건 / 이미저장 {already}건 / PDF스캔 {scanned}건 → 확인 {len(confirmed)}건")

    print(f"\n스캔 {scanned}건 → 확인됨 {len(confirmed)}건")

    if not confirmed:
        print("저장할 리포트 없음.")
        return

    # 3단계: LLM 분석 및 저장
    print(f"\n── 3단계: LLM 분석 ({len(confirmed)}건) ──")
    done, failed = 0, 0
    for i, (company, report, pdf_bytes) in enumerate(confirmed, 1):
        cname = company["name"]
        print(f"[{i}/{len(confirmed)}] {cname} — {report['title']}")
        print(f"  LLM...", end=" ", flush=True)
        try:
            analysis = analyze_pdf_bytes(pdf_bytes, cname, report["title"])
            print("완료")
        except Exception as e:
            print(f"실패: {e}")
            failed += 1
            continue

        report["source"] = "네이버금융 산업분석"
        saved = save_research_note(vault_path, cname, report, analysis)
        print(f"  저장: {saved.relative_to(vault_path)}")
        done += 1

    print(f"\n완료 — 저장 {done}건 / 실패 {failed}건")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="네이버 금융 산업분석 → 미국/해외 기업 리포트 수집",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  --date today                         오늘
  --date 2026-05-14                    특정 날짜
  --from 2026-04-14 --to 2026-05-14    한 달
  --date today --company NVIDIA        단일 기업
        """,
    )
    parser.add_argument("--vault",   required=True)
    parser.add_argument("--date",    default=None)
    parser.add_argument("--from",    dest="date_from", default=None)
    parser.add_argument("--to",      dest="date_to",   default=None)
    parser.add_argument("--company", default=None)
    args = parser.parse_args()

    vault_path = Path(args.vault).resolve()
    if not vault_path.exists():
        print(f"오류: 볼트 경로 없음 — {vault_path}", file=sys.stderr)
        sys.exit(1)

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
            date_from = date_to = datetime.now().strftime("%Y-%m-%d")
    except ValueError as e:
        print(f"오류: {e}", file=sys.stderr)
        sys.exit(1)

    run_batch(vault_path, date_from, date_to, args.company)


if __name__ == "__main__":
    main()
