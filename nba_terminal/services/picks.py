"""Historical picks archive helpers."""

from __future__ import annotations

from pathlib import Path

from nba_terminal.analytics import parse_pick_date_from_name

DEFAULT_PICKS_DIR = Path(__file__).resolve().parents[1] / "data" / "picks"


def list_pick_files(picks_dir: Path = DEFAULT_PICKS_DIR) -> list[Path]:
    """Return dated pick markdown files newest first."""
    if not picks_dir.exists():
        return []
    files = [
        path
        for path in picks_dir.iterdir()
        if path.is_file() and path.suffix.lower() == ".md" and parse_pick_date_from_name(path.name)
    ]
    return sorted(files, key=lambda path: parse_pick_date_from_name(path.name) or (0, 0, 0), reverse=True)


def read_pick_file(path: Path) -> str:
    """Read a pick markdown file with a forgiving UTF-8 fallback."""
    return path.read_text(encoding="utf-8", errors="replace")
