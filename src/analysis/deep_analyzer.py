"""
심층분석 — 멀티소스 수집 + Gemini 2.5 Pro 투자 판단 초안 생성

소스 (우선순위):
  1. Companies/{기업}/Daily/   — 최근 14일 뉴스 요약
  2. Companies/{기업}/Research/ — 최근 증권사 리포트 요약
  3. Companies/{기업}/Memos/   — 내 투자 판단 히스토리
  4. Reports/{섹터}/           — 최신 TechReport (섹터 매칭)
"""

from __future__ import annotations

import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

_GEMINI_CMD   = "gemini"
_GEMINI_MODEL = "gemini-2.5-pro"
_TIMEOUT      = 180

_SYSTEM_PROMPT = """\
당신은 개인 투자자를 위한 심층 투자 분석 어시스턴트다.

[분석 원칙]
- 반드시 한국어로만 작성한다.
- 사실과 추정을 명확히 구분한다: 사실은 "~임", 추정은 "~으로 보임", "~가능성 있음".
- 매수 근거와 리스크를 대칭적으로 다룬다. 한쪽으로 치우치지 않는다.
- 구체적 수치(목표주가, 컨센서스, 날짜)는 출처와 함께 제시한다.
- 투자 판단은 어디까지나 참고용임을 명시한다.

[출력 형식]
## 매수 근거
번호 포인트 3~5개. 각 포인트에 근거 출처 명시.

## 리스크 요인
번호 포인트 3~5개. 심각도(상/중/하) 표시.

## 포지션 제안
단기 / 장기 전망 분리. 구체적 행동 제안 (분할매수, 관망, 비중확대 등).

## 추적 지표
투자 논리를 검증하기 위해 앞으로 모니터링할 지표 3~5개.
"""


def _read_daily_notes(company_path: Path, days: int = 14) -> str:
    daily_dir = company_path / "Daily"
    if not daily_dir.exists():
        return ""

    today = datetime.now(timezone.utc)
    notes = sorted(daily_dir.glob("*.md"), reverse=True)
    collected: list[str] = []

    for note in notes[:days]:
        text = note.read_text(encoding="utf-8")
        synthesis = ""
        m = re.search(r"## 종합 분석\n\n(.*?)(?:\n---|\Z)", text, re.DOTALL)
        if m:
            synthesis = m.group(1).strip()[:800]
        titles = re.findall(r"^### \d+\. (.+)$", text, re.MULTILINE)[:5]
        if synthesis or titles:
            date_label = note.stem[:10]
            collected.append(
                f"[{date_label}] 뉴스 {len(titles)}건\n"
                + "\n".join(f"  - {t}" for t in titles)
                + (f"\n  종합: {synthesis}" if synthesis else "")
            )

    return "\n\n".join(collected)


def _read_research(company_path: Path, limit: int = 5) -> str:
    research_dir = company_path / "Research"
    if not research_dir.exists():
        return ""

    notes = sorted(research_dir.glob("*.md"), reverse=True)[:limit]
    collected: list[str] = []

    for note in notes:
        text = note.read_text(encoding="utf-8")
        # frontmatter에서 날짜·증권사 추출
        date_m = re.search(r"^date:\s*(.+)$", text, re.MULTILINE)
        broker_m = re.search(r"^broker:\s*(.+)$", text, re.MULTILINE)
        title_m = re.search(r"^title:\s*\"?(.+?)\"?$", text, re.MULTILINE)
        # 본문에서 핵심 주장·투자 포인트 추출
        body = re.sub(r"^---.*?---\n", "", text, flags=re.DOTALL)
        body = body[:600].strip()
        label = f"[{date_m.group(1).strip() if date_m else '?'}] {broker_m.group(1).strip() if broker_m else ''}"
        if title_m:
            label += f" — {title_m.group(1).strip()}"
        collected.append(f"{label}\n{body}")

    return "\n\n".join(collected)


def _read_memos(company_path: Path) -> str:
    memo_dir = company_path / "Memos"
    if not memo_dir.exists():
        return ""

    notes = sorted(memo_dir.glob("*.md"), reverse=True)[:5]
    collected: list[str] = []

    for note in notes:
        text = note.read_text(encoding="utf-8")
        body = re.sub(r"^---.*?---\n", "", text, flags=re.DOTALL).strip()[:500]
        if body:
            collected.append(f"[{note.stem}]\n{body}")

    return "\n\n".join(collected)


def _find_tech_report(vault: Path, company_path: Path) -> str:
    """company_path에서 섹터를 추정해 최신 TechReport를 찾는다."""
    reports_dir = vault / "Reports"
    if not reports_dir.exists():
        return ""

    # 최근 30일 내 모든 리포트에서 기업명 포함 여부 확인
    company_name = company_path.name
    found: list[tuple[str, str]] = []

    for md in sorted(reports_dir.rglob("*.md"), reverse=True)[:20]:
        text = md.read_text(encoding="utf-8")
        if company_name in text or company_name.lower() in text.lower():
            date_m = re.search(r"^date:\s*(.+)$", text, re.MULTILINE)
            body = re.sub(r"^---.*?---\n", "", text, flags=re.DOTALL).strip()[:600]
            label = f"[TechReport {md.parent.name}/{md.stem}]"
            found.append((label, body))
            if len(found) >= 2:
                break

    return "\n\n".join(f"{label}\n{body}" for label, body in found)


def _call_gemini(prompt: str) -> str:
    if not shutil.which(_GEMINI_CMD):
        return ""
    try:
        result = subprocess.run(
            [_GEMINI_CMD, "--model", _GEMINI_MODEL, prompt],
            capture_output=True, text=True, timeout=_TIMEOUT,
        )
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return ""
    except Exception:
        return ""


def analyze(vault: Path, company: str) -> tuple[str, str]:
    """
    멀티소스 수집 후 Gemini 2.5 Pro로 투자 판단 초안 생성.
    Returns: (draft_text, sources_summary)
    """
    from src.obsidian.company_manager import company_dir as _company_dir

    try:
        company_path = _company_dir(vault, company)
    except ValueError:
        # 볼트에서 직접 검색
        matches = list(vault.glob(f"Companies/*/{company}"))
        if not matches:
            return f"{company} 기업 디렉토리를 찾을 수 없음", ""
        company_path = matches[0]

    print(f"  [analyzer] 소스 수집: {company_path.name}")

    daily   = _read_daily_notes(company_path)
    research = _read_research(company_path)
    memos   = _read_memos(company_path)
    techreport = _find_tech_report(vault, company_path)

    sources_parts = []
    if daily:
        sources_parts.append(f"Daily 노트 {daily.count('[20')}")
    if research:
        sources_parts.append(f"증권사 리포트 {research.count('[20')}건")
    if memos:
        sources_parts.append(f"메모 {memos.count('[')}")
    if techreport:
        sources_parts.append("TechReport")
    sources_summary = " / ".join(sources_parts) or "소스 없음"

    sections = [f"분석 대상: {company}"]
    if daily:
        sections.append(f"## 최근 뉴스 (Daily 노트)\n{daily}")
    if research:
        sections.append(f"## 증권사 리포트 요약\n{research}")
    if memos:
        sections.append(f"## 내 투자 판단 히스토리 (Memos)\n{memos}")
    if techreport:
        sections.append(f"## 관련 TechReport\n{techreport}")

    if len(sections) == 1:
        return f"{company} 관련 데이터 없음 — Daily 노트를 먼저 수집하세요", ""

    user_content = "\n\n".join(sections)
    full_prompt = _SYSTEM_PROMPT + "\n\n" + user_content

    print(f"  [analyzer] Gemini 2.5 Pro 분석 중... (소스: {sources_summary})")
    draft = _call_gemini(full_prompt)

    if not draft:
        draft = "Gemini CLI 호출 실패 — gemini 명령 확인 필요"

    return draft, sources_summary


def save_memo(vault: Path, company: str, content: str, date_str: str | None = None) -> Path:
    """
    분석 결과 + 사용자 코멘트를 Memos/{date}_심층분석.md로 저장.
    다음 RAG 사이클에서 ChromaDB에 임베딩됨.
    """
    from src.obsidian.company_manager import company_dir as _company_dir

    try:
        company_path = _company_dir(vault, company)
    except ValueError:
        matches = list(vault.glob(f"Companies/*/{company}"))
        company_path = matches[0] if matches else vault / "Companies" / "KR" / company

    date_str = date_str or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    memo_dir = company_path / "Memos"
    memo_dir.mkdir(parents=True, exist_ok=True)

    # 같은 날 중복 방지
    suffix = ""
    for s in ["", "_b", "_c"]:
        candidate = memo_dir / f"{date_str}_심층분석{s}.md"
        if not candidate.exists():
            path = candidate
            break
    else:
        path = memo_dir / f"{date_str}_심층분석_{datetime.now().strftime('%H%M%S')}.md"

    frontmatter = (
        f"---\n"
        f"type: deep-analysis\n"
        f"company: {company}\n"
        f"date: {date_str}\n"
        f"created: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}\n"
        f"tags:\n"
        f"  - analysis\n"
        f"  - {company}\n"
        f"---\n\n"
        f"# {company} 심층 분석 — {date_str}\n\n"
    )
    path.write_text(frontmatter + content + "\n", encoding="utf-8")
    return path
