# NBA Stats Functions - Usage Guide

## Overview
This module provides two simple functions to fetch NBA player statistics using the `nba_api` library.

## Functions

### 1. `get_player_season_stats(player_name, season)`
Fetches a player's average statistics for an entire season.

**Parameters:**
- `player_name` (str): Full name of the player (e.g., "Stephen Curry", "LeBron James")
- `season` (str): NBA season in format "YYYY-YY" (e.g., "2023-24", "2022-23")

**Returns:**
Dictionary with:
- `averages`: Average points, rebounds, assists, blocks, steals
- `std_devs`: Standard deviation for each stat
- `games_played`: Total games played

**Example:**
```python
from formula import get_player_season_stats

stats = get_player_season_stats("Stephen Curry", "2023-24")
print(f"Points: {stats['averages']['points']:.1f} ± {stats['std_devs']['points']:.1f}")
print(f"Rebounds: {stats['averages']['rebounds']:.1f} ± {stats['std_devs']['rebounds']:.1f}")
print(f"Assists: {stats['averages']['assists']:.1f} ± {stats['std_devs']['assists']:.1f}")
print(f"Games: {stats['games_played']}")
```

### 2. `get_player_vs_team_stats(player_name, season, opponent_team)`
Fetches a player's statistics against a specific opponent team.

**Parameters:**
- `player_name` (str): Full name of the player
- `season` (str): NBA season in format "YYYY-YY"
- `opponent_team` (str): Team name, nickname, or abbreviation (e.g., "Lakers", "LAL", "Warriors")

**Returns:**
Dictionary with:
- `averages`: Average points, rebounds, assists, blocks, steals vs that team
- `std_devs`: Standard deviation for each stat
- `games_played`: Games played vs that team

**Example:**
```python
from formula import get_player_vs_team_stats

stats = get_player_vs_team_stats("LeBron James", "2023-24", "Warriors")
print(f"Points vs Warriors: {stats['averages']['points']:.1f} ± {stats['std_devs']['points']:.1f}")
print(f"Games vs Warriors: {stats['games_played']}")
```

## Stats Included
Both functions return the following statistics:
- **Points (PTS)**: Points scored
- **Rebounds (REB)**: Total rebounds (offensive + defensive)
- **Assists (AST)**: Assists
- **Blocks (BLK)**: Blocks
- **Steals (STL)**: Steals

Each stat includes:
- **Average**: Mean value across games
- **Standard Deviation**: Measure of variability

## Implementation Details

### Simple & Clean Design
- Uses `nba_api.stats.static.players` to find player IDs by name
- Uses `nba_api.stats.static.teams` to find team IDs
- Uses `PlayerGameLog` endpoint to get game-by-game data
- Filters games by opponent using the MATCHUP column
- Calculates statistics using pandas DataFrames

### Error Handling
Both functions will raise `ValueError` if:
- Player name not found
- Team name not found (for vs_team function)
- No games found for the specified season
- Multiple matches found (ambiguous names)

### Season Format
Use the NBA season format: `"YYYY-YY"` where:
- `"2023-24"` = 2023-2024 season
- `"2022-23"` = 2022-2023 season
- etc.

### Team Name Flexibility
The `opponent_team` parameter is flexible and accepts:
- Abbreviations: `"LAL"`, `"GSW"`, `"BOS"`
- Nicknames: `"Lakers"`, `"Warriors"`, `"Celtics"`
- Full names: `"Los Angeles Lakers"`, `"Golden State Warriors"`

## Dependencies
```
nba_api
numpy
pandas
```

## Example Output
```
Stephen Curry - 2023-24 Season Stats:
Games Played: 74
Points: 26.4 ± 9.6
Rebounds: 4.5 ± 2.4
Assists: 5.1 ± 2.4
Blocks: 0.4 ± 0.6
Steals: 0.7 ± 0.9

LeBron James vs Warriors - 2023-24 Season:
Games Played: 3
Points: 36.3 ± 3.5
Rebounds: 11.7 ± 7.2
Assists: 10.7 ± 1.5
Blocks: 0.3 ± 0.6
Steals: 1.0 ± 1.0
```
