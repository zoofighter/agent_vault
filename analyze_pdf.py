#!/opt/anaconda3/bin/python
"""
PDF 분석 스크립트

로컬 비전 LLM(gemma4:26b)으로 PDF를 페이지별로 읽고 요약한다.
사용: python analyze_pdf.py <PDF파일경로> [--pages 1-5] [--summary]
"""

import argparse
import base64
import sys
from pathlib import Path

import fitz   # PyMuPDF
import ollama

_MODEL = "gemma4:26b"
_DPI   = 150   # 해상도 — 높을수록 정확하지만 느림


def pdf_to_images(pdf_path: str, page_range: tuple[int, int] | None = None) -> list[tuple[int, bytes]]:
    """PDF 페이지를 PNG 이미지 바이트로 변환한다."""
    doc = fitz.open(pdf_path)
    total = len(doc)
    start, end = (0, total) if page_range is None else (page_range[0] - 1, page_range[1])
    end = min(end, total)

    images = []
    for i in range(start, end):
        pix = doc[i].get_pixmap(dpi=_DPI)
        images.append((i + 1, pix.tobytes("png")))
    doc.close()
    return images


def analyze_page(page_num: int, img_bytes: bytes, question: str = "") -> str:
    """단일 페이지를 LLM으로 분석한다."""
    prompt = question or "이 페이지의 핵심 내용을 한국어로 간결하게 요약해줘. 표나 수치가 있으면 포함해줘."
    img_b64 = base64.b64encode(img_bytes).decode()

    response = ollama.chat(
        model=_MODEL,
        messages=[{
            "role": "user",
            "content": prompt,
            "images": [img_b64],
        }]
    )
    return response["message"]["content"].strip()


def summarize_all(page_summaries: list[tuple[int, str]]) -> str:
    """페이지별 요약을 종합해 전체 보고서 요약을 생성한다."""
    combined = "\n\n".join(f"[페이지 {n}]\n{s}" for n, s in page_summaries)
    prompt = (
        "아래는 보고서 각 페이지의 요약이다.\n\n"
        f"{combined}\n\n"
        "이 보고서의 전체 핵심 내용을 다음 구조로 한국어로 작성해줘:\n"
        "## 보고서 개요\n"
        "## 핵심 발견사항 (3~5개)\n"
        "## 주요 데이터/수치\n"
        "## 결론 및 시사점"
    )
    response = ollama.chat(
        model=_MODEL,
        messages=[{"role": "user", "content": prompt}]
    )
    return response["message"]["content"].strip()


def parse_page_range(s: str) -> tuple[int, int]:
    parts = s.split("-")
    if len(parts) == 2:
        return int(parts[0]), int(parts[1])
    return int(parts[0]), int(parts[0])


def main():
    parser = argparse.ArgumentParser(description="PDF 분석 (gemma4:26b)")
    parser.add_argument("pdf", help="PDF 파일 경로")
    parser.add_argument("--pages", help="페이지 범위 (예: 1-10)", default=None)
    parser.add_argument("--summary", action="store_true", help="전체 요약 생성")
    parser.add_argument("--question", "-q", help="각 페이지에 물어볼 질문", default="")
    parser.add_argument("--output", "-o", help="결과 저장 파일 (.md)", default=None)
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"파일 없음: {pdf_path}")
        sys.exit(1)

    page_range = parse_page_range(args.pages) if args.pages else None

    doc = fitz.open(str(pdf_path))
    total_pages = len(doc)
    doc.close()
    print(f"PDF: {pdf_path.name} ({total_pages}페이지)")
    if page_range:
        print(f"분석 범위: {page_range[0]}~{page_range[1]}페이지")

    images = pdf_to_images(str(pdf_path), page_range)
    print(f"분석 시작 ({len(images)}페이지) — 모델: {_MODEL}\n")

    page_summaries = []
    lines = []

    for page_num, img_bytes in images:
        print(f"[{page_num}/{total_pages}] 분석 중...", end=" ", flush=True)
        result = analyze_page(page_num, img_bytes, args.question)
        page_summaries.append((page_num, result))
        lines.append(f"## 페이지 {page_num}\n\n{result}\n")
        print("완료")

    output_parts = [f"# {pdf_path.stem} — 분석 결과\n\n"]
    output_parts += lines

    if args.summary and len(page_summaries) > 1:
        print("\n전체 요약 생성 중...")
        overall = summarize_all(page_summaries)
        output_parts.insert(1, f"---\n\n# 전체 요약\n\n{overall}\n\n---\n\n")
        print("완료")

    result_text = "".join(output_parts)

    # 출력
    print("\n" + "=" * 60)
    print(result_text[:2000] + ("..." if len(result_text) > 2000 else ""))

    # 파일 저장
    out_path = Path(args.output) if args.output else pdf_path.with_suffix(".md")
    out_path.write_text(result_text, encoding="utf-8")
    print(f"\n저장: {out_path}")


if __name__ == "__main__":
    main()
