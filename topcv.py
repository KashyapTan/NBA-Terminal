import time
import tkinter as tk
from tkinter import ttk
import pandas as pd
import numpy as np
from nba_api.stats.static import teams
from nba_api.stats.endpoints import commonteamroster, playergamelog

# Game windows to analyze
GAME_WINDOWS = [5, 10, 15, 20]

# Stats to track
STATS_MAP = {
    'Points': 'PTS',
    'Rebounds': 'REB',
    'Assists': 'AST',
    'Steals': 'STL',
    'Blocks': 'BLK'
}

# Modern color palette (matching p.py)
COLORS = {
    'bg_primary': '#0f0f0f',
    'bg_card': '#1a1a1a',
    'bg_elevated': '#242424',
    'bg_hover': '#2a2a2a',
    'text_primary': '#ffffff',
    'text_secondary': '#8b8b8b',
    'text_tertiary': '#5c5c5c',
    'accent': '#6366f1',
    'accent_soft': '#4f46e5',
    'success': '#10b981',
    'warning': '#f59e0b',
    'danger': '#ef4444',
    'border': '#2a2a2a',
    'divider': '#1f1f1f',
}


def get_team_player_cvs(team_name, season):
    """
    Calculates the Coefficient of Variation (CV) for Points, Rebounds, Assists, Steals, and Blocks
    for all players on a given team for the last 5, 10, 15, and 20 games.
    
    Parameters:
    -----------
    team_name : str
        Name or abbreviation of the team (e.g., "Lakers", "LAL")
    season : str
        NBA season in format "YYYY-YY" (e.g., "2024-25")
        
    Returns:
    --------
    dict
        Dictionary containing player stats organized by game window
    """
    
    # 1. Find Team ID
    nba_teams = teams.get_teams()
    team_found = None
    for team in nba_teams:
        if team['full_name'].lower() == team_name.lower() or \
           team['abbreviation'].lower() == team_name.lower() or \
           team['nickname'].lower() == team_name.lower():
            team_found = team
            break
            
    if not team_found:
        print(f"Team '{team_name}' not found.")
        return None, None

    team_id = team_found['id']
    print(f"Fetching roster for {team_found['full_name']} ({season})...")

    # 2. Get Roster
    try:
        roster_endpoint = commonteamroster.CommonTeamRoster(team_id=team_id, season=season)
        roster_df = roster_endpoint.get_data_frames()[0]
    except Exception as e:
        print(f"Error fetching roster: {e}")
        return None, None

    # Structure: {window: {stat: [player_data]}}
    results = {window: {stat: [] for stat in STATS_MAP.keys()} for window in GAME_WINDOWS}
    
    print(f"Found {len(roster_df)} players. Fetching game logs...")
    
    # 3. Iterate through players and get stats
    for index, row in roster_df.iterrows():
        player_id = row['PLAYER_ID']
        player_name = row['PLAYER']
        
        # Add a small delay to avoid rate limiting
        time.sleep(0.6) 
        
        try:
            gamelog = playergamelog.PlayerGameLog(
                player_id=player_id, 
                season=season, 
                season_type_all_star='Regular Season'
            )
            games_df = gamelog.get_data_frames()[0]
            
            if games_df.empty:
                continue
            
            total_games = len(games_df)
            
            # Calculate CV for each game window
            for window in GAME_WINDOWS:
                if total_games < window:
                    continue  # Not enough games for this window
                
                # Get the last N games (games_df is already sorted most recent first)
                recent_games = games_df.head(window)
                
                for stat_name, col in STATS_MAP.items():
                    mean = recent_games[col].mean()
                    std = recent_games[col].std()
                    
                    if mean > 0 and std > 0:
                        cv = std / mean
                        
                        if not np.isnan(cv) and not np.isinf(cv):
                            results[window][stat_name].append({
                                'name': player_name,
                                'cv': cv,
                                'mean': mean,
                                'std': std,
                                'games': window
                            })
            
            print(f"Processed {player_name} ({total_games} games)")
            
        except Exception as e:
            print(f"Error processing {player_name}: {e}")

    # Sort all results by CV (ascending - lowest first = most consistent)
    for window in GAME_WINDOWS:
        for stat in STATS_MAP.keys():
            results[window][stat] = sorted(
                results[window][stat], 
                key=lambda x: x['cv'], 
                reverse=False
            )
    
    return results, team_found['full_name']


def show_cv_gui(results, team_name):
    """Display CV results in a modern minimalist GUI"""
    
    root = tk.Tk()
    root.title(f"CV Analysis • {team_name}")
    root.geometry("1100x850")
    root.configure(bg=COLORS['bg_primary'])
    
    # Configure ttk styles
    style = ttk.Style()
    style.theme_use('clam')
    style.configure('TFrame', background=COLORS['bg_primary'])
    style.configure('Card.TFrame', background=COLORS['bg_card'])
    style.configure('TScrollbar', background=COLORS['bg_card'], troughcolor=COLORS['bg_primary'],
                    bordercolor=COLORS['bg_primary'], arrowcolor=COLORS['text_secondary'])
    
    # Main scrollable canvas
    main_canvas = tk.Canvas(root, bg=COLORS['bg_primary'], highlightthickness=0, bd=0)
    scrollbar = ttk.Scrollbar(root, orient="vertical", command=main_canvas.yview)
    scrollable_frame = tk.Frame(main_canvas, bg=COLORS['bg_primary'])
    
    scrollable_frame.bind(
        "<Configure>",
        lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all"))
    )
    
    main_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    main_canvas.configure(yscrollcommand=scrollbar.set)
    
    def on_mousewheel(event):
        main_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    main_canvas.bind_all("<MouseWheel>", on_mousewheel)
    
    main_canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    
    # Content container
    content_frame = tk.Frame(scrollable_frame, bg=COLORS['bg_primary'])
    content_frame.pack(fill="both", expand=True, padx=32, pady=32)
    
    # ===== HERO SECTION =====
    hero_frame = tk.Frame(content_frame, bg=COLORS['bg_primary'])
    hero_frame.pack(fill="x", pady=(0, 32))
    
    tk.Label(hero_frame, text="COEFFICIENT OF VARIATION ANALYSIS", 
             bg=COLORS['bg_primary'], fg=COLORS['text_tertiary'], 
             font=('Segoe UI', 10, 'bold')).pack(anchor='w')
    
    tk.Label(hero_frame, text=team_name, 
             bg=COLORS['bg_primary'], fg=COLORS['text_primary'], 
             font=('Segoe UI', 28, 'bold')).pack(anchor='w', pady=(4, 0))
    
    tk.Label(hero_frame, text="Lower CV = More Consistent Performance", 
             bg=COLORS['bg_primary'], fg=COLORS['text_secondary'], 
             font=('Segoe UI', 12)).pack(anchor='w', pady=(2, 0))
    
    # State for current view
    current_stat = tk.StringVar(value='Points')
    current_window = tk.IntVar(value=10)
    
    # ===== FILTER SECTION =====
    filter_frame = tk.Frame(content_frame, bg=COLORS['bg_primary'])
    filter_frame.pack(fill="x", pady=(0, 24))
    
    # Stat selector
    stat_label_frame = tk.Frame(filter_frame, bg=COLORS['bg_primary'])
    stat_label_frame.pack(side='left')
    
    tk.Label(stat_label_frame, text="STAT", bg=COLORS['bg_primary'], fg=COLORS['text_tertiary'],
             font=('Segoe UI', 9, 'bold')).pack(anchor='w')
    
    stat_buttons_frame = tk.Frame(stat_label_frame, bg=COLORS['bg_primary'])
    stat_buttons_frame.pack(anchor='w', pady=(6, 0))
    
    # Game window selector
    window_label_frame = tk.Frame(filter_frame, bg=COLORS['bg_primary'])
    window_label_frame.pack(side='right')
    
    tk.Label(window_label_frame, text="GAME WINDOW", bg=COLORS['bg_primary'], fg=COLORS['text_tertiary'],
             font=('Segoe UI', 9, 'bold')).pack(anchor='e')
    
    window_buttons_frame = tk.Frame(window_label_frame, bg=COLORS['bg_primary'])
    window_buttons_frame.pack(anchor='e', pady=(6, 0))
    
    # Results display frame
    results_container = tk.Frame(content_frame, bg=COLORS['bg_primary'])
    results_container.pack(fill="both", expand=True)
    
    def update_display():
        """Update the results display based on current filters"""
        # Clear previous results
        for widget in results_container.winfo_children():
            widget.destroy()
        
        stat = current_stat.get()
        window = current_window.get()
        
        data = results.get(window, {}).get(stat, [])
        
        if not data:
            no_data_label = tk.Label(results_container, 
                                     text=f"No data available for Last {window} Games",
                                     bg=COLORS['bg_primary'], fg=COLORS['text_secondary'],
                                     font=('Segoe UI', 14))
            no_data_label.pack(pady=40)
            return
        
        # Create results card
        card = tk.Frame(results_container, bg=COLORS['bg_card'])
        card.pack(fill="x", pady=(0, 16))
        
        inner = tk.Frame(card, bg=COLORS['bg_card'])
        inner.pack(fill="x", padx=24, pady=20)
        
        # Card title
        title_frame = tk.Frame(inner, bg=COLORS['bg_card'])
        title_frame.pack(fill="x", pady=(0, 16))
        
        tk.Label(title_frame, text=f"TOP CONSISTENT PLAYERS • {stat.upper()} • LAST {window} GAMES",
                 bg=COLORS['bg_card'], fg=COLORS['text_secondary'],
                 font=('Segoe UI', 10, 'bold')).pack(side='left')
        
        player_count = len(data)
        tk.Label(title_frame, text=f"{player_count} players",
                 bg=COLORS['bg_card'], fg=COLORS['text_tertiary'],
                 font=('Segoe UI', 10)).pack(side='right')
        
        # Table header
        header_row = tk.Frame(inner, bg=COLORS['bg_card'])
        header_row.pack(fill="x", pady=(0, 12))
        
        headers = [('Rank', 6, 'w'), ('Player', 22, 'w'), ('CV %', 10, 'center'), 
                   ('Mean', 10, 'center'), ('Std Dev', 10, 'center'), ('Consistency', 14, 'e')]
        for header, width, anchor in headers:
            tk.Label(header_row, text=header, bg=COLORS['bg_card'], fg=COLORS['text_tertiary'],
                     font=('Segoe UI', 10, 'bold'), width=width, anchor=anchor).pack(side='left', padx=4)
        
        # Divider
        tk.Frame(inner, bg=COLORS['divider'], height=1).pack(fill='x', pady=(0, 8))
        
        # Data rows (top 10)
        for i, player in enumerate(data[:10], 1):
            cv_percent = player['cv'] * 100
            
            # Determine consistency rating and color
            if cv_percent < 30:
                consistency = "Elite"
                row_accent = COLORS['success']
            elif cv_percent < 50:
                consistency = "Good"
                row_accent = COLORS['accent']
            elif cv_percent < 70:
                consistency = "Average"
                row_accent = COLORS['warning']
            else:
                consistency = "Variable"
                row_accent = COLORS['danger']
            
            # Alternate row backgrounds
            row_bg = COLORS['bg_card'] if i % 2 == 1 else COLORS['bg_elevated']
            
            row = tk.Frame(inner, bg=row_bg)
            row.pack(fill="x", pady=4)
            
            # Rank with accent bar
            rank_frame = tk.Frame(row, bg=row_bg)
            rank_frame.pack(side='left', padx=4)
            
            if i <= 3:
                rank_color = COLORS['accent'] if i == 1 else (COLORS['success'] if i == 2 else COLORS['warning'])
            else:
                rank_color = COLORS['text_tertiary']
            
            tk.Label(rank_frame, text=f"#{i}", bg=row_bg, fg=rank_color,
                     font=('Segoe UI', 11, 'bold'), width=6, anchor='w').pack(side='left')
            
            # Player name
            tk.Label(row, text=player['name'], bg=row_bg, fg=COLORS['text_primary'],
                     font=('Segoe UI', 11), width=22, anchor='w').pack(side='left', padx=4)
            
            # CV %
            tk.Label(row, text=f"{cv_percent:.1f}%", bg=row_bg, fg=row_accent,
                     font=('Segoe UI', 11, 'bold'), width=10, anchor='center').pack(side='left', padx=4)
            
            # Mean
            tk.Label(row, text=f"{player['mean']:.1f}", bg=row_bg, fg=COLORS['text_secondary'],
                     font=('Segoe UI', 11), width=10, anchor='center').pack(side='left', padx=4)
            
            # Std Dev
            tk.Label(row, text=f"{player['std']:.1f}", bg=row_bg, fg=COLORS['text_secondary'],
                     font=('Segoe UI', 11), width=10, anchor='center').pack(side='left', padx=4)
            
            # Consistency rating
            tk.Label(row, text=consistency, bg=row_bg, fg=row_accent,
                     font=('Segoe UI', 11, 'bold'), width=14, anchor='e').pack(side='left', padx=4)
        
        # Summary section
        tk.Frame(inner, bg=COLORS['divider'], height=1).pack(fill='x', pady=(16, 12))
        
        summary_frame = tk.Frame(inner, bg=COLORS['bg_card'])
        summary_frame.pack(fill="x")
        
        # Calculate summary stats
        if data:
            avg_cv = np.mean([p['cv'] for p in data]) * 100
            min_cv = min([p['cv'] for p in data]) * 100
            most_consistent = data[0]['name'] if data else "N/A"
            
            tk.Label(summary_frame, text=f"Most Consistent: {most_consistent}",
                     bg=COLORS['bg_card'], fg=COLORS['text_secondary'],
                     font=('Segoe UI', 10)).pack(side='left')
            
            tk.Label(summary_frame, text=f"Avg CV: {avg_cv:.1f}%  •  Best CV: {min_cv:.1f}%",
                     bg=COLORS['bg_card'], fg=COLORS['text_tertiary'],
                     font=('Segoe UI', 10)).pack(side='right')
    
    def create_filter_button(parent, text, variable, value, is_stat=True):
        """Create a styled filter button"""
        def on_click():
            if is_stat:
                current_stat.set(value)
            else:
                current_window.set(value)
            update_all_buttons()
            update_display()
        
        def get_colors():
            is_active = (variable.get() == value)
            if is_active:
                return COLORS['accent'], COLORS['text_primary']
            else:
                return COLORS['bg_elevated'], COLORS['text_secondary']
        
        bg, fg = get_colors()
        btn = tk.Label(parent, text=text, bg=bg, fg=fg,
                       font=('Segoe UI', 10, 'bold'), padx=16, pady=8, cursor='hand2')
        btn.pack(side='left', padx=(0, 6))
        btn.bind('<Button-1>', lambda e: on_click())
        
        # Store reference for updates
        btn._variable = variable
        btn._value = value
        btn._get_colors = get_colors
        
        return btn
    
    stat_buttons = []
    window_buttons = []
    
    def update_all_buttons():
        """Update all button colors based on current selection"""
        for btn in stat_buttons + window_buttons:
            bg, fg = btn._get_colors()
            btn.configure(bg=bg, fg=fg)
    
    # Create stat buttons
    for stat in STATS_MAP.keys():
        btn = create_filter_button(stat_buttons_frame, stat, current_stat, stat, is_stat=True)
        stat_buttons.append(btn)
    
    # Create window buttons
    for window in GAME_WINDOWS:
        btn = create_filter_button(window_buttons_frame, f"Last {window}", current_window, window, is_stat=False)
        window_buttons.append(btn)
    
    # Initial display
    update_display()
    
    # ===== FOOTER =====
    footer = tk.Frame(content_frame, bg=COLORS['bg_primary'])
    footer.pack(fill="x", pady=(24, 0))
    
    close_btn = tk.Button(footer, text="Close", command=root.destroy,
                          bg=COLORS['bg_elevated'], fg=COLORS['text_secondary'],
                          font=('Segoe UI', 10), padx=24, pady=10,
                          relief=tk.FLAT, cursor='hand2', bd=0,
                          activebackground=COLORS['bg_hover'],
                          activeforeground=COLORS['text_primary'])
    close_btn.pack()
    
    # Center window
    root.update_idletasks()
    x = (root.winfo_screenwidth() // 2) - (1100 // 2)
    y = (root.winfo_screenheight() // 2) - (850 // 2)
    root.geometry(f"1100x850+{x}+{y}")
    
    root.mainloop()


if __name__ == "__main__":
    # Get user input
    team = input("Enter team name or abbreviation (e.g., 'Lakers' or 'LAL'): ")
    season = "2025-26"
    
    # Fetch and calculate CV data
    results, team_name = get_team_player_cvs(team, season)
    
    if results and team_name:
        print("\nLaunching GUI...")
        show_cv_gui(results, team_name)
    else:
        print("Failed to retrieve data.")
