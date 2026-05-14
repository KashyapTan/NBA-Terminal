"""Reusable Qt helpers for terminal pages."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QFrame,
    QHeaderView,
    QLabel,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from nba_terminal.theme import COLORS


def clear_layout(layout: QVBoxLayout) -> None:
    """Delete every widget and child layout from a Qt layout."""
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()
            continue
        child_layout = item.layout()
        if child_layout is not None:
            clear_layout(child_layout)


def title_label(text: str, size: int = 28) -> QLabel:
    """Create a terminal page title label."""
    label = QLabel(text)
    label.setStyleSheet(
        f"color: {COLORS['text_primary']}; font-size: {size}px; font-weight: 800;"
    )
    return label


def eyebrow_label(text: str) -> QLabel:
    """Create a compact uppercase section label."""
    label = QLabel(text)
    label.setStyleSheet(
        f"color: {COLORS['text_tertiary']}; font-size: 11px; font-weight: 800;"
    )
    return label


def card() -> QFrame:
    """Create a standard bordered terminal card."""
    frame = QFrame()
    frame.setStyleSheet(
        "QFrame {"
        f"background-color: {COLORS['bg_card']};"
        f"border: 1px solid {COLORS['border']};"
        "border-radius: 8px;"
        "}"
        "QLabel { border: none; }"
    )
    return frame


def scroll_page() -> tuple[QScrollArea, QWidget, QVBoxLayout]:
    """Create a scroll area with a content widget and vertical layout."""
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    content = QWidget()
    layout = QVBoxLayout(content)
    layout.setContentsMargins(28, 28, 28, 28)
    layout.setSpacing(18)
    scroll.setWidget(content)
    return scroll, content, layout


def populate_table(
    table: QTableWidget,
    headers: Sequence[str],
    rows: Sequence[Sequence[Any]],
    color_key_column: int | None = None,
) -> None:
    """Populate a read-only table and optionally color rows by a color-key column."""
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(list(headers))
    table.setRowCount(len(rows))
    table.verticalHeader().setVisible(False)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

    for row_index, row in enumerate(rows):
        color = None
        if color_key_column is not None and color_key_column < len(row):
            color = COLORS.get(str(row[color_key_column]))
        for column_index, value in enumerate(row):
            if column_index == color_key_column:
                value = ""
            item = QTableWidgetItem(str(value))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setForeground(QColor(color or COLORS["text_primary"]))
            table.setItem(row_index, column_index, item)

    header = table.horizontalHeader()
    for index in range(table.columnCount()):
        header.setSectionResizeMode(index, QHeaderView.ResizeMode.Stretch)


class ErrorPanel(QWidget):
    """Small error panel shown when a page cannot be loaded."""

    def __init__(self, title: str, message: str) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(8)
        layout.addWidget(eyebrow_label("PAGE ERROR"))
        layout.addWidget(title_label(title, 22))
        body = QLabel(message)
        body.setWordWrap(True)
        body.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 13px;")
        layout.addWidget(body)
        layout.addStretch()

