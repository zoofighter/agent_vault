#!/usr/bin/env python3
"""
report_download/*.html → Obsidian Research 폴더 배치 등록

사용:
  python run_html_reports.py                          # report_download/ 전체 처리
  python run_html_reports.py --file "분석.html"       # 단일 파일
  python run_html_reports.py --file "분석.html" --company SK하이닉스
  python run_html_reports.py --no-archive             # 아카이브 없이 실행
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.research.register_html import main

if __name__ == "__main__":
    main()
