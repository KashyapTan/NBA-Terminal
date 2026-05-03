"""
NBA Player Percentile Statistics and Visualization Module

This module provides functions to calculate percentiles and create box plots
for NBA player statistics.
"""

import numpy as np
import matplotlib.pyplot as plt
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


def get_player_percentiles_season(player_name, season, season_type='Regular Season'):
    """
    Get percentile statistics for a player's season performance.
    
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
        Dictionary containing percentiles (25th, 50th, 75th, 100th) for each stat
        and the raw game data
    
    Example:
    --------
    >>> result = get_player_percentiles_season("Stephen Curry", "2023-24")
    >>> print(f"Points 50th percentile: {result['percentiles']['points']['50th']}")
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
    
    # Calculate percentiles for each stat
    stats = ['PTS', 'REB', 'AST', 'BLK', 'STL']
    stat_names = ['points', 'rebounds', 'assists', 'blocks', 'steals']
    
    result = {
        'percentiles': {},
        'raw_data': {},
        'player_name': player_name,
        'season': season,
        'season_type': season_type,
        'games_played': len(df)
    }
    
    for stat, name in zip(stats, stat_names):
        data = df[stat].values
        result['percentiles'][name] = {
            '25th': np.percentile(data, 25),
            '50th': np.percentile(data, 50),  # median
            '75th': np.percentile(data, 75),
            '100th': np.percentile(data, 100)  # max
        }
        result['raw_data'][name] = data
    
    return result


def plot_player_percentiles_season(player_name, season, save_path=None, season_type='Regular Season'):
    """
    Create box plots showing percentiles and actual game values for a player's season.
    
    Parameters:
    -----------
    player_name : str
        Full name of the player
    season : str
        NBA season in format "YYYY-YY"
    season_type : str, optional
        Data scope to fetch. Supported values: "Regular Season", "Playoffs".
    save_path : str, optional
        Path to save the figure. If None, displays the plot.
    
    Returns:
    --------
    dict
        The percentiles data used to create the plots
    
    Example:
    --------
    >>> plot_player_percentiles_season("Stephen Curry", "2023-24")
    """
    # Get percentile data
    data = get_player_percentiles_season(player_name, season, season_type=season_type)
    
    # Create subplots for each stat
    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
    fig.suptitle(f'{player_name} - {season} {season_type} Statistics\n(Box plots with game-by-game data)', 
                 fontsize=16, fontweight='bold')
    
    stat_names = ['points', 'rebounds', 'assists', 'blocks', 'steals']
    stat_labels = ['Points', 'Rebounds', 'Assists', 'Blocks', 'Steals']
    
    # Flatten axes for easier iteration
    axes = axes.flatten()
    
    for idx, (stat_name, label) in enumerate(zip(stat_names, stat_labels)):
        ax = axes[idx]
        
        # Get data
        raw_data = data['raw_data'][stat_name]
        percentiles = data['percentiles'][stat_name]
        
        # Create box plot
        bp = ax.boxplot([raw_data], 
                        widths=0.4,
                        patch_artist=True,
                        showfliers=False)  # We'll plot all points manually
        
        # Style the box plot
        bp['boxes'][0].set_facecolor('lightblue')
        bp['boxes'][0].set_alpha(0.7)
        bp['medians'][0].set_color('red')
        bp['medians'][0].set_linewidth(2)
        
        # Plot all actual game values as scatter points
        x_pos = np.ones(len(raw_data))
        ax.scatter(x_pos, raw_data, alpha=0.4, s=30, color='navy', label='Game values')
        
        # Add percentile labels
        ax.text(1.3, percentiles['25th'], f"25th: {percentiles['25th']:.1f}", 
                va='center', fontsize=9, color='blue')
        ax.text(1.3, percentiles['50th'], f"50th: {percentiles['50th']:.1f}", 
                va='center', fontsize=9, color='red', fontweight='bold')
        ax.text(1.3, percentiles['75th'], f"75th: {percentiles['75th']:.1f}", 
                va='center', fontsize=9, color='blue')
        ax.text(1.3, percentiles['100th'], f"Max: {percentiles['100th']:.1f}", 
                va='center', fontsize=9, color='green')
        
        # Set labels and title
        ax.set_ylabel(label, fontsize=11, fontweight='bold')
        ax.set_title(f'{label} Distribution', fontsize=12)
        ax.set_xticks([])
        ax.grid(True, alpha=0.3, axis='y')
        ax.legend(loc='upper right', fontsize=8)
    
    # Hide the last subplot (we only have 5 stats)
    axes[5].axis('off')
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        # print(f"Plot saved to {save_path}")
    else:
        plt.show()
    
    return data


def get_player_percentiles_vs_team(player_name, season, opponent_team, season_type='Regular Season'):
    """
    Get percentile statistics for a player's performance vs a specific team.
    
    Parameters:
    -----------
    player_name : str
        Full name of the player (e.g., "LeBron James")
    season : str
        NBA season in format "YYYY-YY" (e.g., "2023-24")
    opponent_team : str
        Team name, nickname, or abbreviation (e.g., "Lakers", "LAL")
    season_type : str, optional
        Data scope to fetch. Supported values: "Regular Season", "Playoffs".
    
    Returns:
    --------
    dict
        Dictionary containing percentiles for each stat vs the opponent
    
    Example:
    --------
    >>> result = get_player_percentiles_vs_team("Stephen Curry", "2023-24", "Lakers")
    >>> print(f"Points 50th percentile vs Lakers: {result['percentiles']['points']['50th']}")
    """
    # Find player by name
    player_list = players.find_players_by_full_name(player_name)
    
    if not player_list:
        raise ValueError(f"Player '{player_name}' not found")
    
    if len(player_list) > 1:
        raise ValueError(f"Multiple players found for '{player_name}': {player_list}")
    
    player_id = player_list[0]['id']
    season_type = _normalize_season_type(season_type)
    
    # Find opponent team
    team_list = None
    
    # Try by abbreviation first (most specific)
    if len(opponent_team) <= 3:
        team_obj = teams.find_team_by_abbreviation(opponent_team.upper())
        if team_obj:
            team_list = [team_obj]
    
    # Try by nickname
    if not team_list:
        team_list = teams.find_teams_by_nickname(opponent_team)
    
    # Try by full name
    if not team_list:
        team_list = teams.find_teams_by_full_name(opponent_team)
    
    if not team_list:
        raise ValueError(f"Team '{opponent_team}' not found")
    
    if len(team_list) > 1:
        raise ValueError(f"Multiple teams found for '{opponent_team}': {team_list}")
    
    opponent_abbrev = team_list[0]['abbreviation']
    opponent_full_name = team_list[0]['full_name']
    
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
    
    # Filter for games vs opponent team
    df_vs_team = df[df['MATCHUP'].str.contains(opponent_abbrev, case=False, na=False)]
    
    if df_vs_team.empty:
        raise ValueError(f"No games found for {player_name} vs {opponent_team} in {season} ({season_type})")
    
    # Calculate percentiles for each stat
    stats = ['PTS', 'REB', 'AST', 'BLK', 'STL']
    stat_names = ['points', 'rebounds', 'assists', 'blocks', 'steals']
    
    result = {
        'percentiles': {},
        'raw_data': {},
        'player_name': player_name,
        'season': season,
        'season_type': season_type,
        'opponent': opponent_full_name,
        'games_played': len(df_vs_team)
    }
    
    for stat, name in zip(stats, stat_names):
        data = df_vs_team[stat].values
        result['percentiles'][name] = {
            '25th': np.percentile(data, 25),
            '50th': np.percentile(data, 50),
            '75th': np.percentile(data, 75),
            '100th': np.percentile(data, 100)
        }
        result['raw_data'][name] = data
    
    return result


def plot_player_percentiles_vs_team(player_name, season, opponent_team, save_path=None, season_type='Regular Season'):
    """
    Create box plots showing percentiles and actual game values for a player vs a team.
    
    Parameters:
    -----------
    player_name : str
        Full name of the player
    season : str
        NBA season in format "YYYY-YY"
    opponent_team : str
        Team name, nickname, or abbreviation
    season_type : str, optional
        Data scope to fetch. Supported values: "Regular Season", "Playoffs".
    save_path : str, optional
        Path to save the figure. If None, displays the plot.
    
    Returns:
    --------
    dict
        The percentiles data used to create the plots
    
    Example:
    --------
    >>> plot_player_percentiles_vs_team("LeBron James", "2023-24", "Warriors")
    """
    # Get percentile data
    data = get_player_percentiles_vs_team(player_name, season, opponent_team, season_type=season_type)
    
    # Create subplots for each stat
    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
    fig.suptitle(f'{player_name} vs {data["opponent"]} - {season} {season_type}\n'
                 f'(Box plots with game-by-game data - {data["games_played"]} games)', 
                 fontsize=16, fontweight='bold')
    
    stat_names = ['points', 'rebounds', 'assists', 'blocks', 'steals']
    stat_labels = ['Points', 'Rebounds', 'Assists', 'Blocks', 'Steals']
    
    # Flatten axes for easier iteration
    axes = axes.flatten()
    
    for idx, (stat_name, label) in enumerate(zip(stat_names, stat_labels)):
        ax = axes[idx]
        
        # Get data
        raw_data = data['raw_data'][stat_name]
        percentiles = data['percentiles'][stat_name]
        
        # Create box plot
        bp = ax.boxplot([raw_data], 
                        widths=0.4,
                        patch_artist=True,
                        showfliers=False)
        
        # Style the box plot
        bp['boxes'][0].set_facecolor('lightcoral')
        bp['boxes'][0].set_alpha(0.7)
        bp['medians'][0].set_color('darkred')
        bp['medians'][0].set_linewidth(2)
        
        # Plot all actual game values as scatter points
        x_pos = np.ones(len(raw_data))
        ax.scatter(x_pos, raw_data, alpha=0.5, s=40, color='darkblue', 
                  marker='D', label='Game values')
        
        # Add percentile labels
        ax.text(1.3, percentiles['25th'], f"25th: {percentiles['25th']:.1f}", 
                va='center', fontsize=9, color='blue')
        ax.text(1.3, percentiles['50th'], f"50th: {percentiles['50th']:.1f}", 
                va='center', fontsize=9, color='darkred', fontweight='bold')
        ax.text(1.3, percentiles['75th'], f"75th: {percentiles['75th']:.1f}", 
                va='center', fontsize=9, color='blue')
        ax.text(1.3, percentiles['100th'], f"Max: {percentiles['100th']:.1f}", 
                va='center', fontsize=9, color='green')
        
        # Set labels and title
        ax.set_ylabel(label, fontsize=11, fontweight='bold')
        ax.set_title(f'{label} Distribution', fontsize=12)
        ax.set_xticks([])
        ax.grid(True, alpha=0.3, axis='y')
        ax.legend(loc='upper right', fontsize=8)
    
    # Hide the last subplot
    axes[5].axis('off')
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        # print(f"Plot saved to {save_path}")
    else:
        plt.show()
    
    return data

def print_player_percentile(player, season, season_type='Regular Season'):
    try:
        # print(f"\nAnalyzing {player} - {season} Season:")
        # print("-" * 70)
        
        # Save plot to file instead of showing
        data = plot_player_percentiles_season(
            player,
            season,
            save_path=f"charts/{player.replace(' ', '_').lower()}_{season}.png",
            season_type=season_type
        )
        
        # print(f"\nGames Played: {data['games_played']}")
        # print("\nPercentile Statistics:")
        # for stat in ['points', 'rebounds', 'assists', 'blocks', 'steals']:
        #     p = data['percentiles'][stat]
        #     print(f"\n{stat.capitalize()}:")
        #     print(f"  25th percentile: {p['25th']:.1f}")
        #     print(f"  50th percentile (median): {p['50th']:.1f}")
        #     print(f"  75th percentile: {p['75th']:.1f}")
        #     print(f"  100th percentile (max): {p['100th']:.1f}")
    
    except Exception as e:
        print(f"Error: {e}")

def print_player_percentile_vs_team(player, season, opponent, season_type='Regular Season'):
    try:
        # print(f"\n\nAnalyzing {player} vs {opponent} - {season}:")
        # print("-" * 70)
        
        # Save plot to file
        data = plot_player_percentiles_vs_team(
            player,
            season,
            opponent,
            save_path=f"charts/{player.replace(' ', '_').lower()}_vs_{opponent.replace(' ', '_').lower()}_{season}.png",
            season_type=season_type
        )
        
        # print(f"\nGames Played: {data['games_played']}")
        # print("\nPercentile Statistics vs Warriors:")
        # for stat in ['points', 'rebounds', 'assists']:
        #     p = data['percentiles'][stat]
        #     print(f"\n{stat.capitalize()}:")
        #     print(f"  25th: {p['25th']:.1f}, 50th: {p['50th']:.1f}, "
        #           f"75th: {p['75th']:.1f}, Max: {p['100th']:.1f}")
    
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    player = 'Shai Gilgeous-Alexander'
    team = 'Hornets'
    print_player_percentile(player, "2025-26")
    print_player_percentile_vs_team(player, "2025-26", team)
























    # # Example usage
    # print("NBA Player Percentile Statistics")
    # print("=" * 70)
    
    # # Example 1: Season percentiles with visualization
    # try:
    #     player = "Stephen Curry"
    #     season = "2024-25"
    #     print(f"\nAnalyzing {player} - {season} Season:")
    #     print("-" * 70)
        
    #     # Save plot to file instead of showing
    #     data = plot_player_percentiles_season(player, season, 
    #                                           save_path=f"charts/{player.replace(' ', '_').lower()}_season_stats.png")
        
    #     print(f"\nGames Played: {data['games_played']}")
    #     print("\nPercentile Statistics:")
    #     for stat in ['points', 'rebounds', 'assists', 'blocks', 'steals']:
    #         p = data['percentiles'][stat]
    #         print(f"\n{stat.capitalize()}:")
    #         print(f"  25th percentile: {p['25th']:.1f}")
    #         print(f"  50th percentile (median): {p['50th']:.1f}")
    #         print(f"  75th percentile: {p['75th']:.1f}")
    #         print(f"  100th percentile (max): {p['100th']:.1f}")
    
    # except Exception as e:
    #     print(f"Error: {e}")
    
    # # Example 2: Percentiles vs specific team
    # try:
    #     player = "Stephen Curry"
    #     season = "2024-25"
    #     opponent = "Spurs"
    #     print(f"\n\nAnalyzing {player} vs {opponent} - {season}:")
    #     print("-" * 70)
        
    #     # Save plot to file
    #     data = plot_player_percentiles_vs_team(player, season, opponent,
    #                                            save_path=f"charts/{player.replace(' ', '_').lower()}_vs_{opponent.replace(' ', '_').lower()}.png")
        
    #     print(f"\nGames Played: {data['games_played']}")
    #     print("\nPercentile Statistics vs Warriors:")
    #     for stat in ['points', 'rebounds', 'assists']:
    #         p = data['percentiles'][stat]
    #         print(f"\n{stat.capitalize()}:")
    #         print(f"  25th: {p['25th']:.1f}, 50th: {p['50th']:.1f}, "
    #               f"75th: {p['75th']:.1f}, Max: {p['100th']:.1f}")
    
    # except Exception as e:
    #     print(f"Error: {e}")
