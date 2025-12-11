import time
import pandas as pd
import numpy as np
from nba_api.stats.static import teams
from nba_api.stats.endpoints import commonteamroster, playergamelog

def get_team_player_cvs(team_name, season):
    """
    Calculates the Coefficient of Variation (CV) for Points, Rebounds, Assists, Steals, and Blocks
    for all players on a given team for a specific season.
    
    Parameters:
    -----------
    team_name : str
        Name or abbreviation of the team (e.g., "Lakers", "LAL")
    season : str
        NBA season in format "YYYY-YY" (e.g., "2024-25")
        
    Returns:
    --------
    None
        Prints the sorted lists of players by CV for each stat.
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
        return

    team_id = team_found['id']
    print(f"Fetching roster for {team_found['full_name']} ({season})...")

    # 2. Get Roster
    try:
        roster_endpoint = commonteamroster.CommonTeamRoster(team_id=team_id, season=season)
        roster_df = roster_endpoint.get_data_frames()[0]
    except Exception as e:
        print(f"Error fetching roster: {e}")
        return

    player_stats = []
    
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
                
            # Calculate stats
            stats_map = {
                'Points': 'PTS',
                'Rebounds': 'REB',
                'Assists': 'AST',
                'Steals': 'STL',
                'Blocks': 'BLK'
            }
            
            p_data = {'name': player_name, 'games': len(games_df)}
            
            for stat_name, col in stats_map.items():
                mean = games_df[col].mean()
                std = games_df[col].std()
                
                if mean > 0:
                    cv = std / mean
                else:
                    cv = 0.0 # Or handle as infinity/NaN if preferred, but 0 implies no variation (or no stats)
                    
                p_data[stat_name] = {
                    'mean': mean,
                    'std': std,
                    'cv': cv
                }
            
            player_stats.append(p_data)
            print(f"Processed {player_name}")
            
        except Exception as e:
            print(f"Error processing {player_name}: {e}")

    # 4. Display results
    stats_to_display = ['Points', 'Rebounds', 'Assists', 'Steals', 'Blocks']
    
    for stat in stats_to_display:
        print(f"\n{'='*20}")
        print(f"Top CV for {stat} (Ascending)")
        print(f"{'='*20}")
        print(f"{'Player':<25} | {'CV %':<6} | {'Mean':<6} | {'Std Dev':<6} | {'Games':<5}")
        print("-" * 60)
        
        # Filter out players with 0, NaN, or infinite CV first
        valid_players = [
            p for p in player_stats 
            if p[stat]['cv'] > 0 and not np.isnan(p[stat]['cv']) and not np.isinf(p[stat]['cv'])
        ]
        
        # Sort by CV ascending (lowest CV first)
        sorted_players = sorted(valid_players, key=lambda x: x[stat]['cv'], reverse=False)
        
        # Display top 5 lowest CVs
        for p in sorted_players[:5]:
            s_info = p[stat]
            cv_percent = s_info['cv'] * 100
            print(f"{p['name']:<25} | {cv_percent:<6.2f} | {s_info['mean']:<6.2f} | {s_info['std']:<6.2f} | {p['games']:<5}")

if __name__ == "__main__":
    # Example usage
    team = input("Enter team name or abbreviation (e.g., 'Lakers' or 'LAL'): ")
    season = "2025-26"
    get_team_player_cvs(team, season)
