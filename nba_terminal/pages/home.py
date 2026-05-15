"""Dashboard page for the unified NBA Terminal."""

from __future__ import annotations

from PyQt6.QtWidgets import QGridLayout, QLabel, QVBoxLayout, QWidget

from nba_terminal.theme import COLORS
from nba_terminal.ui.common import card, eyebrow_label, scroll_page, title_label

MODULES = (
    ("Player Analytics", "pages/player_stats.py", "Season, opponent, rolling, hit-rate, and game-log views."),
    ("Points Predictor", "pages/predictions.py", "Transparent weighted player points projection."),
    ("Team Defense", "pages/team_defense.py", "Opponent FG% and shot-zone defense rankings."),
    ("Consistency", "pages/consistency.py", "Team CV rankings by player, stat, and game window."),
    ("Slate Scanner", "pages/slate_scanner.py", "Today slate scan for recent scoring edges."),
    ("Stats Explorer", "pages/api_explorer.py", "Searchable nba_api endpoint and dataset reference."),
    ("Picks Archive", "nba_terminal/data/picks/*.MD", "Historical pick notes in one searchable terminal view."),
)


class HomePage(QWidget):
    """First terminal screen with module status cards."""

    def __init__(self) -> None:
        super().__init__()
        scroll, _, layout = scroll_page()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

        layout.addWidget(eyebrow_label("NBA TERMINAL"))
        layout.addWidget(title_label("Terminal Dashboard"))

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)
        for index, (name, source, detail) in enumerate(MODULES):
            grid.addWidget(self._module_card(name, source, detail), index // 2, index % 2)
        layout.addLayout(grid)
        layout.addStretch()

    def _module_card(self, name: str, source: str, detail: str) -> QWidget:
        frame = card()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(10)

        source_label = QLabel(source)
        source_label.setStyleSheet(
            f"color: {COLORS['text_tertiary']}; font-size: 11px; font-weight: 700;"
        )
        layout.addWidget(source_label)

        name_label = QLabel(name)
        name_label.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-size: 18px; font-weight: bold;"
        )
        layout.addWidget(name_label)

        detail_label = QLabel(detail)
        detail_label.setWordWrap(True)
        detail_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        layout.addWidget(detail_label)
        return frame
