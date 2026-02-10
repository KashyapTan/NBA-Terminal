# NBA Percentile Statistics Module

## Overview
This module provides comprehensive percentile analysis and visualization for NBA player statistics, including box plots showing the distribution of performance metrics.

## Features
- Calculate 25th, 50th (median), 75th, and 100th (max) percentiles for player statistics
- Visualize distributions with box plots
- Plot all individual game performances on the box plots
- Analyze season-wide performance
- Analyze performance against specific opponents
- Support for Points, Rebounds, Assists, Blocks, and Steals

---

## Functions

### 1. `get_player_percentiles_season(player_name, season)`

Calculates percentile statistics for a player's entire season.

**Parameters:**
- `player_name` (str): Full name of the player (e.g., "Stephen Curry")
- `season` (str): NBA season in format "YYYY-YY" (e.g., "2023-24")

**Returns:**
Dictionary containing:
- `percentiles`: Dict with 25th, 50th, 75th, 100th percentiles for each stat
- `raw_data`: Array of actual game values for each stat
- `player_name`: Player name
- `season`: Season
- `games_played`: Number of games

**Example:**
```python
from percentile import get_player_percentiles_season

data = get_player_percentiles_season("Stephen Curry", "2023-24")
print(f"Median points: {data['percentiles']['points']['50th']}")
print(f"75th percentile rebounds: {data['percentiles']['rebounds']['75th']}")
```

**Output Structure:**
```python
{
    'percentiles': {
        'points': {'25th': 20.2, '50th': 27.0, '75th': 31.8, '100th': 60.0},
        'rebounds': {'25th': 3.0, '50th': 4.0, '75th': 6.0, '100th': 11.0},
        'assists': {...},
        'blocks': {...},
        'steals': {...}
    },
    'raw_data': {
        'points': [array of game scores],
        'rebounds': [array of game rebounds],
        ...
    },
    'games_played': 74
}
```

---

### 2. `plot_player_percentiles_season(player_name, season, save_path=None)`

Creates box plot visualizations showing percentile distributions for all stats.

**Parameters:**
- `player_name` (str): Full name of the player
- `season` (str): NBA season in format "YYYY-YY"
- `save_path` (str, optional): Path to save the figure (e.g., "curry_stats.png"). If None, displays the plot.

**Returns:**
- Dictionary with percentile data (same as `get_player_percentiles_season`)

**Visualization Features:**
- 5 separate box plots (Points, Rebounds, Assists, Blocks, Steals)
- Box shows 25th-75th percentile range (IQR)
- Red line indicates median (50th percentile)
- Whiskers show min/max
- Individual game values plotted as blue dots
- Percentile labels on the right side

**Example:**
```python
from percentile import plot_player_percentiles_season

# Display plot interactively
data = plot_player_percentiles_season("LeBron James", "2023-24")

# Save to file
data = plot_player_percentiles_season("LeBron James", "2023-24", 
                                      save_path="lebron_season.png")
```

---

### 3. `get_player_percentiles_vs_team(player_name, season, opponent_team)`

Calculates percentile statistics for games against a specific opponent.

**Parameters:**
- `player_name` (str): Full name of the player
- `season` (str): NBA season in format "YYYY-YY"
- `opponent_team` (str): Team name, nickname, or abbreviation (e.g., "Lakers", "LAL", "Warriors")

**Returns:**
Dictionary containing:
- `percentiles`: Percentiles for each stat vs that opponent
- `raw_data`: Actual game values vs that opponent
- `opponent`: Full team name
- `games_played`: Games played vs that opponent

**Example:**
```python
from percentile import get_player_percentiles_vs_team

data = get_player_percentiles_vs_team("Kevin Durant", "2023-24", "Celtics")
print(f"Games vs Celtics: {data['games_played']}")
print(f"Median points vs Celtics: {data['percentiles']['points']['50th']}")
```

---

### 4. `plot_player_percentiles_vs_team(player_name, season, opponent_team, save_path=None)`

Creates box plot visualizations for games against a specific team.

**Parameters:**
- `player_name` (str): Full name of the player
- `season` (str): NBA season in format "YYYY-YY"
- `opponent_team` (str): Team name, nickname, or abbreviation
- `save_path` (str, optional): Path to save the figure

**Returns:**
- Dictionary with percentile data

**Example:**
```python
from percentile import plot_player_percentiles_vs_team

# Analyze performance vs a specific team
data = plot_player_percentiles_vs_team("Stephen Curry", "2023-24", "LAL",
                                       save_path="curry_vs_lakers.png")
```

---

## Understanding the Box Plots

### Box Plot Components:
```
    Max (100th) ----  •  ---- Whisker top
                        |
    75th percentile --- □
                        ▓   Box (IQR)
    Median (50th) ----  ━  ---- Red line
                        ▓   Box (IQR)
    25th percentile --- □
                        |
    Min ----------- •  ---- Whisker bottom

    • • • = Individual game values (scatter points)
```

### Key Insights from Box Plots:

**1. Consistency**
- Narrow box (small IQR) = Consistent performance
- Wide box (large IQR) = Variable performance

**2. Median Performance**
- Red line shows typical/median game
- Compare this across different opponents or players

**3. High Performance Games**
- Points far above 75th percentile show standout games
- Max value shows career-high for that context

**4. Floor vs Ceiling**
- Distance from 25th to Max shows performance range
- Players with tight distributions are more predictable

---

## Practical Use Cases

### 1. Evaluate Player Consistency
```python
data = get_player_percentiles_season("Nikola Jokic", "2023-24")

# Calculate IQR (smaller = more consistent)
iqr = data['percentiles']['points']['75th'] - data['percentiles']['points']['25th']
print(f"Points IQR: {iqr:.1f} (consistency metric)")
```

### 2. Compare Performance vs Different Teams
```python
# Check if player performs better against certain teams
teams = ["Warriors", "Lakers", "Celtics"]

for team in teams:
    data = get_player_percentiles_vs_team("Damian Lillard", "2023-24", team)
    median = data['percentiles']['points']['50th']
    print(f"Median vs {team}: {median:.1f} pts")
```

### 3. Identify Outlier Performances
```python
data = get_player_percentiles_season("Luka Doncic", "2023-24")

# Games above 75th percentile are strong performances
threshold = data['percentiles']['points']['75th']
outliers = data['raw_data']['points'][data['raw_data']['points'] > threshold]
print(f"Had {len(outliers)} games with {threshold:.0f}+ points")
```

### 4. Season-Long Analysis
```python
# Generate comprehensive report
player = "Giannis Antetokounmpo"
season = "2023-24"

data = get_player_percentiles_season(player, season)
plot_player_percentiles_season(player, season, save_path=f"{player}_report.png")

print(f"{player} - {season} Report")
print(f"Games: {data['games_played']}")
print(f"Typical Game (50th): {data['percentiles']['points']['50th']:.1f} pts")
print(f"Strong Game (75th): {data['percentiles']['points']['75th']:.1f} pts")
print(f"Career High: {data['percentiles']['points']['100th']:.1f} pts")
```

---

## Statistical Definitions

- **25th Percentile**: 25% of games are below this value (lower quartile)
- **50th Percentile (Median)**: Middle value; 50% of games above/below
- **75th Percentile**: 75% of games are below this value (upper quartile)
- **100th Percentile (Max)**: Best performance of the season
- **IQR (Interquartile Range)**: Difference between 75th and 25th percentiles; measures variability

---

## Dependencies
```
nba_api
numpy
matplotlib
pandas
```

## File Outputs
Box plots are saved as PNG files with 300 DPI resolution, suitable for:
- Presentations
- Reports
- Social media
- Analysis documentation

---

## Example Complete Workflow

```python
from percentile import (
    get_player_percentiles_season,
    plot_player_percentiles_season,
    get_player_percentiles_vs_team,
    plot_player_percentiles_vs_team
)

# 1. Analyze full season
player = "Joel Embiid"
season = "2023-24"

print(f"Analyzing {player} - {season}")
season_data = plot_player_percentiles_season(player, season, 
                                             save_path="embiid_season.png")

print(f"\nSeason Statistics:")
print(f"Games: {season_data['games_played']}")
for stat in ['points', 'rebounds']:
    p = season_data['percentiles'][stat]
    print(f"{stat}: 50th={p['50th']:.1f}, 75th={p['75th']:.1f}")

# 2. Analyze vs specific rival
opponent = "Celtics"
vs_data = plot_player_percentiles_vs_team(player, season, opponent,
                                          save_path="embiid_vs_celtics.png")

print(f"\nVs {opponent} ({vs_data['games_played']} games):")
print(f"Median points: {vs_data['percentiles']['points']['50th']:.1f}")

# 3. Compare to season average
season_median = season_data['percentiles']['points']['50th']
vs_median = vs_data['percentiles']['points']['50th']
diff = vs_median - season_median

print(f"\nPerformance vs {opponent}: {diff:+.1f} pts vs season median")
```

---

## Tips

1. **Team Names**: Use any format - "GSW", "Warriors", or "Golden State Warriors"
2. **Sample Size**: Be cautious with small sample sizes (< 5 games)
3. **Consistency**: Narrow IQR indicates reliable performance
4. **Outliers**: Points far from box indicate exceptional games
5. **Comparisons**: Use median (50th) for fair comparisons between contexts
