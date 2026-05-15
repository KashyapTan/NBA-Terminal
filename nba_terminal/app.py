"""Application shell for the unified NBA Terminal."""

from __future__ import annotations

import sys
from collections.abc import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from nba_terminal import __version__
from nba_terminal.pages.api_explorer import ApiExplorerPage
from nba_terminal.pages.consistency import ConsistencyPage
from nba_terminal.pages.home import HomePage
from nba_terminal.pages.picks_archive import PicksArchivePage
from nba_terminal.pages.player_profile import PlayerProfilePage
from nba_terminal.pages.player_stats import PlayerStatsPage
from nba_terminal.pages.predictions import PredictionsPage
from nba_terminal.pages.slate_scanner import SlateScannerPage
from nba_terminal.pages.team_defense import TeamDefensePage
from nba_terminal.theme import COLORS, app_stylesheet, apply_app_theme

PageFactory = Callable[[], QWidget]


class NBATerminal(QMainWindow):
    """Top-level PyQt application with sidebar navigation."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"NBA Terminal v{__version__}")
        self.resize(1720, 980)
        self.setStyleSheet(app_stylesheet())

        self.nav = QListWidget()
        self.nav.setFixedWidth(230)
        self.nav.setStyleSheet(
            "QListWidget {"
            f"background-color: {COLORS['bg_card']};"
            f"border: none; border-right: 1px solid {COLORS['border']};"
            f"color: {COLORS['text_secondary']}; padding: 10px;"
            "}"
            "QListWidget::item { padding: 10px 12px; border-radius: 5px; }"
            f"QListWidget::item:selected {{ background-color: {COLORS['accent']}; color: white; }}"
            f"QListWidget::item:hover {{ background-color: {COLORS['bg_hover']}; }}"
        )
        self.stack = QStackedWidget()

        shell = QWidget()
        shell_layout = QHBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)
        shell_layout.addWidget(self._build_sidebar())
        shell_layout.addWidget(self.stack, 1)
        self.setCentralWidget(shell)

        self._add_pages()
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setFixedWidth(230)
        sidebar.setStyleSheet(f"background-color: {COLORS['bg_card']};")
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 18, 12, 12)
        layout.setSpacing(14)

        title = QLabel("NBA Terminal")
        title.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-size: 20px; font-weight: 900;"
        )
        subtitle = QLabel("v0.1")
        subtitle.setStyleSheet(f"color: {COLORS['text_tertiary']}; font-size: 11px;")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self.nav, 1)
        return sidebar

    def _add_pages(self) -> None:
        pages: tuple[tuple[str, PageFactory], ...] = (
            ("Dashboard", HomePage),
            ("Player Profile", PlayerProfilePage),
            ("Player Game Logs", PlayerStatsPage),
            ("Points Predictor", PredictionsPage),
            ("Team Defense", TeamDefensePage),
            ("Consistency", ConsistencyPage),
            ("Slate Scanner", SlateScannerPage),
            ("Stats Explorer", ApiExplorerPage),
            ("Picks Archive", PicksArchivePage),
        )
        for label, factory in pages:
            item = QListWidgetItem(label)
            item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter)
            self.nav.addItem(item)
            self.stack.addWidget(factory())


def main(argv: list[str] | None = None) -> int:
    """Start the NBA Terminal app."""
    app = QApplication(argv or sys.argv)
    apply_app_theme(app)
    window = NBATerminal()
    window.show()
    return app.exec()
