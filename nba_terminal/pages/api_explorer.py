"""Native NBA API endpoint explorer page."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from nba_terminal.services.api_catalog import CATEGORY_ORDER, EndpointInfo, build_endpoint_infos
from nba_terminal.ui.common import eyebrow_label, style_secondary_button, title_label


class ApiExplorerPage(QWidget):
    """Search and inspect nba_api endpoint metadata without network calls."""

    def __init__(self) -> None:
        super().__init__()
        self.endpoint_infos = build_endpoint_infos()
        self.category_counts = self._build_category_counts()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 40, 24)
        layout.setSpacing(16)
        layout.addWidget(eyebrow_label("NBA API"))
        layout.addWidget(title_label("Stats Explorer"))

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter endpoints, datasets, or columns")
        self.search_input.textChanged.connect(self._filter_endpoints)
        layout.addWidget(self.search_input)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.category_list = QListWidget()
        self.category_list.currentItemChanged.connect(self._filter_endpoints)
        self.endpoint_list = QListWidget()
        self.endpoint_list.currentItemChanged.connect(self._show_endpoint_details)
        detail = QWidget()
        detail_layout = QVBoxLayout(detail)
        self.endpoint_title = QLabel("Select an endpoint")
        self.endpoint_summary = QLabel("")
        buttons = QHBoxLayout()
        expand = QPushButton("Expand All")
        collapse = QPushButton("Collapse All")
        style_secondary_button(expand)
        style_secondary_button(collapse)
        expand.clicked.connect(lambda: self.dataset_tree.expandAll())
        collapse.clicked.connect(lambda: self.dataset_tree.collapseAll())
        buttons.addWidget(expand)
        buttons.addWidget(collapse)
        buttons.addStretch()
        self.dataset_tree = QTreeWidget()
        self.dataset_tree.setHeaderLabels(["Datasets and Columns"])
        detail_layout.addWidget(self.endpoint_title)
        detail_layout.addWidget(self.endpoint_summary)
        detail_layout.addLayout(buttons)
        detail_layout.addWidget(self.dataset_tree)
        splitter.addWidget(self.category_list)
        splitter.addWidget(self.endpoint_list)
        splitter.addWidget(detail)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setStretchFactor(2, 4)
        layout.addWidget(splitter, 1)
        self._populate_categories()
        self._filter_endpoints()

    def _build_category_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {"All": len(self.endpoint_infos)}
        for info in self.endpoint_infos:
            counts[info.category] = counts.get(info.category, 0) + 1
        return counts

    def _populate_categories(self) -> None:
        self.category_list.clear()
        for category in CATEGORY_ORDER:
            count = self.category_counts.get(category, 0)
            if category != "All" and count == 0:
                continue
            item = QListWidgetItem(f"{category} ({count})")
            item.setData(Qt.ItemDataRole.UserRole, category)
            self.category_list.addItem(item)
        if self.category_list.count():
            self.category_list.setCurrentRow(0)

    def _current_category(self) -> str:
        item = self.category_list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else "All"

    def _filter_endpoints(self) -> None:
        category = self._current_category()
        query = self.search_input.text().strip().lower()
        self.endpoint_list.clear()
        for info in self.endpoint_infos:
            if category != "All" and info.category != category:
                continue
            if query and query not in info.search_blob:
                continue
            item = QListWidgetItem(info.name)
            item.setData(Qt.ItemDataRole.UserRole, info)
            self.endpoint_list.addItem(item)
        if self.endpoint_list.count():
            self.endpoint_list.setCurrentRow(0)
        else:
            self._clear_details()

    def _clear_details(self) -> None:
        self.endpoint_title.setText("Select an endpoint")
        self.endpoint_summary.setText("")
        self.dataset_tree.clear()

    def _show_endpoint_details(self) -> None:
        item = self.endpoint_list.currentItem()
        if not item:
            self._clear_details()
            return
        info = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(info, EndpointInfo):
            self._clear_details()
            return
        self.endpoint_title.setText(f"{info.name} - {info.category}")
        self.endpoint_summary.setText(f"Datasets: {info.dataset_count} | Columns: {info.column_count}")
        self.dataset_tree.clear()
        for dataset_name, columns in info.datasets.items():
            dataset_item = QTreeWidgetItem([f"{dataset_name} ({len(columns)})"])
            for column in columns:
                dataset_item.addChild(QTreeWidgetItem([column]))
            self.dataset_tree.addTopLevelItem(dataset_item)
