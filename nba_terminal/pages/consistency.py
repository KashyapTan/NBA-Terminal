"""Team consistency and coefficient-of-variation terminal page."""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from nba_terminal.analytics import flatten_consistency_results, summarize_consistency
from nba_terminal.services.consistency import fetch_team_consistency
from nba_terminal.theme import COLORS
from nba_terminal.ui.common import card, eyebrow_label, populate_table, scroll_page, style_primary_button, title_label

STATS = ("Points", "Rebounds", "Assists", "Steals", "Blocks")
WINDOWS = (5, 10, 15, 20)


class ConsistencyWorker(QThread):
    """Fetch team player CVs without blocking Qt."""

    finished = pyqtSignal(dict, str)
    error = pyqtSignal(str)

    def __init__(self, team_name: str, season: str) -> None:
        super().__init__()
        self.team_name = team_name
        self.season = season

    def run(self) -> None:
        try:
            results, resolved_team_name = fetch_team_consistency(self.team_name, self.season)
            self.finished.emit(results, resolved_team_name)
        except Exception as exc:
            self.error.emit(str(exc))


class ConsistencyPage(QWidget):
    """Qt-native consistency/CV page."""

    def __init__(self) -> None:
        super().__init__()
        self.results: dict = {}
        self.team_name = ""
        self.worker: ConsistencyWorker | None = None

        scroll, _, layout = scroll_page()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

        layout.addWidget(eyebrow_label("CONSISTENCY"))
        layout.addWidget(title_label("Team CV Board"))

        controls_card = card(radius=12)
        controls = QGridLayout(controls_card)
        controls.setContentsMargins(25, 20, 25, 20)
        controls.setHorizontalSpacing(14)
        controls.setVerticalSpacing(8)
        self.team_input = QLineEdit("Lakers")
        self.season_input = QLineEdit("2025-26")
        self.stat_combo = QComboBox()
        self.stat_combo.addItems(STATS)
        self.window_combo = QComboBox()
        self.window_combo.addItems([f"Last {window}" for window in WINDOWS])
        self.window_combo.setCurrentIndex(1)
        self.load_button = QPushButton("Load CV")
        style_primary_button(self.load_button)
        self.load_button.clicked.connect(self.start_fetch)
        self.stat_combo.currentIndexChanged.connect(self.refresh_table)
        self.window_combo.currentIndexChanged.connect(self.refresh_table)

        fields = (
            ("TEAM", self.team_input, 0, 0, 2),
            ("SEASON", self.season_input, 0, 2, 1),
            ("STAT", self.stat_combo, 0, 3, 1),
            ("WINDOW", self.window_combo, 0, 4, 1),
        )
        for label, widget, row, column, span in fields:
            controls.addWidget(eyebrow_label(label), row, column, 1, span)
            controls.addWidget(widget, row + 1, column, 1, span)
        controls.addWidget(QLabel(""), 0, 5)
        controls.addWidget(self.load_button, 1, 5)
        controls.setColumnStretch(0, 2)
        controls.setColumnStretch(1, 1)
        controls.setColumnStretch(2, 1)
        controls.setColumnStretch(3, 1)
        controls.setColumnStretch(4, 1)
        layout.addWidget(controls_card)

        self.status = QLabel("Ready")
        self.status.setStyleSheet(f"color: {COLORS['text_tertiary']};")
        layout.addWidget(self.status)

        self.summary = QLabel("")
        self.summary.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        layout.addWidget(self.summary)

        self.table = QTableWidget()
        self.table.setMinimumHeight(620)
        layout.addWidget(self.table)

    def start_fetch(self) -> None:
        team = self.team_input.text().strip()
        season = self.season_input.text().strip()
        if not team or not season:
            self.status.setText("Enter a team and season.")
            return
        self.load_button.setEnabled(False)
        self.status.setText(f"Fetching CV board for {team}...")
        self.worker = ConsistencyWorker(team, season)
        self.worker.finished.connect(self.display_results)
        self.worker.error.connect(self.display_error)
        self.worker.start()

    def display_error(self, message: str) -> None:
        self.load_button.setEnabled(True)
        self.status.setText(f"Error: {message}")

    def display_results(self, results: dict, team_name: str) -> None:
        self.load_button.setEnabled(True)
        self.results = results
        self.team_name = team_name
        self.status.setText(f"Loaded {team_name}.")
        self.refresh_table()

    def refresh_table(self) -> None:
        if not self.results:
            return
        stat = self.stat_combo.currentText()
        window = WINDOWS[self.window_combo.currentIndex()]
        rows = flatten_consistency_results(self.results, window, stat, limit=15)
        summary = summarize_consistency(rows)
        self.summary.setText(
            f"{self.team_name} | {stat} | Last {window}: "
            f"{summary['count']} players | Best {summary['best_player']} "
            f"({summary['best_cv']:.1f}% CV) | Avg {summary['avg_cv']:.1f}%"
        )
        table_rows = [
            [
                row["rank"],
                row.get("name", ""),
                f"{row['cv_percent']:.1f}%",
                f"{float(row.get('mean', 0.0)):.1f}",
                f"{float(row.get('std', 0.0)):.1f}",
                row["label"],
                row["color_key"],
            ]
            for row in rows
        ]
        populate_table(
            self.table,
            ("Rank", "Player", "CV", "Mean", "Std Dev", "Tier"),
            table_rows,
            color_key_column=6,
        )
