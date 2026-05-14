from pathlib import Path


def test_terminal_package_does_not_import_archived_or_root_legacy_modules():
    root = Path(__file__).resolve().parents[1]
    forbidden = (
        "nba_terminal.legacy",
        "from helper",
        "import helper",
        "from archive",
        "import archive",
        "from p_qt",
        "from stats_qt",
        "from stats_explorer",
        "from topcv",
        "from confident_bets",
    )
    offenders = []
    for path in (root / "nba_terminal").rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="replace")
        for token in forbidden:
            if token in text:
                offenders.append(f"{path.relative_to(root)} contains {token}")
    assert offenders == []
