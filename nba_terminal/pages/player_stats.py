"""Native player analytics terminal page."""

from __future__ import annotations

from typing import Any

import pandas as pd
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFrame,
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
    HIT_THRESHOLDS,
    fetch_player_game_log,
    filter_vs_team,
    hit_rates,
    rolling_summaries,
    summarize_stats,
    visible_game_log_columns,
)
from nba_terminal.theme import COLORS
from nba_terminal.ui.common import (
    card,
    eyebrow_label,
    scroll_page,
    style_primary_button,
    style_secondary_button,
    style_terminal_table,
    title_label,
)

SEASONS = ("2020-21", "2021-22", "2022-23", "2023-24", "2024-25", "2025-26")
STAT_LABELS = {
    "points": "PTS",
    "rebounds": "REB",
    "assists": "AST",
    "steals": "STL",
    "blocks": "BLK",
    "3pt": "3PM",
}
ROLLING_STAT_LABELS = {
    "points": "PTS",
    "rebounds": "REB",
    "assists": "AST",
    "steals": "STL",
    "blocks": "BLK",
    "3pt": "3PM",
}
GAME_LOG_HEADERS = {
    "GAME_DATE": "DATE",
    "MATCHUP": "MATCHUP",
    "WL": "W/L",
    "FG_PCT": "FG%",
    "FG3M": "3PM",
    "FG3A": "3PA",
    "FG3_PCT": "3P%",
    "FT_PCT": "FT%",
    "TS_PCT": "TS%",
    "PLUS_MINUS": "+/-",
}
GAME_LOG_COLUMN_WEIGHTS = {
    "GAME_DATE": 78,
    "MATCHUP": 92,
    "WL": 30,
    "MIN": 34,
    "PTS": 36,
    "REB": 36,
    "AST": 36,
    "STL": 34,
    "BLK": 34,
    "PRA": 38,
    "PR": 34,
    "PA": 34,
    "RA": 34,
    "FGM": 36,
    "FGA": 36,
    "FG_PCT": 48,
    "FG3M": 40,
    "FG3A": 40,
    "FG3_PCT": 50,
    "FTM": 36,
    "FTA": 36,
    "FT_PCT": 48,
    "TS_PCT": 48,
    "PLUS_MINUS": 42,
}


class CompactGameLogTable(QTableWidget):
    """Game-log table that fits all stat columns into the visible card width."""

    def __init__(self) -> None:
        super().__init__()
        self._game_log_columns: list[str] = []

    def set_game_log_columns(self, columns: list[str]) -> None:
        self._game_log_columns = columns
        self._fit_columns_to_viewport()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._fit_columns_to_viewport()

    def _fit_columns_to_viewport(self) -> None:
        if not self._game_log_columns:
            return
        available_width = max(1, self.viewport().width() - 2)
        weights = [GAME_LOG_COLUMN_WEIGHTS.get(column, 36) for column in self._game_log_columns]
        total_weight = sum(weights)
        widths = [max(24, int(available_width * weight / total_weight)) for weight in weights]
        remainder = available_width - sum(widths)
        if widths and remainder > 0:
            widths[-1] += remainder

        header = self.horizontalHeader()
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(24)
        for index, width in enumerate(widths):
            header.setSectionResizeMode(index, QHeaderView.ResizeMode.Fixed)
            self.setColumnWidth(index, width)


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
        layout.addWidget(self.results_tabs)
        layout.addStretch()

    def _build_controls(self, layout: QVBoxLayout) -> None:
        controls = card()
        inner = QVBoxLayout(controls)
        inner.setContentsMargins(18, 16, 18, 16)
        inner.setSpacing(12)

        top = QGridLayout()
        top.setHorizontalSpacing(12)
        self.player_input = QLineEdit("James Harden")
        self.opponent_input = QLineEdit("76ers")
        self.fetch_button = QPushButton("Fetch Statistics")
        self.fetch_button.setMinimumWidth(150)
        style_primary_button(self.fetch_button)
        self.fetch_button.clicked.connect(self.start_fetch)
        self.clear_button = QPushButton("Clear Results")
        self.clear_button.setMinimumWidth(130)
        style_secondary_button(self.clear_button)
        self.clear_button.clicked.connect(self.clear_results)
        top.addWidget(eyebrow_label("PLAYER"), 0, 0)
        top.addWidget(eyebrow_label("OPPONENT"), 0, 1)
        top.addWidget(QLabel(""), 0, 2)
        top.addWidget(self.player_input, 1, 0)
        top.addWidget(self.opponent_input, 1, 1)
        top.addWidget(self.fetch_button, 1, 2)
        top.addWidget(self.clear_button, 1, 3)
        top.setColumnStretch(0, 3)
        top.setColumnStretch(1, 2)
        top.setColumnStretch(2, 0)
        top.setColumnStretch(3, 0)
        inner.addLayout(top)

        season_row = QHBoxLayout()
        season_row.setSpacing(10)
        self.season_checks: dict[str, QCheckBox] = {}
        for season in SEASONS:
            check = QCheckBox(season)
            check.setChecked(season in {"2024-25", "2025-26"})
            self.season_checks[season] = check
            season_row.addWidget(check)
        season_row.addSpacing(18)

        self.season_type_group = QButtonGroup(self)
        self.regular_radio = QRadioButton("Regular Season")
        self.playoffs_radio = QRadioButton("Playoffs")
        self.regular_radio.setChecked(True)
        for radio in (self.regular_radio, self.playoffs_radio):
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

        layout.addWidget(self._rolling_card(item["rolling"]))

        hit_row = QHBoxLayout()
        hit_row.setSpacing(24)
        hit_row.addWidget(self._hit_rate_card("Points Rates", item["hit_rates"].get("PTS", {}), "PTS"), 1)
        hit_row.addWidget(self._hit_rate_card("Rebounds Rates", item["hit_rates"].get("REB", {}), "REB"), 1)
        hit_row.addWidget(self._hit_rate_card("Assists Rates", item["hit_rates"].get("AST", {}), "AST"), 1)
        layout.addLayout(hit_row)

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
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(12)
        layout.addWidget(eyebrow_label(title.upper()))

        grid = QGridLayout()
        grid.setContentsMargins(0, 5, 0, 5)
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(8)
        headers = ("Stat", "Avg", "Std", "CV%")
        for row, text in enumerate(headers):
            label = QLabel(text)
            label.setStyleSheet(f"color: {COLORS['text_tertiary']}; font-size: 11px;")
            grid.addWidget(label, row, 0)

        for column, (key, label_text) in enumerate(STAT_LABELS.items(), start=1):
            grid.setColumnStretch(column, 1)
            avg = float(stats["averages"].get(key, 0.0))
            std = float(stats["std_devs"].get(key, 0.0))
            cv = std / avg if avg > 0 else 0.0
            values = (label_text, f"{avg:.1f}", f"{std:.1f}", format_percentage(cv))
            for row, value in enumerate(values):
                label = QLabel(value)
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                color = COLORS["text_primary"]
                if row == 0:
                    color = COLORS["text_secondary"]
                elif row == 2:
                    color = COLORS["text_tertiary"]
                elif row == 3:
                    color = self._cv_color(cv)
                label.setStyleSheet(
                    f"color: {color}; font-size: {'14' if row == 1 else '12'}px;"
                    f"font-weight: {'bold' if row in {0, 1} else 'normal'};"
                )
                grid.addWidget(label, row, column)
        layout.addLayout(grid)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"background-color: {COLORS['divider']}; max-height: 1px; border: none;")
        layout.addWidget(line)

        footer = QHBoxLayout()
        games_label = QLabel("Games Played")
        games_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        games_value = QLabel(str(stats["games_played"]))
        games_value.setStyleSheet(f"color: {COLORS['text_primary']}; font-weight: bold; font-size: 12px;")
        footer.addWidget(games_label)
        footer.addStretch()
        footer.addWidget(games_value)
        layout.addLayout(footer)
        return frame

    def _rolling_card(self, rolling: dict[int, dict[str, Any]]) -> QWidget:
        frame = card()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(eyebrow_label("ROLLING TRENDS"))
        table = self._base_table()
        rows = []
        stat_keys = tuple(ROLLING_STAT_LABELS)
        for window in (5, 10, 15):
            stats = rolling.get(window)
            if not stats:
                rows.append([f"L{window}", *("-" for _ in stat_keys)])
                rows.append(["CV%", *("-" for _ in stat_keys)])
                continue
            rows.append(
                [
                    f"L{window}",
                    *(f"{float(stats['averages'].get(stat, 0.0)):.1f}" for stat in stat_keys),
                ]
            )
            rows.append(
                [
                    "CV%",
                    *(
                        format_percentage(
                            float(stats["std_devs"].get(stat, 0.0))
                            / float(stats["averages"].get(stat, 0.0))
                            if float(stats["averages"].get(stat, 0.0)) > 0
                            else 0.0
                        )
                        for stat in stat_keys
                    ),
                ]
            )
        self._fill_table(table, ("Games", *ROLLING_STAT_LABELS.values()), rows)
        for row_index in range(table.rowCount()):
            label_item = table.item(row_index, 0)
            if label_item is None:
                continue
            if label_item.text() == "CV%":
                label_item.setForeground(QColor(COLORS["text_tertiary"]))
                for column_index, stat in enumerate(stat_keys, start=1):
                    window = (5, 10, 15)[row_index // 2]
                    stats = rolling.get(window)
                    if not stats:
                        continue
                    avg = float(stats["averages"].get(stat, 0.0))
                    std = float(stats["std_devs"].get(stat, 0.0))
                    cv = std / avg if avg > 0 else 0.0
                    item = table.item(row_index, column_index)
                    if item is not None:
                        item.setForeground(QColor(self._cv_color(cv)))
            else:
                label_item.setForeground(QColor(COLORS["text_primary"]))
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setFixedHeight(235)
        layout.addWidget(table)
        return frame

    def _hit_rate_card(self, title: str, rates: dict[int, dict[int, float]], stat: str) -> QWidget:
        frame = card()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setSpacing(12)
        layout.addWidget(eyebrow_label(title.upper()))
        thresholds = HIT_THRESHOLDS[stat]
        grid = QGridLayout()
        grid.setContentsMargins(0, 8, 0, 8)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)

        grid.addWidget(self._hit_rate_label("GAMES", COLORS["text_secondary"], bold=True), 0, 0)
        for column, threshold in enumerate(thresholds, start=1):
            grid.addWidget(self._hit_rate_label(f"{threshold}+", COLORS["text_secondary"], bold=True), 0, column)
            grid.setColumnStretch(column, 1)

        for row, window in enumerate((5, 10, 15), start=1):
            grid.addWidget(self._hit_rate_label(f"L{window}", COLORS["text_primary"], bold=True), row, 0)
            for column, threshold in enumerate(thresholds, start=1):
                rate = float(rates.get(window, {}).get(threshold, 0.0))
                grid.addWidget(
                    self._hit_rate_label(f"{rate:.0f}%", self._hit_rate_color(rate), bold=True),
                    row,
                    column,
                )
        layout.addLayout(grid)
        return frame

    def _game_log_table(self, frame: pd.DataFrame, minimum_height: int = 430) -> QTableWidget:
        table = CompactGameLogTable()
        style_terminal_table(table)
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
        self._fill_table(table, tuple(self._game_log_header(column) for column in columns), rows)
        table.set_game_log_columns(columns)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setMinimumHeight(minimum_height)
        return table

    def _base_table(self) -> QTableWidget:
        table = QTableWidget()
        style_terminal_table(table)
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

    def clear_results(self) -> None:
        self._clear_results()
        self.results_tabs.setVisible(False)
        self.status.setText("Results cleared.")

    def _clear_results(self) -> None:
        while self.results_tabs.count():
            widget = self.results_tabs.widget(0)
            self.results_tabs.removeTab(0)
            widget.deleteLater()

    @staticmethod
    def _hit_rate_label(text: str, color: str, *, bold: bool = False) -> QLabel:
        label = QLabel(text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(
            f"color: {color}; font-size: 12px; font-weight: {'bold' if bold else 'normal'}; border: none;"
        )
        return label

    @staticmethod
    def _game_log_header(column: str) -> str:
        return GAME_LOG_HEADERS.get(column, column)

    @staticmethod
    def _cv_color(cv: float) -> str:
        if cv < 0.30:
            return COLORS["success"]
        if cv < 0.50:
            return COLORS["warning"]
        return COLORS["danger"]

    @staticmethod
    def _hit_rate_color(rate: float) -> str:
        if rate >= 80:
            return COLORS["success"]
        if rate >= 50:
            return COLORS["warning"]
        return COLORS["danger"]
