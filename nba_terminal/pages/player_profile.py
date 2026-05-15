"""All-around player season profile terminal page."""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
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

from nba_terminal.analytics import format_percentage, safe_float
from nba_terminal.services.player_data import PLAYER_PROFILE_WINDOWS, fetch_player_stat_profile
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
KPI_METRICS = (
    ("PTS", "Base", "PTS", "number"),
    ("REB", "Base", "REB", "number"),
    ("AST", "Base", "AST", "number"),
    ("MIN", "Base", "MIN", "number"),
    ("TS%", "Advanced", "TS_PCT", "pct"),
    ("USG%", "Advanced", "USG_PCT", "pct"),
    ("NET RTG", "Advanced", "NET_RATING", "number"),
    ("PIE", "Advanced", "PIE", "pct"),
)
METRIC_GROUPS = {
    "Production": (
        ("Games", "Base", "GP", "integer"),
        ("Wins", "Base", "W", "integer"),
        ("Losses", "Base", "L", "integer"),
        ("Win %", "Base", "W_PCT", "pct"),
        ("Minutes", "Base", "MIN", "number"),
        ("Points", "Base", "PTS", "number"),
        ("Rebounds", "Base", "REB", "number"),
        ("Assists", "Base", "AST", "number"),
        ("Turnovers", "Base", "TOV", "number"),
        ("Steals", "Base", "STL", "number"),
        ("Blocks", "Base", "BLK", "number"),
        ("Plus/Minus", "Base", "PLUS_MINUS", "signed"),
        ("NBA Fantasy", "Base", "NBA_FANTASY_PTS", "number"),
        ("Double-Doubles", "Base", "DD2", "number"),
        ("Triple-Doubles", "Base", "TD3", "number"),
    ),
    "Shooting": (
        ("FGM", "Base", "FGM", "number"),
        ("FGA", "Base", "FGA", "number"),
        ("FG%", "Base", "FG_PCT", "pct"),
        ("3PM", "Base", "FG3M", "number"),
        ("3PA", "Base", "FG3A", "number"),
        ("3P%", "Base", "FG3_PCT", "pct"),
        ("FTM", "Base", "FTM", "number"),
        ("FTA", "Base", "FTA", "number"),
        ("FT%", "Base", "FT_PCT", "pct"),
        ("eFG%", "Advanced", "EFG_PCT", "pct"),
        ("TS%", "Advanced", "TS_PCT", "pct"),
        ("FGM PG", "Advanced", "FGM_PG", "number"),
        ("FGA PG", "Advanced", "FGA_PG", "number"),
    ),
    "Advanced": (
        ("Off Rating", "Advanced", "OFF_RATING", "number"),
        ("Def Rating", "Advanced", "DEF_RATING", "number"),
        ("Net Rating", "Advanced", "NET_RATING", "signed"),
        ("Ast %", "Advanced", "AST_PCT", "pct"),
        ("Ast/TO", "Advanced", "AST_TO", "number"),
        ("Ast Ratio", "Advanced", "AST_RATIO", "number"),
        ("OReb %", "Advanced", "OREB_PCT", "pct"),
        ("DReb %", "Advanced", "DREB_PCT", "pct"),
        ("Reb %", "Advanced", "REB_PCT", "pct"),
        ("Team TOV %", "Advanced", "TM_TOV_PCT", "pct"),
        ("Usage %", "Advanced", "USG_PCT", "pct"),
        ("Pace", "Advanced", "PACE", "number"),
        ("Possessions", "Advanced", "POSS", "integer"),
        ("PIE", "Advanced", "PIE", "pct"),
    ),
    "Scoring Mix": (
        ("2PA Share", "Scoring", "PCT_FGA_2PT", "pct"),
        ("3PA Share", "Scoring", "PCT_FGA_3PT", "pct"),
        ("2PT Points", "Scoring", "PCT_PTS_2PT", "pct"),
        ("Midrange Points", "Scoring", "PCT_PTS_2PT_MR", "pct"),
        ("3PT Points", "Scoring", "PCT_PTS_3PT", "pct"),
        ("Fastbreak Points", "Scoring", "PCT_PTS_FB", "pct"),
        ("FT Points", "Scoring", "PCT_PTS_FT", "pct"),
        ("Off TOV Points", "Scoring", "PCT_PTS_OFF_TOV", "pct"),
        ("Paint Points", "Scoring", "PCT_PTS_PAINT", "pct"),
        ("Ast 2PM", "Scoring", "PCT_AST_2PM", "pct"),
        ("Unast 2PM", "Scoring", "PCT_UAST_2PM", "pct"),
        ("Ast 3PM", "Scoring", "PCT_AST_3PM", "pct"),
        ("Unast 3PM", "Scoring", "PCT_UAST_3PM", "pct"),
        ("Ast FGM", "Scoring", "PCT_AST_FGM", "pct"),
        ("Unast FGM", "Scoring", "PCT_UAST_FGM", "pct"),
    ),
    "Team Share": (
        ("Usage %", "Usage", "USG_PCT", "pct"),
        ("FGM Share", "Usage", "PCT_FGM", "pct"),
        ("FGA Share", "Usage", "PCT_FGA", "pct"),
        ("3PM Share", "Usage", "PCT_FG3M", "pct"),
        ("3PA Share", "Usage", "PCT_FG3A", "pct"),
        ("FTM Share", "Usage", "PCT_FTM", "pct"),
        ("FTA Share", "Usage", "PCT_FTA", "pct"),
        ("REB Share", "Usage", "PCT_REB", "pct"),
        ("AST Share", "Usage", "PCT_AST", "pct"),
        ("TOV Share", "Usage", "PCT_TOV", "pct"),
        ("STL Share", "Usage", "PCT_STL", "pct"),
        ("BLK Share", "Usage", "PCT_BLK", "pct"),
        ("PTS Share", "Usage", "PCT_PTS", "pct"),
    ),
    "Misc & Defense": (
        ("Off TOV Pts", "Misc", "PTS_OFF_TOV", "number"),
        ("2nd Chance Pts", "Misc", "PTS_2ND_CHANCE", "number"),
        ("Fastbreak Pts", "Misc", "PTS_FB", "number"),
        ("Paint Pts", "Misc", "PTS_PAINT", "number"),
        ("Fouls Drawn", "Misc", "PFD", "number"),
        ("Blocked Attempts", "Misc", "BLKA", "number"),
        ("Def Rating", "Defense", "DEF_RATING", "number"),
        ("DReb", "Defense", "DREB", "number"),
        ("DReb %", "Defense", "DREB_PCT", "pct"),
        ("DReb Share", "Defense", "PCT_DREB", "pct"),
        ("Steals", "Defense", "STL", "number"),
        ("Steal Share", "Defense", "PCT_STL", "pct"),
        ("Blocks", "Defense", "BLK", "number"),
        ("Block Share", "Defense", "PCT_BLK", "pct"),
        ("Def Win Shares", "Defense", "DEF_WS", "number"),
    ),
}


class PlayerProfileWorker(QThread):
    """Fetch player profile seasons without blocking Qt."""

    finished = pyqtSignal(list)
    status = pyqtSignal(str)

    def __init__(self, player: str, seasons: list[str], season_type: str) -> None:
        super().__init__()
        self.player = player
        self.seasons = seasons
        self.season_type = season_type

    def run(self) -> None:
        results = []
        for season in reversed(self.seasons):
            self.status.emit(f"Fetching {self.player} {season} {self.season_type.lower()} profile...")
            try:
                results.append(fetch_player_stat_profile(self.player, season, self.season_type))
            except Exception as exc:
                results.append(
                    {
                        "player": self.player,
                        "season": season,
                        "season_type": self.season_type,
                        "error": str(exc),
                    }
                )
        self.finished.emit(results)


class PlayerProfilePage(QWidget):
    """Qt-native player stat profile page."""

    def __init__(self) -> None:
        super().__init__()
        self.worker: PlayerProfileWorker | None = None

        scroll, _, layout = scroll_page()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

        layout.addWidget(eyebrow_label("PLAYER STATS"))
        layout.addWidget(title_label("Player Season Profile"))
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
        self.fetch_button = QPushButton("Load Player Profile")
        self.fetch_button.setMinimumWidth(170)
        style_primary_button(self.fetch_button)
        self.fetch_button.clicked.connect(self.start_fetch)
        self.clear_button = QPushButton("Clear Results")
        self.clear_button.setMinimumWidth(130)
        style_secondary_button(self.clear_button)
        self.clear_button.clicked.connect(self.clear_results)

        top.addWidget(eyebrow_label("PLAYER"), 0, 0)
        top.addWidget(QLabel(""), 0, 1)
        top.addWidget(self.player_input, 1, 0)
        top.addWidget(self.fetch_button, 1, 1)
        top.addWidget(self.clear_button, 1, 2)
        top.setColumnStretch(0, 1)
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
        seasons = [season for season, check in self.season_checks.items() if check.isChecked()]
        season_type = "Playoffs" if self.playoffs_radio.isChecked() else "Regular Season"
        if not player or not seasons:
            self.status.setText("Enter a player and select at least one season.")
            return

        self.fetch_button.setEnabled(False)
        self.status.setText("Fetching...")
        self._clear_results()
        self.worker = PlayerProfileWorker(player, seasons, season_type)
        self.worker.status.connect(self.status.setText)
        self.worker.finished.connect(self.display_results)
        self.worker.start()

    def display_results(self, seasons: list[dict[str, Any]]) -> None:
        self.fetch_button.setEnabled(True)
        loaded = sum(1 for item in seasons if "error" not in item)
        failed = len(seasons) - loaded
        suffix = f" | {failed} failed" if failed else ""
        self.status.setText(f"Loaded {loaded} season profile(s){suffix}.")
        self._clear_results()
        for item in seasons:
            self.results_tabs.addTab(self._season_page(item), str(item["season"]))
        self.results_tabs.setVisible(bool(seasons))

    def clear_results(self) -> None:
        self._clear_results()
        self.results_tabs.setVisible(False)
        self.status.setText("Results cleared.")

    def _clear_results(self) -> None:
        while self.results_tabs.count():
            widget = self.results_tabs.widget(0)
            self.results_tabs.removeTab(0)
            widget.deleteLater()

    def _season_page(self, item: dict[str, Any]) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(16)

        header = QLabel(self._season_header(item))
        header.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 22px; font-weight: 800;")
        layout.addWidget(header)

        if "error" in item:
            layout.addWidget(self._warnings_card([str(item["error"])], title="LOAD FAILED"))
            layout.addStretch()
            return page

        self._add_kpi_grid(layout, item)
        layout.addWidget(self._dashboard_tabs(item))

        detail_row = QHBoxLayout()
        detail_row.setSpacing(14)
        detail_row.addWidget(self._game_summary_card(item), 3)
        detail_row.addWidget(self._hit_rates_card(item), 2)
        layout.addLayout(detail_row)

        layout.addWidget(self._shooting_tabs(item))
        warnings = item.get("warnings") or []
        if warnings:
            layout.addWidget(self._warnings_card(warnings))
        layout.addStretch()
        return page

    def _add_kpi_grid(self, layout: QVBoxLayout, item: dict[str, Any]) -> None:
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        for index, metric in enumerate(KPI_METRICS):
            grid.addWidget(self._kpi_card(item, *metric), index // 4, index % 4)
        layout.addLayout(grid)

    def _kpi_card(self, item: dict[str, Any], label: str, measure: str, column: str, value_type: str) -> QWidget:
        frame = card()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(6)

        record = item["measures"].get(measure, {})
        rank = self._rank_text(record, column)
        value = self._format_value(record.get(column), value_type)

        title = QLabel(label)
        title.setStyleSheet(f"color: {COLORS['text_tertiary']}; font-size: 11px; font-weight: 800;")
        metric = QLabel(value)
        metric.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 26px; font-weight: 900;")
        rank_label = QLabel(rank or "Rank -")
        rank_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
        layout.addWidget(title)
        layout.addWidget(metric)
        layout.addWidget(rank_label)
        return frame

    def _dashboard_tabs(self, item: dict[str, Any]) -> QTabWidget:
        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        for label, metrics in METRIC_GROUPS.items():
            rows = []
            for name, measure, column, value_type in metrics:
                record = item["measures"].get(measure, {})
                if column not in record or record.get(column) == "":
                    continue
                rows.append(
                    [
                        name,
                        self._format_value(record.get(column), value_type),
                        self._rank_text(record, column) or "-",
                        measure,
                    ]
                )
            tabs.addTab(self._table_page(("Metric", "Value", "Rank", "Source"), rows, 380), label)
        return tabs

    def _game_summary_card(self, item: dict[str, Any]) -> QWidget:
        rows = []
        for row in item.get("game_summary", []):
            value_type = str(row.get("type", "number"))
            rows.append(
                [
                    row.get("label", ""),
                    self._format_value(row.get("avg"), value_type),
                    *(self._format_value(row.get(f"last_{window}"), value_type) for window in PLAYER_PROFILE_WINDOWS),
                    self._format_value(row.get("std"), value_type),
                    format_percentage(row.get("cv")),
                ]
            )
        headers = ("Stat", "Season", "L5", "L10", "L20", "Std", "CV")
        return self._table_card("GAME-LOG PROFILE", headers, rows, 470)

    def _hit_rates_card(self, item: dict[str, Any]) -> QWidget:
        rows = []
        for row in item.get("hit_rate_rows", []):
            rows.append(
                [
                    row.get("market", ""),
                    self._format_rate(row.get("season")),
                    *(self._format_rate(row.get(f"last_{window}")) for window in PLAYER_PROFILE_WINDOWS),
                ]
            )
        headers = ("Market", "Season", "L5", "L10", "L20")
        return self._table_card("HIT RATES", headers, rows, 470)

    def _shooting_tabs(self, item: dict[str, Any]) -> QTabWidget:
        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        splits = item.get("shooting_splits") or {}
        headers = ("Split", "FGM", "FGA", "FG%", "3PM", "3PA", "3P%", "eFG%", "Ast FGM", "Unast FGM")
        for label, records in splits.items():
            rows = []
            for record in self._shot_records(label, records):
                rows.append(
                    [
                        self._split_name(record),
                        self._format_value(record.get("FGM"), "number"),
                        self._format_value(record.get("FGA"), "number"),
                        self._format_value(record.get("FG_PCT"), "pct"),
                        self._format_value(record.get("FG3M"), "number"),
                        self._format_value(record.get("FG3A"), "number"),
                        self._format_value(record.get("FG3_PCT"), "pct"),
                        self._format_value(record.get("EFG_PCT"), "pct"),
                        self._format_value(record.get("PCT_AST_FGM"), "pct"),
                        self._format_value(record.get("PCT_UAST_FGM"), "pct"),
                    ]
                )
            tabs.addTab(self._table_page(headers, rows, 360), label)
        if not splits:
            tabs.addTab(self._table_page(("Status",), [["Shooting splits unavailable"]], 180), "Shooting Splits")
        return tabs

    def _table_card(self, title: str, headers: tuple[str, ...], rows: list[list[Any]], height: int) -> QWidget:
        frame = card()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(10)
        layout.addWidget(eyebrow_label(title))
        layout.addWidget(self._table(headers, rows, height))
        return frame

    def _table_page(self, headers: tuple[str, ...], rows: list[list[Any]], height: int) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addWidget(self._table(headers, rows, height))
        return page

    def _table(self, headers: tuple[str, ...], rows: list[list[Any]], height: int) -> QTableWidget:
        table = QTableWidget()
        style_terminal_table(table, bordered=True)
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
        table.setMinimumHeight(height)
        return table

    def _warnings_card(self, warnings: list[str], title: str = "DATA WARNINGS") -> QWidget:
        frame = card()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(8)
        layout.addWidget(eyebrow_label(title))
        for warning in warnings:
            label = QLabel(f"- {warning}")
            label.setWordWrap(True)
            label.setStyleSheet(f"color: {COLORS['warning']}; font-size: 12px; border: none;")
            layout.addWidget(label)
        return frame

    @staticmethod
    def _season_header(item: dict[str, Any]) -> str:
        team = f" | {item['team']}" if item.get("team") else ""
        return f"{item['player']}{team} | {item['season']} {item['season_type']}"

    @staticmethod
    def _rank_text(record: dict[str, Any], column: str) -> str:
        rank = record.get(f"{column}_RANK")
        if rank in {None, ""}:
            return ""
        return f"Rank {safe_float(rank):.0f}"

    @staticmethod
    def _format_value(value: Any, value_type: str) -> str:
        if value in {None, ""}:
            return "-"
        if value_type == "pct":
            return format_percentage(value)
        if value_type == "integer":
            return f"{safe_float(value):.0f}"
        if value_type == "signed":
            return f"{safe_float(value):+.1f}"
        return f"{safe_float(value):.1f}"

    @staticmethod
    def _format_rate(value: Any) -> str:
        return f"{safe_float(value):.0f}%"

    @staticmethod
    def _split_name(record: dict[str, Any]) -> str:
        return str(record.get("GROUP_VALUE") or record.get("GROUP_SET") or record.get("PLAYER_NAME") or "Overall")

    @staticmethod
    def _shot_records(label: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if label == "Shot Type Summary":
            return sorted(records, key=lambda record: safe_float(record.get("FGA")), reverse=True)[:15]
        return records
