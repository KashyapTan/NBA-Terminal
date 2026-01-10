# 🏀 NBA Picks & Predictions

An advanced NBA player prop prediction and statistics analysis toolkit powered by machine learning and real-time NBA data. This project combines XGBoost modeling, zone-based matchup analysis, and statistical consistency metrics to provide data-driven insights for NBA betting and fantasy sports.

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![NBA API](https://img.shields.io/badge/nba__api-Latest-orange.svg)
![XGBoost](https://img.shields.io/badge/XGBoost-ML-green.svg)

---

## 📋 Table of Contents

- [Features](#-features)
- [Installation](#-installation)
- [Quick Start](#-quick-start)
- [Tools Overview](#-tools-overview)
- [Custom Analytics](#-custom-analytics)
  - [Zone Matchup Score](#-zone-matchup-score)
  - [Coefficient of Variation (CV)](#-coefficient-of-variation-cv)
- [Project Structure](#-project-structure)
- [Screenshots](#-screenshots)
- [Contributing](#-contributing)

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🎯 **ML Points Prediction** | XGBoost-powered player points predictions with zone matchup analysis |
| 📊 **Player Statistics Viewer** | Comprehensive GUI for season stats, vs-team stats, and game logs |
| 🛡️ **Team Defense Analytics** | League-wide defensive zone statistics with visual rankings |
| 📈 **Percentile Charts** | Box plots showing player performance distributions |
| 🔄 **Coefficient of Variation** | Identify the most consistent players on any team |
| 🎨 **Modern GUI** | Dark-themed, professional interface using Tkinter |
| 💾 **Smart Caching** | 24-hour cache to minimize API calls |

---

## 🚀 Installation

### Prerequisites

- Python 3.8 or higher
- pip package manager

### Install Dependencies

```bash
pip install pandas numpy xgboost scikit-learn nba_api tqdm matplotlib pillow
```

### Clone the Repository

```bash
git clone https://github.com/yourusername/nba-picks-n-predictions.git
cd nba-picks-n-predictions
```

---

## 🎮 Quick Start

### 1. Player Statistics Analysis (GUI)

```bash
python stats.py
```

Enter a player name and opponent team to view:
- Season averages with standard deviations
- Performance vs specific opponents
- Rolling averages (L5, L10, L15)
- Percentile box plots
- Complete game logs with clickable box scores

### 2. Points Prediction (ML Model)

```bash
python p.py
```

Follow the prompts to:
1. Enter the player name
2. Enter projected minutes
3. Enter the player's team and opponent

The model will output a predicted point total with detailed zone matchup analysis.

### 3. Team Defense Rankings

```bash
python team_zone_stats.py
```

View all 30 NBA teams ranked by defensive efficiency with zone-by-zone breakdowns.

### 4. Team Consistency Analysis

```bash
python topcv.py
```

Enter a team to see which players are most consistent (lowest CV) in each statistical category.

---

## 🛠️ Tools Overview

### `p.py` - Points Predictor (XGBoost ML Model)

The flagship prediction tool using machine learning with the following features:

- **Model**: XGBoost Regressor with regularization to prevent overfitting
- **Features Used**:
  - Projected minutes
  - Season and rolling averages (L5, L10)
  - Home/Away advantage
  - Rest days
  - Opponent defensive rating
  - Expected extra possessions (pace differential)
  - **Zone Matchup Score** (custom metric)
  - **Mean Reversion Signal** (recent vs season average)

- **Training**: Time-series cross-validation with 5 folds
- **Output**: Predicted points with feature importance breakdown

### `stats.py` - Player Statistics GUI

A comprehensive statistics viewer with:

- **Season Stats**: Averages, standard deviations, and CV% for all major stats
- **Vs-Team Stats**: Historical performance against specific opponents
- **Rolling Stats**: L5, L10, L15 game averages with CV%
- **Percentile Charts**: Visual box plots saved to `charts/` folder
- **Game Logs**: Clickable games that show full box scores

### `team_zone_stats.py` - League Defense Dashboard

Displays all NBA teams' defensive statistics:

- Overall opponent FG% allowed
- Opponent 3PT% allowed
- Zone-by-zone FG% allowed:
  - Restricted Area
  - In The Paint (Non-RA)
  - Mid-Range
  - Corner 3
  - Above the Break 3
- Color-coded rankings (Elite → Poor)

### `topcv.py` - Team Consistency Analyzer

Identifies the most consistent players on any team by calculating CV for:
- Points
- Rebounds
- Assists
- Steals
- Blocks

### `get_matchup_info.py` - Matchup Data Fetcher

Automatically fetches upcoming game information:
- Home/Away status
- Rest days since last game
- Opponent defensive rating
- Opponent pace
- Opponent zone defense stats

### Helper Modules (`helper/`)

| Module | Purpose |
|--------|---------|
| `formula.py` | Core stat calculation functions |
| `percentile.py` | Percentile calculations and box plot generation |
| `gamelog.py` | Game log fetching and formatting |

---

## 📐 Custom Analytics

### 🎯 Zone Matchup Score

The **Zone Matchup Score** is a custom metric I created that quantifies how favorable a shooting matchup is for a player against a specific opponent's defense.

#### How It Works

1. **Player Shooting Profile**: Analyzes where a player takes their shots from (shot frequency by zone):
   - Restricted Area
   - In The Paint (Non-RA)
   - Mid-Range
   - Corner 3
   - Above the Break 3

2. **Opponent Zone Defense**: Fetches the opponent's FG% allowed in each zone

3. **League Averages**: Compares against league-wide zone defense averages

4. **Calculation**:
   ```
   For each zone:
     Zone Score = (Frequency) × (Opp_FG% - League_FG%) × Point_Value × 100
   
   Total Zone Matchup Score = Sum of all zone scores
   ```

#### Interpretation

| Score | Meaning |
|-------|---------|
| **> +1.0** | 🟢 Favorable matchup - opponent is weak in zones the player shoots from |
| **-1.0 to +1.0** | ⚪ Neutral matchup |
| **< -1.0** | 🔴 Unfavorable matchup - opponent is strong in zones the player shoots from |

#### Example

If Anthony Edwards shoots 35% of his shots from the Restricted Area, and the opponent allows 70% FG there (vs 65% league average):
```
Zone Score = 0.35 × (0.70 - 0.65) × 2.0 × 100 = +3.5 points contribution
```

This metric helps identify when a player's shooting style matches up well (or poorly) against a specific defense.

---

### 📉 Coefficient of Variation (CV)

The **Coefficient of Variation (CV)** measures how consistent a player is at producing a particular stat. It's a standardized measure of dispersion that allows comparison across different players and stat categories.

#### Formula

```
CV = (Standard Deviation / Mean) × 100%
```

#### Why CV Matters for Betting

**Lower CV = More Consistent = More Predictable**

When betting on player props, consistency is crucial:

| CV Range | Interpretation | Betting Implication |
|----------|----------------|---------------------|
| **< 30%** | Very Consistent | Safe for betting - player reliably hits their average |
| **30-50%** | Moderately Consistent | Reasonable reliability |
| **50-70%** | Inconsistent | Higher variance - props are riskier |
| **> 70%** | Highly Volatile | Avoid or use for contrarian plays |

#### Example: Points CV

| Player | Avg PTS | Std Dev | CV% | Assessment |
|--------|---------|---------|-----|------------|
| Player A | 25.0 | 5.0 | 20% | Very consistent scorer |
| Player B | 25.0 | 12.5 | 50% | Boom-or-bust scorer |

Both players average 25 PPG, but Player A is far more reliable for prop betting.

#### Where CV Appears in This Project

1. **`stats.py`** - Shows CV% for every stat in the stats cards and rolling averages
2. **`topcv.py`** - Ranks all players on a team by CV for each stat category
3. **`helper/formula.py`** - Calculates CV as part of stat analysis

#### Using CV for Prop Betting Strategy

- **Low CV players**: Target their props at or slightly above their average
- **High CV players**: Look for line value or avoid entirely
- **Combine with matchup**: A consistent player with a favorable zone matchup = high-confidence pick

---

## 📁 Project Structure

```
nba-picks-n-predictions/
│
├── p.py                    # Main prediction model (XGBoost)
├── stats.py                # Player statistics GUI
├── team_zone_stats.py      # League defense dashboard
├── topcv.py                # Team consistency analyzer
├── get_matchup_info.py     # Matchup data fetcher
├── d.py                    # Quick stats runner (CLI)
├── c.py                    # Chart folder utility
│
├── helper/
│   ├── formula.py          # Core stat calculations
│   ├── percentile.py       # Percentile & box plot generation
│   └── gamelog.py          # Game log utilities
│
├── charts/                 # Generated percentile charts
├── picks/                  # Historical pick records (MD files)
├── guides/                 # Additional documentation
│
└── README.md               # This file
```

---

## 📊 Screenshots

### Points Prediction GUI
The prediction output shows:
- Predicted points with confidence bounds
- Zone matchup breakdown table
- Pace and tempo analysis
- Mean reversion indicators
- Feature importance rankings

### Statistics Viewer
Features a dark-themed interface with:
- Stat cards showing averages and CV%
- Rolling stats (L5/L10/L15)
- Embedded percentile charts
- Interactive game logs

### Team Defense Dashboard
Color-coded rankings:
- 🟢 Elite (Top 5)
- 🔵 Good (6-15)
- ⚪ Average (16-20)
- 🟡 Below Average (21-25)
- 🔴 Poor (26-30)

---

## 📚 Additional Resources

- [guides/COMPLETE_GUIDE.md](guides/COMPLETE_GUIDE.md) - In-depth documentation
- [guides/PERCENTILE_GUIDE.md](guides/PERCENTILE_GUIDE.md) - Understanding percentiles

---

## 🤝 Contributing

Contributions are welcome! Feel free to:
- Report bugs
- Suggest new features
- Submit pull requests

---

## ⚠️ Disclaimer

This tool is for educational and entertainment purposes only. Sports betting involves risk, and past performance does not guarantee future results. Always gamble responsibly.

---

## 📄 License

MIT License - feel free to use and modify for your own projects.

---
## Coming Soon
- Migrate front-end to electron/react instead of py GUI's
