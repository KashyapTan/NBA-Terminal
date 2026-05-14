"""Historical picks archive terminal page."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from nba_terminal.services.picks import DEFAULT_PICKS_DIR, list_pick_files, read_pick_file
from nba_terminal.theme import COLORS
from nba_terminal.ui.common import eyebrow_label, title_label


class PicksArchivePage(QWidget):
    """Browse historical pick markdown files from the picks directory."""

    def __init__(self) -> None:
        super().__init__()
        self.picks_dir = DEFAULT_PICKS_DIR
        self.files = list_pick_files(self.picks_dir)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 28, 28, 28)
        root.setSpacing(16)
        root.addWidget(eyebrow_label("PICKS ARCHIVE"))
        root.addWidget(title_label("Historical Picks"))

        split = QHBoxLayout()
        self.file_list = QListWidget()
        self.file_list.setMinimumWidth(260)
        self.file_list.setStyleSheet(
            f"background-color: {COLORS['bg_card']}; border: 1px solid {COLORS['border']};"
        )
        self.file_list.currentItemChanged.connect(self.display_pick)
        split.addWidget(self.file_list, 1)

        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setStyleSheet(
            f"background-color: {COLORS['bg_card']}; color: {COLORS['text_primary']};"
            f"border: 1px solid {COLORS['border']}; padding: 12px;"
        )
        split.addWidget(self.preview, 4)
        root.addLayout(split)

        self.status = QLabel("")
        self.status.setStyleSheet(f"color: {COLORS['text_tertiary']};")
        root.addWidget(self.status)
        self.populate_files()

    def populate_files(self) -> None:
        self.file_list.clear()
        for path in self.files:
            item = QListWidgetItem(path.name)
            item.setData(Qt.ItemDataRole.UserRole, path)
            self.file_list.addItem(item)
        self.status.setText(f"{len(self.files)} pick files")
        if self.file_list.count():
            self.file_list.setCurrentRow(0)

    def display_pick(self) -> None:
        item = self.file_list.currentItem()
        if item is None:
            self.preview.clear()
            return
        path = item.data(Qt.ItemDataRole.UserRole)
        self.preview.setPlainText(read_pick_file(path))
