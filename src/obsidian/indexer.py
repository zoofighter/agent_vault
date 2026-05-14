"""
볼트 파일 변경 감지 (mtime + MD5)

index_state.json 에 {파일경로: {mtime, md5}} 를 저장하고
다음 실행 시 변경된 파일만 반환한다.
"""

import hashlib
import json
from pathlib import Path

_STATE_FILE = "data/index_state.json"
_SKIP_DIRS = {"News", "Curated", "Daily", "Archive", "Digest", "Content", ".obsidian", "__pycache__"}


def _md5(path: Path) -> str:
    h = hashlib.md5()
    h.update(path.read_bytes())
    return h.hexdigest()


def _load_state(state_path: Path) -> dict:
    if state_path.exists():
        try:
            return json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_state(state_path: Path, state: dict) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def get_changed_files(vault_path: str | Path, state_file: str = _STATE_FILE) -> list[Path]:
    """
    볼트에서 변경된 마크다운 파일 목록을 반환하고 상태를 갱신한다.

    News/ 폴더는 색인 대상에서 제외 (뉴스 노트 자체는 참조 문서가 아님).
    """
    vault = Path(vault_path)
    state_path = Path(state_file)
    state = _load_state(state_path)

    changed: list[Path] = []
    current_keys: set[str] = set()

    for md_file in vault.rglob("*.md"):
        # News/ 및 기타 제외 디렉터리 건너뜀
        if any(part in _SKIP_DIRS for part in md_file.parts):
            continue

        key = str(md_file)
        current_keys.add(key)
        mtime = str(md_file.stat().st_mtime)
        prev = state.get(key, {})

        if prev.get("mtime") == mtime:
            continue  # mtime 동일 → MD5 계산 생략

        md5 = _md5(md_file)
        if prev.get("md5") != md5:
            changed.append(md_file)

        state[key] = {"mtime": mtime, "md5": md5}

    # 삭제된 파일 정리
    for key in list(state.keys()):
        if key not in current_keys:
            del state[key]

    _save_state(state_path, state)
    return changed
