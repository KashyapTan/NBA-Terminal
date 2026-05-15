"""Team defense rankings terminal page."""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from nba_terminal.analytics import (
    defense_rank_tier,
    format_percentage,
    league_averages,
    sort_team_defense,
)
from nba_terminal.services.nba_fetchers import fetch_team_defense_stats
from nba_terminal.theme import COLORS
from nba_terminal.ui.common import card, eyebrow_label, populate_table, scroll_page, style_primary_button, title_label


class TeamDefenseWorker(QThread):
    """Fetch team defense stats without blocking the Qt UI thread."""

    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, season: str) -> None:
        super().__init__()
        self.season = season

    def run(self) -> None:
        try:
            self.finished.emit(fetch_team_defense_stats(self.season))
        except Exception as exc:
            self.error.emit(str(exc))


class TeamDefensePage(QWidget):
    """Qt-native team defense dashboard."""

    def __init__(self) -> None:
        super().__init__()
        self.worker: TeamDefenseWorker | None = None
        scroll, _, layout = scroll_page()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

        layout.addWidget(eyebrow_label("TEAM DEFENSE"))
        layout.addWidget(title_label("Shot Zone Defense"))

        controls_card = card(radius=12)
        controls = QGridLayout(controls_card)
        controls.setContentsMargins(25, 20, 25, 20)
        controls.setHorizontalSpacing(14)
        self.season_input = QLineEdit("2025-26")
        self.load_button = QPushButton("Load Defense")
        style_primary_button(self.load_button)
        self.load_button.clicked.connect(self.start_fetch)
        controls.addWidget(eyebrow_label("SEASON"), 0, 0)
        controls.addWidget(QLabel(""), 0, 1)
        controls.addWidget(self.season_input, 1, 0)
        controls.addWidget(self.load_button, 1, 1)
        controls.setColumnStretch(0, 1)
        controls.setColumnStretch(1, 0)
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
        season = self.season_input.text().strip()
        if not season:
            self.status.setText("Enter a season.")
            return
        self.load_button.setEnabled(False)
        self.status.setText(f"Fetching team defense for {season}...")
        self.worker = TeamDefenseWorker(season)
        self.worker.finished.connect(self.display_results)
        self.worker.error.connect(self.display_error)
        self.worker.start()

    def display_error(self, message: str) -> None:
        self.load_button.setEnabled(True)
        self.status.setText(f"Error: {message}")

    def display_results(self, data: list[dict]) -> None:
        self.load_button.setEnabled(True)
        ranked = sort_team_defense(data)
        averages = league_averages(ranked)
        self.status.setText(f"Loaded {len(ranked)} teams.")
        self.summary.setText(
            "League averages: "
            f"OPP FG {format_percentage(averages['OPP_FG_PCT'])} | "
            f"OPP 3P {format_percentage(averages['OPP_FG3_PCT'])} | "
            f"RA {format_percentage(averages['Restricted Area'])} | "
            f"Paint {format_percentage(averages['In The Paint (Non-RA)'])}"
        )

        rows = []
        for rank, team in enumerate(ranked, start=1):
            tier, color_key = defense_rank_tier(rank)
            rows.append(
                [
                    rank,
                    team["Team"],
                    tier,
                    format_percentage(team["OPP_FG_PCT"]),
                    format_percentage(team["OPP_FG3_PCT"]),
                    format_percentage(team["Restricted Area"]),
                    format_percentage(team["In The Paint (Non-RA)"]),
                    format_percentage(team["Mid-Range"]),
                    format_percentage(team["Corner 3"]),
                    format_percentage(team["Above the Break 3"]),
                    color_key,
                ]
            )
        populate_table(
            self.table,
            (
                "Rank",
                "Team",
                "Tier",
                "OPP FG",
                "OPP 3P",
                "Rest. Area",
                "Paint",
                "Mid",
                "Corner 3",
                "Above Break 3",
            ),
            rows,
            color_key_column=10,
        )


class TeamDefenseCard(QWidget):
    """Compact team defense summary card for future dashboard reuse."""

    def __init__(self, title: str, value: str) -> None:
        super().__init__()
        frame = card()
        layout = QVBoxLayout(self)
        layout.addWidget(frame)
        inner = QVBoxLayout(frame)
        inner.addWidget(QLabel(title))
        inner.addWidget(QLabel(value))
