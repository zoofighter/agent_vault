#!/usr/bin/env python3
"""
TechDoc Generation Agent — Gemini CLI로 Docu/ 섹터 골격 채우기

골격 파일(헤딩만 있음)을 읽어서 챕터(## N부)별로 Gemini 2.5 Pro에 보내고
내용이 채워진 텍스트로 교체한 뒤 저장한다.

Usage:
  python run_docgen.py --sector 반도체 --vault ./agent_vault
  python run_docgen.py --sector 반도체 --vault ./agent_vault --chapter 3
  python run_docgen.py --all --vault ./agent_vault
  python run_docgen.py --sector 반도체 --vault ./agent_vault --dry-run
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

_GEMINI_CMD   = "gemini"
_GEMINI_MODEL = "gemini-2.5-pro"

_SECTOR_DOCS: dict[str, str] = {
    "반도체":    "반도체/반도체_TechDoc.md",
    "AI":        "AI/AI_TechDoc.md",
    "바이오":    "바이오/바이오_TechDoc.md",
    "2차전지":   "2차전지/2차전지_TechDoc.md",
    "자동차":    "자동차/자동차_TechDoc.md",
    "에너지":    "에너지/에너지_TechDoc.md",
    "디스플레이":"디스플레이/디스플레이_TechDoc.md",
    "헬스케어":  "헬스케어/헬스케어_TechDoc.md",
    "우주방산":  "우주방산/우주방산_TechDoc.md",
    "양자컴퓨팅":"양자컴퓨팅/양자컴퓨팅_TechDoc.md",
    "로보틱스":  "로보틱스/로보틱스_TechDoc.md",
}

_FILL_PROMPT = """\
당신은 개인 투자자를 위한 섹터 기술 문서를 작성하는 전문가다.

[작성 규칙]
- 반드시 한국어로만 작성한다. 영문 기술 용어는 한국어 옆 괄호로 병기 (예: 패키징(CoWoS)).
- 문장은 짧게. 한 번호에 한 사실. 구어체: "~임", "~함", "~인 것임".
- 어려운 개념은 일상 비유로 설명한다.
- 투자자 관점에서 "왜 중요한가"를 항상 포함한다.
- ### 소제목 아래에 3~8개 번호 포인트로 채운다.
- #### 소소제목 아래에 2~5개 번호 포인트로 채운다.
- 헤딩(##, ###, ####)은 그대로 유지하고 내용만 추가한다.
- 마크다운 코드블록(```), 표, 인용문(>) 활용 가능.
- 중국어·일본어·러시아어를 절대 섞지 않는다.

[작업 지시]
아래 골격의 각 섹션에 내용을 채워라.
헤딩은 수정하지 말고 그 아래에 번호 포인트를 추가한다.
골격에 이미 내용이 있는 줄은 그대로 유지한다.

섹터: {sector}
챕터: {chapter_title}

--- 골격 시작 ---
{skeleton}
--- 골격 끝 ---
"""


def _split_chapters(text: str) -> tuple[str, list[tuple[str, str]]]:
    """frontmatter + 문서 제목과 챕터 목록 분리."""
    # frontmatter 분리 (--- ... --- 블록)
    fm_match = re.match(r"^---\n.*?---\n", text, re.DOTALL)
    header = fm_match.group(0) if fm_match else ""
    body = text[len(header):]

    # ## N부 또는 ## 부록 으로 챕터 분할
    parts = re.split(r"(?=\n## )", body)
    preamble = parts[0]  # 문서 제목 + 소개 (## 이전)
    chapters: list[tuple[str, str]] = []

    for part in parts[1:]:
        title_match = re.match(r"\n## (.+)", part)
        title = title_match.group(1).strip() if title_match else "챕터"
        chapters.append((title, part))

    return header + preamble, chapters


def _call_gemini(sector: str, chapter_title: str, skeleton: str, timeout: int = 240) -> str:
    prompt = _FILL_PROMPT.format(
        sector=sector,
        chapter_title=chapter_title,
        skeleton=skeleton.strip(),
    )
    try:
        result = subprocess.run(
            [_GEMINI_CMD, "--model", _GEMINI_MODEL, prompt],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = result.stdout.strip()
        if not out and result.stderr:
            # stderr에 오류 내용이 있을 수 있음
            print(f"    stderr: {result.stderr[:200]}")
        return out
    except subprocess.TimeoutExpired:
        print(f"    타임아웃 ({timeout}초) — 스킵")
        return ""
    except Exception as e:
        print(f"    오류: {e}")
        return ""


def _sanitize(text: str) -> str:
    """CJK(중국어·일본어)·키릴 문자 제거."""
    _CJK_REPLACE = {
        "増加": "증가", "需要": "수요", "技術": "기술", "市場": "시장",
        "供給": "공급", "生産": "생산", "投資": "투자", "企業": "기업",
    }
    for zh, ko in _CJK_REPLACE.items():
        text = text.replace(zh, ko)
    text = re.sub(r"[一-鿿぀-ヿ　-〿]", "", text)
    text = re.sub(r"[Ѐ-ӿ]", "", text)
    return text


def fill_doc(doc_path: Path, sector: str, target_chapter: int | None, dry_run: bool) -> bool:
    """골격 파일을 읽어 챕터별로 Gemini가 채운 내용으로 교체한다."""
    if not doc_path.exists():
        print(f"  파일 없음: {doc_path}")
        return False

    raw = doc_path.read_text(encoding="utf-8")
    preamble, chapters = _split_chapters(raw)

    if not chapters:
        print(f"  챕터 없음 — 건너뜀")
        return False

    print(f"  챕터 {len(chapters)}개 감지")
    filled_chapters: list[str] = []

    for idx, (title, skeleton) in enumerate(chapters, 1):
        if target_chapter is not None and idx != target_chapter:
            filled_chapters.append(skeleton)
            continue

        print(f"  [{idx}/{len(chapters)}] {title} 생성 중...")
        if dry_run:
            print(f"    --dry-run: Gemini 호출 생략")
            filled_chapters.append(skeleton)
            continue

        filled = _call_gemini(sector, title, skeleton)
        if filled:
            filled = _sanitize(filled)
            # 챕터 헤딩을 항상 고정 (Gemini 출력에 헤딩 포함 여부 무관)
            filled = re.sub(r"^#+\s+" + re.escape(title) + r"\s*\n?", "", filled).lstrip("\n")
            filled = "\n## " + title + "\n" + filled
            filled_chapters.append(filled)
            print(f"    완료 ({len(filled)} chars)")
        else:
            print(f"    실패 — 원본 유지")
            filled_chapters.append(skeleton)

    if dry_run:
        return True

    new_content = preamble + "".join(filled_chapters)
    # frontmatter의 status를 업데이트
    if target_chapter is None:
        new_content = re.sub(r"(?m)^status: in-progress", "status: complete", new_content)
    doc_path.write_text(new_content, encoding="utf-8")
    print(f"  저장: {doc_path}")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="TechDoc 골격 채우기 (Gemini CLI)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--sector", help="섹터명 (예: 반도체)")
    group.add_argument("--all", action="store_true", help="전체 11개 섹터 순차 실행")
    parser.add_argument("--vault", default="./agent_vault", help="볼트 경로 (기본: ./agent_vault)")
    parser.add_argument("--chapter", type=int, default=None, help="특정 챕터 번호만 (예: --chapter 3)")
    parser.add_argument("--dry-run", action="store_true", help="Gemini 호출 없이 시뮬레이션")
    args = parser.parse_args()

    if not shutil.which(_GEMINI_CMD):
        print(f"오류: '{_GEMINI_CMD}' 명령을 찾을 수 없음. npm install -g @google/gemini-cli 필요.")
        sys.exit(1)

    docu_dir = Path(args.vault) / "Docu"
    if not docu_dir.exists():
        print(f"오류: {docu_dir} 없음")
        sys.exit(1)

    sectors = list(_SECTOR_DOCS.keys()) if args.all else [args.sector]

    for sector in sectors:
        rel = _SECTOR_DOCS.get(sector)
        if not rel:
            print(f"알 수 없는 섹터: {sector}. 사용 가능: {list(_SECTOR_DOCS)}")
            continue

        doc_path = docu_dir / rel
        print(f"\n[{sector}] {doc_path.name}")
        fill_doc(doc_path, sector, args.chapter, args.dry_run)

    print("\n완료.")


if __name__ == "__main__":
    main()
