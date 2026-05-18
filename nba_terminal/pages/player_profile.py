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
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from nba_terminal.analytics import format_percentage, safe_float
from nba_terminal.services.player_data import (
    PLAYER_PROFILE_WINDOWS,
    clear_player_profile_cache,
    fetch_player_stat_profile,
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
TABLE_HEADER_HEIGHT = 34
TABLE_ROW_HEIGHT = 30
TABLE_CHROME_HEIGHT = 8
DASHBOARD_GROUP_COLORS = {
    "Production": "accent",
    "Shooting": "success",
    "Advanced": "warning",
    "Scoring Mix": "accent_soft",
    "Team Share": "accent",
    "Misc & Defense": "danger",
}
SHOOTING_SPLIT_COLORS = {
    "Assisted": "accent",
    "Distance 5ft": "success",
    "Distance 8ft": "success",
    "Overall": "accent_soft",
    "Shot Area": "warning",
    "Shot Type Summary": "danger",
}
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
METRIC_GROUP_GRID_SPACING = 16
METRIC_GROUP_TABLE_ROWS = max(len(metrics) for metrics in METRIC_GROUPS.values())
METRIC_GROUP_TABLE_HEIGHT = (
    TABLE_HEADER_HEIGHT + (METRIC_GROUP_TABLE_ROWS * TABLE_ROW_HEIGHT) + TABLE_CHROME_HEIGHT
)
METRIC_GROUP_CARD_HEIGHT = METRIC_GROUP_TABLE_HEIGHT + 88


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
        self.clear_cache_button = QPushButton("Clear Cache")
        self.clear_cache_button.setMinimumWidth(120)
        style_secondary_button(self.clear_cache_button)
        self.clear_cache_button.clicked.connect(self.clear_cache)
        self.clear_button = QPushButton("Clear Results")
        self.clear_button.setMinimumWidth(130)
        style_secondary_button(self.clear_button)
        self.clear_button.clicked.connect(self.clear_results)

        top.addWidget(eyebrow_label("PLAYER"), 0, 0)
        top.addWidget(QLabel(""), 0, 1)
        top.addWidget(self.player_input, 1, 0)
        top.addWidget(self.fetch_button, 1, 1)
        top.addWidget(self.clear_cache_button, 1, 2)
        top.addWidget(self.clear_button, 1, 3)
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
        cache_hits = sum(1 for item in seasons if item.get("cache_hit"))
        status_parts = [f"Loaded {loaded} season profile(s)"]
        if cache_hits:
            status_parts.append(f"{cache_hits} from cache")
        if failed:
            status_parts.append(f"{failed} failed")
        self.status.setText(" | ".join(status_parts) + ".")
        self._clear_results()
        for item in seasons:
            self.results_tabs.addTab(self._season_page(item), str(item["season"]))
        self.results_tabs.setVisible(bool(seasons))

    def clear_cache(self) -> None:
        removed = clear_player_profile_cache()
        self.status.setText(f"Cleared {removed} cached player profile(s).")

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

        if "error" in item:
            header = QLabel(self._season_header(item))
            header.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 22px; font-weight: 800;")
            layout.addWidget(header)
            layout.addWidget(self._warnings_card([str(item["error"])], title="LOAD FAILED"))
            layout.addStretch()
            return page

        layout.addWidget(self._profile_header_card(item))
        self._add_kpi_grid(layout, item)
        self._add_metric_group_grid(layout, item)

        detail_row = QHBoxLayout()
        detail_row.setSpacing(14)
        detail_row.addWidget(self._game_summary_card(item), 3)
        detail_row.addWidget(self._hit_rates_card(item), 2)
        layout.addLayout(detail_row)

        layout.addWidget(self._shooting_splits_card(item))
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
        for column in range(4):
            grid.setColumnStretch(column, 1)
        layout.addLayout(grid)

    def _kpi_card(self, item: dict[str, Any], label: str, measure: str, column: str, value_type: str) -> QWidget:
        frame = card()
        frame.setMinimumHeight(108)
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(6)

        record = item["measures"].get(measure, {})
        rank = self._rank_text(record, column)
        raw_value = record.get(column)
        value = self._format_value(raw_value, value_type)

        title = QLabel(label)
        title.setStyleSheet(f"color: {COLORS['text_tertiary']}; font-size: 11px; font-weight: 800;")
        metric = QLabel(value)
        metric.setStyleSheet(
            f"color: {self._metric_color(column, raw_value)}; font-size: 26px; font-weight: 900;"
        )
        rank_label = QLabel(rank or "Rank -")
        rank_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
        layout.addWidget(title)
        layout.addWidget(metric)
        layout.addWidget(rank_label)
        return frame

    def _profile_header_card(self, item: dict[str, Any]) -> QWidget:
        frame = card()
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(18)

        title_block = QVBoxLayout()
        title_block.setSpacing(4)
        title = QLabel(str(item.get("player", "")))
        title.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 24px; font-weight: 900;")
        subtitle = QLabel(f"{item['season']} {item['season_type']}")
        subtitle.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 13px;")
        title_block.addWidget(title)
        title_block.addWidget(subtitle)
        layout.addLayout(title_block, 1)

        base = item["measures"].get("Base", {})
        badges = [
            ("TEAM", str(item.get("team") or "-")),
            ("GP", self._format_value(base.get("GP"), "integer")),
            ("RECORD", self._record_text(base)),
            ("AGE", self._format_value(base.get("AGE"), "number")),
        ]
        badge_row = QHBoxLayout()
        badge_row.setSpacing(8)
        for label, value in badges:
            badge_row.addWidget(self._badge(label, value))
        layout.addLayout(badge_row)
        return frame

    def _add_metric_group_grid(self, layout: QVBoxLayout, item: dict[str, Any]) -> None:
        section = QLabel("Season Dashboard")
        section.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 16px; font-weight: 900;")
        layout.addWidget(section)

        grid = QGridLayout()
        grid.setContentsMargins(0, 2, 0, 4)
        grid.setHorizontalSpacing(METRIC_GROUP_GRID_SPACING)
        grid.setVerticalSpacing(METRIC_GROUP_GRID_SPACING)
        for index, (label, metrics) in enumerate(METRIC_GROUPS.items()):
            card_widget = self._metric_group_card(label, self._metric_group_rows(item, metrics))
            grid.addWidget(card_widget, index // 2, index % 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)

    def _metric_group_card(self, title: str, rows: list[list[Any]]) -> QWidget:
        color = COLORS[DASHBOARD_GROUP_COLORS.get(title, "accent")]
        frame = card()
        frame.setStyleSheet(
            "QFrame {"
            f"background-color: {COLORS['bg_card']};"
            f"border: 1px solid {COLORS['border']};"
            f"border-left: 3px solid {color};"
            "border-radius: 8px;"
            "}"
            "QLabel { border: none; }"
        )
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        frame.setFixedHeight(METRIC_GROUP_CARD_HEIGHT)
        frame.setMinimumWidth(0)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(10)

        heading = QHBoxLayout()
        heading.addWidget(self._dashboard_heading(title, color))
        heading.addStretch()
        count = QLabel(f"{len(rows)} stats")
        count.setStyleSheet(f"color: {COLORS['text_tertiary']}; font-size: 11px; border: none;")
        heading.addWidget(count)
        layout.addLayout(heading)
        layout.addWidget(
            self._table(
                ("Metric", "Value", "Rank"),
                rows,
                max_height=METRIC_GROUP_TABLE_HEIGHT,
                min_height=METRIC_GROUP_TABLE_HEIGHT,
                accent_color=color,
                color_ranks=True,
            )
        )
        return frame

    def _metric_group_rows(
        self,
        item: dict[str, Any],
        metrics: tuple[tuple[str, str, str, str], ...],
    ) -> list[list[Any]]:
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
                ]
            )
        return rows

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
        return self._table_card(
            "GAME-LOG PROFILE",
            headers,
            rows,
            max_height=520,
            min_height=250,
            accent_color=COLORS["accent"],
            color_cv=True,
        )

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
        return self._table_card(
            "HIT RATES",
            headers,
            rows,
            max_height=520,
            min_height=250,
            accent_color=COLORS["success"],
            color_rates=True,
        )

    def _shooting_splits_card(self, item: dict[str, Any]) -> QWidget:
        frame = card()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(14)

        heading = QHBoxLayout()
        heading.addWidget(self._dashboard_heading("SHOOTING SPLITS", COLORS["success"]))
        heading.addStretch()
        layout.addLayout(heading)

        splits = item.get("shooting_splits") or {}
        headers = ("Split", "FGM", "FGA", "FG%", "3PM", "3PA", "3P%", "eFG%", "Ast FGM", "Unast FGM")
        if not splits:
            table = self._table(("Status",), [["Shooting splits unavailable"]], max_height=180, min_height=120)
            layout.addWidget(table)
            return frame

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)
        for index, (label, records) in enumerate(splits.items()):
            grid.addWidget(
                self._shooting_split_card(label, headers, self._shooting_split_rows(label, records)),
                index,
                0,
            )
        grid.setColumnStretch(0, 1)
        layout.addLayout(grid)
        return frame

    def _shooting_split_card(self, title: str, headers: tuple[str, ...], rows: list[list[Any]]) -> QWidget:
        color = COLORS[SHOOTING_SPLIT_COLORS.get(title, "success")]
        frame = card()
        frame.setStyleSheet(
            "QFrame {"
            f"background-color: {COLORS['bg_primary']};"
            f"border: 1px solid {COLORS['border']};"
            f"border-left: 3px solid {color};"
            "border-radius: 8px;"
            "}"
            "QLabel { border: none; }"
        )
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(10)

        heading = QHBoxLayout()
        heading.addWidget(self._dashboard_heading(title, color))
        heading.addStretch()
        count = QLabel(f"{len(rows)} splits")
        count.setStyleSheet(f"color: {COLORS['text_tertiary']}; font-size: 11px; border: none;")
        heading.addWidget(count)
        layout.addLayout(heading)
        layout.addWidget(
            self._table(
                headers,
                rows,
                max_height=520,
                min_height=150,
                accent_color=color,
                color_shooting=True,
            )
        )
        return frame

    def _shooting_split_rows(self, label: str, records: list[dict[str, Any]]) -> list[list[Any]]:
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
        return rows

    def _table_card(
        self,
        title: str,
        headers: tuple[str, ...],
        rows: list[list[Any]],
        max_height: int,
        min_height: int,
        accent_color: str | None = None,
        color_rates: bool = False,
        color_cv: bool = False,
    ) -> QWidget:
        frame = card()
        if accent_color is not None:
            frame.setStyleSheet(
                "QFrame {"
                f"background-color: {COLORS['bg_card']};"
                f"border: 1px solid {COLORS['border']};"
                f"border-left: 3px solid {accent_color};"
                "border-radius: 8px;"
                "}"
                "QLabel { border: none; }"
            )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(10)
        layout.addWidget(self._dashboard_heading(title, accent_color) if accent_color else eyebrow_label(title))
        layout.addWidget(
            self._table(
                headers,
                rows,
                max_height=max_height,
                min_height=min_height,
                accent_color=accent_color,
                color_rates=color_rates,
                color_cv=color_cv,
            )
        )
        return frame

    def _table_page(
        self,
        headers: tuple[str, ...],
        rows: list[list[Any]],
        max_height: int,
        min_height: int,
    ) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addWidget(self._table(headers, rows, max_height=max_height, min_height=min_height))
        return page

    def _table(
        self,
        headers: tuple[str, ...],
        rows: list[list[Any]],
        max_height: int,
        min_height: int = 126,
        accent_color: str | None = None,
        color_ranks: bool = False,
        color_rates: bool = False,
        color_cv: bool = False,
        color_shooting: bool = False,
    ) -> QTableWidget:
        table = QTableWidget()
        style_terminal_table(table, bordered=True)
        display_rows = rows or [["No data", *("-" for _ in headers[1:])]]
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setRowCount(len(display_rows))
        table.verticalHeader().setDefaultSectionSize(TABLE_ROW_HEIGHT)
        table.horizontalHeader().setFixedHeight(TABLE_HEADER_HEIGHT)
        table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        for row_index, row in enumerate(display_rows):
            for column_index, value in enumerate(row):
                item = QTableWidgetItem(str(value))
                alignment = Qt.AlignmentFlag.AlignVCenter
                alignment |= Qt.AlignmentFlag.AlignLeft if column_index == 0 else Qt.AlignmentFlag.AlignRight
                item.setTextAlignment(alignment)
                item.setForeground(
                    QColor(
                        self._cell_color(
                            headers[column_index],
                            str(value),
                            column_index,
                            accent_color,
                            color_ranks,
                            color_rates,
                            color_cv,
                            color_shooting,
                        )
                    )
                )
                table.setItem(row_index, column_index, item)
        header = table.horizontalHeader()
        if table.columnCount() == 1:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        elif color_shooting:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            widths = {
                "FGM": 74,
                "FGA": 74,
                "FG%": 76,
                "3PM": 74,
                "3PA": 74,
                "3P%": 76,
                "eFG%": 76,
                "Ast FGM": 88,
                "Unast FGM": 104,
            }
            for index, header_label in enumerate(headers[1:], start=1):
                header.setSectionResizeMode(index, QHeaderView.ResizeMode.Fixed)
                table.setColumnWidth(index, widths.get(header_label, 76))
        elif table.columnCount() <= 5:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            for index in range(1, table.columnCount()):
                header.setSectionResizeMode(index, QHeaderView.ResizeMode.Fixed)
                table.setColumnWidth(index, 86)
        else:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            for index in range(1, table.columnCount()):
                header.setSectionResizeMode(index, QHeaderView.ResizeMode.Fixed)
                table.setColumnWidth(index, 70)
        row_height = TABLE_HEADER_HEIGHT + (len(display_rows) * TABLE_ROW_HEIGHT) + TABLE_CHROME_HEIGHT
        table.setFixedHeight(max(min_height, min(max_height, row_height)))
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
    def _badge(label: str, value: str) -> QLabel:
        badge = QLabel(f"{label}  {value}")
        badge.setStyleSheet(
            "QLabel {"
            f"background-color: {COLORS['bg_elevated']};"
            f"color: {COLORS['text_secondary']};"
            f"border: 1px solid {COLORS['border']};"
            "border-radius: 6px; padding: 7px 10px; font-size: 11px; font-weight: 800;"
            "}"
        )
        return badge

    @staticmethod
    def _dashboard_heading(text: str, color: str) -> QLabel:
        label = QLabel(text.upper())
        label.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: 900; border: none;")
        return label

    @staticmethod
    def _record_text(base: dict[str, Any]) -> str:
        wins = base.get("W")
        losses = base.get("L")
        if wins in {None, ""} or losses in {None, ""}:
            return "-"
        return f"{safe_float(wins):.0f}-{safe_float(losses):.0f}"

    @staticmethod
    def _metric_color(column: str, value: Any) -> str:
        if column == "NET_RATING":
            return COLORS["success"] if safe_float(value) >= 0 else COLORS["danger"]
        if column in {"TS_PCT", "PIE"}:
            return COLORS["success"]
        if column == "USG_PCT":
            return COLORS["accent"]
        return COLORS["text_primary"]

    @staticmethod
    def _cell_color(
        header: str,
        value: str,
        column_index: int,
        accent_color: str | None,
        color_ranks: bool,
        color_rates: bool,
        color_cv: bool,
        color_shooting: bool,
    ) -> str:
        if value in {"-", "No data"}:
            return COLORS["text_tertiary"]
        if color_ranks and header == "Rank":
            return PlayerProfilePage._rank_color(value)
        if color_rates and header in {"Season", "L5", "L10", "L20"}:
            return PlayerProfilePage._rate_color(value)
        if color_cv and header == "CV":
            return PlayerProfilePage._cv_color(value)
        if color_shooting:
            return PlayerProfilePage._shooting_cell_color(header, value, accent_color)
        if header == "Value" and accent_color is not None:
            return PlayerProfilePage._value_color(value, accent_color)
        if color_cv and accent_color is not None and header in {"Season", "L5", "L10", "L20"}:
            return accent_color
        if accent_color is None:
            return COLORS["text_primary"]
        if column_index == 0:
            return COLORS["text_primary"]
        return COLORS["text_secondary"]

    @staticmethod
    def _rank_color(value: str) -> str:
        rank_text = value.replace("Rank", "").strip()
        rank = safe_float(rank_text, default=0.0)
        if rank <= 0:
            return COLORS["text_tertiary"]
        if rank <= 50:
            return COLORS["success"]
        if rank <= 150:
            return COLORS["accent"]
        if rank <= 300:
            return COLORS["warning"]
        return COLORS["danger"]

    @staticmethod
    def _value_color(value: str, accent_color: str) -> str:
        if value.startswith("+"):
            return COLORS["success"]
        if value.startswith("-"):
            return COLORS["danger"]
        return accent_color

    @staticmethod
    def _rate_color(value: str) -> str:
        rate = safe_float(value.rstrip("%"), default=-1.0)
        if rate < 0:
            return COLORS["text_tertiary"]
        if rate >= 75:
            return COLORS["success"]
        if rate >= 50:
            return COLORS["accent"]
        if rate >= 25:
            return COLORS["warning"]
        return COLORS["danger"]

    @staticmethod
    def _cv_color(value: str) -> str:
        cv = safe_float(value.rstrip("%"), default=-1.0)
        if cv < 0:
            return COLORS["text_tertiary"]
        if cv < 30:
            return COLORS["success"]
        if cv < 50:
            return COLORS["accent"]
        if cv < 75:
            return COLORS["warning"]
        return COLORS["danger"]

    @staticmethod
    def _shooting_cell_color(header: str, value: str, accent_color: str | None) -> str:
        if header == "Split":
            return COLORS["text_primary"]
        if header in {"FGM", "FGA", "3PM", "3PA"}:
            return accent_color or COLORS["accent"]
        if header in {"FG%", "eFG%"}:
            return PlayerProfilePage._field_goal_pct_color(value)
        if header == "3P%":
            return PlayerProfilePage._three_point_pct_color(value)
        if header in {"Ast FGM", "Unast FGM"}:
            return PlayerProfilePage._rate_color(value)
        return COLORS["text_secondary"]

    @staticmethod
    def _field_goal_pct_color(value: str) -> str:
        pct = safe_float(value.rstrip("%"), default=-1.0)
        if pct < 0:
            return COLORS["text_tertiary"]
        if pct >= 60:
            return COLORS["success"]
        if pct >= 50:
            return COLORS["accent"]
        if pct >= 40:
            return COLORS["warning"]
        return COLORS["danger"]

    @staticmethod
    def _three_point_pct_color(value: str) -> str:
        pct = safe_float(value.rstrip("%"), default=-1.0)
        if pct < 0:
            return COLORS["text_tertiary"]
        if pct >= 38:
            return COLORS["success"]
        if pct >= 34:
            return COLORS["accent"]
        if pct >= 30:
            return COLORS["warning"]
        return COLORS["danger"]

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
