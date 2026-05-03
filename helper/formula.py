"""
NBA Player Statistics Module

This module provides functions to fetch and analyze NBA player statistics
using the nba_api library.
"""

import numpy as np
from nba_api.stats.static import players, teams
from nba_api.stats.endpoints import playergamelog

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


def get_player_season_stats(player_name, season, season_type='Regular Season'):
    """
    Get a player's average stats and standard deviations for a season.
    
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
    dict
        Dictionary containing:
        - 'averages': dict with avg points, rebounds, assists, blocks, steals
        - 'std_devs': dict with std dev for each stat
        - 'games_played': int number of games
    
    Example:
    --------
    >>> stats = get_player_season_stats("Stephen Curry", "2023-24")
    >>> print(f"Points: {stats['averages']['points']:.1f} ± {stats['std_devs']['points']:.1f}")
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
    
    # Calculate stats
    stats = {
        'averages': {
            'points': df['PTS'].mean(),
            'rebounds': df['REB'].mean(),
            'assists': df['AST'].mean(),
            'blocks': df['BLK'].mean(),
            'steals': df['STL'].mean(),
            '3pt': df['FG3M'].mean()
        },
        'std_devs': {
            'points': df['PTS'].std(),
            'rebounds': df['REB'].std(),
            'assists': df['AST'].std(),
            'blocks': df['BLK'].std(),
            'steals': df['STL'].std(),
            '3pt': df['FG3M'].std()
        },
        'games_played': len(df)
    }
    
    return stats


def get_player_vs_team_stats(player_name, season, opponent_team, season_type='Regular Season'):
    """
    Get a player's average stats and standard deviations vs a specific team.
    
    Parameters:
    -----------
    player_name : str
        Full name of the player (e.g., "LeBron James")
    season : str
        NBA season in format "YYYY-YY" (e.g., "2023-24")
    opponent_team : str
        Team name, nickname, or abbreviation (e.g., "Lakers", "LAL", "Los Angeles Lakers")
    season_type : str, optional
        Data scope to fetch. Supported values: "Regular Season", "Playoffs".
    
    Returns:
    --------
    dict
        Dictionary containing:
        - 'averages': dict with avg points, rebounds, assists, blocks, steals
        - 'std_devs': dict with std dev for each stat
        - 'games_played': int number of games against this opponent
    
    Example:
    --------
    >>> stats = get_player_vs_team_stats("Stephen Curry", "2023-24", "Lakers")
    >>> print(f"Points vs Lakers: {stats['averages']['points']:.1f}")
    """
    # Find player by name
    player_list = players.find_players_by_full_name(player_name)
    
    if not player_list:
        raise ValueError(f"Player '{player_name}' not found")
    
    if len(player_list) > 1:
        raise ValueError(f"Multiple players found for '{player_name}': {player_list}")
    
    player_id = player_list[0]['id']
    season_type = _normalize_season_type(season_type)
    
    # Find opponent team - try multiple search methods
    team_list = None
    
    # Try by abbreviation first (most specific)
    if len(opponent_team) <= 3:
        team_obj = teams.find_team_by_abbreviation(opponent_team.upper())
        if team_obj:
            team_list = [team_obj]
    
    # Try by full name before nickname (more specific)
    if not team_list:
        team_list = teams.find_teams_by_full_name(opponent_team)
    
    # Try by nickname last (can match multiple teams)
    if not team_list:
        team_list = teams.find_teams_by_nickname(opponent_team)
        # If nickname search returns multiple results, filter by checking if the nickname matches exactly
        if team_list and len(team_list) > 1:
            exact_matches = [t for t in team_list if t['nickname'].lower() == opponent_team.lower()]
            if exact_matches:
                team_list = exact_matches
    
    if not team_list:
        raise ValueError(f"Team '{opponent_team}' not found")
    
    if len(team_list) > 1:
        # Provide helpful error message with team abbreviations
        team_info = [f"{t['full_name']} ({t['abbreviation']})" for t in team_list]
        raise ValueError(f"Multiple teams found for '{opponent_team}': {', '.join(team_info)}. Please use team abbreviation instead.")
    
    opponent_abbrev = team_list[0]['abbreviation']
    
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
    
    # Filter for games vs opponent team (MATCHUP column contains "vs OPP" or "@ OPP")
    df_vs_team = df[df['MATCHUP'].str.contains(opponent_abbrev, case=False, na=False)]
    
    if df_vs_team.empty:
        raise ValueError(f"No games found for {player_name} vs {opponent_team} in {season} ({season_type})")
    
    # Calculate stats
    stats = {
        'averages': {
            'points': df_vs_team['PTS'].mean(),
            'rebounds': df_vs_team['REB'].mean(),
            'assists': df_vs_team['AST'].mean(),
            'blocks': df_vs_team['BLK'].mean(),
            'steals': df_vs_team['STL'].mean(),
            '3pt': df_vs_team['FG3M'].mean()
        },
        'std_devs': {
            'points': df_vs_team['PTS'].std(),
            'rebounds': df_vs_team['REB'].std(),
            'assists': df_vs_team['AST'].std(),
            'blocks': df_vs_team['BLK'].std(),
            'steals': df_vs_team['STL'].std(),
            '3pt': df_vs_team['FG3M'].std()
        },
        'games_played': len(df_vs_team)
    }
    
    return stats

def print_player_season_stats(player, season, season_type='Regular Season'):
    try:
        stats = get_player_season_stats(player, season, season_type=season_type)
        print(f"Stats for {player} in {season} ({season_type}):")
        print(f"Games Played: {stats['games_played']}")
        print(f"Points: {stats['averages']['points']:.1f} ± {stats['std_devs']['points']:.1f} | CV: {100 * (stats['std_devs']['points']/stats['averages']['points']) if stats['averages']['points'] > 0 else 0:.2f}")
        print(f"Rebounds: {stats['averages']['rebounds']:.1f} ± {stats['std_devs']['rebounds']:.1f} | CV: {100 * (stats['std_devs']['rebounds']/stats['averages']['rebounds']) if stats['averages']['rebounds'] > 0 else 0:.2f}")
        print(f"Assists: {stats['averages']['assists']:.1f} ± {stats['std_devs']['assists']:.1f} | CV: {100 * (stats['std_devs']['assists']/stats['averages']['assists']) if stats['averages']['assists'] > 0 else 0:.2f}")
        print(f"Blocks: {stats['averages']['blocks']:.1f} ± {stats['std_devs']['blocks']:.1f} | CV: {100 * (stats['std_devs']['blocks']/stats['averages']['blocks']) if stats['averages']['blocks'] > 0 else 0:.2f}")
        print(f"Steals: {stats['averages']['steals']:.1f} ± {stats['std_devs']['steals']:.1f} | CV: {100 * (stats['std_devs']['steals']/stats['averages']['steals']) if stats['averages']['steals'] > 0 else 0:.2f}")
        print(f"3PT: {stats['averages']['3pt']:.1f} ± {stats['std_devs']['3pt']:.1f} | CV: {100 * (stats['std_devs']['3pt']/stats['averages']['3pt']) if stats['averages']['3pt'] > 0 else 0:.2f}")
    except ValueError as e:
        print(f"Error: {e}")

def print_player_vs_team_stats(player, season, opponent, season_type='Regular Season'):
    try:
        stats = get_player_vs_team_stats(player, season, opponent, season_type=season_type)
        print(f"Stats for {player} vs {opponent} in {season} ({season_type}):")
        print(f"Games Played: {stats['games_played']}")
        print(f"Points: {stats['averages']['points']:.1f} ± {stats['std_devs']['points']:.1f} | CV: {100 * (stats['std_devs']['points']/stats['averages']['points']) if stats['averages']['points'] > 0 else 0:.2f}")
        print(f"Rebounds: {stats['averages']['rebounds']:.1f} ± {stats['std_devs']['rebounds']:.1f} | CV: {100 * (stats['std_devs']['rebounds']/stats['averages']['rebounds']) if stats['averages']['rebounds'] > 0 else 0:.2f}")
        print(f"Assists: {stats['averages']['assists']:.1f} ± {stats['std_devs']['assists']:.1f} | CV: {100 * (stats['std_devs']['assists']/stats['averages']['assists']) if stats['averages']['assists'] > 0 else 0:.2f}")
        print(f"Blocks: {stats['averages']['blocks']:.1f} ± {stats['std_devs']['blocks']:.1f} | CV: {100 * (stats['std_devs']['blocks']/stats['averages']['blocks']) if stats['averages']['blocks'] > 0 else 0:.2f}")
        print(f"Steals: {stats['averages']['steals']:.1f} ± {stats['std_devs']['steals']:.1f} | CV: {100 * (stats['std_devs']['steals']/stats['averages']['steals']) if stats['averages']['steals'] > 0 else 0:.2f}")
        print(f"3PT: {stats['averages']['3pt']:.1f} ± {stats['std_devs']['3pt']:.1f} | CV: {100 * (stats['std_devs']['3pt']/stats['averages']['3pt']) if stats['averages']['3pt'] > 0 else 0:.2f}")
    except ValueError as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    # SGA POINT CV IS 23
    player = 'Shai Gilgeous-Alexander'
    team = 'Hornets'
    print_player_season_stats(player, '2024-25')
    print_player_season_stats(player, '2025-26')
    print_player_vs_team_stats(player, '2024-25', team)
    print_player_vs_team_stats(player, '2025-26', team)



























    # # Example usage
    # print("NBA Stats Functions")
    # print("=" * 50)
    
    # # Example 1: Season stats
    # try:
    #     player = "Shai Gilgeous-Alexander"
    #     season = "2023-24"
    #     print(f"\n{player} - {season} Season Stats:")
    #     stats = get_player_season_stats(player, season)
    #     print(f"Games Played: {stats['games_played']}")
    #     print(f"Points: {stats['averages']['points']:.1f} ± {stats['std_devs']['points']:.1f}")
    #     print(f"Rebounds: {stats['averages']['rebounds']:.1f} ± {stats['std_devs']['rebounds']:.1f}")
    #     print(f"Assists: {stats['averages']['assists']:.1f} ± {stats['std_devs']['assists']:.1f}")
    #     print(f"Blocks: {stats['averages']['blocks']:.1f} ± {stats['std_devs']['blocks']:.1f}")
    #     print(f"Steals: {stats['averages']['steals']:.1f} ± {stats['std_devs']['steals']:.1f}")
    # except Exception as e:
    #     print(f"Error: {e}")
    
    # # Example 2: Stats vs specific team
    # try:
    #     player = "LeBron"
    #     season = "2023-24"
    #     opponent = "Warriors"
    #     print(f"\n{player} vs {opponent} - {season} Season:")
    #     stats = get_player_vs_team_stats(player, season, opponent)
    #     print(f"Games Played: {stats['games_played']}")
    #     print(f"Points: {stats['averages']['points']:.1f} ± {stats['std_devs']['points']:.1f}")
    #     print(f"Rebounds: {stats['averages']['rebounds']:.1f} ± {stats['std_devs']['rebounds']:.1f}")
    #     print(f"Assists: {stats['averages']['assists']:.1f} ± {stats['std_devs']['assists']:.1f}")
    #     print(f"Blocks: {stats['averages']['blocks']:.1f} ± {stats['std_devs']['blocks']:.1f}")
    #     print(f"Steals: {stats['averages']['steals']:.1f} ± {stats['std_devs']['steals']:.1f}")
    # except Exception as e:
    #     print(f"Error: {e}")

