"""
Quick Start Guide - NBA Percentile Analysis

This script shows the simplest way to use the percentile functions.
"""

from percentile import (
    plot_player_percentiles_season,
    plot_player_percentiles_vs_team
)


def main():
    print("NBA PERCENTILE ANALYSIS - QUICK START")
    print("=" * 60)
    
    # Example 1: Analyze a player's full season
    print("\n1. Season Analysis:")
    print("-" * 60)
    player = "Luka Doncic"
    season = "2023-24"
    
    print(f"Analyzing {player} for {season} season...")
    data = plot_player_percentiles_season(
        player_name=player,
        season=season,
        save_path="luka_season_analysis.png"
    )
    
    print(f"\n✓ Analysis complete!")
    print(f"  Games played: {data['games_played']}")
    print(f"  Median points: {data['percentiles']['points']['50th']:.1f}")
    print(f"  Best game: {data['percentiles']['points']['100th']:.0f} points")
    print(f"  Plot saved as: luka_season_analysis.png")
    
    # Example 2: Analyze vs a specific team
    print("\n\n2. Opponent Analysis:")
    print("-" * 60)
    player = "Anthony Edwards"
    opponent = "Lakers"
    
    print(f"Analyzing {player} vs {opponent} in {season}...")
    data = plot_player_percentiles_vs_team(
        player_name=player,
        season=season,
        opponent_team=opponent,
        save_path="edwards_vs_lakers.png"
    )
    
    print(f"\n✓ Analysis complete!")
    print(f"  Games vs {opponent}: {data['games_played']}")
    print(f"  Median points: {data['percentiles']['points']['50th']:.1f}")
    print(f"  Plot saved as: edwards_vs_lakers.png")
    
    print("\n" + "=" * 60)
    print("Done! Check the PNG files for visual box plots.")
    print("\nBox plots show:")
    print("  • Distribution of performance across games")
    print("  • 25th, 50th (median), 75th, and max percentiles")
    print("  • All individual game values as points")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nError: {e}")
        print("\nMake sure you have:")
        print("  1. Valid player name (e.g., 'Stephen Curry')")
        print("  2. Valid season (e.g., '2023-24')")
        print("  3. Valid team name for opponent analysis")
