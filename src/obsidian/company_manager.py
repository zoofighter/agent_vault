"""
companies.csv를 읽고 Obsidian 볼트에 회사별 폴더 구조를 자동 생성/동기화한다.

CSV 컬럼: name, region, ticker, exchange, sector, industry, active, keywords

볼트 구조:
  Companies/
    {region}/
      삼성전자/
        삼성전자.md
        Daily/
        Research/
        Memos/

사용법:
  python -m src.obsidian.company_manager --vault ./agent_vault
  python -m src.obsidian.company_manager --vault ./agent_vault --status
  python -m src.obsidian.company_manager --vault ./agent_vault --dry-run
"""

import argparse
import csv
import sys
from pathlib import Path

from src.obsidian.templates import company_note

COMPANIES_CSV = Path(__file__).resolve().parents[2] / "companies.csv"
COMPANIES_FOLDER = "Companies"
SUBFOLDERS = ["Daily", "Research", "Memos"]

_REGION_MAP: dict[str, str] | None = None


def _get_region_map() -> dict[str, str]:
    global _REGION_MAP
    if _REGION_MAP is None:
        mapping: dict[str, str] = {}
        with open(COMPANIES_CSV, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                name = row.get("name", "").strip()
                region = row.get("region", "").strip()
                if name:
                    mapping[name] = region
        _REGION_MAP = mapping
    return _REGION_MAP


def get_region(name: str) -> str:
    """companies.csv에서 기업의 region 코드를 반환한다."""
    return _get_region_map().get(name, "")


def company_dir(vault_path: Path, name: str) -> Path:
    """
    기업의 볼트 디렉터리 경로를 반환한다.
    companies.csv에 region이 없으면 ValueError를 발생시킨다.
    """
    region = get_region(name)
    if not region:
        raise ValueError(f"Region not found for '{name}' — check companies.csv")
    return vault_path / COMPANIES_FOLDER / region / name


def load_companies(csv_path: Path = COMPANIES_CSV) -> list[dict]:
    companies = []
    with open(csv_path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("name", "").strip()
            ticker = row.get("ticker", "").strip()
            if not name:
                continue
            if not ticker and row.get("exchange", "").strip().upper() != "PRIVATE":
                continue

            company = {"name": name, "ticker": ticker}
            company["region"] = row.get("region", "").strip()
            company["exchange"] = row.get("exchange", "").strip()
            company["sector"] = row.get("sector", "").strip()
            company["industry"] = row.get("industry", "").strip()
            active_raw = row.get("active", "true").strip().lower()
            company["active"] = active_raw not in ("false", "0", "no", "n")

            kw_raw = row.get("keywords", "").strip()
            company["keywords"] = [k.strip() for k in kw_raw.split(",") if k.strip()]

            companies.append(company)
    return companies


def active_companies(companies: list[dict]) -> list[dict]:
    return [c for c in companies if c.get("active", True)]


def sync_vault(vault_path: Path, dry_run: bool = False) -> list[str]:
    companies = load_companies()
    created = []

    for company in companies:
        if not company["active"]:
            continue

        name = company["name"]
        try:
            co_dir = company_dir(vault_path, name)
        except ValueError as e:
            print(f"  [warn] {e} — 건너뜀")
            continue
        note_path = co_dir / f"{name}.md"

        if not dry_run:
            co_dir.mkdir(parents=True, exist_ok=True)
            for sub in SUBFOLDERS:
                (co_dir / sub).mkdir(exist_ok=True)

        if not note_path.exists():
            if not dry_run:
                note_path.write_text(company_note(company), encoding="utf-8")
            created.append(str(note_path))

    return created


def print_status(vault_path: Path) -> None:
    companies = load_companies()

    print(f"\n{'회사명':<16} {'리전':<8} {'티커':<8} {'섹터':<16} {'수집':<6} {'폴더':<6} {'프로필'}")
    print("-" * 76)
    for c in companies:
        name = c["name"]
        region = c.get("region", "?")
        ticker = c["ticker"]
        sector = c["sector"] or "-"
        active = "활성" if c["active"] else "중지"
        try:
            co_dir = company_dir(vault_path, name)
        except ValueError:
            co_dir = vault_path / COMPANIES_FOLDER / "?" / name
        folder_status = "있음" if co_dir.exists() else "없음"
        note_status = "있음" if (co_dir / f"{name}.md").exists() else "없음"
        print(f"{name:<16} {region:<8} {ticker:<8} {sector:<16} {active:<6} {folder_status:<6} {note_status}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="기업 볼트 동기화 도구")
    parser.add_argument("--vault", required=True, help="Obsidian 볼트 경로")
    parser.add_argument("--status", action="store_true", help="등록 현황만 출력")
    parser.add_argument("--dry-run", action="store_true", help="실제 파일 생성 없이 시뮬레이션")
    args = parser.parse_args()

    vault_path = Path(args.vault).resolve()
    if not vault_path.exists():
        print(f"오류: 볼트 경로를 찾을 수 없습니다 — {vault_path}", file=sys.stderr)
        sys.exit(1)

    if args.status:
        print_status(vault_path)
        return

    created = sync_vault(vault_path, dry_run=args.dry_run)
    prefix = "[dry-run] " if args.dry_run else ""

    if created:
        for path in created:
            print(f"{prefix}생성: {path}")
    else:
        print(f"{prefix}변경 사항 없음 — 모든 회사 파일이 이미 존재합니다.")


if __name__ == "__main__":
    main()
