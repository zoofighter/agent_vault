#!/usr/bin/env python3
"""
볼트 구조 마이그레이션

Companies/{company}/ → Companies/{region}/{company}/

기존 News/, Curated/ 서브폴더는 삭제하지 않음 (아카이브 유지).
마이그레이션 완료 후 ChromaDB와 index_state.json을 초기화한다
(경로 변경으로 다음 실행 시 전체 재인덱스 필요).

사용법:
  python migrate_vault.py --vault ./sample_vault --dry-run
  python migrate_vault.py --vault ./sample_vault
"""

import argparse
import csv
import shutil
import sys
import unicodedata
from pathlib import Path

COMPANIES_CSV = Path(__file__).parent / "companies.csv"
COMPANIES_FOLDER = "Companies"
CHROMA_PATH = Path(__file__).parent / "data" / "chroma"
INDEX_STATE = Path(__file__).parent / "data" / "index_state.json"
REGION_FOLDERS = {"KR", "US", "CN", "TW", "JP", "Private"}


def _load_region_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    with open(COMPANIES_CSV, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            name = row.get("name", "").strip()
            region = row.get("region", "").strip()
            if name and region:
                mapping[name] = region
    return mapping


def migrate(vault_path: Path, dry_run: bool) -> None:
    region_map = _load_region_map()
    companies_root = vault_path / COMPANIES_FOLDER

    if not companies_root.exists():
        print(f"오류: {companies_root} 없음")
        sys.exit(1)

    moved, skipped, warned = [], [], []

    for co_dir in sorted(companies_root.iterdir()):
        if not co_dir.is_dir():
            continue
        name = unicodedata.normalize("NFC", co_dir.name)

        # 이미 region 폴더면 건너뜀
        if name in REGION_FOLDERS:
            continue

        region = region_map.get(name)
        if not region:
            print(f"  [warn] '{name}' — companies.csv에 region 없음, 건너뜀")
            warned.append(name)
            continue

        dest_parent = companies_root / region
        dest = dest_parent / name

        if dest.exists():
            print(f"  [skip] 이미 존재: {COMPANIES_FOLDER}/{region}/{name}")
            skipped.append(name)
            continue

        print(f"  {name:<20} → {COMPANIES_FOLDER}/{region}/{name}")
        moved.append(name)

        if not dry_run:
            dest_parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(co_dir), str(dest))

    prefix = "[dry-run] " if dry_run else ""
    print(f"\n{prefix}이동: {len(moved)}개 / 건너뜀: {len(skipped)}개 / 경고: {len(warned)}개")

    if dry_run or not moved:
        return

    # ChromaDB + index_state 초기화
    if CHROMA_PATH.exists():
        shutil.rmtree(CHROMA_PATH)
        print(f"ChromaDB 초기화: {CHROMA_PATH}/")
    if INDEX_STATE.exists():
        INDEX_STATE.unlink()
        print(f"인덱스 상태 초기화: {INDEX_STATE}")

    print("\n마이그레이션 완료. 다음 실행 시 전체 재인덱싱이 수행됩니다.")


def main() -> None:
    parser = argparse.ArgumentParser(description="볼트 구조 마이그레이션")
    parser.add_argument("--vault", required=True, help="Obsidian 볼트 경로")
    parser.add_argument("--dry-run", action="store_true",
                        help="실제 파일 이동 없이 시뮬레이션")
    args = parser.parse_args()

    vault_path = Path(args.vault).resolve()
    if not vault_path.exists():
        print(f"오류: 볼트 경로 없음 — {vault_path}", file=sys.stderr)
        sys.exit(1)

    migrate(vault_path, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
