"""Native player analytics terminal page."""

from __future__ import annotations

from typing import Any

import pandas as pd
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from nba_terminal.analytics import format_percentage
from nba_terminal.services.player_data import (
    fetch_player_game_log,
    filter_vs_team,
    hit_rates,
    rolling_summaries,
    summarize_stats,
    visible_game_log_columns,
)
from nba_terminal.theme import COLORS
from nba_terminal.ui.common import card, eyebrow_label, scroll_page, title_label

SEASONS = ("2020-21", "2021-22", "2022-23", "2023-24", "2024-25", "2025-26")
STAT_LABELS = {
    "points": "PTS",
    "rebounds": "REB",
    "assists": "AST",
    "steals": "STL",
    "blocks": "BLK",
    "3pt": "3PM",
}


class PlayerStatsWorker(QThread):
    """Fetch player stats in the background."""

    finished = pyqtSignal(list)
    error = pyqtSignal(str)
    status = pyqtSignal(str)

    def __init__(self, player: str, opponent: str, seasons: list[str], season_type: str) -> None:
        super().__init__()
        self.player = player
        self.opponent = opponent
        self.seasons = seasons
        self.season_type = season_type

    def run(self) -> None:
        try:
            rows = []
            for season in reversed(self.seasons):
                self.status.emit(f"Fetching {self.player} {season}...")
                log = fetch_player_game_log(self.player, season, self.season_type)
                vs_log = filter_vs_team(log, self.opponent) if not log.empty else log
                rows.append(
                    {
                        "season": season,
                        "season_type": self.season_type,
                        "game_log": log,
                        "vs_log": vs_log,
                        "season_stats": summarize_stats(log),
                        "vs_stats": summarize_stats(vs_log),
                        "rolling": rolling_summaries(log),
                        "hit_rates": {stat: hit_rates(log, stat) for stat in ("PTS", "REB", "AST")},
                    }
                )
            self.finished.emit(rows)
        except Exception as exc:
            self.error.emit(str(exc))


class PlayerStatsPage(QWidget):
    """Player analytics view powered entirely by nba_terminal services."""

    def __init__(self) -> None:
        super().__init__()
        self.worker: PlayerStatsWorker | None = None
        scroll, _, layout = scroll_page()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

        layout.addWidget(eyebrow_label("PLAYER ANALYTICS"))
        layout.addWidget(title_label("Player Stats Board"))
        self._build_controls(layout)

        self.status = QLabel("Ready")
        self.status.setStyleSheet(f"color: {COLORS['text_tertiary']}; font-size: 12px;")
        layout.addWidget(self.status)

        self.results_tabs = QTabWidget()
        self.results_tabs.setDocumentMode(True)
        self.results_tabs.setVisible(False)
        self.results_tabs.setStyleSheet(
            "QTabWidget::pane {"
            f"border: 1px solid {COLORS['border']};"
            f"background: {COLORS['bg_primary']};"
            "}"
            "QTabBar::tab {"
            f"background: {COLORS['bg_elevated']}; color: {COLORS['text_secondary']};"
            "padding: 9px 14px; margin-right: 2px;"
            "}"
            "QTabBar::tab:selected {"
            f"background: {COLORS['accent']}; color: {COLORS['text_primary']};"
            "}"
        )
        layout.addWidget(self.results_tabs)
        layout.addStretch()

    def _build_controls(self, layout: QVBoxLayout) -> None:
        controls = card()
        inner = QVBoxLayout(controls)
        inner.setContentsMargins(18, 16, 18, 16)
        inner.setSpacing(14)

        top = QGridLayout()
        top.setHorizontalSpacing(12)
        self.player_input = QLineEdit("James Harden")
        self.opponent_input = QLineEdit("76ers")
        self.fetch_button = QPushButton("Fetch Statistics")
        self.fetch_button.setMinimumWidth(150)
        self.fetch_button.clicked.connect(self.start_fetch)
        top.addWidget(eyebrow_label("PLAYER"), 0, 0)
        top.addWidget(eyebrow_label("OPPONENT"), 0, 1)
        top.addWidget(QLabel(""), 0, 2)
        top.addWidget(self.player_input, 1, 0)
        top.addWidget(self.opponent_input, 1, 1)
        top.addWidget(self.fetch_button, 1, 2)
        top.setColumnStretch(0, 3)
        top.setColumnStretch(1, 2)
        top.setColumnStretch(2, 0)
        inner.addLayout(top)

        season_row = QHBoxLayout()
        season_row.setSpacing(10)
        self.season_checks: dict[str, QCheckBox] = {}
        for season in SEASONS:
            check = QCheckBox(season)
            check.setChecked(season in {"2024-25", "2025-26"})
            check.setStyleSheet(f"color: {COLORS['text_secondary']};")
            self.season_checks[season] = check
            season_row.addWidget(check)
        season_row.addSpacing(18)

        self.season_type_group = QButtonGroup(self)
        self.regular_radio = QRadioButton("Regular Season")
        self.playoffs_radio = QRadioButton("Playoffs")
        self.regular_radio.setChecked(True)
        for radio in (self.regular_radio, self.playoffs_radio):
            radio.setStyleSheet(f"color: {COLORS['text_secondary']};")
            self.season_type_group.addButton(radio)
            season_row.addWidget(radio)
        season_row.addStretch()
        inner.addLayout(season_row)
        layout.addWidget(controls)

    def start_fetch(self) -> None:
        player = self.player_input.text().strip()
        opponent = self.opponent_input.text().strip()
        seasons = [season for season, check in self.season_checks.items() if check.isChecked()]
        season_type = "Playoffs" if self.playoffs_radio.isChecked() else "Regular Season"
        if not player or not opponent or not seasons:
            self.status.setText("Enter player, opponent, and at least one season.")
            return
        self.fetch_button.setEnabled(False)
        self.status.setText("Fetching...")
        self._clear_results()
        self.worker = PlayerStatsWorker(player, opponent, seasons, season_type)
        self.worker.status.connect(self.status.setText)
        self.worker.finished.connect(self.display_results)
        self.worker.error.connect(self.display_error)
        self.worker.start()

    def display_error(self, message: str) -> None:
        self.fetch_button.setEnabled(True)
        self.status.setText(f"Error: {message}")

    def display_results(self, seasons: list[dict[str, Any]]) -> None:
        self.fetch_button.setEnabled(True)
        self.status.setText(f"Loaded {len(seasons)} season(s).")
        self._clear_results()
        for item in seasons:
            self.results_tabs.addTab(self._season_page(item), item["season"])
        self.results_tabs.setVisible(bool(seasons))

    def _season_page(self, item: dict[str, Any]) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(16)

        header = QLabel(f"{item['season']} - {item['season_type']}")
        header.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 22px; font-weight: 800;")
        layout.addWidget(header)

        cards = QHBoxLayout()
        cards.setSpacing(14)
        cards.addWidget(self._stat_card("Overall", item["season_stats"]), 1)
        cards.addWidget(self._stat_card("Vs Opponent", item["vs_stats"]), 1)
        layout.addLayout(cards)

        trend_row = QHBoxLayout()
        trend_row.setSpacing(14)
        trend_row.addWidget(self._rolling_card(item["rolling"]), 1)
        trend_row.addWidget(self._hit_rate_card(item["hit_rates"]), 2)
        layout.addLayout(trend_row)

        layout.addWidget(self._section_title("Game Log"))
        layout.addWidget(self._game_log_table(item["game_log"]))
        if not item["vs_log"].empty:
            layout.addWidget(self._section_title("Vs Opponent Log"))
            layout.addWidget(self._game_log_table(item["vs_log"], minimum_height=240))
        layout.addStretch()
        return page

    def _section_title(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 15px; font-weight: 800;")
        return label

    def _stat_card(self, title: str, stats: dict[str, Any]) -> QWidget:
        frame = card()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        layout.addWidget(eyebrow_label(title.upper()))

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)
        headers = ("Stat", "Avg", "Std", "CV")
        for row, text in enumerate(headers):
            label = QLabel(text)
            label.setStyleSheet(f"color: {COLORS['text_tertiary']}; font-size: 11px;")
            grid.addWidget(label, row, 0)

        for column, (key, label_text) in enumerate(STAT_LABELS.items(), start=1):
            avg = float(stats["averages"].get(key, 0.0))
            std = float(stats["std_devs"].get(key, 0.0))
            cv = std / avg if avg > 0 else 0.0
            values = (label_text, f"{avg:.1f}", f"{std:.1f}", format_percentage(cv))
            for row, value in enumerate(values):
                label = QLabel(value)
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                color = COLORS["text_primary"] if row in {0, 1} else COLORS["text_secondary"]
                label.setStyleSheet(f"color: {color}; font-weight: {'800' if row in {0, 1} else '500'};")
                grid.addWidget(label, row, column)
        layout.addLayout(grid)

        footer = QLabel(f"Games: {stats['games_played']}")
        footer.setStyleSheet(f"color: {COLORS['text_secondary']};")
        layout.addWidget(footer)
        return frame

    def _rolling_card(self, rolling: dict[int, dict[str, Any]]) -> QWidget:
        frame = card()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(eyebrow_label("ROLLING TRENDS"))
        table = self._base_table()
        rows = [
            [
                f"L{window}",
                f"{stats['averages'].get('points', 0.0):.1f}",
                f"{stats['averages'].get('rebounds', 0.0):.1f}",
                f"{stats['averages'].get('assists', 0.0):.1f}",
                f"{stats['averages'].get('3pt', 0.0):.1f}",
            ]
            for window, stats in rolling.items()
        ]
        self._fill_table(table, ("Window", "PTS", "REB", "AST", "3PM"), rows)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setFixedHeight(140)
        layout.addWidget(table)
        return frame

    def _hit_rate_card(self, rates: dict[str, dict[int, dict[int, float]]]) -> QWidget:
        frame = card()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(eyebrow_label("HIT RATES"))
        table = self._base_table()
        rows = []
        for stat, windows in rates.items():
            for window, thresholds in windows.items():
                compact = "   ".join(f"{threshold}+ {rate:.0f}%" for threshold, rate in thresholds.items())
                rows.append([stat, f"L{window}", compact])
        self._fill_table(table, ("Stat", "Window", "Rates"), rows)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setFixedHeight(190)
        layout.addWidget(table)
        return frame

    def _game_log_table(self, frame: pd.DataFrame, minimum_height: int = 430) -> QTableWidget:
        table = self._base_table()
        columns = visible_game_log_columns(frame)
        rows = []
        for _, row in frame.iterrows():
            values = []
            for column in columns:
                value = row.get(column, "")
                if column.endswith("_PCT") or column == "TS_PCT":
                    values.append(format_percentage(value))
                elif column == "GAME_DATE" and not pd.isna(value):
                    values.append(pd.to_datetime(value).strftime("%Y-%m-%d"))
                elif isinstance(value, float):
                    values.append(f"{value:.1f}" if value != int(value) else f"{value:.0f}")
                else:
                    values.append(value)
            rows.append(values)
        self._fill_table(table, tuple(columns), rows)
        header = table.horizontalHeader()
        for index, column in enumerate(columns):
            mode = (
                QHeaderView.ResizeMode.ResizeToContents
                if column in {"GAME_DATE", "MATCHUP"}
                else QHeaderView.ResizeMode.Interactive
            )
            header.setSectionResizeMode(index, mode)
        table.setMinimumHeight(minimum_height)
        return table

    def _base_table(self) -> QTableWidget:
        table = QTableWidget()
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(True)
        table.setWordWrap(False)
        table.setStyleSheet(
            "QTableWidget {"
            f"background-color: {COLORS['bg_card']}; color: {COLORS['text_primary']};"
            f"alternate-background-color: {COLORS['bg_elevated']};"
            f"border: 1px solid {COLORS['border']}; gridline-color: {COLORS['divider']};"
            "}"
            "QTableWidget::item { padding: 4px; }"
        )
        return table

    def _fill_table(self, table: QTableWidget, headers: tuple[str, ...], rows: list[list[Any]]) -> None:
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for column_index, value in enumerate(row):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setForeground(QColor(COLORS["text_primary"]))
                table.setItem(row_index, column_index, item)
        header = table.horizontalHeader()
        for index in range(table.columnCount()):
            header.setSectionResizeMode(index, QHeaderView.ResizeMode.Stretch)

    def _clear_results(self) -> None:
        while self.results_tabs.count():
            widget = self.results_tabs.widget(0)
            self.results_tabs.removeTab(0)
            widget.deleteLater()
