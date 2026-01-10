"""
Zone Stats Test - Displays all NBA teams' defensive zone stats
Shows opponent FG% allowed by zone, overall opponent FG%, and opponent 3PT FG%
All data sorted in ascending order (best defense first)
"""

import tkinter as tk
from tkinter import ttk
from nba_api.stats.endpoints import leaguedashteamshotlocations, leaguedashteamstats
from nba_api.stats.static import teams
import pandas as pd
import numpy as np

SEASON = "2025-26"

def fetch_all_stats():
    """Fetch zone stats and overall opponent stats for all teams"""
    print("Fetching team defense stats...")
    
    # Get team ID to abbreviation mapping
    nba_teams = teams.get_teams()
    id_to_info = {t['id']: {'abbrev': t['abbreviation'], 'name': t['full_name']} for t in nba_teams}
    
    # 1. Fetch overall opponent stats (FG%, 3PT%)
    print("  → Fetching overall opponent stats...")
    opp_stats = leaguedashteamstats.LeagueDashTeamStats(
        season=SEASON,
        measure_type_detailed_defense='Opponent',
        per_mode_detailed='PerGame'
    )
    opp_df = opp_stats.get_data_frames()[0]
    
    # 2. Fetch zone stats using correct endpoint
    print("  → Fetching zone defense stats...")
    shot_locs = leaguedashteamshotlocations.LeagueDashTeamShotLocations(
        season=SEASON,
        per_mode_detailed='PerGame',
        distance_range='By Zone',
        measure_type_simple='Opponent'
    )
    zone_df = shot_locs.get_data_frames()[0]
    
    # Process data for each team
    all_teams_data = []
    
    for _, opp_row in opp_df.iterrows():
        team_id = opp_row['TEAM_ID']
        if team_id not in id_to_info:
            continue
            
        team_info = id_to_info[team_id]
        
        # Get overall stats
        overall_fg_pct = opp_row['OPP_FG_PCT']
        overall_fg3_pct = opp_row['OPP_FG3_PCT']
        
        # Find zone stats for this team
        zone_row = zone_df[zone_df.iloc[:, 0] == team_id]
        
        zone_stats = {}
        if not zone_row.empty:
            zone_row = zone_row.iloc[0]
            for col in zone_df.columns:
                if len(col) == 2:
                    zone_name, stat_type = str(col[0]), str(col[1])
                    if stat_type == 'OPP_FG_PCT' and zone_name not in ['', 'Backcourt']:
                        zone_stats[zone_name] = zone_row[col]
        
        # Combine corner 3s
        corner_3_pct = None
        if 'Left Corner 3' in zone_stats and 'Right Corner 3' in zone_stats:
            corner_3_pct = (zone_stats['Left Corner 3'] + zone_stats['Right Corner 3']) / 2
        
        all_teams_data.append({
            'Team': team_info['abbrev'],
            'Full Name': team_info['name'],
            'OPP_FG_PCT': overall_fg_pct,
            'OPP_FG3_PCT': overall_fg3_pct,
            'Restricted Area': zone_stats.get('Restricted Area', 0),
            'In The Paint (Non-RA)': zone_stats.get('In The Paint (Non-RA)', 0),
            'Mid-Range': zone_stats.get('Mid-Range', 0),
            'Corner 3': corner_3_pct if corner_3_pct else zone_stats.get('Corner 3', 0),
            'Above the Break 3': zone_stats.get('Above the Break 3', 0)
        })
    
    print(f"  → Fetched stats for {len(all_teams_data)} teams")
    return all_teams_data


def create_gui(all_teams_data):
    """Create a nice GUI to display the stats"""
    
    root = tk.Tk()
    root.title(f"NBA Team Defense Stats - {SEASON}")
    root.geometry("1400x900")
    root.configure(bg='#0a0a0a')
    
    # Style configuration
    style = ttk.Style()
    style.theme_use('clam')
    style.configure('Title.TLabel', font=('Arial', 18, 'bold'), foreground='#00d9ff', background='#0a0a0a')
    style.configure('Subtitle.TLabel', font=('Arial', 11), foreground='#888888', background='#0a0a0a')
    style.configure('Treeview', background='#1a1a1a', foreground='#ffffff', fieldbackground='#1a1a1a', 
                    font=('Consolas', 10), rowheight=28)
    style.configure('Treeview.Heading', background='#2a2a2a', foreground='#00d9ff', 
                    font=('Arial', 10, 'bold'))
    style.map('Treeview', background=[('selected', '#00d9ff')], foreground=[('selected', '#000000')])
    
    # Main frame
    main_frame = tk.Frame(root, bg='#0a0a0a')
    main_frame.pack(fill='both', expand=True, padx=20, pady=20)
    
    # Title
    title_frame = tk.Frame(main_frame, bg='#0a0a0a')
    title_frame.pack(fill='x', pady=(0, 5))
    
    ttk.Label(title_frame, text="🏀 NBA TEAM DEFENSE STATS", style='Title.TLabel').pack()
    ttk.Label(title_frame, text=f"Opponent FG% Allowed by Zone | Season {SEASON} | Sorted by Overall OPP FG% (Best → Worst)", 
              style='Subtitle.TLabel').pack(pady=(5, 0))
    
    # Legend
    legend_frame = tk.Frame(main_frame, bg='#1a1a1a', pady=10, padx=15)
    legend_frame.pack(fill='x', pady=(10, 15))
    
    legend_items = [
        ("🟢 Elite (Top 5)", "#00ff88"),
        ("🔵 Good (6-15)", "#00d9ff"),
        ("⚪ Average (16-20)", "#ffffff"),
        ("🟡 Below Avg (21-25)", "#ffcc00"),
        ("🔴 Poor (26-30)", "#ff4444")
    ]
    
    for text, color in legend_items:
        tk.Label(legend_frame, text=text, bg='#1a1a1a', fg=color, font=('Arial', 9)).pack(side='left', padx=15)
    
    # Sort data by overall OPP_FG_PCT (ascending - best defense first)
    sorted_data = sorted(all_teams_data, key=lambda x: x['OPP_FG_PCT'])
    
    # Create treeview
    columns = ('Rank', 'Team', 'OPP FG%', 'OPP 3P%', 'Rest. Area', 'Paint', 'Mid-Range', 'Corner 3', 'Above Break 3')
    
    tree_frame = tk.Frame(main_frame, bg='#0a0a0a')
    tree_frame.pack(fill='both', expand=True)
    
    tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=30)
    
    # Configure columns
    col_widths = [50, 80, 90, 90, 100, 100, 100, 100, 110]
    for col, width in zip(columns, col_widths):
        tree.heading(col, text=col)
        tree.column(col, width=width, anchor='center')
    
    # Scrollbar
    scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    
    tree.pack(side='left', fill='both', expand=True)
    scrollbar.pack(side='right', fill='y')
    
    # Insert data
    for rank, team in enumerate(sorted_data, 1):
        values = (
            rank,
            team['Team'],
            f"{team['OPP_FG_PCT']:.1%}",
            f"{team['OPP_FG3_PCT']:.1%}",
            f"{team['Restricted Area']:.1%}",
            f"{team['In The Paint (Non-RA)']:.1%}",
            f"{team['Mid-Range']:.1%}",
            f"{team['Corner 3']:.1%}",
            f"{team['Above the Break 3']:.1%}"
        )
        
        # Determine tag based on rank
        if rank <= 5:
            tag = 'elite'
        elif rank <= 15:
            tag = 'good'
        elif rank <= 20:
            tag = 'average'
        elif rank <= 25:
            tag = 'below'
        else:
            tag = 'poor'
        
        tree.insert('', 'end', values=values, tags=(tag,))
    
    # Configure tags for coloring
    tree.tag_configure('elite', background='#0d2818', foreground='#00ff88')
    tree.tag_configure('good', background='#0d1f28', foreground='#00d9ff')
    tree.tag_configure('average', background='#1a1a1a', foreground='#ffffff')
    tree.tag_configure('below', background='#28250d', foreground='#ffcc00')
    tree.tag_configure('poor', background='#280d0d', foreground='#ff4444')
    
    # Stats summary at bottom
    summary_frame = tk.Frame(main_frame, bg='#1a1a1a', pady=10, padx=15)
    summary_frame.pack(fill='x', pady=(15, 0))
    
    # Calculate league averages
    avg_fg = np.mean([t['OPP_FG_PCT'] for t in all_teams_data])
    avg_fg3 = np.mean([t['OPP_FG3_PCT'] for t in all_teams_data])
    avg_ra = np.mean([t['Restricted Area'] for t in all_teams_data])
    avg_paint = np.mean([t['In The Paint (Non-RA)'] for t in all_teams_data])
    avg_mid = np.mean([t['Mid-Range'] for t in all_teams_data])
    
    tk.Label(summary_frame, text="LEAGUE AVERAGES:", bg='#1a1a1a', fg='#00d9ff', 
             font=('Arial', 10, 'bold')).pack(side='left', padx=(0, 20))
    
    avgs = [
        f"OPP FG%: {avg_fg:.1%}",
        f"OPP 3P%: {avg_fg3:.1%}",
        f"Rest. Area: {avg_ra:.1%}",
        f"Paint: {avg_paint:.1%}",
        f"Mid-Range: {avg_mid:.1%}"
    ]
    
    for avg in avgs:
        tk.Label(summary_frame, text=avg, bg='#1a1a1a', fg='#ffffff', 
                 font=('Arial', 10)).pack(side='left', padx=15)
    
    # Close button
    close_btn = tk.Button(main_frame, text="Close", command=root.destroy,
                          bg='#e74c3c', fg='white', font=('Arial', 11, 'bold'),
                          padx=30, pady=8, relief=tk.FLAT, cursor='hand2')
    close_btn.pack(pady=(15, 0))
    
    # Center window
    root.update_idletasks()
    x = (root.winfo_screenwidth() // 2) - (1400 // 2)
    y = (root.winfo_screenheight() // 2) - (900 // 2)
    root.geometry(f"1400x900+{x}+{y}")
    
    root.mainloop()


if __name__ == "__main__":
    print("=" * 60)
    print(f"NBA ZONE DEFENSE STATS TEST - {SEASON}")
    print("=" * 60)
    
    try:
        data = fetch_all_stats()
        
        # Print to console as well
        print("\n" + "=" * 100)
        print(f"{'Rank':<5} {'Team':<5} {'OPP FG%':<10} {'OPP 3P%':<10} {'Rest.Area':<10} {'Paint':<10} {'Mid':<10} {'Corner3':<10} {'Above3':<10}")
        print("-" * 100)
        
        sorted_data = sorted(data, key=lambda x: x['OPP_FG_PCT'])
        for rank, team in enumerate(sorted_data, 1):
            print(f"{rank:<5} {team['Team']:<5} {team['OPP_FG_PCT']:.1%}      {team['OPP_FG3_PCT']:.1%}      "
                  f"{team['Restricted Area']:.1%}     {team['In The Paint (Non-RA)']:.1%}     "
                  f"{team['Mid-Range']:.1%}     {team['Corner 3']:.1%}     {team['Above the Break 3']:.1%}")
        
        print("=" * 100)
        print("\nLaunching GUI...")
        create_gui(data)
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
