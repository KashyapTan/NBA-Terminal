# NBA Statistics Analysis - Complete Module Summary

## 📊 Overview
This module provides comprehensive NBA player statistics analysis with two main components:

1. **Basic Statistics** (formula.py) - Averages and standard deviations
2. **Percentile Analysis** (percentile.py) - Distribution analysis with visualizations

---

## 📁 Files Structure

```
nba/
├── formula.py              # Basic stats functions (averages, std dev)
├── percentile.py          # Percentile analysis with box plots
├── README.md              # Basic stats documentation
├── PERCENTILE_GUIDE.md    # Percentile analysis documentation
├── quick_start.py         # Simple usage examples
├── test_stats.py          # Test basic stats functions
└── test_percentiles.py    # Test percentile functions
```

---

## 🎯 Quick Reference

### Function 1: Season Averages (formula.py)
```python
from formula import get_player_season_stats

stats = get_player_season_stats("Stephen Curry", "2023-24")
# Returns: averages, std_devs, games_played
```

### Function 2: Stats vs Team (formula.py)
```python
from formula import get_player_vs_team_stats

stats = get_player_vs_team_stats("LeBron James", "2023-24", "Warriors")
# Returns: averages, std_devs, games_played (filtered by opponent)
```

### Function 3: Season Percentiles (percentile.py)
```python
from percentile import plot_player_percentiles_season

data = plot_player_percentiles_season("Luka Doncic", "2023-24", 
                                       save_path="luka.png")
# Returns: percentiles (25th, 50th, 75th, 100th), raw_data, games_played
# Creates: Box plot visualization with all game values
```

### Function 4: Percentiles vs Team (percentile.py)
```python
from percentile import plot_player_percentiles_vs_team

data = plot_player_percentiles_vs_team("Kevin Durant", "2023-24", "Celtics",
                                        save_path="kd_vs_celtics.png")
# Returns: percentiles for games vs that team, raw_data
# Creates: Box plot visualization
```

---

## 📈 What Each Module Provides

### formula.py - Statistical Measures
**Metrics:**
- Average (mean) points, rebounds, assists, blocks, steals
- Standard deviation for each metric
- Games played

**Use Cases:**
- Quick performance summary
- Season comparisons
- Consistency analysis (via std dev)

**Example Output:**
```
Points: 26.4 ± 9.6
Rebounds: 4.5 ± 2.4
Assists: 5.1 ± 2.4
```

---

### percentile.py - Distribution Analysis
**Metrics:**
- 25th percentile (lower quartile)
- 50th percentile (median)
- 75th percentile (upper quartile)
- 100th percentile (maximum)
- IQR (75th - 25th) for consistency

**Visualizations:**
- Box plots showing distribution
- Individual game values plotted
- Percentile markers
- Separate graphs for each stat

**Use Cases:**
- Understanding performance distribution
- Identifying outlier games
- Visual comparison of consistency
- Analyzing performance ceiling/floor

**Example Box Plot Features:**
```
   Max •
       |
   75% □━━━━┐
       ║     │ IQR (middle 50%)
   50% ━━━━━━  ← Median (red line)
       ║     │
   25% □━━━━┘
       |
       • • •  ← Individual games
```

---

## 🚀 Getting Started

### 1. Install Dependencies
```bash
pip install nba_api numpy pandas matplotlib
```

### 2. Basic Usage
```python
# Import functions
from formula import get_player_season_stats
from percentile import plot_player_percentiles_season

# Get season stats
stats = get_player_season_stats("Nikola Jokic", "2023-24")
print(f"Average: {stats['averages']['points']:.1f} ± {stats['std_devs']['points']:.1f}")

# Get percentiles with visualization
data = plot_player_percentiles_season("Nikola Jokic", "2023-24")
print(f"Median: {data['percentiles']['points']['50th']:.1f}")
print(f"75th percentile: {data['percentiles']['points']['75th']:.1f}")
```

### 3. Run Examples
```bash
# Test basic stats
python test_stats.py

# Test percentile analysis
python test_percentiles.py

# Quick start demo
python quick_start.py
```

---

## 📊 Statistics Covered

All functions analyze these five core statistics:

| Statistic | Abbreviation | Description |
|-----------|--------------|-------------|
| Points | PTS | Points scored |
| Rebounds | REB | Total rebounds (OFF + DEF) |
| Assists | AST | Assists |
| Blocks | BLK | Blocked shots |
| Steals | STL | Steals |

---

## 🎓 Understanding the Metrics

### Mean vs Median
- **Mean (Average)**: Sum of all values / count
  - Affected by outliers
  - Use for: overall performance level
  
- **Median (50th percentile)**: Middle value when sorted
  - Not affected by outliers
  - Use for: typical game performance

### Standard Deviation vs IQR
- **Standard Deviation**: Measure of spread around the mean
  - Higher = more variable performance
  - Use for: overall consistency
  
- **IQR (Interquartile Range)**: Range of middle 50% of data
  - 75th percentile - 25th percentile
  - Use for: consistency ignoring outliers

### When to Use Each

**Use Averages (formula.py) when:**
- You need a quick summary
- Comparing season totals
- Standard statistical reports

**Use Percentiles (percentile.py) when:**
- You want to understand distribution
- Looking for consistency patterns
- Identifying hot/cold streaks
- Need visual representation
- Analyzing matchup-specific performance

---

## 💡 Practical Examples

### Example 1: Find Most Consistent Scorer
```python
from percentile import get_player_percentiles_season

players = ["Giannis Antetokounmpo", "Joel Embiid", "Nikola Jokic"]
for player in players:
    data = get_player_percentiles_season(player, "2023-24")
    iqr = data['percentiles']['points']['75th'] - data['percentiles']['points']['25th']
    print(f"{player}: IQR = {iqr:.1f} (lower = more consistent)")
```

### Example 2: Matchup Analysis
```python
from percentile import plot_player_percentiles_vs_team

# How does a player perform against a tough opponent?
player = "Damian Lillard"
opponents = ["Warriors", "Celtics", "Nuggets"]

for opp in opponents:
    data = plot_player_percentiles_vs_team(player, "2023-24", opp,
                                           save_path=f"lillard_vs_{opp}.png")
    median = data['percentiles']['points']['50th']
    print(f"Median vs {opp}: {median:.1f} pts ({data['games_played']} games)")
```

### Example 3: Season Comparison
```python
from formula import get_player_season_stats

player = "Luka Doncic"
seasons = ["2021-22", "2022-23", "2023-24"]

print(f"{player} - Season Progression:")
for season in seasons:
    stats = get_player_season_stats(player, season)
    print(f"{season}: {stats['averages']['points']:.1f} ppg")
```

---

## 🎨 Visualization Features

Box plots generated include:
- ✅ Percentile markers (25th, 50th, 75th, max)
- ✅ Box showing IQR (25th-75th range)
- ✅ Median line (red, bold)
- ✅ All individual game values as scatter points
- ✅ Percentile labels on right side
- ✅ Grid for easy reading
- ✅ Separate subplots for each stat
- ✅ High resolution (300 DPI) for presentations

---

## 🔧 Troubleshooting

### Player Not Found
```python
# Be specific with player names
❌ "Curry"
✅ "Stephen Curry"

❌ "LeBron"  
✅ "LeBron James"
```

### Season Format
```python
# Use correct format
❌ "2024" or "2023-2024"
✅ "2023-24"
```

### Team Names
```python
# All formats work
✅ "LAL" (abbreviation)
✅ "Lakers" (nickname)
✅ "Los Angeles Lakers" (full name)
```

---

## 📚 Documentation Files

- **README.md** - Basic statistics documentation
- **PERCENTILE_GUIDE.md** - Detailed percentile analysis guide
- **quick_start.py** - Simplest usage examples
- **test_stats.py** - Comprehensive basic stats examples
- **test_percentiles.py** - Advanced percentile demonstrations

---

## 🎯 Key Takeaways

1. **Two complementary approaches**: averages for summaries, percentiles for distributions
2. **Visual analysis**: Box plots reveal patterns invisible in numbers alone
3. **Flexible inputs**: Works with various player/team name formats
4. **Matchup-specific**: Analyze performance against particular opponents
5. **Production-ready**: High-quality visualizations suitable for presentations

---

## 📞 Function Summary Table

| Function | Module | Input | Output | Visualization |
|----------|--------|-------|--------|---------------|
| `get_player_season_stats` | formula.py | player, season | avg, std dev | ❌ |
| `get_player_vs_team_stats` | formula.py | player, season, team | avg, std dev | ❌ |
| `get_player_percentiles_season` | percentile.py | player, season | percentiles | ❌ |
| `plot_player_percentiles_season` | percentile.py | player, season | percentiles | ✅ Box plots |
| `get_player_percentiles_vs_team` | percentile.py | player, season, team | percentiles | ❌ |
| `plot_player_percentiles_vs_team` | percentile.py | player, season, team | percentiles | ✅ Box plots |

---

## ✨ Happy Analyzing!

You now have a complete toolkit for NBA player statistical analysis, from basic summaries to advanced distribution visualizations. Explore player performance, compare matchups, and uncover insights in your data! 🏀📊
