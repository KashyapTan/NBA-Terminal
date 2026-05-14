from pathlib import Path

from nba_terminal.services.picks import list_pick_files, read_pick_file


def test_list_pick_files_newest_first(tmp_path: Path):
    old = tmp_path / "12_31_2025.MD"
    new = tmp_path / "1_2_2026.MD"
    ignored = tmp_path / "notes.txt"
    bad = tmp_path / "not_a_date.MD"
    old.write_text("old", encoding="utf-8")
    new.write_text("new", encoding="utf-8")
    ignored.write_text("ignore", encoding="utf-8")
    bad.write_text("bad", encoding="utf-8")

    assert list_pick_files(tmp_path) == [new, old]
    assert list_pick_files(tmp_path / "missing") == []


def test_read_pick_file(tmp_path: Path):
    path = tmp_path / "1_1_2026.MD"
    path.write_bytes("Jalen Brunson over".encode("utf-8"))

    assert read_pick_file(path) == "Jalen Brunson over"
