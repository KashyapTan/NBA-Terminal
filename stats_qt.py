import sys
import os
import threading
import pandas as pd
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QLineEdit, QPushButton, QCheckBox, QRadioButton, QScrollArea, 
    QFrame, QTableWidget, QTableWidgetItem, QHeaderView, 
    QMessageBox, QDialog, QGridLayout, QProgressBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor, QPalette

from helper.formula import get_player_season_stats, get_player_vs_team_stats
from helper.gamelog import get_player_game_log
from nba_api.stats.static import teams
from nba_api.stats.endpoints import boxscoretraditionalv2, boxscoretraditionalv3
from archive.c import clear_charts_folder

# --- COLORS (Modern palette transferred from tkinter version) ---
# We keep the exact same hex codes to maintain the visual style.
COLORS = {
    'bg_primary': '#0f0f0f',        # Deep black background
    'bg_card': '#1a1a1a',           # Card background
    'bg_elevated': '#242424',       # Elevated elements
    'bg_hover': '#2a2a2a',          # Hover state
    'text_primary': '#ffffff',      # Primary text
    'text_secondary': '#8b8b8b',    # Secondary/muted text
    'text_tertiary': '#5c5c5c',     # Tertiary text
    'accent': '#6366f1',            # Modern indigo accent
    'accent_soft': '#4f46e5',       # Softer accent
    'success': '#10b981',           # Green for positive
    'warning': '#f59e0b',           # Amber for warning
    'danger': '#ef4444',            # Red for negative
    'border': '#2a2a2a',            # Subtle border
    'divider': '#1f1f1f',           # Divider lines
}

# --- CUSTOM WIDGETS ---

class StatCard(QFrame):
    """
    In PyQt, custom widgets are often classes inheriting from QFrame or QWidget.
    This replaces the 'create_stat_card' function.
    """
    def __init__(self, title, stats_data):
        super().__init__()
        # Styling using QSS (Qt Style Sheets) - very similar to CSS
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_card']};
                border-radius: 8px;
                border: 1px solid {COLORS['border']};
            }}
            QLabel {{
                border: none;
            }}
        """)
        
        # QVBoxLayout stacks widgets vertically
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(12)
        
        # Title Label
        title_label = QLabel(title.upper())
        title_label.setStyleSheet(f"color: {COLORS['text_tertiary']}; font-weight: bold; font-size: 11px;")
        layout.addWidget(title_label)
        
        # Grid layout for the stats table (Rows x Columns)
        grid = QGridLayout()
        grid.setContentsMargins(0, 5, 0, 5)
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(8)
        
        # Set column 0 (labels) to not stretch, and others to stretch equally
        grid.setColumnStretch(0, 0)
        
        row_labels = ['Stat', 'Avg', 'Std', 'CV%']
        for i, label in enumerate(row_labels):
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {COLORS['text_tertiary']}; font-size: 11px;")
            grid.addWidget(lbl, i, 0) 
            
        stat_order = ['points', 'rebounds', 'assists', 'blocks', 'steals', '3pt']
        stat_names = ['PTS', 'REB', 'AST', 'BLK', 'STL', '3PM']
        
        col_idx = 1
        for stat_key, stat_name in zip(stat_order, stat_names):
            if stat_key in stats_data['averages']:
                grid.setColumnStretch(col_idx, 1)
                avg = stats_data['averages'][stat_key]
                std = stats_data['std_devs'][stat_key]
                cv = 100 * (std / avg) if avg > 0 else 0
                
                # Stat Name Header
                name_lbl = QLabel(stat_name)
                name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                name_lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-weight: bold; font-size: 12px;")
                grid.addWidget(name_lbl, 0, col_idx)
                
                # Average Value
                avg_lbl = QLabel(f"{avg:.1f}")
                avg_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                avg_lbl.setStyleSheet(f"color: {COLORS['text_primary']}; font-weight: bold; font-size: 14px;")
                grid.addWidget(avg_lbl, 1, col_idx)
                
                # Standard Deviation
                std_lbl = QLabel(f"±{std:.1f}")
                std_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                std_lbl.setStyleSheet(f"color: {COLORS['text_tertiary']}; font-size: 11px;")
                grid.addWidget(std_lbl, 2, col_idx)
                
                # Coefficient of Variation (Color coded)
                cv_color = COLORS['success'] if cv < 30 else (COLORS['warning'] if cv < 50 else COLORS['danger'])
                cv_lbl = QLabel(f"{cv:.0f}%")
                cv_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                cv_lbl.setStyleSheet(f"color: {cv_color}; font-size: 11px;")
                grid.addWidget(cv_lbl, 3, col_idx)
                
                col_idx += 1
                
        layout.addLayout(grid)
        
        # Divider Line
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"background-color: {COLORS['divider']}; max-height: 1px; border: none;")
        layout.addWidget(line)
        
        # Games Played Summary at bottom
        games_layout = QHBoxLayout()
        games_lbl = QLabel("Games Played")
        games_lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        val_lbl = QLabel(str(stats_data['games_played']))
        val_lbl.setStyleSheet(f"color: {COLORS['text_primary']}; font-weight: bold; font-size: 12px;")
        games_layout.addWidget(games_lbl)
        games_layout.addStretch() # Pushes the next widget to the right
        games_layout.addWidget(val_lbl)
        layout.addLayout(games_layout)

class RollingStatsCard(QFrame):
    """
    Card for showing Last 5, 10, 15 game trends.
    """
    def __init__(self, title, game_log_df):
        super().__init__()
        self.setStyleSheet(f"background-color: {COLORS['bg_card']}; border-radius: 8px; border: 1px solid {COLORS['border']};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        
        title_label = QLabel(title.upper())
        title_label.setStyleSheet(f"color: {COLORS['text_tertiary']}; font-weight: bold; font-size: 11px; border: none;")
        layout.addWidget(title_label)
        
        grid = QGridLayout()
        grid.setSpacing(10)
        
        stat_order = ['points', 'rebounds', 'assists', 'blocks', 'steals', '3pt']
        stat_names = ['PTS', 'REB', 'AST', 'BLK', 'STL', '3PM']
        windows = [5, 10, 15]
        
        # Header Row
        lbl_games = QLabel("GAMES")
        lbl_games.setStyleSheet(f"color: {COLORS['text_secondary']}; font-weight: bold; border: none;")
        grid.addWidget(lbl_games, 0, 0)
        for i, name in enumerate(stat_names):
            lbl = QLabel(name)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-weight: bold; border: none;")
            grid.addWidget(lbl, 0, i + 1)
            
        current_row = 1
        for n in windows:
            stats = self.calculate_rolling_stats(game_log_df, n)
            
            # Row Label (L5, L10, L15)
            ln_lbl = QLabel(f"L{n}")
            ln_lbl.setStyleSheet(f"color: {COLORS['text_primary']}; font-weight: bold; border: none;")
            grid.addWidget(ln_lbl, current_row, 0)
            
            # Data cells
            for i, stat_key in enumerate(stat_order):
                if stats and stat_key in stats['averages']:
                    val = stats['averages'][stat_key]
                    val_lbl = QLabel(f"{val:.1f}")
                    val_lbl.setStyleSheet(f"color: {COLORS['text_primary']}; font-weight: bold; font-size: 13px; border: none;")
                else:
                    val_lbl = QLabel("-")
                    val_lbl.setStyleSheet(f"color: {COLORS['text_tertiary']}; border: none;")
                val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                grid.addWidget(val_lbl, current_row, i + 1)
            
            current_row += 1
            
            # CV% Row for consistency
            cv_title = QLabel("CV%")
            cv_title.setStyleSheet(f"color: {COLORS['text_tertiary']}; font-size: 11px; border: none;")
            grid.addWidget(cv_title, current_row, 0)
            
            for i, stat_key in enumerate(stat_order):
                if stats and stat_key in stats['averages'] and stat_key in stats['std_devs']:
                    avg = stats['averages'][stat_key]
                    std = stats['std_devs'][stat_key]
                    cv = 100 * (std / avg) if avg > 0 else 0
                    cv_color = COLORS['success'] if cv < 30 else (COLORS['warning'] if cv < 50 else COLORS['danger'])
                    cv_lbl = QLabel(f"{cv:.0f}%")
                    cv_lbl.setStyleSheet(f"color: {cv_color}; font-size: 11px; border: none;")
                else:
                    cv_lbl = QLabel("-")
                    cv_lbl.setStyleSheet(f"color: {COLORS['text_tertiary']}; border: none;")
                cv_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                grid.addWidget(cv_lbl, current_row, i + 1)
            
            current_row += 1
            
        layout.addLayout(grid)
        
        # Info Footer
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"background-color: {COLORS['divider']}; max-height: 1px; border: none;")
        layout.addWidget(line)
        
        info_layout = QHBoxLayout()
        info_lbl = QLabel("Total Games Available")
        info_lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; border: none;")
        total_val = QLabel(str(len(game_log_df) if game_log_df is not None else 0))
        total_val.setStyleSheet(f"color: {COLORS['text_primary']}; font-weight: bold; border: none;")
        info_layout.addWidget(info_lbl)
        info_layout.addStretch()
        info_layout.addWidget(total_val)
        layout.addLayout(info_layout)

    def calculate_rolling_stats(self, game_log_df, n_games):
        if game_log_df is None or game_log_df.empty or len(game_log_df) < n_games:
            return None
        recent_games = game_log_df.head(n_games)
        stats = {'averages': {}, 'std_devs': {}, 'games_played': n_games}
        col_mapping = {'points': 'PTS', 'rebounds': 'REB', 'assists': 'AST', 'blocks': 'BLK', 'steals': 'STL', '3pt': 'FG3M'}
        for stat_key, col_name in col_mapping.items():
            if col_name in recent_games.columns:
                values = pd.to_numeric(recent_games[col_name], errors='coerce')
                stats['averages'][stat_key] = values.mean()
                stats['std_devs'][stat_key] = values.std()
        return stats

class HitRateCard(QFrame):
    """
    Card for Hit Rates for a specific stat (Points, Rebounds, or Assists).
    """
    def __init__(self, title, game_log_df, stat_type='PTS'):
        super().__init__()
        self.setStyleSheet(f"background-color: {COLORS['bg_card']}; border-radius: 8px; border: 1px solid {COLORS['border']};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)
        
        title_lbl = QLabel(title.upper())
        title_lbl.setStyleSheet(f"color: {COLORS['text_tertiary']}; font-weight: bold; font-size: 11px; border: none;")
        layout.addWidget(title_lbl)
        
        grid = QGridLayout()
        grid.setContentsMargins(0, 10, 0, 10)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)
        
        # Define thresholds based on stat type
        if stat_type == 'PTS':
            thresholds = [10, 12, 15, 18, 20, 25, 30]
        else: # REB or AST
            thresholds = [4, 5, 6, 7, 8, 9, 10, 11, 12]
            
        windows = [5, 10, 15]
        
        # Column Headings
        grid.addWidget(QLabel(""), 0, 0)
        for i, t in enumerate(thresholds):
            lbl = QLabel(f"{t}+")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-weight: bold; border: none;")
            grid.addWidget(lbl, 0, i + 1)
            
        # Data Rows
        for row_idx, n in enumerate(windows):
            ln_lbl = QLabel(f"L{n}")
            ln_lbl.setStyleSheet(f"color: {COLORS['text_primary']}; font-weight: bold; border: none;")
            grid.addWidget(ln_lbl, row_idx + 1, 0)
            
            rates = self.calculate_hit_rates(game_log_df, n, thresholds, stat_type)
            for i, t in enumerate(thresholds):
                if rates and t in rates:
                    rate = rates[t]
                    color = COLORS['success'] if rate >= 80 else (COLORS['warning'] if rate >= 50 else COLORS['danger'])
                    lbl = QLabel(f"{rate:.0f}%")
                    lbl.setStyleSheet(f"color: {color}; font-weight: bold; border: none;")
                else:
                    lbl = QLabel("-")
                    lbl.setStyleSheet(f"color: {COLORS['text_tertiary']}; border: none;")
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                grid.addWidget(lbl, row_idx + 1, i + 1)
                
        layout.addLayout(grid)
        
        # Legend
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"background-color: {COLORS['divider']}; max-height: 1px; border: none;")
        layout.addWidget(line)
        
        legend = QHBoxLayout()
        for color, text in [(COLORS['success'], "≥80%"), (COLORS['warning'], "50-79%"), (COLORS['danger'], "<50%")]:
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {color}; border: none;")
            txt = QLabel(text)
            txt.setStyleSheet(f"color: {COLORS['text_tertiary']}; font-size: 10px; border: none;")
            legend.addWidget(dot)
            legend.addWidget(txt)
            legend.addSpacing(10)
        legend.addStretch()
        layout.addLayout(legend)

    def calculate_hit_rates(self, df, n, thresholds, col):
        if df is None or df.empty or len(df) < n: return None
        recent = df.head(n)
        res = {}
        for t in thresholds:
            hits = len(recent[recent[col] >= t])
            res[t] = (hits / n) * 100
        return res

class GameLogTable(QTableWidget):
    """
    A stylized QTableWidget representing the game log display.
    Replaces the ttk.Treeview in the tkinter version.
    """
    def __init__(self, df, title, parent_gui):
        super().__init__()
        self.parent_gui = parent_gui
        self.setup_table(df)
        
    def setup_table(self, df):
        # Column mapping and logic
        calculated_cols = ['PRA', 'PR', 'PA', 'RA']
        visible_columns = ['GAME_DATE', 'MATCHUP', 'WL', 'MIN', 'PTS', 'REB', 'AST', 'STL', 'BLK', 
                   'PRA', 'PR', 'PA', 'RA',
                   'FGM', 'FGA', 'FG_PCT', 'FG3M', 'FG3A', 'FG3_PCT', 'FTM', 'FTA', 'FT_PCT', 'TS_PCT', 'PLUS_MINUS']
        
        cols_to_use = [c for c in visible_columns if c in df.columns or c in calculated_cols]
        self.setColumnCount(len(cols_to_use))
        self.setHorizontalHeaderLabels([c.replace('_PCT', '%').replace('PLUS_MINUS', '+/-') for c in cols_to_use])
        
        # Track Game_IDs for double-click opening (support both Case variants)
        # nba_api can be inconsistent with 'Game_ID' vs 'GAME_ID'
        id_col = next((c for c in df.columns if c.upper() == 'GAME_ID'), None)
        game_id_list = []
        if id_col:
            game_id_list = df[id_col].astype(str).tolist()

        self.setRowCount(len(df))
        for r_idx, (idx, row) in enumerate(df.iterrows()):
            pts = float(row.get('PTS', 0) or 0)
            reb = float(row.get('REB', 0) or 0)
            ast = float(row.get('AST', 0) or 0)
            calc_vals = {'PRA': pts+reb+ast, 'PR': pts+reb, 'PA': pts+ast, 'RA': reb+ast}
            
            # Row Background based on Win/Loss
            wl = str(row.get('WL', ''))
            row_color = QColor('#0d291a') if wl == 'W' else (QColor('#291414') if wl == 'L' else QColor(COLORS['bg_primary']))
            
            for c_idx, col_name in enumerate(cols_to_use):
                if col_name in calc_vals:
                    val = str(int(calc_vals[col_name]))
                else:
                    raw_val = row.get(col_name)
                    if col_name in ['FG_PCT', 'FG3_PCT', 'FT_PCT', 'TS_PCT']:
                        try: val = f"{float(raw_val)*100:.1f}%" if raw_val else "0.0%"
                        except: val = str(raw_val)
                    elif col_name == 'PLUS_MINUS':
                        try:
                            pm = float(raw_val) if raw_val else 0
                            val = f"{pm:+.0f}" if pm != 0 else "0"
                        except: val = str(raw_val)
                    else:
                        val = str(raw_val) if raw_val is not None else ""
                
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setBackground(row_color)
                item.setForeground(QColor(COLORS['text_primary']))
                self.setItem(r_idx, c_idx, item)
            
            # Store the Game_ID in the hidden UserRole for double-click access
            if game_id_list and r_idx < len(game_id_list):
                self.item(r_idx, 0).setData(Qt.ItemDataRole.UserRole, game_id_list[r_idx])

        # Style the Table headers and grid
        self.verticalHeader().setVisible(False)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        
        # Optimized Column Resizing:
        # We use ResizeToContents for text columns to ensure they are never cut off.
        # We use Stretch for all numeric/stat columns so they fill the space evenly.
        header = self.horizontalHeader()
        for i in range(self.columnCount()):
            col_name = cols_to_use[i]
            if col_name in ['GAME_DATE', 'MATCHUP']:
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
            else:
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
        
        header.setStyleSheet(f"QHeaderView::section {{ background-color: {COLORS['bg_elevated']}; color: {COLORS['text_secondary']}; border: none; padding: 4px; font-weight: bold; }}")
        self.setStyleSheet(f"QTableWidget {{ background-color: {COLORS['bg_primary']}; color: {COLORS['text_primary']}; gridline-color: {COLORS['divider']}; border: none; }}")
        
        self.itemDoubleClicked.connect(self.on_double_click)

    def on_double_click(self, item):
        # Retrieve the hidden Game_ID
        game_id = self.item(item.row(), 0).data(Qt.ItemDataRole.UserRole)
        if game_id:
            self.parent_gui.show_box_score(game_id)

# --- THREADING WORKER ---

class FetchWorker(QThread):
    """
    In Qt, we perform blocking operations (like API calls) in a separate thread.
    We communicate with the GUI via Signals.
    """
    status_update = pyqtSignal(str)
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, player, team, seasons, season_type, parent_abbrev_func):
        super().__init__()
        self.player = player
        self.team = team
        self.seasons = seasons
        self.season_type = season_type
        self.find_team_abbrev = parent_abbrev_func

    def run(self):
        try:
            all_data = []
            for season in reversed(self.seasons):
                season_data = {'season': season, 'season_type': self.season_type}
                
                self.status_update.emit(f"Fetching {self.player} stats for {season} ({self.season_type})...")
                try: season_data['season_stats'] = get_player_season_stats(self.player, season, season_type=self.season_type)
                except Exception as e: season_data['season_error'] = str(e)
                
                self.status_update.emit(f"Fetching vs {self.team} for {season} ({self.season_type})...")
                try: season_data['vs_team_stats'] = get_player_vs_team_stats(self.player, season, self.team, season_type=self.season_type)
                except Exception as e: season_data['vs_team_error'] = str(e)
                
                self.status_update.emit(f"Fetching game log for {season} ({self.season_type})...")
                try:
                    df = get_player_game_log(self.player, season, season_type=self.season_type)
                    season_data['game_log'] = df
                    # Use provided helper function
                    team_abbrev = self.find_team_abbrev(self.team)
                    if team_abbrev:
                        vs_df = df[df['MATCHUP'].str.contains(team_abbrev, case=False, na=False)]
                        season_data['vs_team_log'] = vs_df if not vs_df.empty else None
                    else:
                        season_data['team_not_found'] = True
                except Exception as e: season_data['game_log_error'] = str(e)
                
                all_data.append(season_data)
                
            self.finished.emit(all_data)
        except Exception as e:
            self.error.emit(str(e))

# --- MAIN WINDOW ---

class NBAStatsPyQt(QMainWindow):
    """
    The main application window using PyQt6.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NBA Player Statistics Viewer (PyQt6)")
        self.resize(1600, 900)
        
        # Set Global Dark Theme
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(COLORS['bg_primary']))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(COLORS['text_primary']))
        self.setPalette(palette)
        
        self.setup_ui()
        
    def setup_ui(self):
        # 1. Main Central Widget & Scroll Area
        # PyQt layout: QMainWindow -> CentralWidget -> MainLayout -> ScrollArea -> ContentWidget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0,0,0,0)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background-color: {COLORS['bg_primary']}; }}")
        
        self.content_container = QWidget()
        self.content_container.setStyleSheet(f"background-color: {COLORS['bg_primary']};")
        self.content_layout = QVBoxLayout(self.content_container)
        self.content_layout.setContentsMargins(32, 32, 32, 32)
        self.content_layout.setSpacing(24)
        
        scroll.setWidget(self.content_container)
        main_layout.addWidget(scroll)
        
        # 2. Hero Section
        hero = QVBoxLayout()
        sub_title = QLabel("NBA STATISTICS")
        sub_title.setStyleSheet(f"color: {COLORS['text_tertiary']}; font-weight: bold; font-size: 11px;")
        main_title = QLabel("Player Analytics")
        main_title.setStyleSheet(f"color: {COLORS['text_primary']}; font-weight: bold; font-size: 32px;")
        hero.addWidget(sub_title)
        hero.addWidget(main_title)
        self.content_layout.addLayout(hero)
        
        # 3. Input Section (Card)
        input_card = QFrame()
        input_card.setStyleSheet(f"background-color: {COLORS['bg_card']}; border-radius: 12px; border: 1px solid {COLORS['border']};")
        input_vbox = QVBoxLayout(input_card)
        
        fields_layout = QHBoxLayout()
        # Player Input
        p_vbox = QVBoxLayout()
        p_vbox.addWidget(QLabel("PLAYER NAME", styleSheet=f"color: {COLORS['text_tertiary']}; font-size: 10px; font-weight: bold; border: none;"))
        self.player_input = QLineEdit("James Harden")
        self.style_input(self.player_input)
        p_vbox.addWidget(self.player_input)
        fields_layout.addLayout(p_vbox)
        
        fields_layout.addSpacing(20)
        
        # Team Input
        t_vbox = QVBoxLayout()
        t_vbox.addWidget(QLabel("OPPONENT TEAM", styleSheet=f"color: {COLORS['text_tertiary']}; font-size: 10px; font-weight: bold; border: none;"))
        self.team_input = QLineEdit("76ers")
        self.style_input(self.team_input)
        t_vbox.addWidget(self.team_input)
        fields_layout.addLayout(t_vbox)
        
        input_vbox.addLayout(fields_layout)
        self.content_layout.addWidget(input_card)
        
        # 4. Season Selection Section (Card)
        season_card = QFrame()
        season_card.setStyleSheet(f"background-color: {COLORS['bg_card']}; border-radius: 12px; border: 1px solid {COLORS['border']};")
        season_vbox = QVBoxLayout(season_card)
        season_vbox.addWidget(QLabel("SELECT SEASONS", styleSheet=f"color: {COLORS['text_tertiary']}; font-size: 10px; font-weight: bold; border: none;"))
        
        checks_hbox = QHBoxLayout()
        self.season_checks = {}
        seasons_list = ['2020-21', '2021-22', '2022-23', '2023-24', '2024-25', '2025-26']
        for s in seasons_list:
            cb = QCheckBox(s)
            cb.setStyleSheet(f"color: {COLORS['text_primary']}; border: none;")
            cb.setChecked(s in ['2024-25', '2025-26'])
            self.season_checks[s] = cb
            checks_hbox.addWidget(cb)
        checks_hbox.addStretch()
        season_vbox.addLayout(checks_hbox)
        
        btns_hbox = QHBoxLayout()
        sel_all = QPushButton("Select All")
        desel_all = QPushButton("Deselect All")
        for b in [sel_all, desel_all]:
            b.setStyleSheet(f"background-color: {COLORS['bg_elevated']}; color: {COLORS['text_secondary']}; border: none; padding: 6px 12px; border-radius: 4px;")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
        sel_all.clicked.connect(lambda: [c.setChecked(True) for c in self.season_checks.values()])
        desel_all.clicked.connect(lambda: [c.setChecked(False) for c in self.season_checks.values()])
        btns_hbox.addWidget(sel_all)
        btns_hbox.addWidget(desel_all)
        btns_hbox.addStretch()
        season_vbox.addLayout(btns_hbox)

        season_type_row = QHBoxLayout()
        season_type_label = QLabel("DATASET TYPE")
        season_type_label.setStyleSheet(f"color: {COLORS['text_tertiary']}; font-size: 10px; font-weight: bold; border: none;")
        season_type_row.addWidget(season_type_label)
        season_type_row.addSpacing(10)

        self.regular_season_radio = QRadioButton("Regular Season")
        self.playoffs_radio = QRadioButton("Playoffs")
        self.regular_season_radio.setChecked(True)
        for radio in [self.regular_season_radio, self.playoffs_radio]:
            radio.setStyleSheet(
                f"color: {COLORS['text_primary']}; border: none;"
                f"font-size: 12px; spacing: 6px;"
            )
            season_type_row.addWidget(radio)
        season_type_row.addStretch()
        season_vbox.addLayout(season_type_row)
        self.content_layout.addWidget(season_card)
        
        # 5. Buttons Row
        btn_layout = QHBoxLayout()
        self.fetch_btn = QPushButton("Fetch Statistics")
        self.fetch_btn.setFixedSize(200, 48)
        self.fetch_btn.setStyleSheet(f"background-color: {COLORS['accent']}; color: {COLORS['text_primary']}; font-weight: bold; font-size: 14px; border-radius: 6px; border: none;")
        self.fetch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fetch_btn.clicked.connect(self.start_fetch)
        
        clear_btn = QPushButton("Clear Results")
        clear_btn.setFixedSize(160, 48)
        clear_btn.setStyleSheet(f"background-color: {COLORS['bg_elevated']}; color: {COLORS['text_secondary']}; font-size: 13px; border-radius: 6px; border: none;")
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.clicked.connect(self.clear_results)
        
        btn_layout.addWidget(self.fetch_btn)
        btn_layout.addWidget(clear_btn)
        btn_layout.addStretch()
        self.content_layout.addLayout(btn_layout)
        
        # 6. Status Label
        self.status_lbl = QLabel("Ready")
        self.status_lbl.setStyleSheet(f"color: {COLORS['text_tertiary']}; font-size: 12px;")
        self.content_layout.addWidget(self.status_lbl)
        
        # 7. Dynamic Results Area
        # We will add widgets here when statistics are loaded
        self.results_area = QVBoxLayout()
        self.results_area.setSpacing(24)
        self.content_layout.addLayout(self.results_area)
        
        # Add stretch to keep everything pushed to the top
        self.content_layout.addStretch()

    def style_input(self, widget):
        widget.setStyleSheet(f"""
            QLineEdit {{
                background-color: {COLORS['bg_elevated']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                padding: 10px;
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border: 1px solid {COLORS['accent']};
            }}
        """)

    def find_team_abbreviation(self, team_input):
        # Precise logic from the formula.py helper
        team_list = None
        if len(team_input) <= 3:
            obj = teams.find_team_by_abbreviation(team_input.upper())
            if obj: team_list = [obj]
        if not team_list: team_list = teams.find_teams_by_full_name(team_input)
        if not team_list:
            team_list = teams.find_teams_by_nickname(team_input)
            if team_list and len(team_list) > 1:
                exact = [t for t in team_list if t['nickname'].lower() == team_input.lower()]
                if exact: team_list = exact
        if not team_list or len(team_list) > 1: return None
        return team_list[0]['abbreviation']

    def start_fetch(self):
        # Gather inputs
        player = self.player_input.text().strip()
        team = self.team_input.text().strip()
        seasons = [s for s, cb in self.season_checks.items() if cb.isChecked()]
        season_type = "Playoffs" if self.playoffs_radio.isChecked() else "Regular Season"
        
        if not player or not team or not seasons:
            QMessageBox.critical(self, "Input Error", "Please provide a Player, Opponent Team, and at least one Season.")
            return
            
        # Disable UI during fetch
        self.fetch_btn.setEnabled(False)
        self.fetch_btn.setText("Fetching...")
        self.clear_results()
        
        # Setup Background Worker
        self.worker = FetchWorker(player, team, seasons, season_type, self.find_team_abbreviation)
        self.worker.status_update.connect(lambda msg: self.status_lbl.setText(msg))
        self.worker.finished.connect(self.on_fetch_finished)
        self.worker.error.connect(lambda e: QMessageBox.critical(self, "API Error", e))
        self.worker.start()

    def on_fetch_finished(self, all_data):
        self.fetch_btn.setEnabled(True)
        self.fetch_btn.setText("Fetch Statistics")
        selected_type = all_data[0].get('season_type', 'Regular Season') if all_data else 'Regular Season'
        self.status_lbl.setText(f"Loaded {len(all_data)} season(s) for {selected_type}.")
        
        player = self.player_input.text().strip()
        team = self.team_input.text().strip()
        
        for data in all_data:
            season = data['season']
            season_type = data.get('season_type', 'Regular Season')
            
            # --- Season Header ---
            header_lbl = QLabel(f"NBA Terminal ● {season} ● {season_type}")
            header_lbl.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 24px; font-weight: bold; margin-top: 10px;")
            self.results_area.addWidget(header_lbl)
            
            # --- Stats Cards (Side by Side) ---
            stats_hbox = QHBoxLayout()
            stats_hbox.setSpacing(24)
            if data.get('season_stats'):
                stats_hbox.addWidget(StatCard(f"{player} Overall - {season} ({season_type})", data['season_stats']), 1)
            if data.get('vs_team_stats'):
                stats_hbox.addWidget(StatCard(f"{player} vs {team} - {season} ({season_type})", data['vs_team_stats']), 1)
            self.results_area.addLayout(stats_hbox)
            
            # --- Advanced Trends (L5/L10/L15 & Hit Rates) ---
            if data.get('game_log') is not None:
                self.results_area.addWidget(RollingStatsCard("Rolling Trends", data['game_log']))
                
                # Add extra breathing room before Hit Rates
                self.results_area.addSpacing(16)
                
                hits_hbox = QHBoxLayout()
                hits_hbox.setSpacing(24)
                hits_hbox.addWidget(HitRateCard("Points Rates", data['game_log'], 'PTS'), 1)
                hits_hbox.addWidget(HitRateCard("Rebounds Rates", data['game_log'], 'REB'), 1)
                hits_hbox.addWidget(HitRateCard("Assists Rates", data['game_log'], 'AST'), 1)
                self.results_area.addLayout(hits_hbox)
                
                # Add breathing room after Hit Rates
                self.results_area.addSpacing(16)
            
            # --- Game Log Table ---
            if data.get('game_log') is not None:
                log_title = QLabel(f"{player} - {season} ({season_type}) Game Log")
                log_title.setStyleSheet("color: white; font-weight: bold; font-size: 14px; margin-top: 10px;")
                self.results_area.addWidget(log_title)
                
                table = GameLogTable(data['game_log'], "", self)
                table.setMinimumHeight(400)
                self.results_area.addWidget(table)
            
            # --- vs Opponent Log Table ---
            if data.get('vs_team_log') is not None:
                vs_title = QLabel(f"{player} vs {team} - {season} ({season_type}) Game Log")
                vs_title.setStyleSheet("color: white; font-weight: bold; font-size: 14px; margin-top: 10px;")
                self.results_area.addWidget(vs_title)
                
                vs_table = GameLogTable(data['vs_team_log'], "", self)
                vs_table.setMinimumHeight(200)
                self.results_area.addWidget(vs_table)
                
            # Separator Line
            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.HLine)
            sep.setStyleSheet(f"background-color: {COLORS['divider']}; max-height: 1px; margin: 20px 0;")
            self.results_area.addWidget(sep)

    def clear_results(self):
        # Recursively delete widgets in the results layout
        self.clear_layout(self.results_area)
        self.status_lbl.setText("Results cleared.")

    def clear_layout(self, layout):
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                else:
                    self.clear_layout(item.layout())

    def show_box_score(self, game_id):
        # Open the custom Box Score Dialog
        dialog = BoxScoreDialog(game_id, self)
        dialog.exec()

class BoxScoreDialog(QDialog):
    """
    A secondary window (Dialog) to display full game box scores.
    """
    def __init__(self, game_id, parent):
        super().__init__(parent)
        self.setWindowTitle(f"Box Score - {game_id}")
        self.setMinimumSize(1200, 850)
        self.setStyleSheet(f"background-color: {COLORS['bg_primary']}; color: white;")
        
        self.main_layout = QVBoxLayout(self)
        self.status = QLabel("Loading Box Score Details...")
        self.main_layout.addWidget(self.status)
        
        # Ensure 10-digit ID
        self.game_id = str(game_id).strip().split('.')[0].zfill(10)
        
        # Start Data Loading
        # For simplicity in this demo, we run UI-blocking, but for production, use a QThread.
        self.load_box_score()

    def load_box_score(self):
        try:
            # Try V2 API First
            print(f"DEBUG: Fetching Box Score V2 for {self.game_id}")
            box = boxscoretraditionalv2.BoxScoreTraditionalV2(game_id=self.game_id)
            player_stats = box.player_stats.get_data_frame() if box.player_stats else pd.DataFrame()
            team_stats = box.team_stats.get_data_frame() if box.team_stats else pd.DataFrame()
            
            # Fallback to V3 if V2 is empty (common for recent games)
            if player_stats.empty:
                print(f"DEBUG: V2 empty, trying V3...")
                box_v3 = boxscoretraditionalv3.BoxScoreTraditionalV3(game_id=self.game_id)
                if box_v3.player_stats:
                    v3_player = box_v3.player_stats.get_data_frame()
                    if not v3_player.empty:
                        # Map V3 columns to V2 format to keep logic consistent
                        v3_player['PLAYER_NAME'] = v3_player['firstName'] + " " + v3_player['familyName']
                        column_map = {
                            'teamTricode': 'TEAM_ABBREVIATION', 'minutes': 'MIN', 'points': 'PTS',
                            'reboundsTotal': 'REB', 'assists': 'AST', 'steals': 'STL', 'blocks': 'BLK',
                            'turnovers': 'TO', 'foulsPersonal': 'PF', 'fieldGoalsMade': 'FGM',
                            'fieldGoalsAttempted': 'FGA', 'fieldGoalsPercentage': 'FG_PCT',
                            'threePointersMade': 'FG3M', 'threePointersAttempted': 'FG3A',
                            'threePointersPercentage': 'FG3_PCT', 'freeThrowsMade': 'FTM',
                            'freeThrowsAttempted': 'FTA', 'freeThrowsPercentage': 'FT_PCT',
                            'plusMinusPoints': 'PLUS_MINUS'
                        }
                        player_stats = v3_player.rename(columns=column_map)
                
                if box_v3.team_stats:
                    v3_team = box_v3.team_stats.get_data_frame()
                    if not v3_team.empty:
                        team_stats = v3_team.rename(columns={'teamTricode': 'TEAM_ABBREVIATION', 'points': 'PTS'})

            if player_stats.empty:
                self.status.setText(f"No box score data found for Game ID {self.game_id}.")
                return

            self.status.setVisible(False)
            
            # 1. Matchup Header
            if not team_stats.empty and len(team_stats) >= 2:
                t1, t2 = team_stats.iloc[0], team_stats.iloc[1]
                header_text = f"{t1['TEAM_ABBREVIATION']} {t1['PTS']} - {t2['PTS']} {t2['TEAM_ABBREVIATION']}"
                header = QLabel(header_text)
                header.setStyleSheet("font-size: 28px; font-weight: bold; padding: 20px; color: white;")
                header.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.main_layout.addWidget(header)
            
            # 2. Player Stats Tables (One per team)
            teams_list = player_stats['TEAM_ABBREVIATION'].unique()
            for team_abbr in teams_list:
                subset = player_stats[player_stats['TEAM_ABBREVIATION'] == team_abbr].copy()
                
                # Sort by PRA then Minutes (Matching original logic)
                for col in ['PTS', 'REB', 'AST']:
                    if col in subset.columns:
                        subset[col] = pd.to_numeric(subset[col], errors='coerce').fillna(0)
                subset['PRA'] = subset.get('PTS', 0) + subset.get('REB', 0) + subset.get('AST', 0)
                
                # Helper to parse "MM:SS" style minutes
                def parse_min(x):
                    try:
                        if pd.isna(x) or not x: return 0
                        if isinstance(x, str) and ':' in x:
                            m, s = x.split(':')
                            return float(m) + float(s)/60
                        return float(x)
                    except: return 0
                subset['MIN_SORT'] = subset['MIN'].apply(parse_min) if 'MIN' in subset.columns else 0
                subset = subset.sort_values(by=['PRA', 'MIN_SORT'], ascending=[False, False])

                team_lbl = QLabel(f"Team: {team_abbr}")
                team_lbl.setStyleSheet("font-size: 18px; font-weight: bold; margin-top: 15px; color: #8b8b8b;")
                self.main_layout.addWidget(team_lbl)
                
                cols = ['PLAYER_NAME', 'MIN', 'PTS', 'REB', 'AST', 'STL', 'BLK', 'TO', 'PF', 'FG_PCT', 'FG3_PCT', 'FT_PCT', 'PLUS_MINUS']
                # Filter cols that actually exist in the dataframe
                final_cols = [c for c in cols if c in subset.columns]
                
                table = QTableWidget(len(subset), len(final_cols))
                table.setHorizontalHeaderLabels([c.replace('_PCT', '%').replace('PLUS_MINUS', '+/-') for c in final_cols])
                table.setStyleSheet(f"QTableWidget {{ background-color: {COLORS['bg_card']}; border: none; gridline-color: #1f1f1f; }}")
                
                for r_idx, (_, row) in enumerate(subset.iterrows()):
                    for c_idx, col in enumerate(final_cols):
                        val = row.get(col, "")
                        if '_PCT' in col:
                            try: val = f"{float(val)*100:.1f}%" if val else ""
                            except: pass
                        item = QTableWidgetItem(str(val))
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                        item.setForeground(QColor("white"))
                        table.setItem(r_idx, c_idx, item)
                
                # Optimized Column Resizing:
                # Use ResizeToContents for identity columns, Stretch for numeric stats.
                header = table.horizontalHeader()
                for i in range(len(final_cols)):
                    col_name = final_cols[i]
                    if col_name in ['PLAYER_NAME', 'TEAM_ABBREVIATION', 'PLAYER_POSITION']:
                        header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
                    else:
                        header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
                
                table.verticalHeader().setVisible(False)
                table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
                table.setMinimumHeight(300)
                self.main_layout.addWidget(table)
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.status.setText(f"Critical error loading box score: {str(e)}")

# --- APP STARTUP ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Modern font for the whole application
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    window = NBAStatsPyQt()
    window.show()
    sys.exit(app.exec())
