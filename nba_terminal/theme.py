"""Shared colors and Qt style helpers for the NBA Terminal."""

from __future__ import annotations

from importlib import resources

from PyQt6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PyQt6.QtWidgets import QApplication

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


def _load_terminal_font() -> str:
    """Load the bundled UI font and return its Qt family name."""
    for family in ("Segoe UI", "Arial", "Tahoma"):
        if family in QFontDatabase.families():
            return family

    font_resource = resources.files("nba_terminal").joinpath("assets", "fonts", "DejaVuSans.ttf")
    with resources.as_file(font_resource) as font_path:
        if not font_path.exists():
            return "Segoe UI"
        font_id = QFontDatabase.addApplicationFont(str(font_path))
    families = QFontDatabase.applicationFontFamilies(font_id) if font_id >= 0 else []
    return families[0] if families else "Segoe UI"


def apply_app_theme(app: QApplication) -> None:
    """Apply the terminal-wide dark Qt palette and base font."""
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(COLORS["bg_primary"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(COLORS["text_primary"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(COLORS["bg_card"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(COLORS["bg_elevated"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(COLORS["text_primary"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(COLORS["bg_elevated"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(COLORS["text_primary"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(COLORS["accent"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(COLORS["text_primary"]))
    app.setPalette(palette)
    app.setFont(QFont(_load_terminal_font(), 10))


def app_stylesheet() -> str:
    """Return the base stylesheet shared by all terminal pages."""
    return f"""
        QMainWindow, QWidget {{
            background-color: {COLORS["bg_primary"]};
            color: {COLORS["text_primary"]};
        }}
        QScrollArea {{
            border: none;
            background: transparent;
        }}
        QScrollBar:vertical {{
            background: {COLORS["bg_primary"]};
            width: 10px;
            margin: 0;
        }}
        QScrollBar::handle:vertical {{
            background: {COLORS["bg_hover"]};
            min-height: 30px;
            border-radius: 5px;
        }}
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {{
            height: 0;
        }}
        QLineEdit, QComboBox {{
            background-color: {COLORS["bg_elevated"]};
            color: {COLORS["text_primary"]};
            border: 1px solid {COLORS["border"]};
            border-radius: 4px;
            padding: 10px;
            font-size: 14px;
        }}
        QLineEdit:focus, QComboBox:focus {{
            border: 1px solid {COLORS["accent"]};
        }}
        QCheckBox, QRadioButton {{
            color: {COLORS["text_secondary"]};
            spacing: 6px;
            font-size: 13px;
        }}
        QPushButton {{
            background-color: {COLORS["bg_elevated"]};
            color: {COLORS["text_secondary"]};
            border: none;
            border-radius: 6px;
            padding: 10px 14px;
            font-weight: 700;
            font-size: 13px;
        }}
        QPushButton:hover {{
            background-color: {COLORS["bg_hover"]};
            color: {COLORS["text_primary"]};
        }}
        QPushButton:disabled {{
            color: {COLORS["text_tertiary"]};
            background-color: {COLORS["divider"]};
        }}
        QTableWidget {{
            background-color: {COLORS["bg_primary"]};
            color: {COLORS["text_primary"]};
            border: none;
            gridline-color: {COLORS["divider"]};
            alternate-background-color: {COLORS["bg_elevated"]};
        }}
        QHeaderView::section {{
            background-color: {COLORS["bg_elevated"]};
            color: {COLORS["text_secondary"]};
            border: none;
            padding: 6px 8px;
            font-weight: 700;
        }}
        QListWidget, QTreeWidget, QTextEdit {{
            background-color: {COLORS["bg_card"]};
            color: {COLORS["text_primary"]};
            border: 1px solid {COLORS["border"]};
            padding: 6px;
        }}
        QListWidget::item, QTreeWidget::item {{
            padding: 8px;
        }}
        QListWidget::item:selected, QTreeWidget::item:selected {{
            background-color: {COLORS["bg_hover"]};
            color: {COLORS["text_primary"]};
        }}
        QTabWidget::pane {{
            border: 1px solid {COLORS["divider"]};
            background: {COLORS["bg_primary"]};
        }}
        QTabBar::tab {{
            background: {COLORS["bg_elevated"]};
            color: {COLORS["text_secondary"]};
            padding: 10px 14px;
            margin-right: 2px;
        }}
        QTabBar::tab:selected {{
            background: {COLORS["accent"]};
            color: {COLORS["text_primary"]};
        }}
    """
