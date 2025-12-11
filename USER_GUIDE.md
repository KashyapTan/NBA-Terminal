# NBA Player Prop Predictor - User Guide

This guide explains how to use the `p.py` script to predict NBA player points using the XGBoost model with advanced zone matchup analysis.

## 1. Prerequisites

Ensure you have the required Python packages installed:

```bash
pip install pandas numpy xgboost scikit-learn nba_api tqdm
```

## 2. How to Run a Prediction

The process involves two main steps:
1.  **Get Matchup Info**: Run the helper script to fetch live data for the upcoming game.
2.  **Run Prediction**: Update the main script with that data to get the prediction.

### Step 1: Get Matchup Info (`get_matchup_info.py`)

This script fetches the "Next Game" inputs automatically, including the opponent's defensive stats and zone shooting allowances.

1.  Open `get_matchup_info.py`.
2.  Update the **Constants** at the top of the file:
    ```python
    PLAYER_TEAM_ABBREV = "MIN" # e.g., Timberwolves
    OPPONENT_ABBREV = "PHX"    # e.g., Suns
    DATE_TODAY = "2025-12-08"  # Date of the game
    SEASON = "2025-26"         # Current Season
    ```
3.  Run the script:
    ```bash
    python get_matchup_info.py
    ```
4.  **Copy the Output**: The script will print a dictionary at the end, looking like this:
    ```python
    --- INPUTS FOR P.PY ---
    {'Home_Away': 1, 'Rest_Days': 1, 'Opponent_Def_Rating': 111.4, ... 'Opponent_Zone_Stats': {...}}
    ```

### Step 2: Run Prediction (`p.py`)

1.  Open `p.py`.
2.  **Update Target Player**:
    ```python
    TARGET_PLAYER = "Anthony Edwards" # Line ~22
    ```
3.  **Update Inputs**: Scroll to the bottom (around line ~400) inside the `if __name__ == "__main__":` block.
4.  **Paste the `Opponent_Zone_Stats`**:
    Replace the `opp_zones` dictionary with the one you copied from Step 1.
    ```python
    # Opponent Zone Stats (PHX) - Paste from get_matchup_info.py
    opp_zones = {
        'Restricted Area': 0.708,
        'In The Paint (Non-RA)': 0.451,
        ...
    }
    ```
5.  **Update `next_game_inputs`**:
    Update the values in the `next_game_inputs` dictionary with the values from Step 1 (`Home_Away`, `Rest_Days`, `Opponent_Def_Rating`, `Opponent_Pace`).
    *   **Proj_Minutes**: You must find this manually. Good sources:
        *   [SportsLine Projections](https://www.sportsline.com/nba/expert-projections/simulation/)
        *   [Rotowire](https://www.rotowire.com/basketball/nba-lineups.php)
        *   *Or just use their season average if unsure.*

6.  Run the script:
    ```bash
    python p.py
    ```

## 3. Understanding the Output

The script will output:
1.  **Model Training Metrics**: MAE (Mean Absolute Error) for the cross-validation folds. Lower is better.
2.  **Zone Matchup Score Calculation**: A table showing exactly how the score was derived based on the player's shooting habits vs. the opponent's defense.
3.  **Predicted Points**: The final predicted point total.
4.  **Feature Importance**: Which factors contributed most to this specific prediction.

## 4. Input Parameters Explained

| Parameter | Description | Source |
| :--- | :--- | :--- |
| `Proj_Minutes` | Projected minutes for the player. | SportsLine, Rotowire, or manual estimate. |
| `Last_5_PTS` | Average points in last 5 games. | **Automatically calculated** by `p.py`. |
| `Last_5_FGA` | Average shot attempts in last 5 games. | **Automatically calculated** by `p.py`. |
| `Home_Away` | 1 for Home, 0 for Away. | `get_matchup_info.py` |
| `Rest_Days` | Days since last game (capped at 5). | `get_matchup_info.py` |
| `Opponent_Def_Rating` | Opponent's Defensive Rating (Points allowed per 100 poss). | `get_matchup_info.py` |
| `Opponent_Pace` | Opponent's Pace (Possessions per 48 min). | `get_matchup_info.py` |
| `Zone_Matchup_Score` | Custom metric for shooting matchup favorability. | **Calculated in `p.py`** using `opp_zones`. |

## 5. Caching

*   The script creates a file named `nba_stats_cache.pkl`.
*   This stores heavy API data (Team Zone Stats, Player Profiles).
*   It expires every **24 hours**.
*   If you need to force a refresh, simply delete this file.
