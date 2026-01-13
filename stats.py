import tkinter as tk
from tkinter import ttk, messagebox
from helper.formula import get_player_season_stats, get_player_vs_team_stats
from helper.gamelog import get_player_game_log
import threading
from PIL import Image, ImageTk
import os
import pandas as pd
from nba_api.stats.static import teams
from nba_api.stats.endpoints import boxscoretraditionalv2, boxscoretraditionalv3
from c import clear_charts_folder

class NBAStatsGUI:
    # Modern color palette matching p.py
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
    
    def __init__(self, root):
        self.root = root
        self.root.title("NBA Player Statistics Viewer")
        self.root.geometry("1575x900")
        self.root.configure(bg=self.COLORS['bg_primary'])
        
        # Store image references to prevent garbage collection
        self.chart_images = []
        
        # Modern style configuration
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TFrame', background=self.COLORS['bg_primary'])
        style.configure('TLabel', background=self.COLORS['bg_primary'], foreground=self.COLORS['text_primary'], font=('Segoe UI', 10))
        style.configure('Title.TLabel', font=('Segoe UI', 20, 'bold'), foreground=self.COLORS['text_primary'])
        style.configure('Subtitle.TLabel', font=('Segoe UI', 12, 'bold'), foreground=self.COLORS['text_primary'])
        style.configure('Stat.TLabel', font=('Segoe UI', 11), foreground=self.COLORS['text_secondary'])
        style.configure('TButton', font=('Segoe UI', 10, 'bold'), padding=8)
        style.configure('TEntry', fieldbackground=self.COLORS['bg_card'], foreground=self.COLORS['text_primary'])
        style.configure('TCheckbutton', background=self.COLORS['bg_primary'], foreground=self.COLORS['text_primary'])
        style.configure('TScrollbar', background=self.COLORS['bg_card'], troughcolor=self.COLORS['bg_primary'],
                        bordercolor=self.COLORS['bg_primary'], arrowcolor=self.COLORS['text_secondary'])
        
        # Setup the GUI
        self.setup_gui()
    
    def find_team_abbreviation(self, team_input):
        """
        Find team abbreviation using the same logic as formula.py and percentile.py.
        Tries abbreviation, full name, then nickname.
        
        Returns:
        --------
        str or None: Team abbreviation if found, None otherwise
        """
        team_list = None
        
        # Try by abbreviation first (most specific)
        if len(team_input) <= 3:
            team_obj = teams.find_team_by_abbreviation(team_input.upper())
            if team_obj:
                team_list = [team_obj]
        
        # Try by full name before nickname (more specific)
        if not team_list:
            team_list = teams.find_teams_by_full_name(team_input)
        
        # Try by nickname last (can match multiple teams)
        if not team_list:
            team_list = teams.find_teams_by_nickname(team_input)
            # If nickname search returns multiple results, filter by checking if the nickname matches exactly
            if team_list and len(team_list) > 1:
                exact_matches = [t for t in team_list if t['nickname'].lower() == team_input.lower()]
                if exact_matches:
                    team_list = exact_matches
        
        if not team_list:
            return None
        
        if len(team_list) > 1:
            # Return None to indicate ambiguity
            return None
        
        return team_list[0]['abbreviation']
    
    def setup_gui(self):
        """Setup the GUI components"""
        # Main container with scrollbar
        main_canvas = tk.Canvas(self.root, bg=self.COLORS['bg_primary'], highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=main_canvas.yview)
        self.scrollable_frame = ttk.Frame(main_canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all"))
        )
        
        main_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        main_canvas.configure(yscrollcommand=scrollbar.set)
        
        main_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Bind mouse wheel
        main_canvas.bind_all("<MouseWheel>", lambda e: main_canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        
        main_frame = ttk.Frame(self.scrollable_frame, padding="32")
        main_frame.grid(row=0, column=0, sticky="nsew")
        
        # Hero Section - Title
        hero_frame = tk.Frame(main_frame, bg=self.COLORS['bg_primary'])
        hero_frame.grid(row=0, column=0, columnspan=6, pady=(0, 32), sticky="ew")
        
        tk.Label(hero_frame, text="NBA STATISTICS", bg=self.COLORS['bg_primary'], 
                fg=self.COLORS['text_tertiary'], font=('Segoe UI', 10, 'bold')).pack(anchor='w')
        tk.Label(hero_frame, text="Player Analytics", bg=self.COLORS['bg_primary'], 
                fg=self.COLORS['text_primary'], font=('Segoe UI', 28, 'bold')).pack(anchor='w', pady=(4, 0))
        
        # Input section - Modern card style
        input_card = tk.Frame(main_frame, bg=self.COLORS['bg_card'])
        input_card.grid(row=1, column=0, columnspan=6, pady=(0, 16), sticky="ew")
        
        input_inner = tk.Frame(input_card, bg=self.COLORS['bg_card'])
        input_inner.pack(fill="x", padx=24, pady=20)
        
        # Input fields row
        input_row = tk.Frame(input_inner, bg=self.COLORS['bg_card'])
        input_row.pack(fill="x")
        
        # Player Name
        player_frame = tk.Frame(input_row, bg=self.COLORS['bg_card'])
        player_frame.pack(side='left', fill='x', expand=True, padx=(0, 16))
        tk.Label(player_frame, text="PLAYER NAME", bg=self.COLORS['bg_card'], 
                fg=self.COLORS['text_tertiary'], font=('Segoe UI', 9)).pack(anchor='w')
        self.player_entry = tk.Entry(player_frame, width=30, font=('Segoe UI', 11),
                                     bg=self.COLORS['bg_elevated'], fg=self.COLORS['text_primary'],
                                     insertbackground=self.COLORS['text_primary'], relief=tk.FLAT,
                                     highlightthickness=1, highlightbackground=self.COLORS['border'],
                                     highlightcolor=self.COLORS['accent'])
        self.player_entry.pack(fill='x', pady=(6, 0), ipady=8)
        self.player_entry.insert(0, "James Harden")
        
        # Team Name
        team_frame = tk.Frame(input_row, bg=self.COLORS['bg_card'])
        team_frame.pack(side='left', fill='x', expand=True)
        tk.Label(team_frame, text="OPPONENT TEAM", bg=self.COLORS['bg_card'], 
                fg=self.COLORS['text_tertiary'], font=('Segoe UI', 9)).pack(anchor='w')
        self.team_entry = tk.Entry(team_frame, width=30, font=('Segoe UI', 11),
                                   bg=self.COLORS['bg_elevated'], fg=self.COLORS['text_primary'],
                                   insertbackground=self.COLORS['text_primary'], relief=tk.FLAT,
                                   highlightthickness=1, highlightbackground=self.COLORS['border'],
                                   highlightcolor=self.COLORS['accent'])
        self.team_entry.pack(fill='x', pady=(6, 0), ipady=8)
        self.team_entry.insert(0, "76ers")
        
        # Season selection - Modern card style
        season_card = tk.Frame(main_frame, bg=self.COLORS['bg_card'])
        season_card.grid(row=2, column=0, columnspan=6, pady=(0, 16), sticky="ew")
        
        season_inner = tk.Frame(season_card, bg=self.COLORS['bg_card'])
        season_inner.pack(fill="x", padx=24, pady=20)
        
        tk.Label(season_inner, text="SELECT SEASONS", bg=self.COLORS['bg_card'], 
                fg=self.COLORS['text_tertiary'], font=('Segoe UI', 9)).pack(anchor='w')
        
        # Season checkboxes row
        checkbox_frame = tk.Frame(season_inner, bg=self.COLORS['bg_card'])
        checkbox_frame.pack(fill="x", pady=(12, 0))
        
        # Create checkbuttons for seasons 2020-21 through 2025-26
        self.season_vars = {}
        seasons = ['2020-21', '2021-22', '2022-23', '2023-24', '2024-25', '2025-26']
        
        for i, season in enumerate(seasons):
            var = tk.BooleanVar(value=(season in ['2024-25', '2025-26']))  # Default last 2 seasons
            self.season_vars[season] = var
            cb = tk.Checkbutton(checkbox_frame, text=season, variable=var,
                               bg=self.COLORS['bg_card'], fg=self.COLORS['text_primary'],
                               selectcolor=self.COLORS['bg_elevated'], activebackground=self.COLORS['bg_card'],
                               activeforeground=self.COLORS['text_primary'], font=('Segoe UI', 10),
                               highlightthickness=0, bd=0, cursor='hand2')
            cb.pack(side='left', padx=(0, 20))
        
        # Select/Deselect all buttons
        select_frame = tk.Frame(season_inner, bg=self.COLORS['bg_card'])
        select_frame.pack(fill="x", pady=(12, 0))
        
        tk.Button(select_frame, text="Select All", command=self.select_all_seasons,
                 bg=self.COLORS['bg_elevated'], fg=self.COLORS['text_secondary'], font=('Segoe UI', 9), 
                 padx=16, pady=6, relief=tk.FLAT, cursor='hand2', bd=0,
                 activebackground=self.COLORS['bg_hover'], activeforeground=self.COLORS['text_primary']).pack(side='left', padx=(0, 8))
        tk.Button(select_frame, text="Deselect All", command=self.deselect_all_seasons,
                 bg=self.COLORS['bg_elevated'], fg=self.COLORS['text_secondary'], font=('Segoe UI', 9), 
                 padx=16, pady=6, relief=tk.FLAT, cursor='hand2', bd=0,
                 activebackground=self.COLORS['bg_hover'], activeforeground=self.COLORS['text_primary']).pack(side='left')
        
        # Action Buttons - Modern style
        button_frame = tk.Frame(main_frame, bg=self.COLORS['bg_primary'])
        button_frame.grid(row=3, column=0, columnspan=6, pady=(0, 24))
        
        self.fetch_btn = tk.Button(button_frame, text="Fetch Statistics", command=self.fetch_stats,
                                   bg=self.COLORS['accent'], fg=self.COLORS['text_primary'], 
                                   font=('Segoe UI', 11, 'bold'),
                                   padx=32, pady=12, relief=tk.FLAT, cursor='hand2', bd=0,
                                   activebackground=self.COLORS['accent_soft'], 
                                   activeforeground=self.COLORS['text_primary'])
        self.fetch_btn.pack(side='left', padx=(0, 12))
        
        clear_btn = tk.Button(button_frame, text="Clear Results", command=self.clear_results,
                             bg=self.COLORS['bg_elevated'], fg=self.COLORS['text_secondary'], 
                             font=('Segoe UI', 11),
                             padx=24, pady=12, relief=tk.FLAT, cursor='hand2', bd=0,
                             activebackground=self.COLORS['bg_hover'], 
                             activeforeground=self.COLORS['text_primary'])
        clear_btn.pack(side='left')
        
        # Status bar - Modern minimal
        status_frame = tk.Frame(main_frame, bg=self.COLORS['bg_primary'])
        status_frame.grid(row=4, column=0, columnspan=6, pady=(0, 16), sticky=tk.W)
        self.status_label = tk.Label(status_frame, text="Ready", bg=self.COLORS['bg_primary'],
                                     fg=self.COLORS['text_tertiary'], font=('Segoe UI', 10))
        self.status_label.pack(anchor='w')
        
        # Results container - Modern style
        self.results_frame = tk.Frame(main_frame, bg=self.COLORS['bg_primary'])
        self.results_frame.grid(row=5, column=0, columnspan=6, sticky="nsew")
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.scrollable_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.columnconfigure(2, weight=1)
        main_frame.columnconfigure(3, weight=1)
        main_frame.columnconfigure(4, weight=1)
        main_frame.columnconfigure(5, weight=1)
        
    def select_all_seasons(self):
        for var in self.season_vars.values():
            var.set(True)
    
    def deselect_all_seasons(self):
        for var in self.season_vars.values():
            var.set(False)
        
    def update_status(self, message):
        self.status_label.config(text=message)
        self.root.update_idletasks()
        
    def clear_results(self):
        for widget in self.results_frame.winfo_children():
            widget.destroy()
        self.chart_images.clear()
        self.update_status("Results cleared")
    
    def create_stat_card(self, parent, title, stats_data, row, col, colspan=2):
        """Create a modern stat card with organized layout"""
        card = tk.Frame(parent, bg=self.COLORS['bg_card'])
        card.grid(row=row, column=col, columnspan=colspan, padx=8, pady=8, sticky="nsew")
        
        inner = tk.Frame(card, bg=self.COLORS['bg_card'])
        inner.pack(fill="both", expand=True, padx=24, pady=20)
        
        # Title - Modern minimal
        tk.Label(inner, text=title.upper(), bg=self.COLORS['bg_card'], fg=self.COLORS['text_tertiary'],
                font=('Segoe UI', 9, 'bold')).pack(anchor='w')
        
        # Stats table
        table_frame = tk.Frame(inner, bg=self.COLORS['bg_card'])
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(16, 0))
        
        # Row headers (vertical)
        row_labels = ['Stat', 'Avg', 'Std', 'CV%']
        for i, label in enumerate(row_labels):
            tk.Label(table_frame, text=label, bg=self.COLORS['bg_card'], fg=self.COLORS['text_tertiary'],
                    font=('Segoe UI', 9), width=6).grid(row=i, column=0, sticky="w", pady=4)
        
        # Data columns
        stat_order = ['points', 'rebounds', 'assists', 'blocks', 'steals', '3pt']
        stat_names = ['PTS', 'REB', 'AST', 'BLK', 'STL', '3PM']
        
        col_num = 1
        for stat_key, stat_name in zip(stat_order, stat_names):
            if stat_key in stats_data['averages']:
                avg = stats_data['averages'][stat_key]
                std = stats_data['std_devs'][stat_key]
                cv = 100 * (std / avg) if avg > 0 else 0
                
                # Statistic name
                tk.Label(table_frame, text=stat_name, bg=self.COLORS['bg_card'], fg=self.COLORS['text_secondary'],
                        font=('Segoe UI', 10, 'bold'), width=6).grid(row=0, column=col_num, pady=4)
                # Average - Primary value
                tk.Label(table_frame, text=f"{avg:.1f}", bg=self.COLORS['bg_card'], fg=self.COLORS['text_primary'],
                        font=('Segoe UI', 12, 'bold'), width=6).grid(row=1, column=col_num, pady=4)
                # Std Dev
                tk.Label(table_frame, text=f"±{std:.1f}", bg=self.COLORS['bg_card'], fg=self.COLORS['text_tertiary'],
                        font=('Segoe UI', 9), width=6).grid(row=2, column=col_num, pady=4)
                # CV - Color coded
                cv_color = self.COLORS['success'] if cv < 30 else (self.COLORS['warning'] if cv < 50 else self.COLORS['danger'])
                tk.Label(table_frame, text=f"{cv:.0f}%", bg=self.COLORS['bg_card'], fg=cv_color,
                        font=('Segoe UI', 9), width=6).grid(row=3, column=col_num, pady=4)
                
                col_num += 1
        
        # Games played info at bottom - Divider line
        tk.Frame(inner, bg=self.COLORS['divider'], height=1).pack(fill='x', pady=(16, 12))
        
        games_row = tk.Frame(inner, bg=self.COLORS['bg_card'])
        games_row.pack(fill='x')
        tk.Label(games_row, text="Games Played", bg=self.COLORS['bg_card'], 
                fg=self.COLORS['text_secondary'], font=('Segoe UI', 10)).pack(side='left')
        tk.Label(games_row, text=f"{stats_data['games_played']}", bg=self.COLORS['bg_card'], 
                fg=self.COLORS['text_primary'], font=('Segoe UI', 10, 'bold')).pack(side='right')
        
        # Configure column weights
        for i in range(col_num):
            table_frame.columnconfigure(i, weight=1)
    
    def calculate_rolling_stats(self, game_log_df, n_games):
        """Calculate averages and CV for the last n games from game log"""
        if game_log_df is None or game_log_df.empty or len(game_log_df) < n_games:
            return None
        
        # Game log is already sorted most recent first, take first n games
        recent_games = game_log_df.head(n_games)
        
        stats = {
            'averages': {},
            'std_devs': {},
            'games_played': n_games
        }
        
        # Map columns to stat keys
        col_mapping = {
            'points': 'PTS',
            'rebounds': 'REB', 
            'assists': 'AST',
            'blocks': 'BLK',
            'steals': 'STL',
            '3pt': 'FG3M'
        }
        
        for stat_key, col_name in col_mapping.items():
            if col_name in recent_games.columns:
                values = pd.to_numeric(recent_games[col_name], errors='coerce')
                stats['averages'][stat_key] = values.mean()
                stats['std_devs'][stat_key] = values.std()
        
        return stats
    
    def create_rolling_stats_card(self, parent, title, game_log_df, row, col, colspan=6):
        """Create a modern card showing L5, L10, L15 rolling averages with CV"""
        card = tk.Frame(parent, bg=self.COLORS['bg_card'])
        card.grid(row=row, column=col, columnspan=colspan, padx=8, pady=8, sticky="nsew")
        
        inner = tk.Frame(card, bg=self.COLORS['bg_card'])
        inner.pack(fill="both", expand=True, padx=24, pady=20)
        
        # Title - Modern minimal
        tk.Label(inner, text=title.upper(), bg=self.COLORS['bg_card'], fg=self.COLORS['text_tertiary'],
                font=('Segoe UI', 9, 'bold')).pack(anchor='w')
        
        # Stats table
        table_frame = tk.Frame(inner, bg=self.COLORS['bg_card'])
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(16, 0))
        
        stat_order = ['points', 'rebounds', 'assists', 'blocks', 'steals', '3pt']
        stat_names = ['PTS', 'REB', 'AST', 'BLK', 'STL', '3PM']
        windows = [5, 10, 15]
        
        # Calculate stats for each window
        rolling_stats = {}
        for n in windows:
            rolling_stats[n] = self.calculate_rolling_stats(game_log_df, n)
        
        # Configure columns to expand evenly
        table_frame.columnconfigure(0, weight=1)
        for i in range(1, len(stat_names) + 1):
            table_frame.columnconfigure(i, weight=1)
        
        # Header row - stat names
        tk.Label(table_frame, text='GAMES', bg=self.COLORS['bg_card'], fg=self.COLORS['text_secondary'],
                font=('Segoe UI', 10, 'bold')).grid(row=0, column=0, pady=6)
        
        col_num = 1
        for stat_name in stat_names:
            tk.Label(table_frame, text=stat_name, bg=self.COLORS['bg_card'], fg=self.COLORS['text_secondary'],
                    font=('Segoe UI', 10, 'bold')).grid(row=0, column=col_num, pady=6)
            col_num += 1
        
        # Data rows for each window
        row_num = 1
        for n in windows:
            stats = rolling_stats[n]
            
            # Row label (L5, L10, L15)
            tk.Label(table_frame, text=f'L{n}', bg=self.COLORS['bg_card'], fg=self.COLORS['text_primary'],
                    font=('Segoe UI', 10, 'bold')).grid(row=row_num, column=0, pady=6)
            
            col_num = 1
            for stat_key in stat_order:
                if stats and stat_key in stats['averages']:
                    avg = stats['averages'][stat_key]
                    tk.Label(table_frame, text=f"{avg:.1f}", bg=self.COLORS['bg_card'], fg=self.COLORS['text_primary'],
                            font=('Segoe UI', 11, 'bold')).grid(row=row_num, column=col_num, pady=6)
                else:
                    tk.Label(table_frame, text="-", bg=self.COLORS['bg_card'], fg=self.COLORS['text_tertiary'],
                            font=('Segoe UI', 11)).grid(row=row_num, column=col_num, pady=6)
                col_num += 1
            row_num += 1
            
            # CV row for this window
            tk.Label(table_frame, text=f'CV%', bg=self.COLORS['bg_card'], fg=self.COLORS['text_tertiary'],
                    font=('Segoe UI', 9)).grid(row=row_num, column=0, pady=2)
            
            col_num = 1
            for stat_key in stat_order:
                if stats and stat_key in stats['averages'] and stat_key in stats['std_devs']:
                    avg = stats['averages'][stat_key]
                    std = stats['std_devs'][stat_key]
                    cv = 100 * (std / avg) if avg > 0 else 0
                    cv_color = self.COLORS['success'] if cv < 30 else (self.COLORS['warning'] if cv < 50 else self.COLORS['danger'])
                    tk.Label(table_frame, text=f"{cv:.0f}%", bg=self.COLORS['bg_card'], fg=cv_color,
                            font=('Segoe UI', 9)).grid(row=row_num, column=col_num, pady=2)
                else:
                    tk.Label(table_frame, text="-", bg=self.COLORS['bg_card'], fg=self.COLORS['text_tertiary'],
                            font=('Segoe UI', 9)).grid(row=row_num, column=col_num, pady=2)
                col_num += 1
            row_num += 1
        
        # Games available info - Divider
        total_games = len(game_log_df) if game_log_df is not None else 0
        tk.Frame(inner, bg=self.COLORS['divider'], height=1).pack(fill='x', pady=(16, 12))
        
        info_row = tk.Frame(inner, bg=self.COLORS['bg_card'])
        info_row.pack(fill='x')
        tk.Label(info_row, text="Total Games Available", bg=self.COLORS['bg_card'], 
                fg=self.COLORS['text_secondary'], font=('Segoe UI', 10)).pack(side='left')
        tk.Label(info_row, text=f"{total_games}", bg=self.COLORS['bg_card'], 
                fg=self.COLORS['text_primary'], font=('Segoe UI', 10, 'bold')).pack(side='right')
    
    def calculate_hit_rates(self, game_log_df, n_games, thresholds):
        """Calculate hit rates for point thresholds over last n games"""
        if game_log_df is None or game_log_df.empty or len(game_log_df) < n_games:
            return None
        
        recent_games = game_log_df.head(n_games)
        hit_rates = {}
        
        for threshold in thresholds:
            games_hit = len(recent_games[recent_games['PTS'] >= threshold])
            hit_rates[threshold] = (games_hit / n_games) * 100
        
        return hit_rates
    
    def calculate_rebound_hit_rates(self, game_log_df, n_games, thresholds):
        """Calculate hit rates for rebound thresholds over last n games"""
        if game_log_df is None or game_log_df.empty or len(game_log_df) < n_games:
            return None
        
        recent_games = game_log_df.head(n_games)
        hit_rates = {}
        
        for threshold in thresholds:
            games_hit = len(recent_games[recent_games['REB'] >= threshold])
            hit_rates[threshold] = (games_hit / n_games) * 100
        
        return hit_rates
    
    def calculate_assist_hit_rates(self, game_log_df, n_games, thresholds):
        """Calculate hit rates for assist thresholds over last n games"""
        if game_log_df is None or game_log_df.empty or len(game_log_df) < n_games:
            return None
        
        recent_games = game_log_df.head(n_games)
        hit_rates = {}
        
        for threshold in thresholds:
            games_hit = len(recent_games[recent_games['AST'] >= threshold])
            hit_rates[threshold] = (games_hit / n_games) * 100
        
        return hit_rates
    
    def create_hit_rate_card(self, parent, title, game_log_df, row, col, colspan=3):
        """Create a modern card showing hit rates for point thresholds"""
        card = tk.Frame(parent, bg=self.COLORS['bg_card'])
        card.grid(row=row, column=col, columnspan=colspan, padx=8, pady=8, sticky="nsew")
        
        inner = tk.Frame(card, bg=self.COLORS['bg_card'])
        inner.pack(fill="both", expand=True, padx=24, pady=20)
        
        # Title - Modern minimal
        tk.Label(inner, text=title.upper(), bg=self.COLORS['bg_card'], fg=self.COLORS['text_tertiary'],
                font=('Segoe UI', 9, 'bold')).pack(anchor='w')
        
        # Stats table
        table_frame = tk.Frame(inner, bg=self.COLORS['bg_card'])
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(16, 0))
        
        thresholds = [10, 15, 20, 25, 30]
        windows = [5, 10, 15]
        
        # Calculate hit rates for each window
        hit_rates = {}
        for n in windows:
            hit_rates[n] = self.calculate_hit_rates(game_log_df, n, thresholds)
        
        # Configure columns to expand evenly
        table_frame.columnconfigure(0, weight=1)
        for i in range(1, len(thresholds) + 1):
            table_frame.columnconfigure(i, weight=1)
        
        # Header row - threshold columns
        tk.Label(table_frame, text='', bg=self.COLORS['bg_card']).grid(row=0, column=0)
        
        col_num = 1
        for threshold in thresholds:
            tk.Label(table_frame, text=f"{threshold}+", bg=self.COLORS['bg_card'], fg=self.COLORS['text_secondary'],
                    font=('Segoe UI', 10, 'bold')).grid(row=0, column=col_num, pady=6)
            col_num += 1
        
        # Data rows for each window
        row_num = 1
        for n in windows:
            rates = hit_rates[n]
            
            # Row label (L5, L10, L15)
            tk.Label(table_frame, text=f'L{n}', bg=self.COLORS['bg_card'], fg=self.COLORS['text_primary'],
                    font=('Segoe UI', 10, 'bold')).grid(row=row_num, column=0, pady=8)
            
            col_num = 1
            for threshold in thresholds:
                if rates and threshold in rates:
                    rate = rates[threshold]
                    # Color code based on hit rate
                    if rate >= 80:
                        rate_color = self.COLORS['success']
                    elif rate >= 50:
                        rate_color = self.COLORS['warning']
                    else:
                        rate_color = self.COLORS['danger']
                    
                    tk.Label(table_frame, text=f"{rate:.0f}%", bg=self.COLORS['bg_card'], fg=rate_color,
                            font=('Segoe UI', 11, 'bold')).grid(row=row_num, column=col_num, pady=8)
                else:
                    tk.Label(table_frame, text="-", bg=self.COLORS['bg_card'], fg=self.COLORS['text_tertiary'],
                            font=('Segoe UI', 11)).grid(row=row_num, column=col_num, pady=8)
                col_num += 1
            row_num += 1
        
        # Info section - Divider
        tk.Frame(inner, bg=self.COLORS['divider'], height=1).pack(fill='x', pady=(16, 12))
        
        # Legend
        legend_row = tk.Frame(inner, bg=self.COLORS['bg_card'])
        legend_row.pack(fill='x')
        
        tk.Label(legend_row, text="●", bg=self.COLORS['bg_card'], fg=self.COLORS['success'],
                font=('Segoe UI', 8)).pack(side='left')
        tk.Label(legend_row, text="≥80%", bg=self.COLORS['bg_card'], fg=self.COLORS['text_tertiary'],
                font=('Segoe UI', 9)).pack(side='left', padx=(2, 12))
        
        tk.Label(legend_row, text="●", bg=self.COLORS['bg_card'], fg=self.COLORS['warning'],
                font=('Segoe UI', 8)).pack(side='left')
        tk.Label(legend_row, text="50-79%", bg=self.COLORS['bg_card'], fg=self.COLORS['text_tertiary'],
                font=('Segoe UI', 9)).pack(side='left', padx=(2, 12))
        
        tk.Label(legend_row, text="●", bg=self.COLORS['bg_card'], fg=self.COLORS['danger'],
                font=('Segoe UI', 8)).pack(side='left')
        tk.Label(legend_row, text="<50%", bg=self.COLORS['bg_card'], fg=self.COLORS['text_tertiary'],
                font=('Segoe UI', 9)).pack(side='left', padx=(2, 0))
    
    def create_rebound_hit_rate_card(self, parent, title, game_log_df, row, col, colspan=3):
        """Create a modern card showing hit rates for rebound thresholds"""
        card = tk.Frame(parent, bg=self.COLORS['bg_card'])
        card.grid(row=row, column=col, columnspan=colspan, padx=8, pady=8, sticky="nsew")
        
        inner = tk.Frame(card, bg=self.COLORS['bg_card'])
        inner.pack(fill="both", expand=True, padx=24, pady=20)
        
        # Title - Modern minimal
        tk.Label(inner, text=title.upper(), bg=self.COLORS['bg_card'], fg=self.COLORS['text_tertiary'],
                font=('Segoe UI', 9, 'bold')).pack(anchor='w')
        
        # Stats table
        table_frame = tk.Frame(inner, bg=self.COLORS['bg_card'])
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(16, 0))
        
        thresholds = [4, 6, 8, 10, 12]
        windows = [5, 10, 15]
        
        # Calculate hit rates for each window
        hit_rates = {}
        for n in windows:
            hit_rates[n] = self.calculate_rebound_hit_rates(game_log_df, n, thresholds)
        
        # Configure columns to expand evenly
        table_frame.columnconfigure(0, weight=1)
        for i in range(1, len(thresholds) + 1):
            table_frame.columnconfigure(i, weight=1)
        
        # Header row - threshold columns
        tk.Label(table_frame, text='', bg=self.COLORS['bg_card']).grid(row=0, column=0)
        
        col_num = 1
        for threshold in thresholds:
            tk.Label(table_frame, text=f"{threshold}+", bg=self.COLORS['bg_card'], fg=self.COLORS['text_secondary'],
                    font=('Segoe UI', 10, 'bold')).grid(row=0, column=col_num, pady=6)
            col_num += 1
        
        # Data rows for each window
        row_num = 1
        for n in windows:
            rates = hit_rates[n]
            
            # Row label (L5, L10, L15)
            tk.Label(table_frame, text=f'L{n}', bg=self.COLORS['bg_card'], fg=self.COLORS['text_primary'],
                    font=('Segoe UI', 10, 'bold')).grid(row=row_num, column=0, pady=8)
            
            col_num = 1
            for threshold in thresholds:
                if rates and threshold in rates:
                    rate = rates[threshold]
                    # Color code based on hit rate
                    if rate >= 80:
                        rate_color = self.COLORS['success']
                    elif rate >= 50:
                        rate_color = self.COLORS['warning']
                    else:
                        rate_color = self.COLORS['danger']
                    
                    tk.Label(table_frame, text=f"{rate:.0f}%", bg=self.COLORS['bg_card'], fg=rate_color,
                            font=('Segoe UI', 11, 'bold')).grid(row=row_num, column=col_num, pady=8)
                else:
                    tk.Label(table_frame, text="-", bg=self.COLORS['bg_card'], fg=self.COLORS['text_tertiary'],
                            font=('Segoe UI', 11)).grid(row=row_num, column=col_num, pady=8)
                col_num += 1
            row_num += 1
        
        # Info section - Divider
        tk.Frame(inner, bg=self.COLORS['divider'], height=1).pack(fill='x', pady=(16, 12))
        
        # Legend
        legend_row = tk.Frame(inner, bg=self.COLORS['bg_card'])
        legend_row.pack(fill='x')
        
        tk.Label(legend_row, text="●", bg=self.COLORS['bg_card'], fg=self.COLORS['success'],
                font=('Segoe UI', 8)).pack(side='left')
        tk.Label(legend_row, text="≥80%", bg=self.COLORS['bg_card'], fg=self.COLORS['text_tertiary'],
                font=('Segoe UI', 9)).pack(side='left', padx=(2, 12))
        
        tk.Label(legend_row, text="●", bg=self.COLORS['bg_card'], fg=self.COLORS['warning'],
                font=('Segoe UI', 8)).pack(side='left')
        tk.Label(legend_row, text="50-79%", bg=self.COLORS['bg_card'], fg=self.COLORS['text_tertiary'],
                font=('Segoe UI', 9)).pack(side='left', padx=(2, 12))
        
        tk.Label(legend_row, text="●", bg=self.COLORS['bg_card'], fg=self.COLORS['danger'],
                font=('Segoe UI', 8)).pack(side='left')
        tk.Label(legend_row, text="<50%", bg=self.COLORS['bg_card'], fg=self.COLORS['text_tertiary'],
                font=('Segoe UI', 9)).pack(side='left', padx=(2, 0))
    
    def create_assist_hit_rate_card(self, parent, title, game_log_df, row, col, colspan=3):
        """Create a modern card showing hit rates for assist thresholds"""
        card = tk.Frame(parent, bg=self.COLORS['bg_card'])
        card.grid(row=row, column=col, columnspan=colspan, padx=8, pady=8, sticky="nsew")
        
        inner = tk.Frame(card, bg=self.COLORS['bg_card'])
        inner.pack(fill="both", expand=True, padx=24, pady=20)
        
        # Title - Modern minimal
        tk.Label(inner, text=title.upper(), bg=self.COLORS['bg_card'], fg=self.COLORS['text_tertiary'],
                font=('Segoe UI', 9, 'bold')).pack(anchor='w')
        
        # Stats table
        table_frame = tk.Frame(inner, bg=self.COLORS['bg_card'])
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(16, 0))
        
        thresholds = [4, 6, 8, 10, 12]
        windows = [5, 10, 15]
        
        # Calculate hit rates for each window
        hit_rates = {}
        for n in windows:
            hit_rates[n] = self.calculate_assist_hit_rates(game_log_df, n, thresholds)
        
        # Configure columns to expand evenly
        table_frame.columnconfigure(0, weight=1)
        for i in range(1, len(thresholds) + 1):
            table_frame.columnconfigure(i, weight=1)
        
        # Header row - threshold columns
        tk.Label(table_frame, text='', bg=self.COLORS['bg_card']).grid(row=0, column=0)
        
        col_num = 1
        for threshold in thresholds:
            tk.Label(table_frame, text=f"{threshold}+", bg=self.COLORS['bg_card'], fg=self.COLORS['text_secondary'],
                    font=('Segoe UI', 10, 'bold')).grid(row=0, column=col_num, pady=6)
            col_num += 1
        
        # Data rows for each window
        row_num = 1
        for n in windows:
            rates = hit_rates[n]
            
            # Row label (L5, L10, L15)
            tk.Label(table_frame, text=f'L{n}', bg=self.COLORS['bg_card'], fg=self.COLORS['text_primary'],
                    font=('Segoe UI', 10, 'bold')).grid(row=row_num, column=0, pady=8)
            
            col_num = 1
            for threshold in thresholds:
                if rates and threshold in rates:
                    rate = rates[threshold]
                    # Color code based on hit rate
                    if rate >= 80:
                        rate_color = self.COLORS['success']
                    elif rate >= 50:
                        rate_color = self.COLORS['warning']
                    else:
                        rate_color = self.COLORS['danger']
                    
                    tk.Label(table_frame, text=f"{rate:.0f}%", bg=self.COLORS['bg_card'], fg=rate_color,
                            font=('Segoe UI', 11, 'bold')).grid(row=row_num, column=col_num, pady=8)
                else:
                    tk.Label(table_frame, text="-", bg=self.COLORS['bg_card'], fg=self.COLORS['text_tertiary'],
                            font=('Segoe UI', 11)).grid(row=row_num, column=col_num, pady=8)
                col_num += 1
            row_num += 1
        
        # Info section - Divider
        tk.Frame(inner, bg=self.COLORS['divider'], height=1).pack(fill='x', pady=(16, 12))
        
        # Legend
        legend_row = tk.Frame(inner, bg=self.COLORS['bg_card'])
        legend_row.pack(fill='x')
        
        tk.Label(legend_row, text="●", bg=self.COLORS['bg_card'], fg=self.COLORS['success'],
                font=('Segoe UI', 8)).pack(side='left')
        tk.Label(legend_row, text="≥80%", bg=self.COLORS['bg_card'], fg=self.COLORS['text_tertiary'],
                font=('Segoe UI', 9)).pack(side='left', padx=(2, 12))
        
        tk.Label(legend_row, text="●", bg=self.COLORS['bg_card'], fg=self.COLORS['warning'],
                font=('Segoe UI', 8)).pack(side='left')
        tk.Label(legend_row, text="50-79%", bg=self.COLORS['bg_card'], fg=self.COLORS['text_tertiary'],
                font=('Segoe UI', 9)).pack(side='left', padx=(2, 12))
        
        tk.Label(legend_row, text="●", bg=self.COLORS['bg_card'], fg=self.COLORS['danger'],
                font=('Segoe UI', 8)).pack(side='left')
        tk.Label(legend_row, text="<50%", bg=self.COLORS['bg_card'], fg=self.COLORS['text_tertiary'],
                font=('Segoe UI', 9)).pack(side='left', padx=(2, 0))
    
    def create_game_log_display(self, parent, game_log_df, title, row, col, colspan=6):
        """Display game log in a modern scrollable table"""
        card = tk.Frame(parent, bg=self.COLORS['bg_card'])
        card.grid(row=row, column=col, columnspan=colspan, padx=8, pady=8, sticky="nsew")
        
        inner = tk.Frame(card, bg=self.COLORS['bg_card'])
        inner.pack(fill="both", expand=True, padx=24, pady=20)
        
        # Title - Modern minimal
        tk.Label(inner, text=title.upper(), bg=self.COLORS['bg_card'], fg=self.COLORS['text_tertiary'],
                font=('Segoe UI', 9, 'bold')).pack(anchor='w', pady=(0, 16))
        
        # Create frame for treeview and scrollbars
        tree_frame = tk.Frame(inner, bg=self.COLORS['bg_card'])
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # Modern scrollbar style
        scrollbar_style = ttk.Style()
        scrollbar_style.configure("Modern.Vertical.TScrollbar",
                                  background=self.COLORS['bg_elevated'],
                                  troughcolor=self.COLORS['bg_primary'],
                                  bordercolor=self.COLORS['bg_primary'],
                                  arrowcolor=self.COLORS['text_secondary'])
        
        # Create scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", style="Modern.Vertical.TScrollbar")
        
        # Create treeview
        # PRA, PR, PA, RA are calculated columns (not from API)
        calculated_cols = ['PRA', 'PR', 'PA', 'RA']
        visible_columns = ['GAME_DATE', 'MATCHUP', 'WL', 'MIN', 'PTS', 'REB', 'AST', 'STL', 'BLK', 
                   'PRA', 'PR', 'PA', 'RA',
                   'FGM', 'FGA', 'FG_PCT', 'FG3M', 'FG3A', 'FG3_PCT', 'FTM', 'FTA', 'FT_PCT', 'TS_PCT', 'PLUS_MINUS']
        # Filter to only include columns that exist in the dataframe OR are calculated
        visible_columns = [col for col in visible_columns if col in game_log_df.columns or col in calculated_cols]
        
        # Add Game_ID to columns if it exists, but not to visible_columns
        columns = list(visible_columns)
        if 'Game_ID' in game_log_df.columns:
            columns.append('Game_ID')
            # Ensure Game_ID is string to prevent float conversion issues
            game_log_df['Game_ID'] = game_log_df['Game_ID'].astype(str)
        
        tree = ttk.Treeview(tree_frame, columns=columns, displaycolumns=visible_columns, show='headings', 
                           yscrollcommand=vsb.set, height=15)
        
        # Bind double click to show box score
        tree.bind("<Double-1>", self.on_game_click)
        
        vsb.config(command=tree.yview)
        
        # Configure column headings and widths
        column_widths = {
            'GAME_DATE': 110,
            'MATCHUP': 130,
            'WL': 45,
            'MIN': 55,
            'PTS': 55,
            'REB': 55,
            'AST': 55,
            'STL': 55,
            'BLK': 55,
            'PRA': 55,
            'PR': 55,
            'PA': 55,
            'RA': 55,
            'FGM': 55,
            'FGA': 55,
            'FG_PCT': 70,
            'FG3M': 55,
            'FG3A': 55,
            'FG3_PCT': 70,
            'FTM': 55,
            'FTA': 55,
            'FT_PCT': 70,
            'TS_PCT': 70,
            'PLUS_MINUS': 85
        }
        
        # Column header display names
        column_headers = {
            'FG_PCT': 'FG%',
            'FG3_PCT': '3P%',
            'FT_PCT': 'FT%',
            'TS_PCT': 'TS%'
        }
        
        for col in visible_columns:
            header_text = column_headers.get(col, col)
            tree.heading(col, text=header_text, anchor='center')
            width = column_widths.get(col, 80)
            tree.column(col, width=width, anchor='center')
        
        # Modern Treeview styling
        style = ttk.Style()
        style.configure("Modern.Treeview",
                       background=self.COLORS['bg_primary'],
                       foreground=self.COLORS['text_primary'],
                       fieldbackground=self.COLORS['bg_primary'],
                       borderwidth=0,
                       relief='flat',
                       rowheight=32,
                       font=('Segoe UI', 10))
        style.configure("Modern.Treeview.Heading",
                       background=self.COLORS['bg_elevated'],
                       foreground=self.COLORS['text_secondary'],
                       borderwidth=0,
                       relief='flat',
                       font=('Segoe UI', 9, 'bold'))
        style.map('Modern.Treeview', 
                 background=[('selected', self.COLORS['accent_soft'])],
                 foreground=[('selected', self.COLORS['text_primary'])])
        style.map('Modern.Treeview.Heading',
                 background=[('active', self.COLORS['bg_hover'])])
        
        tree.configure(style="Modern.Treeview")
        
        # Insert data
        for idx, row in game_log_df.iterrows():
            values = []
            # Pre-calculate PRA, PR, PA, RA
            pts = float(row['PTS']) if 'PTS' in row and row['PTS'] else 0
            reb = float(row['REB']) if 'REB' in row and row['REB'] else 0
            ast = float(row['AST']) if 'AST' in row and row['AST'] else 0
            calc_values = {'PRA': pts + reb + ast, 'PR': pts + reb, 'PA': pts + ast, 'RA': reb + ast}
            
            for col in columns:
                # Handle calculated columns
                if col in calc_values:
                    values.append(str(int(calc_values[col])))
                    continue
                val = row[col]
                # Format the value
                if col == 'MIN':
                    try:
                        values.append(f"{float(val):.0f}" if val else "0")
                    except:
                        values.append(str(val))
                elif col in ['FG_PCT', 'FG3_PCT', 'FT_PCT', 'TS_PCT']:
                    try:
                        values.append(f"{float(val)*100:.1f}%" if val else "0.0%")
                    except:
                        values.append(str(val))
                elif col == 'PLUS_MINUS':
                    try:
                        pm = float(val) if val else 0
                        values.append(f"{pm:+.0f}" if pm != 0 else "0")
                    except:
                        values.append(str(val))
                elif col in ['GAME_DATE', 'MATCHUP', 'WL', 'Game_ID']:
                    # Text columns - keep as is, show empty if blank
                    values.append(str(val) if val else "")
                else:
                    # Numeric columns - show 0 instead of blank
                    try:
                        num_val = float(val) if val else 0
                        values.append(str(int(num_val)) if num_val == int(num_val) else str(num_val))
                    except:
                        values.append(str(val) if val else "0")
            
            # Color code by win/loss
            wl_value = row['WL'] if 'WL' in game_log_df.columns else None
            if wl_value == 'W':
                tag = 'win'
            elif wl_value == 'L':
                tag = 'loss'
            else:
                tag = 'evenrow' if idx % 2 == 0 else 'oddrow'
            tree.insert('', 'end', values=values, tags=(tag,))
        
        # Modern row colors - subtle win/loss highlighting
        tree.tag_configure('win', background='#0d291a', foreground=self.COLORS['text_primary'])  # Subtle green
        tree.tag_configure('loss', background='#291414', foreground=self.COLORS['text_primary'])  # Subtle red
        tree.tag_configure('evenrow', background=self.COLORS['bg_primary'], foreground=self.COLORS['text_primary'])
        tree.tag_configure('oddrow', background=self.COLORS['bg_primary'], foreground=self.COLORS['text_primary'])
        
        # Pack elements
        tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        # Add summary info - Modern style with divider
        tk.Frame(inner, bg=self.COLORS['divider'], height=1).pack(fill='x', pady=(16, 12))
        
        summary_frame = tk.Frame(inner, bg=self.COLORS['bg_card'])
        summary_frame.pack(fill=tk.X)
        
        total_games = len(game_log_df)
        wins = len(game_log_df[game_log_df['WL'] == 'W']) if 'WL' in game_log_df.columns else 0
        losses = total_games - wins
        
        # Stats row
        stats_row = tk.Frame(summary_frame, bg=self.COLORS['bg_card'])
        stats_row.pack(fill='x')
        
        # Total Games
        tk.Label(stats_row, text="Total", bg=self.COLORS['bg_card'], 
                fg=self.COLORS['text_secondary'], font=('Segoe UI', 10)).pack(side='left')
        tk.Label(stats_row, text=f"{total_games}", bg=self.COLORS['bg_card'], 
                fg=self.COLORS['text_primary'], font=('Segoe UI', 10, 'bold')).pack(side='left', padx=(4, 20))
        
        # Wins
        tk.Label(stats_row, text="Wins", bg=self.COLORS['bg_card'], 
                fg=self.COLORS['text_secondary'], font=('Segoe UI', 10)).pack(side='left')
        tk.Label(stats_row, text=f"{wins}", bg=self.COLORS['bg_card'], 
                fg=self.COLORS['success'], font=('Segoe UI', 10, 'bold')).pack(side='left', padx=(4, 20))
        
        # Losses
        tk.Label(stats_row, text="Losses", bg=self.COLORS['bg_card'], 
                fg=self.COLORS['text_secondary'], font=('Segoe UI', 10)).pack(side='left')
        tk.Label(stats_row, text=f"{losses}", bg=self.COLORS['bg_card'], 
                fg=self.COLORS['danger'], font=('Segoe UI', 10, 'bold')).pack(side='left', padx=(4, 0))
    
    def fetch_stats(self):
        player = self.player_entry.get().strip()
        team = self.team_entry.get().strip()
        
        if not player:
            messagebox.showerror("Error", "Please enter a player name")
            return
        if not team:
            messagebox.showerror("Error", "Please enter an opponent team")
            return
        
        # Get selected seasons
        selected_seasons = [season for season, var in self.season_vars.items() if var.get()]
        
        if not selected_seasons:
            messagebox.showerror("Error", "Please select at least one season")
            return
        
        # Disable button during fetch
        self.fetch_btn.config(state='disabled', text='Fetching...')
        self.clear_results()
        
        # Run in separate thread to prevent GUI freezing
        thread = threading.Thread(target=self.fetch_stats_thread, args=(player, team, selected_seasons))
        thread.daemon = True
        thread.start()
        
    def fetch_stats_thread(self, player, team, seasons):
        try:
            self.update_status("Fetching data from NBA API...")
            
            all_data = []
            
            # Reverse seasons to show most recent first
            for season in reversed(seasons):
                season_data = {
                    'season': season,
                    'season_stats': None,
                    'vs_team_stats': None
                }
                
                # Season statistics
                self.update_status(f"Fetching {player} season stats for {season}...")
                try:
                    stats = get_player_season_stats(player, season)
                    season_data['season_stats'] = stats
                except Exception as e:
                    season_data['season_error'] = str(e)
                
                # VS Team statistics
                self.update_status(f"Fetching {player} vs {team} stats for {season}...")
                try:
                    stats = get_player_vs_team_stats(player, season, team)
                    season_data['vs_team_stats'] = stats
                except Exception as e:
                    season_data['vs_team_error'] = str(e)
                
                # Get game log
                self.update_status(f"Fetching game log for {season}...")
                try:
                    game_log_df = get_player_game_log(player, season)
                    season_data['game_log'] = game_log_df
                    
                    # Find team abbreviation using the same logic as formula.py and percentile.py
                    team_abbrev = self.find_team_abbreviation(team)
                    
                    if team_abbrev:
                        # Filter game log for VS team games using the abbreviation
                        # MATCHUP column contains strings like "LAC @ GSW" or "LAC vs. GSW"
                        vs_team_log = game_log_df[game_log_df['MATCHUP'].str.contains(team_abbrev, case=False, na=False)]
                        season_data['vs_team_log'] = vs_team_log if not vs_team_log.empty else None
                    else:
                        # Could not find team - store error info
                        season_data['vs_team_log'] = None
                        season_data['team_not_found'] = True
                    
                    # Debug: store actual matchups for troubleshooting
                    if season_data['vs_team_log'] is None and not game_log_df.empty:
                        unique_matchups = game_log_df['MATCHUP'].unique().tolist()
                        season_data['available_matchups'] = unique_matchups
                except Exception as e:
                    season_data['game_log_error'] = str(e)
                
                all_data.append(season_data)
            
            # Update GUI in main thread
            self.root.after(0, self.display_results, player, team, all_data)
            
        except Exception as e:
            self.root.after(0, messagebox.showerror, "Error", f"An error occurred: {str(e)}")
        finally:
            self.root.after(0, self.enable_fetch_button)
    
    def display_results(self, player, team, all_data):
        current_row = 0
        
        # Configure results frame columns to be responsive
        for i in range(6):
            self.results_frame.columnconfigure(i, weight=1)
        
        for data in all_data:
            season = data['season']
            
            # Season header - Modern style
            header_frame = tk.Frame(self.results_frame, bg=self.COLORS['bg_primary'])
            header_frame.grid(row=current_row, column=0, columnspan=6, sticky="ew", pady=(24, 8))
            
            tk.Label(header_frame, text="SEASON", bg=self.COLORS['bg_primary'], 
                    fg=self.COLORS['text_tertiary'], font=('Segoe UI', 9)).pack(anchor='w')
            tk.Label(header_frame, text=season, bg=self.COLORS['bg_primary'], 
                    fg=self.COLORS['text_primary'], font=('Segoe UI', 20, 'bold')).pack(anchor='w', pady=(2, 0))
            current_row += 1
            
            # Season stats card
            if data.get('season_stats'):
                self.create_stat_card(self.results_frame, 
                                     f"{player} - {season} Overall Stats",
                                     data['season_stats'], 
                                     current_row, 0, colspan=3)
            elif data.get('season_error'):
                error_card = tk.Frame(self.results_frame, bg=self.COLORS['bg_card'])
                error_card.grid(row=current_row, column=0, columnspan=3, padx=8, pady=8, sticky="ew")
                tk.Label(error_card, text=f"Season Error: {data['season_error']}", 
                        bg=self.COLORS['bg_card'], fg=self.COLORS['danger'],
                        font=('Segoe UI', 10), pady=20, padx=24).pack()
            
            # VS Team stats card
            if data.get('vs_team_stats'):
                self.create_stat_card(self.results_frame, 
                                     f"{player} vs {team} - {season}",
                                     data['vs_team_stats'], 
                                     current_row, 3, colspan=3)
            elif data.get('vs_team_error'):
                error_card = tk.Frame(self.results_frame, bg=self.COLORS['bg_card'])
                error_card.grid(row=current_row, column=3, columnspan=3, padx=8, pady=8, sticky="ew")
                tk.Label(error_card, text=f"VS Team Error: {data['vs_team_error']}", 
                        bg=self.COLORS['bg_card'], fg=self.COLORS['danger'],
                        font=('Segoe UI', 10), pady=20, padx=24).pack()
            
            current_row += 1
            
            # Rolling stats cards - ONLY for current season (2025-26)
            if season == '2025-26' and data.get('game_log') is not None:
                self.create_rolling_stats_card(self.results_frame,
                                              f"{player} - Recent Game Trends (L5/L10/L15)",
                                              data['game_log'],
                                              current_row, 0, colspan=6)
                current_row += 1
                
                # Hit rate cards row - Points, Rebounds, Assists
                self.create_hit_rate_card(self.results_frame,
                                         f"{player} - Points Hit Rate",
                                         data['game_log'],
                                         current_row, 0, colspan=2)
                self.create_rebound_hit_rate_card(self.results_frame,
                                         f"{player} - Rebounds Hit Rate",
                                         data['game_log'],
                                         current_row, 2, colspan=2)
                self.create_assist_hit_rate_card(self.results_frame,
                                         f"{player} - Assists Hit Rate",
                                         data['game_log'],
                                         current_row, 4, colspan=2)
                current_row += 1
            
            # Game log
            if data.get('game_log') is not None:
                self.create_game_log_display(self.results_frame,
                                            data['game_log'],
                                            f"{player} - {season} Game Log (All Games)",
                                            current_row, 0, colspan=6)
                current_row += 1
            elif data.get('game_log_error'):
                error_card = tk.Frame(self.results_frame, bg=self.COLORS['bg_card'])
                error_card.grid(row=current_row, column=0, columnspan=6, padx=8, pady=8, sticky="ew")
                tk.Label(error_card, text=f"Game Log Error: {data['game_log_error']}", 
                        bg=self.COLORS['bg_card'], fg=self.COLORS['danger'],
                        font=('Segoe UI', 10), pady=20, padx=24).pack()
                current_row += 1
            
            # VS Team game log
            if data.get('vs_team_log') is not None:
                self.create_game_log_display(self.results_frame,
                                            data['vs_team_log'],
                                            f"{player} vs {team} - {season} Game Log",
                                            current_row, 0, colspan=6)
                current_row += 1
            else:
                # Show message when no VS team games found
                if data.get('team_not_found'):
                    message = f"Could not find team '{team}'. Please try using the team's full name, nickname, or 3-letter abbreviation."
                else:
                    message = f"No games found for {player} vs {team} in {season} season"
                
                msg_card = tk.Frame(self.results_frame, bg=self.COLORS['bg_card'])
                msg_card.grid(row=current_row, column=0, columnspan=6, padx=8, pady=8, sticky="ew")
                tk.Label(msg_card, text=message, bg=self.COLORS['bg_card'], fg=self.COLORS['text_tertiary'],
                        font=('Segoe UI', 10), pady=16, padx=24).pack()
                current_row += 1
                
                # Show available matchups for debugging
                if 'available_matchups' in data:
                    matchups_text = "Available teams in this season:\n" + "\n".join(data['available_matchups'][:15])
                    if len(data['available_matchups']) > 15:
                        matchups_text += f"\n... and {len(data['available_matchups']) - 15} more"
                    
                    matchups_card = tk.Frame(self.results_frame, bg=self.COLORS['bg_card'])
                    matchups_card.grid(row=current_row, column=0, columnspan=6, padx=8, pady=(0, 8), sticky="ew")
                    tk.Label(matchups_card, text=matchups_text, bg=self.COLORS['bg_card'], fg=self.COLORS['text_tertiary'],
                            font=('Segoe UI', 9), justify='left', pady=12, padx=24).pack(anchor='w')
                    current_row += 1
            
            # Add separator - Modern divider
            separator = tk.Frame(self.results_frame, height=1, bg=self.COLORS['divider'])
            separator.grid(row=current_row, column=0, columnspan=6, sticky="ew", pady=24)
            current_row += 1
        
        self.update_status(f"Statistics loaded successfully for {len(all_data)} season(s)!")
        
    def enable_fetch_button(self):
        self.fetch_btn.config(state='normal', text='Fetch Statistics', bg=self.COLORS['accent'])
    
    def on_game_click(self, event):
        """Handle click on game log row"""
        tree = event.widget
        selection = tree.selection()
        if not selection:
            return
        
        item = selection[0]
        values = tree.item(item, 'values')
        
        # Get columns to find index of Game_ID
        # Note: tree['columns'] returns the column identifiers
        columns = tree['columns']
        
        try:
            if 'Game_ID' in columns:
                game_id_idx = columns.index('Game_ID')
                game_id = values[game_id_idx]
                print(f"DEBUG: Clicked Game ID: '{game_id}'")
                self.show_box_score(game_id)
            else:
                print("DEBUG: Game_ID column not found in tree columns")
                messagebox.showerror("Error", "Game ID not found in data")
        except ValueError:
            # Game_ID not found in columns
            pass
        except Exception as e:
            print(f"DEBUG: Error in on_game_click: {e}")
            messagebox.showerror("Error", f"Could not open box score: {str(e)}")

    def show_box_score(self, game_id):
        """Fetch and display box score for a game"""
        try:
            # Ensure game_id is a string and padded with zeros to 10 digits
            game_id = str(game_id).strip()
            
            # Handle potential float conversion (e.g. "22301195.0")
            if game_id.endswith('.0'):
                game_id = game_id[:-2]
            
            if game_id.lower() == 'nan':
                print("DEBUG: Game ID is 'nan'")
                messagebox.showerror("Error", "Invalid Game ID (nan)")
                return
                
            if not game_id:
                print("DEBUG: Empty Game ID")
                return
                
            game_id = game_id.zfill(10)
            print(f"DEBUG: Fetching box score for Game ID: '{game_id}'")
            
            # Create modern loading window
            loading = tk.Toplevel(self.root)
            loading.title("Loading")
            loading.geometry("300x120")
            loading.configure(bg=self.COLORS['bg_card'])
            loading.resizable(False, False)
            
            loading_inner = tk.Frame(loading, bg=self.COLORS['bg_card'])
            loading_inner.pack(expand=True, fill='both', padx=24, pady=24)
            
            tk.Label(loading_inner, text="LOADING", bg=self.COLORS['bg_card'], 
                    fg=self.COLORS['text_tertiary'], font=('Segoe UI', 9)).pack(anchor='w')
            tk.Label(loading_inner, text="Fetching Box Score...", bg=self.COLORS['bg_card'], 
                    fg=self.COLORS['text_primary'], font=('Segoe UI', 14, 'bold')).pack(anchor='w', pady=(4, 0))
            loading.update()
            
            # Fetch data
            try:
                # Try V2 first
                box = boxscoretraditionalv2.BoxScoreTraditionalV2(game_id=game_id)
                print("DEBUG: Box score V2 object created")
                
                # Initialize empty dataframes
                player_stats = pd.DataFrame()
                team_stats = pd.DataFrame()
                
                if box.player_stats:
                    player_stats = box.player_stats.get_data_frame()
                
                if box.team_stats:
                    team_stats = box.team_stats.get_data_frame()
                
                # If V2 is empty, try V3
                if player_stats.empty:
                    print("DEBUG: V2 empty, trying V3...")
                    box_v3 = boxscoretraditionalv3.BoxScoreTraditionalV3(game_id=game_id)
                    
                    if box_v3.player_stats:
                        v3_player = box_v3.player_stats.get_data_frame()
                        if not v3_player.empty:
                            # Map V3 columns to V2 format
                            v3_player['PLAYER_NAME'] = v3_player['firstName'] + " " + v3_player['familyName']
                            
                            column_map = {
                                'teamTricode': 'TEAM_ABBREVIATION',
                                'minutes': 'MIN',
                                'points': 'PTS',
                                'reboundsTotal': 'REB',
                                'assists': 'AST',
                                'steals': 'STL',
                                'blocks': 'BLK',
                                'turnovers': 'TO',
                                'foulsPersonal': 'PF',
                                'fieldGoalsMade': 'FGM',
                                'fieldGoalsAttempted': 'FGA',
                                'fieldGoalsPercentage': 'FG_PCT',
                                'threePointersMade': 'FG3M',
                                'threePointersAttempted': 'FG3A',
                                'threePointersPercentage': 'FG3_PCT',
                                'freeThrowsMade': 'FTM',
                                'freeThrowsAttempted': 'FTA',
                                'freeThrowsPercentage': 'FT_PCT',
                                'plusMinusPoints': 'PLUS_MINUS'
                            }
                            player_stats = v3_player.rename(columns=column_map)
                            print(f"DEBUG: V3 Player stats shape: {player_stats.shape}")

                    if box_v3.team_stats:
                        v3_team = box_v3.team_stats.get_data_frame()
                        if not v3_team.empty:
                            column_map_team = {
                                'teamTricode': 'TEAM_ABBREVIATION',
                                'points': 'PTS',
                                # Add other team stats if needed for header
                            }
                            team_stats = v3_team.rename(columns=column_map_team)
                            print(f"DEBUG: V3 Team stats shape: {team_stats.shape}")

            except Exception as e:
                print(f"DEBUG: Error fetching box score: {e}")
                loading.destroy()
                messagebox.showerror("Error", f"API Error: {e}")
                return
            
            loading.destroy()
            
            if player_stats.empty:
                print("DEBUG: Player stats DataFrame is empty")
                messagebox.showinfo("Info", f"No box score data available for game {game_id}.")
                return
            
            # Create Modern Box Score Window
            bs_window = tk.Toplevel(self.root)
            bs_window.title(f"Box Score - {game_id}")
            bs_window.geometry("1200x950")
            bs_window.configure(bg=self.COLORS['bg_primary'])
            
            # Create scrollable canvas
            canvas = tk.Canvas(bs_window, bg=self.COLORS['bg_primary'], highlightthickness=0, bd=0)
            scrollbar = ttk.Scrollbar(bs_window, orient="vertical", command=canvas.yview)
            scrollable_frame = tk.Frame(canvas, bg=self.COLORS['bg_primary'])
            
            # Configure modern style for box score treeview
            style = ttk.Style()
            style.configure("BoxScore.Treeview", 
                          background=self.COLORS['bg_primary'],
                          foreground=self.COLORS['text_primary'],
                          fieldbackground=self.COLORS['bg_primary'],
                          rowheight=28,
                          font=('Segoe UI', 10))
            style.configure("BoxScore.Treeview.Heading",
                          background=self.COLORS['bg_elevated'],
                          foreground=self.COLORS['text_secondary'],
                          font=('Segoe UI', 9, 'bold'))
            style.map('BoxScore.Treeview',
                     background=[('selected', self.COLORS['accent_soft'])],
                     foreground=[('selected', self.COLORS['text_primary'])])
            
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            
            # Create window in canvas and keep reference to ID
            window_id = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            
            # Ensure frame expands to fill canvas width
            def on_canvas_configure(event):
                canvas.itemconfig(window_id, width=event.width)
            
            canvas.bind("<Configure>", on_canvas_configure)
            
            canvas.configure(yscrollcommand=scrollbar.set)
            
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            
            # Display Matchup Header - Modern style
            if not team_stats.empty:
                try:
                    team1 = team_stats.iloc[0]
                    team2 = team_stats.iloc[1]
                    
                    header_frame = tk.Frame(scrollable_frame, bg=self.COLORS['bg_primary'])
                    header_frame.pack(fill=tk.X, padx=32, pady=(24, 16))
                    
                    tk.Label(header_frame, text="BOX SCORE", bg=self.COLORS['bg_primary'], 
                            fg=self.COLORS['text_tertiary'], font=('Segoe UI', 9)).pack(anchor='w')
                    
                    score_text = f"{team1['TEAM_ABBREVIATION']} {team1['PTS']} - {team2['PTS']} {team2['TEAM_ABBREVIATION']}"
                    tk.Label(header_frame, text=score_text, bg=self.COLORS['bg_primary'], 
                            fg=self.COLORS['text_primary'], font=('Segoe UI', 24, 'bold')).pack(anchor='w', pady=(4, 0))
                except Exception:
                    pass # Skip header if data format is unexpected
            
            # Display Player Stats for each team
            if 'TEAM_ABBREVIATION' in player_stats.columns:
                teams_list = player_stats['TEAM_ABBREVIATION'].unique()
                
                for team_abbr in teams_list:
                    team_players = player_stats[player_stats['TEAM_ABBREVIATION'] == team_abbr].copy()
                    
                    # Sort by PRA (Points + Rebounds + Assists) then Minutes
                    try:
                        # Ensure numeric columns for calculation
                        calc_cols = ['PTS', 'REB', 'AST']
                        for col in calc_cols:
                            if col in team_players.columns:
                                team_players[col] = pd.to_numeric(team_players[col], errors='coerce').fillna(0)
                        
                        # Calculate PRA
                        pra_series = pd.Series(0, index=team_players.index)
                        if 'PTS' in team_players.columns: pra_series += team_players['PTS']
                        if 'REB' in team_players.columns: pra_series += team_players['REB']
                        if 'AST' in team_players.columns: pra_series += team_players['AST']
                        team_players['PRA'] = pra_series
                        
                        # Parse minutes for sorting
                        def parse_min(x):
                            try:
                                if pd.isna(x): return 0
                                if isinstance(x, str):
                                    if ':' in x:
                                        m, s = x.split(':')
                                        return float(m) + float(s)/60
                                    return float(x)
                                return float(x)
                            except:
                                return 0
                        
                        if 'MIN' in team_players.columns:
                            team_players['MIN_SORT'] = team_players['MIN'].apply(parse_min)
                        else:
                            team_players['MIN_SORT'] = 0
                        
                        # Sort
                        team_players = team_players.sort_values(by=['PRA', 'MIN_SORT'], ascending=[False, False])
                    except Exception as e:
                        print(f"DEBUG: Sorting error: {e}")
                    
                    # Team Header - Modern style
                    team_header = tk.Frame(scrollable_frame, bg=self.COLORS['bg_primary'])
                    team_header.pack(fill=tk.X, padx=32, pady=(16, 8))
                    tk.Label(team_header, text=f"{team_abbr}", bg=self.COLORS['bg_primary'], fg=self.COLORS['text_primary'],
                            font=('Segoe UI', 14, 'bold')).pack(anchor='w')
                    
                    # Create Treeview for team stats in a card
                    cols = ['PLAYER_NAME', 'MIN', 'PTS', 'REB', 'AST', 'STL', 'BLK', 'TO', 'PF', 'FGM', 'FGA', 'FG_PCT', 'FG3M', 'FG3A', 'FG3_PCT', 'FTM', 'FTA', 'FT_PCT', 'PLUS_MINUS']
                    
                    # Filter cols that exist
                    cols = [c for c in cols if c in player_stats.columns]
                    
                    tree_card = tk.Frame(scrollable_frame, bg=self.COLORS['bg_card'])
                    tree_card.pack(fill=tk.X, padx=32, pady=8)
                    
                    tree_inner = tk.Frame(tree_card, bg=self.COLORS['bg_card'])
                    tree_inner.pack(fill=tk.X, padx=16, pady=16)
                    
                    tree = ttk.Treeview(tree_inner, columns=cols, show='headings', 
                                      height=len(team_players), style="BoxScore.Treeview")
                    
                    # Configure columns
                    col_widths = {
                        'PLAYER_NAME': 150, 'MIN': 50, 'PTS': 40, 'REB': 40, 'AST': 40,
                        'STL': 40, 'BLK': 40, 'TO': 40, 'PF': 40,
                        'FGM': 40, 'FGA': 40, 'FG_PCT': 50,
                        'FG3M': 40, 'FG3A': 40, 'FG3_PCT': 50,
                        'FTM': 40, 'FTA': 40, 'FT_PCT': 50, 'PLUS_MINUS': 50
                    }
                    
                    for col in cols:
                        header = col.replace('PLAYER_NAME', 'Player').replace('FG_PCT', 'FG%').replace('FG3_PCT', '3P%').replace('FT_PCT', 'FT%').replace('PLUS_MINUS', '+/-')
                        tree.heading(col, text=header, anchor='center')
                        tree.column(col, width=col_widths.get(col, 50), anchor='center')
                    
                    if 'PLAYER_NAME' in cols:
                        tree.column('PLAYER_NAME', anchor='w')
                    
                    # Insert data
                    for _, row in team_players.iterrows():
                        vals = []
                        for col in cols:
                            val = row.get(col, '')
                            if col in ['FG_PCT', 'FG3_PCT', 'FT_PCT']:
                                try:
                                    vals.append(f"{float(val)*100:.1f}%" if val is not None else "")
                                except:
                                    vals.append(str(val))
                            elif col == 'MIN':
                                 vals.append(str(val))
                            else:
                                 vals.append(str(val))
                        tree.insert('', 'end', values=vals)
                    
                    tree.pack(fill=tk.X)
            else:
                error_frame = tk.Frame(scrollable_frame, bg=self.COLORS['bg_card'])
                error_frame.pack(fill=tk.X, padx=32, pady=16)
                tk.Label(error_frame, text="Player stats format not recognized", 
                        bg=self.COLORS['bg_card'], fg=self.COLORS['danger'],
                        font=('Segoe UI', 10), pady=20, padx=24).pack()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load box score: {str(e)}")


def main():
    root = tk.Tk()
    app = NBAStatsGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
