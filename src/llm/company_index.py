"""
companies.csv → 티커/키워드 인덱스 빌드.
모듈 로드 시 1회 빌드, 이후 재사용.
"""
import csv
from pathlib import Path

_CSV_PATH = Path(__file__).parent.parent.parent / "companies.csv"

# company name → ticker (예: "NVIDIA" → "NVDA", "삼성전자" → "005930")
TICKER_INDEX: dict[str, str] = {}

# company name → keyword list (소문자 정규화)
KEYWORD_INDEX: dict[str, list[str]] = {}


def _build() -> None:
    if not _CSV_PATH.exists():
        return
    with _CSV_PATH.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = row.get("name", "").strip()
            ticker = row.get("ticker", "").strip()
            kw_raw = row.get("keywords", "").strip()
            if not name:
                continue
            if ticker:
                TICKER_INDEX[name] = ticker
            keywords = [k.strip() for k in kw_raw.split(",") if k.strip()]
            KEYWORD_INDEX[name] = keywords


_build()
