"""Today slate model-edge scanner terminal page."""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QLabel, QPushButton, QTableWidget, QVBoxLayout, QWidget

from nba_terminal.analytics import format_signed, sort_confident_bets
from nba_terminal.services.slate import scan_slate_edges
from nba_terminal.theme import COLORS
from nba_terminal.ui.common import eyebrow_label, populate_table, scroll_page, title_label


class SlateScannerWorker(QThread):
    """Run the expensive all-player slate scan off the UI thread."""

    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def run(self) -> None:
        try:
            self.finished.emit(scan_slate_edges())
        except Exception as exc:
            self.error.emit(str(exc))


class SlateScannerPage(QWidget):
    """Qt-native wrapper for the confident bets scanner."""

    def __init__(self) -> None:
        super().__init__()
        self.worker: SlateScannerWorker | None = None

        scroll, _, layout = scroll_page()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

        layout.addWidget(eyebrow_label("SLATE SCANNER"))
        layout.addWidget(title_label("Model Edge Board"))

        self.scan_button = QPushButton("Run Today Scan")
        self.scan_button.clicked.connect(self.start_scan)
        layout.addWidget(self.scan_button)

        self.status = QLabel("Ready")
        self.status.setStyleSheet(f"color: {COLORS['text_tertiary']};")
        layout.addWidget(self.status)

        self.table = QTableWidget()
        self.table.setMinimumHeight(660)
        layout.addWidget(self.table)

    def start_scan(self) -> None:
        self.scan_button.setEnabled(False)
        self.status.setText("Scanning today's players. This can take a while.")
        self.worker = SlateScannerWorker()
        self.worker.finished.connect(self.display_results)
        self.worker.error.connect(self.display_error)
        self.worker.start()

    def display_error(self, message: str) -> None:
        self.scan_button.setEnabled(True)
        self.status.setText(f"Error: {message}")

    def display_results(self, bets: list[dict]) -> None:
        self.scan_button.setEnabled(True)
        rows = sort_confident_bets(bets)
        self.status.setText(f"Found {len(rows)} model edges.")
        table_rows = []
        for bet in rows:
            color_key = "success" if bet.get("direction") == "OVER" else "danger"
            table_rows.append(
                [
                    bet.get("player_name", ""),
                    bet.get("team_abbrev", ""),
                    bet.get("opponent_abbrev", ""),
                    bet.get("direction", ""),
                    f"{float(bet.get('season_avg', 0.0)):.1f}",
                    f"{float(bet.get('prediction', 0.0)):.1f}",
                    format_signed(bet.get("diff")),
                    f"{float(bet.get('last_5', 0.0)):.1f}",
                    f"{float(bet.get('proj_minutes', 0.0)):.1f}",
                    color_key,
                ]
            )
        populate_table(
            self.table,
            ("Player", "Team", "Opp", "Side", "Season", "Pred", "Edge", "L5", "Min"),
            table_rows,
            color_key_column=9,
        )
