import inspect
import json
from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QPalette
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from nba_api.stats import endpoints

COLORS = {
    "bg_primary": "#0f0f0f",
    "bg_card": "#1a1a1a",
    "bg_elevated": "#242424",
    "bg_hover": "#2a2a2a",
    "text_primary": "#ffffff",
    "text_secondary": "#8b8b8b",
    "text_tertiary": "#5c5c5c",
    "accent": "#6366f1",
    "accent_soft": "#4f46e5",
    "success": "#10b981",
    "warning": "#f59e0b",
    "danger": "#ef4444",
    "border": "#2a2a2a",
    "divider": "#1f1f1f",
}

CATEGORY_ORDER = [
    "All",
    "Box Score",
    "Play By Play & Rotation",
    "Player Dashboards",
    "Team Dashboards",
    "Player Tracking (Pt)",
    "Team Tracking (Pt)",
    "League Tracking (Pt)",
    "Shot Charts & Locations",
    "Lineups & On/Off",
    "Matchups & Comparisons",
    "Game Logs & Finders",
    "Schedule & Standings",
    "Leaders & Highlights",
    "Hustle & Defense",
    "Estimated Metrics",
    "Cumulative Stats",
    "Synergy & Play Types",
    "Bio & Profiles",
    "Franchise & History",
    "Draft & Combine",
    "Fantasy",
    "Video",
    "Misc",
]


@dataclass(frozen=True)
class EndpointInfo:
    name: str
    category: str
    datasets: dict
    dataset_count: int
    column_count: int
    search_blob: str


def categorize_endpoint(name: str) -> str:
    if name.startswith("BoxScore"):
        return "Box Score"
    if name in {"PlayByPlay", "PlayByPlayV2", "PlayByPlayV3", "WinProbabilityPBP", "GameRotation"}:
        return "Play By Play & Rotation"
    if name.startswith("PlayerDashboard"):
        return "Player Dashboards"
    if name.startswith("TeamDashboard"):
        return "Team Dashboards"
    if name.startswith("PlayerDashPt"):
        return "Player Tracking (Pt)"
    if name.startswith("TeamDashPt"):
        return "Team Tracking (Pt)"
    if name.startswith("LeagueDashPt"):
        return "League Tracking (Pt)"
    if "ShotChart" in name or "ShotLocations" in name:
        return "Shot Charts & Locations"
    if name in {
        "LeagueDashLineups",
        "TeamDashLineups",
        "LeagueLineupViz",
        "TeamPlayerOnOffSummary",
        "TeamPlayerOnOffDetails",
        "LeaguePlayerOnDetails",
    }:
        return "Lineups & On/Off"
    if name in {"PlayerVsPlayer", "TeamVsPlayer", "TeamAndPlayersVsPlayers", "PlayerCompare", "MatchupsRollup"}:
        return "Matchups & Comparisons"
    if "GameLog" in name or name.endswith("GameLog") or "GameFinder" in name or "GameStreakFinder" in name:
        return "Game Logs & Finders"
    if name in {
        "ScoreboardV2",
        "ScheduleLeagueV2",
        "LeagueStandings",
        "LeagueStandingsV3",
        "PlayoffPicture",
        "ISTStandings",
        "CommonPlayoffSeries",
        "PlayerNextNGames",
    }:
        return "Schedule & Standings"
    if name in {
        "LeagueLeaders",
        "HomePageLeaders",
        "HomePageV2",
        "AllTimeLeadersGrids",
        "LeadersTiles",
        "AssistLeaders",
        "AssistTracker",
    }:
        return "Leaders & Highlights"
    if "Hustle" in name or "Defense" in name or "Defend" in name:
        return "Hustle & Defense"
    if name in {"PlayerEstimatedMetrics", "TeamEstimatedMetrics"}:
        return "Estimated Metrics"
    if name in {"CumeStatsPlayer", "CumeStatsTeam", "CumeStatsPlayerGames", "CumeStatsTeamGames"}:
        return "Cumulative Stats"
    if name in {"SynergyPlayTypes"}:
        return "Synergy & Play Types"
    if name in {
        "CommonPlayerInfo",
        "PlayerProfileV2",
        "PlayerCareerStats",
        "PlayerAwards",
        "PlayerIndex",
        "CommonAllPlayers",
        "CommonTeamRoster",
        "CommonTeamYears",
        "TeamInfoCommon",
        "TeamDetails",
        "TeamYearByYearStats",
        "TeamHistoricalLeaders",
        "TeamPlayerDashboard",
    }:
        return "Bio & Profiles"
    if name.startswith("Franchise"):
        return "Franchise & History"
    if name.startswith("Draft"):
        return "Draft & Combine"
    if "Fantasy" in name or "FanDuel" in name:
        return "Fantasy"
    if name.startswith("Video"):
        return "Video"
    return "Misc"


def stringify_value(value) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=True)
    return str(value)


def normalize_expected_data(expected_data: dict) -> dict:
    datasets = {}
    for dataset_name, dataset_value in expected_data.items():
        if isinstance(dataset_value, list):
            if all(isinstance(item, str) for item in dataset_value):
                columns = dataset_value
            else:
                columns = [stringify_value(item) for item in dataset_value]
        elif isinstance(dataset_value, dict):
            columns = [f"{key}: {stringify_value(value)}" for key, value in dataset_value.items()]
        else:
            columns = [stringify_value(dataset_value)]
        datasets[dataset_name] = columns
    return datasets


def build_endpoint_infos() -> list[EndpointInfo]:
    infos = []
    for name in sorted(dir(endpoints)):
        obj = getattr(endpoints, name)
        if not inspect.isclass(obj):
            continue
        expected_data = getattr(obj, "expected_data", None)
        if not isinstance(expected_data, dict):
            continue
        datasets = normalize_expected_data(expected_data)
        dataset_count = len(datasets)
        column_count = sum(len(columns) for columns in datasets.values())
        category = categorize_endpoint(name)
        search_parts = [name, category]
        search_parts.extend(datasets.keys())
        for columns in datasets.values():
            search_parts.extend(columns)
        search_blob = " ".join(search_parts).lower()
        infos.append(
            EndpointInfo(
                name=name,
                category=category,
                datasets=datasets,
                dataset_count=dataset_count,
                column_count=column_count,
                search_blob=search_blob,
            )
        )
    return infos


class NBAStatsExplorer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NBA API Stats Explorer")
        self.resize(1600, 900)

        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(COLORS["bg_primary"]))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(COLORS["text_primary"]))
        self.setPalette(palette)

        self.endpoint_infos = build_endpoint_infos()
        self.category_counts = self._build_category_counts()

        self._build_ui()
        self._populate_categories()
        self._filter_endpoints()

    def _build_category_counts(self) -> dict:
        counts = {}
        for info in self.endpoint_infos:
            counts[info.category] = counts.get(info.category, 0) + 1
        counts["All"] = len(self.endpoint_infos)
        return counts

    def _build_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        hero_layout = QVBoxLayout()
        subtitle = QLabel("NBA API STATS")
        subtitle.setStyleSheet(f"color: {COLORS['text_tertiary']}; font-weight: bold; font-size: 11px;")
        title = QLabel("Stats Explorer")
        title.setStyleSheet(f"color: {COLORS['text_primary']}; font-weight: bold; font-size: 28px;")
        hero_layout.addWidget(subtitle)
        hero_layout.addWidget(title)
        main_layout.addLayout(hero_layout)

        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter endpoints, datasets, or columns")
        self.search_input.setStyleSheet(
            "QLineEdit {"
            f"background-color: {COLORS['bg_elevated']};"
            f"color: {COLORS['text_primary']};"
            f"border: 1px solid {COLORS['border']};"
            "border-radius: 6px;"
            "padding: 10px;"
            "font-size: 13px;"
            "}"
            "QLineEdit:focus {"
            f"border: 1px solid {COLORS['accent']};"
            "}"
        )
        self.search_input.textChanged.connect(self._filter_endpoints)
        search_row.addWidget(self.search_input)
        main_layout.addLayout(search_row)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.category_list = QListWidget()
        self.category_list.setStyleSheet(
            "QListWidget {"
            f"background-color: {COLORS['bg_card']};"
            f"color: {COLORS['text_primary']};"
            f"border: 1px solid {COLORS['border']};"
            "padding: 6px;"
            "}"
            "QListWidget::item {"
            "padding: 8px;"
            "}"
            "QListWidget::item:selected {"
            f"background-color: {COLORS['bg_hover']};"
            f"color: {COLORS['text_primary']};"
            "}"
        )
        self.category_list.currentItemChanged.connect(self._filter_endpoints)

        self.endpoint_list = QListWidget()
        self.endpoint_list.setStyleSheet(
            "QListWidget {"
            f"background-color: {COLORS['bg_card']};"
            f"color: {COLORS['text_primary']};"
            f"border: 1px solid {COLORS['border']};"
            "padding: 6px;"
            "}"
            "QListWidget::item {"
            "padding: 8px;"
            "}"
            "QListWidget::item:selected {"
            f"background-color: {COLORS['bg_hover']};"
            f"color: {COLORS['text_primary']};"
            "}"
        )
        self.endpoint_list.currentItemChanged.connect(self._show_endpoint_details)

        detail_widget = QWidget()
        detail_layout = QVBoxLayout(detail_widget)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(8)

        self.endpoint_title = QLabel("Select an endpoint")
        self.endpoint_title.setStyleSheet(f"color: {COLORS['text_primary']}; font-weight: bold; font-size: 16px;")
        self.endpoint_summary = QLabel("")
        self.endpoint_summary.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")

        button_row = QHBoxLayout()
        self.expand_btn = QPushButton("Expand All")
        self.collapse_btn = QPushButton("Collapse All")
        for btn in (self.expand_btn, self.collapse_btn):
            btn.setStyleSheet(
                "QPushButton {"
                f"background-color: {COLORS['bg_elevated']};"
                f"color: {COLORS['text_secondary']};"
                "border: none;"
                "padding: 6px 12px;"
                "border-radius: 4px;"
                "}"
                "QPushButton:hover {"
                f"background-color: {COLORS['bg_hover']};"
                "}"
            )
        self.expand_btn.clicked.connect(lambda: self.dataset_tree.expandAll())
        self.collapse_btn.clicked.connect(lambda: self.dataset_tree.collapseAll())
        button_row.addWidget(self.expand_btn)
        button_row.addWidget(self.collapse_btn)
        button_row.addStretch()

        self.dataset_tree = QTreeWidget()
        self.dataset_tree.setHeaderLabels(["Datasets and Columns"])
        self.dataset_tree.setStyleSheet(
            "QTreeWidget {"
            f"background-color: {COLORS['bg_card']};"
            f"color: {COLORS['text_primary']};"
            f"border: 1px solid {COLORS['border']};"
            "}"
            "QTreeWidget::item {"
            "padding: 4px;"
            "}"
        )

        detail_layout.addWidget(self.endpoint_title)
        detail_layout.addWidget(self.endpoint_summary)
        detail_layout.addLayout(button_row)
        detail_layout.addWidget(self.dataset_tree)

        splitter.addWidget(self.category_list)
        splitter.addWidget(self.endpoint_list)
        splitter.addWidget(detail_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setStretchFactor(2, 4)

        main_layout.addWidget(splitter)

    def _populate_categories(self):
        self.category_list.clear()
        for category in CATEGORY_ORDER:
            count = self.category_counts.get(category, 0)
            if category != "All" and count == 0:
                continue
            label = f"{category} ({count})"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, category)
            self.category_list.addItem(item)
        if self.category_list.count() > 0:
            self.category_list.setCurrentRow(0)

    def _current_category(self) -> str:
        item = self.category_list.currentItem()
        if not item:
            return "All"
        category = item.data(Qt.ItemDataRole.UserRole)
        return category or "All"

    def _filter_endpoints(self):
        category = self._current_category()
        query = self.search_input.text().strip().lower()
        filtered = []
        for info in self.endpoint_infos:
            if category != "All" and info.category != category:
                continue
            if query and query not in info.search_blob:
                continue
            filtered.append(info)
        filtered.sort(key=lambda x: x.name)

        self.endpoint_list.clear()
        for info in filtered:
            item = QListWidgetItem(info.name)
            item.setData(Qt.ItemDataRole.UserRole, info)
            self.endpoint_list.addItem(item)

        if self.endpoint_list.count() > 0:
            self.endpoint_list.setCurrentRow(0)
        else:
            self._clear_details()

    def _clear_details(self):
        self.endpoint_title.setText("Select an endpoint")
        self.endpoint_summary.setText("")
        self.dataset_tree.clear()

    def _show_endpoint_details(self):
        item = self.endpoint_list.currentItem()
        if not item:
            self._clear_details()
            return
        info = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(info, EndpointInfo):
            self._clear_details()
            return

        self.endpoint_title.setText(f"{info.name} - {info.category}")
        self.endpoint_summary.setText(
            f"Datasets: {info.dataset_count} | Columns: {info.column_count}"
        )
        self.dataset_tree.clear()
        for dataset_name, columns in info.datasets.items():
            dataset_item = QTreeWidgetItem([f"{dataset_name} ({len(columns)})"])
            for col in columns:
                dataset_item.addChild(QTreeWidgetItem([col]))
            self.dataset_tree.addTopLevelItem(dataset_item)


if __name__ == "__main__":
    app = QApplication([])
    app.setFont(QFont("Segoe UI", 10))
    window = NBAStatsExplorer()
    window.show()
    app.exec()
