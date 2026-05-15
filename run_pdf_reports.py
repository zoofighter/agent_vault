#!/usr/bin/env python3
"""
report_download/*.pdf → Obsidian Research 폴더 배치 등록

사용:
  python run_pdf_reports.py                          # report_download/ 전체 처리
  python run_pdf_reports.py --file "report.pdf"      # 단일 파일
  python run_pdf_reports.py --file "report.pdf" --company NVIDIA
  python run_pdf_reports.py --no-archive             # 아카이브 없이 실행
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.research.register_pdf_batch import main

if __name__ == "__main__":
    main()
