"""
NBA Player Game Log Module

This module provides functions to fetch detailed game-by-game logs
for NBA players using the nba_api library.
"""

from nba_api.stats.static import players
from nba_api.stats.endpoints import playergamelog
import pandas as pd

VALID_SEASON_TYPES = {
    "regular season": "Regular Season",
    "playoffs": "Playoffs",
}


def _normalize_season_type(season_type):
    normalized = VALID_SEASON_TYPES.get(str(season_type).strip().lower())
    if normalized:
        return normalized
    valid_values = ", ".join(sorted(set(VALID_SEASON_TYPES.values())))
    raise ValueError(f"Invalid season type '{season_type}'. Use one of: {valid_values}.")


def get_player_game_log(player_name, season, season_type='Regular Season'):
    """
    Get a player's complete game log for a season.
    
    Parameters:
    -----------
    player_name : str
        Full name of the player (e.g., "LeBron James")
    season : str
        NBA season in format "YYYY-YY" (e.g., "2023-24")
    season_type : str, optional
        Data scope to fetch. Supported values: "Regular Season", "Playoffs".
    
    Returns:
    --------
    pandas.DataFrame
        DataFrame containing all games with columns like:
        - Game_ID, GAME_DATE, MATCHUP (home/away and opponent)
        - WL (Win/Loss), MIN (minutes played)
        - PTS, REB, AST, STL, BLK, TOV
        - FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT
        - FTM, FTA, FT_PCT, PLUS_MINUS
    
    Example:
    --------
    >>> df = get_player_game_log("Stephen Curry", "2023-24")
    >>> print(df[['GAME_DATE', 'MATCHUP', 'PTS', 'AST', 'REB']].head())
    """
    # Find player by name
    player_list = players.find_players_by_full_name(player_name)
    
    if not player_list:
        raise ValueError(f"Player '{player_name}' not found")
    
    if len(player_list) > 1:
        raise ValueError(f"Multiple players found for '{player_name}': {player_list}")
    
    player_id = player_list[0]['id']
    season_type = _normalize_season_type(season_type)
    
    # Get game log for the season
    gamelog = playergamelog.PlayerGameLog(
        player_id=player_id,
        season=season,
        season_type_all_star=season_type
    )
    
    # Convert to dataframe
    df = gamelog.get_data_frames()[0]
    
    if df.empty:
        raise ValueError(f"No games found for {player_name} in {season} ({season_type})")
    
    return df


def print_player_game_log(player_name, season, last_n_games=None, season_type='Regular Season'):
    """
    Print a formatted game log for a player.
    
    Parameters:
    -----------
    player_name : str
        Full name of the player
    season : str
        NBA season in format "YYYY-YY"
    last_n_games : int, optional
        If specified, only show the last N games
    
    Example:
    --------
    >>> print_player_game_log("LeBron James", "2023-24", last_n_games=10)
    """
    try:
        df = get_player_game_log(player_name, season, season_type=season_type)
        
        if last_n_games:
            df = df.head(last_n_games)
        
        print(f"\n{'='*100}")
        print(f"{player_name} - {season} ({season_type}) Game Log")
        print(f"{'='*100}")
        print(f"Total Games: {len(df)}\n")
        
        # Select key columns to display
        display_cols = ['GAME_DATE', 'MATCHUP', 'WL', 'MIN', 'PTS', 'REB', 'AST', 'STL', 'BLK', 'FG3M', 'PLUS_MINUS']
        
        # Check which columns exist in the dataframe
        available_cols = [col for col in display_cols if col in df.columns]
        
        # Print header
        header = ""
        for col in available_cols:
            if col == 'GAME_DATE':
                header += f"{col:<12} "
            elif col == 'MATCHUP':
                header += f"{col:<15} "
            elif col == 'WL':
                header += f"{col:<3} "
            elif col == 'MIN':
                header += f"{col:<6} "
            else:
                header += f"{col:>6} "
        print(header)
        print("-" * 100)
        
        # Print each game
        for _, row in df.iterrows():
            line = ""
            for col in available_cols:
                value = row[col]
                if col == 'GAME_DATE':
                    line += f"{str(value):<12} "
                elif col == 'MATCHUP':
                    line += f"{str(value):<15} "
                elif col == 'WL':
                    line += f"{str(value):<3} "
                elif col == 'MIN':
                    # Handle minutes (could be float or string)
                    try:
                        mins = float(value) if value else 0
                        line += f"{mins:>6.0f} "
                    except:
                        line += f"{str(value):>6} "
                else:
                    # Numeric columns
                    try:
                        num_val = float(value) if value else 0
                        line += f"{num_val:>6.0f} "
                    except:
                        line += f"{str(value):>6} "
            print(line)
        
        print(f"\n{'='*100}\n")
        
    except ValueError as e:
        print(f"Error: {e}")


def get_game_log_summary(player_name, season, season_type='Regular Season'):
    """
    Get a summary dictionary of the game log for easy access.
    
    Parameters:
    -----------
    player_name : str
        Full name of the player
    season : str
        NBA season in format "YYYY-YY"
    
    Returns:
    --------
    dict
        Dictionary containing:
        - 'dataframe': Full game log DataFrame
        - 'total_games': Total number of games
        - 'wins': Number of wins
        - 'losses': Number of losses
        - 'home_games': Number of home games
        - 'away_games': Number of away games
    """
    df = get_player_game_log(player_name, season, season_type=season_type)
    
    summary = {
        'dataframe': df,
        'total_games': len(df),
        'wins': len(df[df['WL'] == 'W']) if 'WL' in df.columns else 0,
        'losses': len(df[df['WL'] == 'L']) if 'WL' in df.columns else 0,
        'home_games': len(df[df['MATCHUP'].str.contains('vs.', na=False)]) if 'MATCHUP' in df.columns else 0,
        'away_games': len(df[df['MATCHUP'].str.contains('@', na=False)]) if 'MATCHUP' in df.columns else 0,
    }
    
    return summary


if __name__ == "__main__":
    # Example usage
    player = 'James Harden'
    season = '2024-25'
    
    print(f"Fetching game log for {player} - {season} season...")
    
    # Get and print last 10 games
    print_player_game_log(player, season, last_n_games=10)
    
    # Get full game log
    try:
        df = get_player_game_log(player, season)
        print(f"\nFull game log retrieved: {len(df)} games")
        print(f"\nAvailable columns:")
        print(df.columns.tolist())
        
        # Show summary
        summary = get_game_log_summary(player, season)
        print(f"\nSummary:")
        print(f"Total Games: {summary['total_games']}")
        print(f"Wins: {summary['wins']}")
        print(f"Losses: {summary['losses']}")
        print(f"Home Games: {summary['home_games']}")
        print(f"Away Games: {summary['away_games']}")
    except Exception as e:
        print(f"Error: {e}")
