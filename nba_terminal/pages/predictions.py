"""Native points projection terminal page."""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from nba_terminal.services.projections import project_points
from nba_terminal.theme import COLORS
from nba_terminal.ui.common import (
    card,
    eyebrow_label,
    scroll_page,
    style_primary_button,
    style_terminal_table,
    title_label,
)


class ProjectionWorker(QThread):
    """Run projection work off the UI thread."""

    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, player: str, team: str, opponent: str, season: str, minutes: float) -> None:
        super().__init__()
        self.player = player
        self.team = team
        self.opponent = opponent
        self.season = season
        self.minutes = minutes

    def run(self) -> None:
        try:
            self.finished.emit(project_points(self.player, self.team, self.opponent, self.season, self.minutes))
        except Exception as exc:
            self.error.emit(str(exc))


class PredictionsPage(QWidget):
    """Transparent points projection page."""

    def __init__(self) -> None:
        super().__init__()
        self.worker: ProjectionWorker | None = None
        scroll, _, layout = scroll_page()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

        self.results = QVBoxLayout()
        self.results.setSpacing(20)

        layout.addWidget(eyebrow_label("POINTS PREDICTOR"))
        layout.addWidget(title_label("Player Projection"))
        self._build_controls(layout)

        self.status = QLabel("Ready")
        self.status.setStyleSheet(f"color: {COLORS['text_tertiary']}; font-size: 12px;")
        layout.addWidget(self.status)
        layout.addLayout(self.results)
        layout.addStretch()

    def _build_controls(self, layout: QVBoxLayout) -> None:
        controls = card(radius=12)
        outer = QVBoxLayout(controls)
        outer.setContentsMargins(25, 25, 25, 25)
        outer.setSpacing(14)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)

        self.player_input = QLineEdit("Stephen Curry")
        self.team_input = QLineEdit("GSW")
        self.opponent_input = QLineEdit("LAL")
        self.season_input = QLineEdit("2025-26")
        self.minutes_input = QLineEdit("34")

        fields = (
            ("PLAYER", self.player_input, 0, 0, 3),
            ("TEAM", self.team_input, 0, 3, 1),
            ("OPPONENT", self.opponent_input, 0, 4, 1),
            ("SEASON", self.season_input, 2, 0, 2),
            ("PROJECTED MINUTES", self.minutes_input, 2, 2, 2),
        )
        for label, widget, row, column, column_span in fields:
            grid.addWidget(eyebrow_label(label), row, column, 1, column_span)
            grid.addWidget(widget, row + 1, column, 1, column_span)

        self.run_button = QPushButton("Project Points")
        self.run_button.setMinimumWidth(150)
        style_primary_button(self.run_button)
        self.run_button.clicked.connect(self.start_projection)
        grid.addWidget(QLabel(""), 2, 4)
        grid.addWidget(self.run_button, 3, 4)

        for column, stretch in enumerate((3, 1, 1, 1, 1)):
            grid.setColumnStretch(column, stretch)
        outer.addLayout(grid)

        note = QLabel("Weighted v1 model: season form, recent form, minutes, opponent defense, pace, rest, and venue.")
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px; border: none;")
        outer.addWidget(note)
        layout.addWidget(controls)

    def start_projection(self) -> None:
        player = self.player_input.text().strip()
        team = self.team_input.text().strip()
        opponent = self.opponent_input.text().strip()
        season = self.season_input.text().strip()
        try:
            minutes = float(self.minutes_input.text().strip())
        except ValueError:
            self.status.setText("Projected minutes must be numeric.")
            return
        if not player or not team or not opponent or not season:
            self.status.setText("Enter player, team, opponent, and season.")
            return
        if minutes <= 0 or minutes > 60:
            self.status.setText("Projected minutes must be between 0 and 60.")
            return

        self._clear_results()
        self.status.setText("Projecting...")
        self.run_button.setEnabled(False)
        self.worker = ProjectionWorker(player, team, opponent, season, minutes)
        self.worker.finished.connect(self.display_projection)
        self.worker.error.connect(self.display_error)
        self.worker.start()

    def display_error(self, message: str) -> None:
        self.run_button.setEnabled(True)
        self.status.setText(f"Error: {message}")

    def display_projection(self, data: dict[str, Any]) -> None:
        self.run_button.setEnabled(True)
        self.status.setText("Projection complete.")
        self._clear_results()
        self.results.addWidget(self._hero_card(data))

        metric_grid = QGridLayout()
        metric_grid.setHorizontalSpacing(12)
        metric_grid.setVerticalSpacing(12)
        metrics = (
            ("Season Avg", data["season_avg"], "PTS"),
            ("Last 5", data["last_5"], "PTS"),
            ("Last 10", data["last_10"], "PTS"),
            ("Avg Min", data["avg_minutes"], "MIN"),
            ("Projected Min", data["projected_minutes"], "MIN"),
            ("Minute Factor", data["minute_factor"], "x"),
        )
        for index, (name, value, suffix) in enumerate(metrics):
            metric_grid.addWidget(self._metric_tile(name, value, suffix), index // 3, index % 3)
        self.results.addLayout(metric_grid)

        detail_row = QHBoxLayout()
        detail_row.setSpacing(14)
        detail_row.addWidget(self._context_card(data), 1)
        detail_row.addWidget(self._factors_card(data), 2)
        self.results.addLayout(detail_row)

        self.results.addWidget(self._formula_card(data))

    def _hero_card(self, data: dict[str, Any]) -> QWidget:
        context = data["context"]
        frame = QFrame()
        frame.setStyleSheet("QFrame { border: none; background: transparent; } QLabel { border: none; }")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(28)

        left = QVBoxLayout()
        left.addWidget(eyebrow_label(data["player_name"].upper()))
        value = QLabel(f"{float(data['projection']):.1f}")
        value.setStyleSheet(f"color: {COLORS['accent']}; font-size: 84px; font-weight: bold;")
        left.addWidget(value)
        label = QLabel("Projected Points")
        label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 14px; font-weight: 700;")
        left.addWidget(label)
        layout.addLayout(left, 1)

        right = QGridLayout()
        right.setHorizontalSpacing(18)
        right.setVerticalSpacing(10)
        rows = (
            ("MATCHUP", f"{context['player_team']} vs {context['opponent']}"),
            ("SEASON", data["season"]),
            ("LOCATION", "Home" if int(context["is_home"]) else "Away / Neutral"),
            ("REST", f"{context['rest_days']} day(s)"),
        )
        for row, (name, text) in enumerate(rows):
            right.addWidget(eyebrow_label(name), row, 0)
            value_label = QLabel(str(text))
            value_label.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 15px; font-weight: 800;")
            right.addWidget(value_label, row, 1)
        layout.addLayout(right, 1)
        return frame

    def _metric_tile(self, name: str, value: Any, suffix: str) -> QWidget:
        frame = card(radius=12)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(7)
        layout.addWidget(eyebrow_label(name.upper()))
        body = QLabel(f"{float(value):.2f} {suffix}")
        body.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 32px; font-weight: bold;")
        layout.addWidget(body)
        return frame

    def _context_card(self, data: dict[str, Any]) -> QWidget:
        context = data["context"]
        rows = [
            ("Opponent", context["opponent_name"]),
            ("Opp DEF RTG", f"{float(context['def_rating']):.1f}"),
            ("League DEF RTG", f"{float(context['league_def_rating']):.1f}"),
            ("Opp Pace", f"{float(context['pace']):.1f}"),
            ("League Pace", f"{float(context['league_pace']):.1f}"),
        ]
        frame = card(radius=12)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.addWidget(eyebrow_label("MATCHUP CONTEXT"))
        table = self._base_table()
        self._fill_table(table, ("Field", "Value"), rows)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table.setFixedHeight(205)
        layout.addWidget(table)
        return frame

    def _factors_card(self, data: dict[str, Any]) -> QWidget:
        frame = card(radius=12)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.addWidget(eyebrow_label("PROJECTION FACTORS"))
        table = self._base_table()
        self._fill_table(table, ("Factor", "Input", "Impact"), self._factor_rows(data))
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        table.setFixedHeight(245)
        layout.addWidget(table)
        return frame

    def _formula_card(self, data: dict[str, Any]) -> QWidget:
        baseline = self._baseline(data)
        frame = card(radius=12)
        layout = QGridLayout(frame)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setHorizontalSpacing(18)
        layout.setVerticalSpacing(8)
        layout.addWidget(eyebrow_label("MODEL FORMULA"), 0, 0, 1, 2)
        formula = QLabel("Baseline = 45% season average + 35% last 5 + 20% last 10")
        formula.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 13px;")
        layout.addWidget(formula, 1, 0)
        final = QLabel("Final = baseline x minute factor + defense + pace + rest + venue adjustments")
        final.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 13px;")
        layout.addWidget(final, 2, 0)
        baseline_label = QLabel(f"Baseline: {baseline:.2f} PTS")
        baseline_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        baseline_label.setStyleSheet(f"color: {COLORS['accent']}; font-size: 20px; font-weight: 900;")
        layout.addWidget(baseline_label, 1, 1, 2, 1)
        return frame

    def _factor_rows(self, data: dict[str, Any]) -> list[tuple[str, str, str]]:
        context = data["context"]
        baseline = self._baseline(data)
        minute_delta = (baseline * float(data["minute_factor"])) - baseline
        return [
            ("Season average", f"{float(data['season_avg']):.2f} PTS", "45% baseline weight"),
            ("Last 5 games", f"{float(data['last_5']):.2f} PTS", "35% baseline weight"),
            ("Last 10 games", f"{float(data['last_10']):.2f} PTS", "20% baseline weight"),
            (
                "Projected minutes",
                f"{float(data['projected_minutes']):.1f} / {float(data['avg_minutes']):.1f}",
                f"{minute_delta:+.2f} pts",
            ),
            (
                "Opponent defense",
                f"{float(context['def_rating']):.1f} vs {float(context['league_def_rating']):.1f}",
                f"{float(data['defense_adjustment']):+.2f} pts",
            ),
            (
                "Opponent pace",
                f"{float(context['pace']):.1f} vs {float(context['league_pace']):.1f}",
                f"{float(data['pace_adjustment']):+.2f} pts",
            ),
            ("Rest", f"{context['rest_days']} day(s)", f"{float(data['rest_adjustment']):+.2f} pts"),
            (
                "Venue",
                "Home" if int(context["is_home"]) else "Away / Neutral",
                f"{float(data['home_adjustment']):+.2f} pts",
            ),
        ]

    def _base_table(self) -> QTableWidget:
        table = QTableWidget()
        style_terminal_table(table)
        return table

    def _fill_table(
        self,
        table: QTableWidget,
        headers: tuple[str, ...],
        rows: list[tuple[Any, ...]],
    ) -> None:
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for column_index, value in enumerate(row):
                item = QTableWidgetItem(str(value))
                alignment = Qt.AlignmentFlag.AlignLeft if column_index == 0 else Qt.AlignmentFlag.AlignCenter
                item.setTextAlignment(alignment | Qt.AlignmentFlag.AlignVCenter)
                item.setForeground(QColor(COLORS["text_primary"]))
                table.setItem(row_index, column_index, item)
        header = table.horizontalHeader()
        for index in range(table.columnCount()):
            header.setSectionResizeMode(index, QHeaderView.ResizeMode.ResizeToContents)

    def _clear_results(self) -> None:
        while self.results.count():
            item = self.results.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_child_layout(item.layout())

    def _clear_child_layout(self, layout: QHBoxLayout | QVBoxLayout | QGridLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_child_layout(item.layout())

    @staticmethod
    def _baseline(data: dict[str, Any]) -> float:
        return (
            (float(data["season_avg"]) * 0.45)
            + (float(data["last_5"]) * 0.35)
            + (float(data["last_10"]) * 0.20)
        )
