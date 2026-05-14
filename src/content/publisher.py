"""
콘텐츠 초안 → agent_vault/Content/{Blog|YouTube}/ 저장
"""

import re
from pathlib import Path

from src.content.curator import ContentCandidate

_CONTENT_DIR = "Content"


def _safe_filename(text: str) -> str:
    text = re.sub(r'[\\/:*?"<>|]', "", text)
    return text.strip()[:60]


def _extract_title(content: str) -> str:
    m = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    return m.group(1).strip() if m else ""


def save_blog(
    vault_path: Path,
    candidate: ContentCandidate,
    content: str,
    dry_run: bool = False,
) -> Path:
    title = _extract_title(content) or f"{candidate.company} 브리핑"
    safe = _safe_filename(title)
    filename = f"{candidate.date}_{candidate.company}_{safe}.md"

    out_dir = vault_path / _CONTENT_DIR / "Blog"
    out_path = out_dir / filename

    frontmatter = (
        f"---\n"
        f"title: \"{title}\"\n"
        f"company: {candidate.company}\n"
        f"date: {candidate.date}\n"
        f"type: blog-draft\n"
        f"tags:\n"
        f"  - content\n"
        f"  - blog\n"
        f"  - {candidate.company}\n"
        f"---\n\n"
    )

    full = frontmatter + content

    if dry_run:
        print(f"  [dry-run] blog: {out_path.relative_to(vault_path)}")
        return out_path

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_text(full, encoding="utf-8")
    return out_path


def save_youtube(
    vault_path: Path,
    candidate: ContentCandidate,
    content: str,
    dry_run: bool = False,
) -> Path:
    filename = f"{candidate.date}_{candidate.company}_스크립트.md"
    out_dir = vault_path / _CONTENT_DIR / "YouTube"
    out_path = out_dir / filename

    frontmatter = (
        f"---\n"
        f"company: {candidate.company}\n"
        f"date: {candidate.date}\n"
        f"type: youtube-script\n"
        f"tags:\n"
        f"  - content\n"
        f"  - youtube\n"
        f"  - {candidate.company}\n"
        f"---\n\n"
    )

    full = frontmatter + content

    if dry_run:
        print(f"  [dry-run] youtube: {out_path.relative_to(vault_path)}")
        return out_path

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_text(full, encoding="utf-8")
    return out_path
