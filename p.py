import pandas as pd
import numpy as np
import sys
import pickle
import os
import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta
from tqdm import tqdm

try:
    import xgboost as xgb
    from sklearn.model_selection import TimeSeriesSplit
    from sklearn.metrics import mean_absolute_error
except ImportError as e:
    print(f"Error: Missing required package. {e}")
    print("Please install them using: pip install xgboost scikit-learn")
    sys.exit(1)

from nba_api.stats.static import players, teams
from nba_api.stats.endpoints import playergamelog, leaguedashteamstats, leaguedashteamshotlocations, playerdashboardbyshootingsplits
import time
import helper.get_matchup_info as get_matchup_info

# --- Configuration ---
TARGET_PLAYER = input("Enter the player to predict: ")  # Player to predict
SEASONS = ["2024-25", "2025-26"]
CACHE_FILE = "nba_stats_cache.pkl"
CACHE_EXPIRY_HOURS = 24 # Cache expires after 24 hours
Proj_Minutes = float(input("Enter projected minutes for the next game: ")) # Projected minutes for the next game

# Zone point values for weighted scoring
ZONE_POINT_VALUES = {
    'Restricted Area': 2.0,
    'In The Paint (Non-RA)': 2.0,
    'Mid-Range': 2.0,
    'Corner 3': 3.0,
    'Above the Break 3': 3.0
}

# Standard zones to track (excluding Backcourt - negligible %)
STANDARD_ZONES = ['Restricted Area', 'In The Paint (Non-RA)', 'Mid-Range', 'Corner 3', 'Above the Break 3']

class NBAPredictor:
    def __init__(self):
        self.model = xgb.XGBRegressor(
            n_estimators=200,
            learning_rate=0.05,
            max_depth=3,
            min_child_weight=5,        
            reg_alpha=1.0, # L1 regularization
            reg_lambda=2.0, # L2 regularization
            subsample=0.8, # Use 80% of data per tree
            colsample_bytree=0.8, # Use 80% of features per tree
            early_stopping_rounds=30,
            n_jobs=-1
        )
        self.feature_columns = []
        self.feature_weights_list = None  # Store for manual application
        self.team_stats_cache = {} # (Season, Team_Abbrev) -> {Def_Rating, Pace, Zone_Stats}
        self.player_profile = {} # {Zone: Frequency}
        self.player_profile_id = None # Track which player's profile is cached
        self.league_zone_stats = {} # Season -> {Zone: Avg_FG_Pct}
        self.league_avg_pace = {} # Season -> Avg Pace
        self.load_cache()

    def load_cache(self):
        if os.path.exists(CACHE_FILE):
            try:
                file_time = datetime.fromtimestamp(os.path.getmtime(CACHE_FILE))
                if datetime.now() - file_time > timedelta(hours=CACHE_EXPIRY_HOURS):
                    print("Cache expired. Will refresh data.")
                    return

                with open(CACHE_FILE, 'rb') as f:
                    data = pickle.load(f)
                    self.team_stats_cache = data.get('team_stats', {})
                    self.league_zone_stats = data.get('league_zones', {})
                    self.player_profile = data.get('player_profile', {})
                    self.player_profile_id = data.get('player_profile_id', None)
                    self.league_avg_pace = data.get('league_avg_pace', {})
                print("Loaded stats from cache.")
            except Exception as e:
                print(f"Error loading cache: {e}")

    def save_cache(self):
        try:
            with open(CACHE_FILE, 'wb') as f:
                pickle.dump({
                    'team_stats': self.team_stats_cache,
                    'league_zones': self.league_zone_stats,
                    'player_profile': self.player_profile,
                    'player_profile_id': self.player_profile_id,
                    'league_avg_pace': self.league_avg_pace
                }, f)
            print("Saved stats to cache.")
        except Exception as e:
            print(f"Error saving cache: {e}")

    def get_player_id(self, player_name):
        player_list = players.find_players_by_full_name(player_name)
        if not player_list:
            raise ValueError(f"Player '{player_name}' not found")
        return player_list[0]['id']

    def fetch_player_profile(self, player_id):
        print(f"Fetching shooting profile for player {player_id}...")
        try:
            # Use the most recent season for profile
            season = SEASONS[-1]
            splits = playerdashboardbyshootingsplits.PlayerDashboardByShootingSplits(
                player_id=player_id,
                season=season,
                per_mode_detailed='PerGame'
            )
            # Order: 0=Overall, 1=Shot5FT, 2=Shot8FT, 3=ShotArea, 4=AssistedShot, 5=ShotTypeSummary, 6=ShotTypeDetail
            area_df = splits.get_data_frames()[3]
            
            # Calculate Frequencies
            total_fga = area_df['FGA'].sum()
            profile = {}
            
            # First pass: collect raw FGA per zone
            raw_fga = {}
            for _, row in area_df.iterrows():
                zone = row['GROUP_VALUE']
                raw_fga[zone] = row['FGA']
            
            # Normalize zones: combine Left/Right Corner 3
            normalized_fga = {}
            corner_3_fga = 0
            for zone, fga in raw_fga.items():
                if 'Corner 3' in zone:  # Catches 'Left Corner 3' and 'Right Corner 3'
                    corner_3_fga += fga
                else:
                    normalized_fga[zone] = fga
            
            if corner_3_fga > 0:
                normalized_fga['Corner 3'] = corner_3_fga
            
            # Calculate frequencies from normalized FGA (only standard zones)
            for zone, fga in normalized_fga.items():
                if zone in STANDARD_ZONES:
                    profile[zone] = fga / total_fga if total_fga > 0 else 0
            
            # Ensure all standard zones exist (with 0 if not present)
            for zone in STANDARD_ZONES:
                if zone not in profile:
                    profile[zone] = 0.0
            
            self.player_profile = profile
            self.player_profile_id = player_id  # Track which player this is for
            print(f"Player Profile: {profile}")
            self.save_cache()
            
        except Exception as e:
            raise RuntimeError(f"Failed to fetch player shooting profile: {e}")

    def fetch_game_logs(self, player_id, seasons):
        # Refresh player profile if it's for a different player
        if not self.player_profile or self.player_profile_id != player_id:
            self.fetch_player_profile(player_id)
        
        all_logs = []
        seasons_with_data = []
        
        for season in seasons:
            print(f"Fetching game logs for season {season}...")
            try:
                log = playergamelog.PlayerGameLog(player_id=player_id, season=season)
                df = log.get_data_frames()[0]
                
                # Check if the player has any games in this season
                if df.empty:
                    print(f"  → No games found for {season} (player may be a rookie)")
                    continue
                    
                df['SEASON_ID'] = season 
                all_logs.append(df)
                seasons_with_data.append(season)
                
                # Pre-fetch team stats for this season
                self.fetch_season_team_stats(season)
                
                time.sleep(0.6) 
            except Exception as e:
                print(f"  → No data for {season}: {e} (player may be a rookie)")
        
        if not all_logs:
            raise ValueError("No game logs found.")
        
        # Detect if player is a rookie (only has current season data)
        if len(seasons_with_data) == 1 and seasons_with_data[0] == seasons[-1]:
            print(f"\n ROOKIE DETECTED: Player only has data for {seasons_with_data[0]}")
            print(f" Using single-season model...\n")
            
        full_df = pd.concat(all_logs, ignore_index=True)
        full_df['GAME_DATE'] = pd.to_datetime(full_df['GAME_DATE'])
        full_df = full_df.sort_values('GAME_DATE').reset_index(drop=True)
        return full_df

    def fetch_season_team_stats(self, season):
        if season in self.team_stats_cache:
            return

        print(f"Fetching team defense stats for {season}...")
        try:
            # 1. Fetch Advanced stats for Def Rating and Pace
            adv_stats = leaguedashteamstats.LeagueDashTeamStats(season=season, measure_type_detailed_defense='Advanced')
            adv_df = adv_stats.get_data_frames()[0]
            
            # Map Team ID to Abbreviation
            nba_teams = teams.get_teams()
            id_to_abbrev = {t['id']: t['abbreviation'] for t in nba_teams}
            
            season_stats = {}
            
            # Process Advanced Stats and calculate league average pace
            pace_values = []
            for _, row in adv_df.iterrows():
                tid = row['TEAM_ID']
                if tid in id_to_abbrev:
                    abbrev = id_to_abbrev[tid]
                    season_stats[abbrev] = {
                        'DEF_RATING': row['DEF_RATING'],
                        'PACE': row['PACE'],
                        'ZONE_DEFENSE': {} # Will populate below (only for current season)
                    }
                    pace_values.append(row['PACE'])
            
            # Store league average pace for this season
            self.league_avg_pace[season] = np.mean(pace_values) if pace_values else 100.0
            
            # 2. Fetch Zone Defense Stats ONLY for current season
            # Previous season zone stats are not used (zone_score=0 for historical games)
            current_season = SEASONS[-1]
            if season != current_season:
                print(f"Skipping zone stats for {season} (only fetching for current season {current_season})")
                self.team_stats_cache[season] = season_stats
                self.save_cache()
                return
            
            print("Fetching zone defense stats using LeagueDashTeamShotLocations...")
            
            # Initialize zone tracking variables
            zone_sums = {z: 0 for z in STANDARD_ZONES}
            zone_counts = {z: 0 for z in STANDARD_ZONES}
            
            # Use LeagueDashTeamShotLocations with Opponent measure - returns CORRECT FG% allowed
            # This endpoint returns ALL teams in one call (much faster than per-team API calls)
            try:
                shot_locs = leaguedashteamshotlocations.LeagueDashTeamShotLocations(
                    season=season,
                    per_mode_detailed='PerGame',
                    distance_range='By Zone',
                    measure_type_simple='Opponent',  # CRITICAL: This gets opponent FG% allowed
                    timeout=60
                )
                
                zone_df = shot_locs.get_data_frames()[0]
                
                # The dataframe has multi-level columns like (('Restricted Area', 'OPP_FG_PCT'))
                # Process each team
                for _, row in zone_df.iterrows():
                    # Get team ID (first column)
                    tid = row.iloc[0]
                    if tid not in id_to_abbrev:
                        continue
                    abbrev = id_to_abbrev[tid]
                    
                    if abbrev not in season_stats:
                        continue
                    
                    # Extract zone FG% allowed - columns are multi-level tuples
                    team_zones = {}
                    corner_pcts = []
                    
                    for col in zone_df.columns:
                        if len(col) == 2:
                            zone_name, stat_type = col
                            # Convert numpy strings to regular strings
                            zone_name = str(zone_name)
                            stat_type = str(stat_type)
                            
                            if stat_type == 'OPP_FG_PCT':
                                pct = row[col]
                                if pd.notna(pct):
                                    if 'Corner 3' in zone_name and zone_name != 'Corner 3':
                                        # Left/Right Corner 3 - collect for averaging
                                        corner_pcts.append(pct)
                                    elif zone_name in STANDARD_ZONES:
                                        team_zones[zone_name] = pct
                    
                    # Combine Left/Right Corner 3 into single Corner 3
                    if corner_pcts:
                        team_zones['Corner 3'] = np.mean(corner_pcts)
                    
                    # Store zone stats for this team
                    final_zones = {}
                    for z in STANDARD_ZONES:
                        if z in team_zones:
                            final_zones[z] = team_zones[z]
                            zone_sums[z] += team_zones[z]
                            zone_counts[z] += 1
                        else:
                            final_zones[z] = 0.45  # Default fallback
                    
                    season_stats[abbrev]['ZONE_DEFENSE'] = final_zones
                
                print(f"Successfully fetched zone stats for {len([a for a in season_stats if season_stats[a].get('ZONE_DEFENSE')])} teams")
                
            except Exception as e:
                print(f"Error fetching zone stats: {e}")
                # Fallback: set empty zone stats
                for abbrev in season_stats:
                    if 'ZONE_DEFENSE' not in season_stats[abbrev] or not season_stats[abbrev]['ZONE_DEFENSE']:
                        season_stats[abbrev]['ZONE_DEFENSE'] = {z: 0.45 for z in STANDARD_ZONES}

            # Calculate League Averages
            league_avgs = {}
            for z in STANDARD_ZONES:
                league_avgs[z] = zone_sums[z] / zone_counts[z] if zone_counts[z] > 0 else 0.45
            
            # Sanity check: warn if too few teams were used
            min_count = min(zone_counts.values()) if zone_counts else 0
            if min_count < 25:
                print(f"WARNING: League averages based on only {min_count} teams (should be ~30)")
            
            self.league_zone_stats[season] = league_avgs
            self.team_stats_cache[season] = season_stats
            self.save_cache()
            print(f"League Zone Averages for {season} (based on {min_count} teams):")
            for z, avg in league_avgs.items():
                print(f"  {z}: {avg:.3f}")
            
        except Exception as e:
            print(f"Error fetching team stats for {season}: {e}")

    def get_opponent_stats(self, row):
        # Parse Opponent Abbreviation from MATCHUP
        try:
            matchup = row['MATCHUP']
            opp_abbrev = matchup.split(' ')[-1]
            season = row['SEASON_ID']
            
            # Current season for zone matchup calculations ONLY
            current_season = SEASONS[-1]
            
            if season in self.team_stats_cache and opp_abbrev in self.team_stats_cache[season]:
                stats = self.team_stats_cache[season][opp_abbrev]
                
                # Zone Matchup Score: ONLY calculated for current season games
                # Previous season zone stats are outdated (roster/coaching changes) and would
                # create train/predict mismatch. Set to 0 for historical games.
                zone_score = 0
                
                if season == current_season:
                    # Only calculate zone matchup for current season games
                    current_season_stats = self.team_stats_cache.get(current_season, {}).get(opp_abbrev, {})
                    if 'ZONE_DEFENSE' in current_season_stats and current_season in self.league_zone_stats:
                        opp_zones = current_season_stats['ZONE_DEFENSE']
                        league_zones = self.league_zone_stats[current_season]
                        
                        for zone, freq in self.player_profile.items():
                            if zone not in STANDARD_ZONES or zone not in opp_zones:
                                continue
                            
                            pts_value = ZONE_POINT_VALUES.get(zone, 2.0)
                            opp_pct = opp_zones[zone]
                            
                            if zone not in league_zones:
                                raise ValueError(f"Missing league zone average for {zone} in season {current_season}")
                            league_pct = league_zones[zone]
                            
                            # Calculate expected points per shot for this zone
                            opp_expected_pts = opp_pct * pts_value
                            league_expected_pts = league_pct * pts_value
                            
                            # Points differential (positive = opponent allows MORE points than avg)
                            pts_differential = opp_expected_pts - league_expected_pts
                            
                            # Weight by player's shooting frequency from this zone
                            zone_score += freq * pts_differential * 100  # Scale up
                # else: zone_score remains 0 for previous season games (2024-25)
                
                # Calculate Expected Extra Possessions
                # Formula: (Opp_Pace - League_Avg_Pace) * (Minutes / 48)
                opp_pace = stats.get('PACE', 100.0)
                league_pace = self.league_avg_pace.get(season, 100.0)
                # Use average minutes from player profile (will be multiplied by actual mins in feature eng)
                extra_poss_per_48 = opp_pace - league_pace
                
                return pd.Series([
                    stats.get('DEF_RATING', 112.0), 
                    extra_poss_per_48,
                    zone_score
                ])
            else:
                raise ValueError(f"Missing opponent stats for {opp_abbrev} in season {season}")
        except Exception as e:
            raise RuntimeError(f"Error getting opponent stats for {row['MATCHUP']}: {e}")

    def feature_engineering(self, df):
        print("Engineering features...")
        
        # 1. Target
        df['Target_PTS'] = df['PTS']
        
        # 2. Basic Context
        df['Home_Away'] = df['MATCHUP'].apply(lambda x: 1 if 'vs.' in x else 0)
        
        # 3. Rest Days
        df['Rest_Days'] = df['GAME_DATE'].diff().dt.days - 1
        df['Rest_Days'] = df['Rest_Days'].fillna(3) 
        df['Rest_Days'] = df['Rest_Days'].apply(lambda x: 0 if x < 0 else (x if x < 5 else 5))
        
        # 4. Rolling Averages
        # Shift by 1 to avoid data leakage
        df['Last_5_PTS'] = df['PTS'].shift(1).rolling(window=5).mean()
        df['Last_5_MIN'] = df['MIN'].shift(1).rolling(window=5).mean()
        df['Last_5_FGA'] = df['FGA'].shift(1).rolling(window=5).mean()
        
        # Add Last 10 Games Rolling Averages
        df['Last_10_PTS'] = df['PTS'].shift(1).rolling(window=10).mean()
        df['Last_10_MIN'] = df['MIN'].shift(1).rolling(window=10).mean()
        df['Last_10_FGA'] = df['FGA'].shift(1).rolling(window=10).mean()
        
        # Season Average - calculate per season, not across all data
        # Group by SEASON_ID and calculate expanding mean within each season
        df['Season_Avg_PTS'] = df.groupby('SEASON_ID')['PTS'].transform(
            lambda x: x.shift(1).expanding().mean()
        )
        
        # 5. MEAN REVERSION FEATURE - Critical for avoiding overestimation
        # Positive = player is running HOT (expect regression DOWN)
        # Negative = player is running COLD (expect regression UP)
        df['Recent_vs_Season'] = df['Last_5_PTS'] - df['Season_Avg_PTS']
        
        # 6. Opponent Stats
        df[['Opponent_Def_Rating', 'Extra_Poss_Per_48', 'Zone_Matchup_Score']] = df.apply(self.get_opponent_stats, axis=1)
        
        # 7. Calculate Expected Extra Possessions based on actual minutes
        # Formula: (Opp_Pace - League_Avg_Pace) * (Minutes / 48)
        df['Expected_Extra_Poss'] = pd.to_numeric(df['Extra_Poss_Per_48'], errors='coerce') * (pd.to_numeric(df['MIN'], errors='coerce') / 48.0)

        # 8. Projected Minutes (Using actual minutes for training)
        df['Proj_Minutes'] = pd.to_numeric(df['MIN'], errors='coerce')
        
        # Ensure all numeric columns are properly typed
        numeric_cols = ['Opponent_Def_Rating', 'Extra_Poss_Per_48', 'Zone_Matchup_Score', 
                        'Expected_Extra_Poss', 'Proj_Minutes']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Drop NaNs created by rolling windows
        df = df.dropna()
        
        return df

    def train(self, df):
        # Simplified feature set - fewer features for small sample size
        features = [
            'Proj_Minutes', 'Season_Avg_PTS',
            'Last_5_PTS', 'Last_10_PTS',
            'Recent_vs_Season',          # Mean reversion signal
            'Home_Away', 'Rest_Days', 
            'Opponent_Def_Rating', 'Expected_Extra_Poss',
            'Zone_Matchup_Score'
        ]
        self.feature_columns = features
        
        # Store season average for prediction bounds
        self.training_season_avg = df['Season_Avg_PTS'].mean()
        self.training_pts_std = df['Target_PTS'].std()
        
        # Create feature weights to cap Rest_Days influence (max ~5% importance)
        # Also reduce weight of Recent_vs_Season to prevent over-correction
        feature_weights = []
        for f in features:
            if f == 'Rest_Days':
                feature_weights.append(0.15)  # Reduced weight
            elif f == 'Recent_vs_Season':
                feature_weights.append(0.5)   # Moderate weight - helps but shouldn't dominate
            else:
                feature_weights.append(1.0)
        
        X = df[features].copy()
        y = df['Target_PTS'].copy()
        
        # Ensure all feature columns are numeric (fixes rookie/missing data issues)
        for col in X.columns:
            X[col] = pd.to_numeric(X[col], errors='coerce')
        y = pd.to_numeric(y, errors='coerce')
        
        # Drop any rows with NaN values created by type conversion
        valid_mask = X.notna().all(axis=1) & y.notna()
        X = X[valid_mask]
        y = y[valid_mask]
        
        if len(X) == 0:
            raise ValueError("No valid training data after type conversion. Check data quality.")
        
        print(f"Training on {len(X)} games...")
        print(f"  → Season Avg PTS: {self.training_season_avg:.1f}")
        print(f"  → PTS Std Dev:    {self.training_pts_std:.1f}")
        
        tscv = TimeSeriesSplit(n_splits=5)
        fold = 1
        mae_scores = []
        
        for train_index, test_index in tscv.split(X):
            X_train, X_test = X.iloc[train_index], X.iloc[test_index]
            y_train, y_test = y.iloc[train_index], y.iloc[test_index]
            
            # Apply feature weights manually via sample weighting columns
            self.model.fit(
                X_train, y_train,
                eval_set=[(X_test, y_test)],
                verbose=False
            )
            
            preds = self.model.predict(X_test)
            mae = mean_absolute_error(y_test, preds)
            print(f"  Fold {fold}: MAE = {mae:.2f} pts")
            mae_scores.append(mae)
            fold += 1
            
        print(f"  ─────────────────────")
        print(f"  Average MAE: {np.mean(mae_scores):.2f} pts")
        
        # Final fit
        # Disable early stopping for final fit as we use all data
        self.model.set_params(early_stopping_rounds=None)
        self.model.fit(X, y, verbose=False)
        print("  ✅ Model training complete!")

    def predict_next_game(self, inputs):
        input_df = pd.DataFrame([inputs])
        input_df = input_df[self.feature_columns]
        raw_pred = self.model.predict(input_df)[0]
        
        # Apply reasonable bounds based on player's baseline
        # Predictions shouldn't deviate more than ~2 std deviations from season average
        # 2 std covers ~95% of outcomes - reasonable for betting predictions
        season_avg = inputs.get('Season_Avg_PTS', self.training_season_avg)
        lower_bound = max(5, season_avg - 2 * self.training_pts_std)  # Floor at 5 pts
        upper_bound = season_avg + 2 * self.training_pts_std
        
        bounded_pred = np.clip(raw_pred, lower_bound, upper_bound)
        
        if abs(raw_pred - bounded_pred) > 0.5:
            print(f"⚠️  Raw prediction {raw_pred:.1f} was bounded to {bounded_pred:.1f} (range: {lower_bound:.1f}-{upper_bound:.1f})")
        
        return bounded_pred


def show_prediction_gui(player_name, prediction, next_game_inputs, zone_data, pace_data, reversion_data, importance_pairs, matchup_info):
    """Display prediction results in a modern minimalist GUI"""
    
    # ===== MODERN COLOR PALETTE =====
    COLORS = {
        'bg_primary': '#0f0f0f',        # Deep black background
        'bg_card': '#1a1a1a',           # Card background
        'bg_elevated': '#242424',       # Elevated elements
        'bg_hover': '#2a2a2a',          # Hover state
        'text_primary': '#ffffff',      # Primary text
        'text_secondary': '#8b8b8b',    # Secondary/muted text
        'text_tertiary': '#5c5c5c',     # Tertiary text
        'accent': '#6366f1',            # Modern indigo accent
        'accent_soft': '#4f46e5',       # Softer accent
        'success': '#10b981',           # Green for positive
        'warning': '#f59e0b',           # Amber for warning
        'danger': '#ef4444',            # Red for negative
        'border': '#2a2a2a',            # Subtle border
        'divider': '#1f1f1f',           # Divider lines
    }
    
    root = tk.Tk()
    root.title(f"NBA Prediction • {player_name}")
    root.geometry("800x900")
    root.configure(bg=COLORS['bg_primary'])
    
    # Configure ttk styles for modern look
    style = ttk.Style()
    style.theme_use('clam')
    style.configure('TFrame', background=COLORS['bg_primary'])
    style.configure('Card.TFrame', background=COLORS['bg_card'])
    style.configure('TScrollbar', background=COLORS['bg_card'], troughcolor=COLORS['bg_primary'],
                    bordercolor=COLORS['bg_primary'], arrowcolor=COLORS['text_secondary'])
    
    # Main scrollable canvas
    main_canvas = tk.Canvas(root, bg=COLORS['bg_primary'], highlightthickness=0, bd=0)
    scrollbar = ttk.Scrollbar(root, orient="vertical", command=main_canvas.yview)
    scrollable_frame = tk.Frame(main_canvas, bg=COLORS['bg_primary'])
    
    scrollable_frame.bind(
        "<Configure>",
        lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all"))
    )
    
    main_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    main_canvas.configure(yscrollcommand=scrollbar.set)
    
    def on_mousewheel(event):
        main_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    main_canvas.bind_all("<MouseWheel>", on_mousewheel)
    
    main_canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    
    # Content container with max width for clean layout
    content_frame = tk.Frame(scrollable_frame, bg=COLORS['bg_primary'])
    content_frame.pack(fill="both", expand=True, padx=32, pady=32)
    
    # ===== HERO SECTION - PREDICTION =====
    hero_frame = tk.Frame(content_frame, bg=COLORS['bg_primary'])
    hero_frame.pack(fill="x", pady=(0, 40))
    
    # Player name - subtle label
    tk.Label(hero_frame, text="POINTS PREDICTION", 
             bg=COLORS['bg_primary'], fg=COLORS['text_tertiary'], 
             font=('Segoe UI', 10, 'bold')).pack(anchor='w')
    
    # Player name - main title
    tk.Label(hero_frame, text=player_name.title(), 
             bg=COLORS['bg_primary'], fg=COLORS['text_primary'], 
             font=('Segoe UI', 28, 'bold')).pack(anchor='w', pady=(4, 0))
    
    # Opponent info
    opponent = matchup_info.get('Opponent_Name', 'Unknown')
    home_away = "Home" if next_game_inputs['Home_Away'] == 1 else "Away"
    tk.Label(hero_frame, text=f"vs {opponent}  •  {home_away}", 
             bg=COLORS['bg_primary'], fg=COLORS['text_secondary'], 
             font=('Segoe UI', 12)).pack(anchor='w', pady=(2, 16))
    
    # Prediction value - large and prominent
    pred_container = tk.Frame(hero_frame, bg=COLORS['bg_primary'])
    pred_container.pack(anchor='w')
    
    tk.Label(pred_container, text=f"{prediction:.1f}", 
             bg=COLORS['bg_primary'], fg=COLORS['accent'], 
             font=('Segoe UI', 56, 'bold')).pack(side='left')
    
    tk.Label(pred_container, text="pts", 
             bg=COLORS['bg_primary'], fg=COLORS['text_tertiary'], 
             font=('Segoe UI', 18)).pack(side='left', padx=(8, 0), pady=(20, 0))
    
    # Helper function to create modern cards
    def create_card(parent, title=None):
        card = tk.Frame(parent, bg=COLORS['bg_card'])
        card.pack(fill="x", pady=(0, 16))
        
        inner = tk.Frame(card, bg=COLORS['bg_card'])
        inner.pack(fill="x", padx=24, pady=20)
        
        if title:
            tk.Label(inner, text=title, bg=COLORS['bg_card'], fg=COLORS['text_secondary'],
                     font=('Segoe UI', 11, 'bold')).pack(anchor='w', pady=(0, 16))
        
        return inner
    
    # Helper to create stat rows
    def create_stat_row(parent, label, value, value_color=None):
        row = tk.Frame(parent, bg=COLORS['bg_card'])
        row.pack(fill="x", pady=6)
        
        tk.Label(row, text=label, bg=COLORS['bg_card'], fg=COLORS['text_secondary'],
                 font=('Segoe UI', 11)).pack(side='left')
        
        color = value_color if value_color else COLORS['text_primary']
        tk.Label(row, text=value, bg=COLORS['bg_card'], fg=color,
                 font=('Segoe UI', 11, 'bold')).pack(side='right')
    
    # ===== KEY METRICS ROW =====
    metrics_frame = tk.Frame(content_frame, bg=COLORS['bg_primary'])
    metrics_frame.pack(fill="x", pady=(0, 24))
    
    # Season avg metric
    def create_metric_box(parent, label, value, subtitle=None):
        box = tk.Frame(parent, bg=COLORS['bg_card'])
        box.pack(side='left', fill='both', expand=True, padx=(0, 8))
        
        inner = tk.Frame(box, bg=COLORS['bg_card'])
        inner.pack(fill="x", padx=20, pady=16)
        
        tk.Label(inner, text=label, bg=COLORS['bg_card'], fg=COLORS['text_tertiary'],
                 font=('Segoe UI', 9)).pack(anchor='w')
        tk.Label(inner, text=value, bg=COLORS['bg_card'], fg=COLORS['text_primary'],
                 font=('Segoe UI', 22, 'bold')).pack(anchor='w', pady=(4, 0))
        if subtitle:
            tk.Label(inner, text=subtitle, bg=COLORS['bg_card'], fg=COLORS['text_secondary'],
                     font=('Segoe UI', 9)).pack(anchor='w', pady=(2, 0))
    
    create_metric_box(metrics_frame, "SEASON AVG", f"{float(next_game_inputs['Season_Avg_PTS']):.1f}")
    create_metric_box(metrics_frame, "LAST 5", f"{float(next_game_inputs['Last_5_PTS']):.1f}")
    create_metric_box(metrics_frame, "LAST 10", f"{float(next_game_inputs['Last_10_PTS']):.1f}")
    
    # Fix last box padding
    for child in metrics_frame.winfo_children():
        child.pack_configure(padx=4)
    metrics_frame.winfo_children()[0].pack_configure(padx=(0, 4))
    metrics_frame.winfo_children()[-1].pack_configure(padx=(4, 0))
    
    # ===== ZONE MATCHUP CARD =====
    zone_card = create_card(content_frame, "ZONE MATCHUP SCORE")
    
    player_profile = zone_data['player_profile']
    opp_zones = zone_data['opp_zones']
    league_zones = zone_data['league_zones']
    zone_score = zone_data['zone_score']
    
    # Table header - must match data row widths exactly
    header_row = tk.Frame(zone_card, bg=COLORS['bg_card'])
    header_row.pack(fill="x", pady=(0, 12))
    
    headers = [('Zone', 22, 'w'), ('Freq', 7, 'center'), ('Pts', 5, 'center'), 
               ('Opp%', 8, 'center'), ('Lg%', 8, 'center'), ('Diff', 8, 'center'), ('Score', 9, 'e')]
    for header, width, anchor in headers:
        tk.Label(header_row, text=header, bg=COLORS['bg_card'], fg=COLORS['text_tertiary'],
                 font=('Segoe UI', 11), width=width, anchor=anchor).pack(side='left', padx=3)
    
    # Divider under header
    tk.Frame(zone_card, bg=COLORS['divider'], height=1).pack(fill='x', pady=(0, 10))
    
    # Zone rows - full data table
    for zone in STANDARD_ZONES:
        freq = player_profile.get(zone, 0)
        if freq == 0:
            continue
        
        pts_value = ZONE_POINT_VALUES.get(zone, 2.0)
        opp_pct = opp_zones.get(zone, 0)
        league_pct = league_zones.get(zone, 0)
        diff_pct = (opp_pct - league_pct) * 100
        
        opp_expected_pts = opp_pct * pts_value
        league_expected_pts = league_pct * pts_value
        pts_differential = opp_expected_pts - league_expected_pts
        score_contrib = freq * pts_differential * 100
        
        # Determine row background based on score
        if score_contrib > 0.5:
            row_bg = '#0d1f14'  # Subtle green tint
        elif score_contrib < -0.5:
            row_bg = '#1f0d0d'  # Subtle red tint
        else:
            row_bg = COLORS['bg_card']
        
        row = tk.Frame(zone_card, bg=row_bg)
        row.pack(fill="x", pady=5)
        
        # Zone name
        tk.Label(row, text=zone, bg=row_bg, fg=COLORS['text_primary'],
                 font=('Segoe UI', 11), width=22, anchor='w').pack(side='left', padx=3)
        
        # Frequency
        tk.Label(row, text=f"{freq:.2f}", bg=row_bg, fg=COLORS['text_secondary'],
                 font=('Segoe UI', 11), width=7, anchor='center').pack(side='left', padx=3)
        
        # Points value
        tk.Label(row, text=f"{pts_value:.0f}", bg=row_bg, fg=COLORS['text_secondary'],
                 font=('Segoe UI', 11), width=5, anchor='center').pack(side='left', padx=3)
        
        # Opp%
        tk.Label(row, text=f"{opp_pct:.1%}", bg=row_bg, fg=COLORS['text_primary'],
                 font=('Segoe UI', 11), width=8, anchor='center').pack(side='left', padx=3)
        
        # League%
        tk.Label(row, text=f"{league_pct:.1%}", bg=row_bg, fg=COLORS['text_secondary'],
                 font=('Segoe UI', 11), width=8, anchor='center').pack(side='left', padx=3)
        
        # Diff%
        diff_color = COLORS['success'] if diff_pct > 1 else (COLORS['danger'] if diff_pct < -1 else COLORS['text_secondary'])
        tk.Label(row, text=f"{diff_pct:+.1f}%", bg=row_bg, fg=diff_color,
                 font=('Segoe UI', 11, 'bold'), width=8, anchor='center').pack(side='left', padx=3)
        
        # Score contribution
        score_color = COLORS['success'] if score_contrib > 0.5 else (COLORS['danger'] if score_contrib < -0.5 else COLORS['text_secondary'])
        tk.Label(row, text=f"{score_contrib:+.2f}", bg=row_bg, fg=score_color,
                 font=('Segoe UI', 11, 'bold'), width=9, anchor='e').pack(side='left', padx=3)
    
    # Divider
    tk.Frame(zone_card, bg=COLORS['divider'], height=1).pack(fill='x', pady=(16, 12))
    
    # Total score
    score_row = tk.Frame(zone_card, bg=COLORS['bg_card'])
    score_row.pack(fill="x")
    
    tk.Label(score_row, text="Total Score", bg=COLORS['bg_card'], fg=COLORS['text_secondary'],
             font=('Segoe UI', 11)).pack(side='left')
    
    score_color = COLORS['success'] if zone_score > 1 else (COLORS['danger'] if zone_score < -1 else COLORS['text_secondary'])
    score_label = "Favorable" if zone_score > 1 else ("Unfavorable" if zone_score < -1 else "Neutral")
    
    tk.Label(score_row, text=f"{zone_score:+.2f}  {score_label}", bg=COLORS['bg_card'], fg=score_color,
             font=('Segoe UI', 11, 'bold')).pack(side='right')
    
    # ===== PACE & REVERSION CARDS (SIDE BY SIDE) =====
    analysis_row = tk.Frame(content_frame, bg=COLORS['bg_primary'])
    analysis_row.pack(fill="x", pady=(0, 16))
    
    # Pace card
    pace_box = tk.Frame(analysis_row, bg=COLORS['bg_card'])
    pace_box.pack(side='left', fill='both', expand=True, padx=(0, 8))
    
    pace_inner = tk.Frame(pace_box, bg=COLORS['bg_card'])
    pace_inner.pack(fill="x", padx=20, pady=20)
    
    tk.Label(pace_inner, text="PACE", bg=COLORS['bg_card'], fg=COLORS['text_secondary'],
             font=('Segoe UI', 10, 'bold')).pack(anchor='w', pady=(0, 12))
    
    opp_pace = pace_data['opp_pace']
    league_pace = pace_data['league_pace']
    pace_diff = opp_pace - league_pace
    
    create_stat_row(pace_inner, "Opponent", f"{opp_pace:.1f}")
    create_stat_row(pace_inner, "League Avg", f"{league_pace:.1f}")
    
    pace_color = COLORS['success'] if pace_diff > 2 else (COLORS['danger'] if pace_diff < -2 else COLORS['text_secondary'])
    create_stat_row(pace_inner, "Differential", f"{pace_diff:+.1f}", pace_color)
    
    # Reversion card
    rev_box = tk.Frame(analysis_row, bg=COLORS['bg_card'])
    rev_box.pack(side='right', fill='both', expand=True, padx=(8, 0))
    
    rev_inner = tk.Frame(rev_box, bg=COLORS['bg_card'])
    rev_inner.pack(fill="x", padx=20, pady=20)
    
    tk.Label(rev_inner, text="TREND", bg=COLORS['bg_card'], fg=COLORS['text_secondary'],
             font=('Segoe UI', 10, 'bold')).pack(anchor='w', pady=(0, 12))
    
    diff = reversion_data['diff']
    create_stat_row(rev_inner, "Recent", f"{reversion_data['last_5']:.1f}")
    create_stat_row(rev_inner, "Season", f"{reversion_data['season_avg']:.1f}")
    
    trend_color = COLORS['warning'] if abs(diff) > 3 else COLORS['text_secondary']
    trend_text = "Hot" if diff > 3 else ("Cold" if diff < -3 else "Stable")
    create_stat_row(rev_inner, "Status", f"{diff:+.1f} • {trend_text}", trend_color)
    
    # ===== DEFENSE & CONTEXT CARD =====
    context_card = create_card(content_frame, "MATCHUP CONTEXT")
    
    def_rating = float(next_game_inputs['Opponent_Def_Rating'])
    def_tier = "Elite" if def_rating < 108 else ("Strong" if def_rating < 112 else ("Average" if def_rating < 115 else "Weak"))
    def_color = COLORS['danger'] if def_rating < 110 else (COLORS['warning'] if def_rating < 114 else COLORS['success'])
    
    create_stat_row(context_card, "Defense Rating", f"{def_rating:.1f} • {def_tier}", def_color)
    create_stat_row(context_card, "Projected Minutes", f"{next_game_inputs['Proj_Minutes']:.0f}")
    create_stat_row(context_card, "Rest Days", f"{next_game_inputs['Rest_Days']}")
    create_stat_row(context_card, "Extra Possessions", f"{float(next_game_inputs['Expected_Extra_Poss']):+.1f}")
    
    # ===== FEATURE IMPORTANCE CARD =====
    importance_card = create_card(content_frame, "MODEL WEIGHTS")
    
    for name, imp in importance_pairs:  # Show all features
        row = tk.Frame(importance_card, bg=COLORS['bg_card'])
        row.pack(fill="x", pady=6)
        
        # Clean feature name
        clean_name = name.replace('_', ' ').title()
        tk.Label(row, text=clean_name, bg=COLORS['bg_card'], fg=COLORS['text_secondary'],
                 font=('Segoe UI', 10), width=18, anchor='w').pack(side='left')
        
        # Progress bar - modern style
        bar_outer = tk.Frame(row, bg=COLORS['bg_elevated'], height=4)
        bar_outer.pack(side='left', fill='x', expand=True, padx=(8, 12))
        bar_outer.pack_propagate(False)
        
        bar_inner = tk.Frame(bar_outer, bg=COLORS['accent'], height=4)
        bar_inner.place(relx=0, rely=0, relwidth=imp, relheight=1)
        
        tk.Label(row, text=f"{imp*100:.0f}%", bg=COLORS['bg_card'], fg=COLORS['text_tertiary'],
                 font=('Segoe UI', 10), width=4, anchor='e').pack(side='right')
    
    # ===== FOOTER =====
    footer = tk.Frame(content_frame, bg=COLORS['bg_primary'])
    footer.pack(fill="x", pady=(24, 0))
    
    # Close button - minimal style
    close_btn = tk.Button(footer, text="Close", command=root.destroy,
                          bg=COLORS['bg_elevated'], fg=COLORS['text_secondary'],
                          font=('Segoe UI', 10), padx=24, pady=10,
                          relief=tk.FLAT, cursor='hand2', bd=0,
                          activebackground=COLORS['bg_hover'],
                          activeforeground=COLORS['text_primary'])
    close_btn.pack()
    
    # Center window
    root.update_idletasks()
    x = (root.winfo_screenwidth() // 2) - (800 // 2)
    y = (root.winfo_screenheight() // 2) - (900 // 2)
    root.geometry(f"800x900+{x}+{y}")
    
    root.mainloop()


if __name__ == "__main__":
    predictor = NBAPredictor()
    
    try:
        print("\n" + "╔" + "═" * 58 + "╗")
        print(f"║   🏀  NBA POINTS PREDICTOR                              ║")
        print(f"║   Player: {TARGET_PLAYER:<43}   ║")
        print("╚" + "═" * 58 + "╝")
        print()
        
        pid = predictor.get_player_id(TARGET_PLAYER)
        df = predictor.fetch_game_logs(pid, SEASONS)
        
        df_processed = predictor.feature_engineering(df)
        
        predictor.train(df_processed)
        
        # For prediction, we need the ACTUAL last N games (not shifted)
        # The shifted values in df_processed are for training (to avoid leakage)
        # But for predicting the NEXT game, we use the most recent actual games
        last_game = df_processed.iloc[-1]
        
        # Calculate actual rolling stats from raw game log (df) for prediction
        # These are the TRUE last 5/10 games before the upcoming game
        actual_last_5_pts = df['PTS'].tail(5).mean()
        actual_last_10_pts = df['PTS'].tail(10).mean()
        
        # Season average should include ALL games in current season
        current_season = SEASONS[-1]
        current_season_games = df[df['SEASON_ID'] == current_season]
        actual_season_avg = current_season_games['PTS'].mean()
        
        # Mean reversion signal using actual values
        actual_recent_vs_season = actual_last_5_pts - actual_season_avg
        
        print("\n" + "╔" + "═" * 58 + "╗")
        print(f"║   🔮  GENERATING PREDICTION FOR {TARGET_PLAYER.upper():<18}   ║")
        print("╚" + "═" * 58 + "╝")
        
        # Fetch Matchup Info
        matchup_info = get_matchup_info.get_game_info()
        
        # Calculate Zone Matchup Score for Next Game
        # We need the League Average for the current season (2025-26)
        current_season = SEASONS[-1]
        league_zones = predictor.league_zone_stats.get(current_season, {})
        player_prof = predictor.player_profile
        
        # Opponent Zone Stats from get_matchup_info
        opp_zones = matchup_info['Opponent_Zone_Stats']
        
        # Sanity check: Compare zone matchup direction with defensive rating
        opp_def_rating = matchup_info['Opponent_Def_Rating']
        opp_name = matchup_info.get('Opponent_Name', 'Unknown')
        
        print("\n" + "═" * 85)
        print("  🎯  ZONE MATCHUP ANALYSIS (Points-Weighted)")
        print("═" * 85)
        
        # Show defensive context
        if opp_def_rating < 108:
            def_tier = "ELITE (Top 5)"
        elif opp_def_rating < 112:
            def_tier = "Strong (Top 10)"
        elif opp_def_rating < 115:
            def_tier = "Average"
        else:
            def_tier = "Weak (Bottom 10)"
        print(f"  Opponent: {opp_name} | Def Rating: {opp_def_rating:.1f} ({def_tier})")
        print("  " + "─" * 83)
        
        print(f"  {'Zone':<22} │ {'Freq':^6} │ {'Pts':^4} │ {'Opp%':^6} │ {'Lg%':^6} │ {'Diff':^6} │ {'Score':^7}")
        print("  " + "─" * 22 + "┼" + "─" * 8 + "┼" + "─" * 6 + "┼" + "─" * 8 + "┼" + "─" * 8 + "┼" + "─" * 8 + "┼" + "─" * 9)
        
        zone_score = 0
        
        for zone in STANDARD_ZONES:
            freq = player_prof.get(zone, 0)
            if freq == 0:
                continue
                
            pts_value = ZONE_POINT_VALUES.get(zone, 2.0)
            
            if zone not in opp_zones:
                raise ValueError(f"Missing opponent zone stats for {zone}")
            opp_pct = opp_zones[zone]
            
            if zone not in league_zones:
                raise ValueError(f"Missing league zone average for {zone}")
            league_pct = league_zones[zone]
            
            # Calculate expected points per shot
            opp_expected_pts = opp_pct * pts_value
            league_expected_pts = league_pct * pts_value
            
            # Points differential
            pts_differential = opp_expected_pts - league_expected_pts
            score_contrib = freq * pts_differential * 100
            zone_score += score_contrib
            
            # Color indicator for score
            score_indicator = "🟢" if score_contrib > 0.5 else ("🔴" if score_contrib < -0.5 else "⚪")
            diff_pct = (opp_pct - league_pct) * 100
            print(f"  {zone:<22} │ {freq:^6.2f} │ {pts_value:^4.0f} │ {opp_pct:^6.1%} │ {league_pct:^6.1%} │ {diff_pct:^+5.1f}% │ {score_contrib:^+6.2f} {score_indicator}")
            
        print("  " + "─" * 22 + "┴" + "─" * 8 + "┴" + "─" * 6 + "┴" + "─" * 8 + "┴" + "─" * 8 + "┴" + "─" * 8 + "┴" + "─" * 9)
        zone_indicator = "🟢 Favorable" if zone_score > 1 else ("🔴 Unfavorable" if zone_score < -1 else "⚪ Neutral")
        print(f"  {'TOTAL ZONE MATCHUP SCORE:':<56} {zone_score:^+6.2f}  {zone_indicator}")
        
        print("═" * 85)

        # Calculate Expected Extra Possessions for prediction
        opp_pace = matchup_info['Opponent_Pace']
        league_pace = predictor.league_avg_pace.get(current_season, 100.0)
        expected_extra_poss = (opp_pace - league_pace) * (Proj_Minutes / 48.0)
        
        print("\n" + "═" * 60)
        print("  📊  PACE & TEMPO ANALYSIS")
        print("═" * 60)
        pace_diff = opp_pace - league_pace
        pace_indicator = "🏃 Fast" if pace_diff > 2 else ("🐢 Slow" if pace_diff < -2 else "➡️  Average")
        print(f"  Opponent Pace:      {opp_pace:>8.1f}")
        print(f"  League Average:     {league_pace:>8.1f}")
        print(f"  Pace Differential:  {pace_diff:>+8.1f}  {pace_indicator}")
        print(f"  Expected Extra Possessions: {expected_extra_poss:>+.1f}")
        print("─" * 60)
        
        # Mean reversion analysis using ACTUAL recent stats
        print("\n" + "═" * 60)
        print("  📈  MEAN REVERSION ANALYSIS")
        print("═" * 60)
        print(f"  Last 5 Games Avg:   {actual_last_5_pts:>8.1f}")
        print(f"  Season Average:     {actual_season_avg:>8.1f}")
        print(f"  Differential:       {actual_recent_vs_season:>+8.1f}")
        print("─" * 60)
        if actual_recent_vs_season > 3:
            print("  ⚠️  Player is HOT → Expect regression DOWN toward season avg")
        elif actual_recent_vs_season < -3:
            print("  ⚠️  Player is COLD → Expect regression UP toward season avg")
        else:
            print("  ✅  Player performing near season average")
        
        # Construct inputs using ACTUAL recent stats (not shifted training values)
        next_game_inputs = {
            'Proj_Minutes': Proj_Minutes,
            'Season_Avg_PTS': actual_season_avg,
            'Last_5_PTS': actual_last_5_pts,
            'Last_10_PTS': actual_last_10_pts,
            'Recent_vs_Season': actual_recent_vs_season,
            'Home_Away': matchup_info['Home_Away'], 
            'Rest_Days': matchup_info['Rest_Days'], 
            'Opponent_Def_Rating': matchup_info['Opponent_Def_Rating'],
            'Expected_Extra_Poss': expected_extra_poss,
            'Zone_Matchup_Score': zone_score
        }
        
        prediction = predictor.predict_next_game(next_game_inputs)
        
        # Print inputs
        print("\n" + "═" * 60)
        print("  🔢  MODEL INPUT FEATURES")
        print("═" * 60)
        home_away_str = "🏠 Home" if next_game_inputs['Home_Away'] == 1 else "✈️  Away"
        rest_str = f"{next_game_inputs['Rest_Days']} day(s)"
        def_rating = float(next_game_inputs['Opponent_Def_Rating'])
        def_indicator = "🛡️ Elite" if def_rating < 108 else ("💪 Strong" if def_rating < 112 else ("📊 Average" if def_rating < 115 else "🎯 Weak"))
        
        print(f"  {'Projected Minutes:':<28} {Proj_Minutes:>10.1f}")
        print(f"  {'Season Average PTS:':<28} {float(next_game_inputs['Season_Avg_PTS']):>10.1f}")
        print(f"  {'Last 5 Games PTS:':<28} {float(next_game_inputs['Last_5_PTS']):>10.1f}")
        print(f"  {'Last 10 Games PTS:':<28} {float(next_game_inputs['Last_10_PTS']):>10.1f}")
        print(f"  {'Recent vs Season:':<28} {float(next_game_inputs['Recent_vs_Season']):>+10.1f}")
        print("  " + "─" * 56)
        print(f"  {'Location:':<28} {home_away_str:>10}")
        print(f"  {'Rest Days:':<28} {rest_str:>10}")
        print("  " + "─" * 56)
        print(f"  {'Opponent Def Rating:':<28} {def_rating:>10.1f}  {def_indicator}")
        print(f"  {'Expected Extra Poss:':<28} {float(next_game_inputs['Expected_Extra_Poss']):>+10.1f}")
        print(f"  {'Zone Matchup Score:':<28} {float(next_game_inputs['Zone_Matchup_Score']):>+10.2f}")
        print("═" * 60)
        
        # Final Prediction Box
        print("\n" + "╔" + "═" * 58 + "╗")
        print("║" + " " * 58 + "║")
        print(f"║   🏀  PREDICTED POINTS FOR {TARGET_PLAYER.upper():<21}    ║")
        print("║" + " " * 58 + "║")
        print(f"║                      {prediction:>6.1f}                              ║")
        print("║" + " " * 58 + "║")
        print("╚" + "═" * 58 + "╝")
        
        print("\n" + "═" * 60)
        print("  📊  FEATURE IMPORTANCE")
        print("═" * 60)
        importances = predictor.model.feature_importances_
        # Sort by importance
        importance_pairs = sorted(zip(predictor.feature_columns, importances), key=lambda x: x[1], reverse=True)
        for name, imp in importance_pairs:
            bar_len = int(imp * 40)
            bar = "█" * bar_len + "░" * (40 - bar_len)
            print(f"  {name:<22} │ {bar} │ {imp*100:>5.1f}%")
        print("═" * 60)
        
        # Launch GUI with results
        show_prediction_gui(
            player_name=TARGET_PLAYER,
            prediction=prediction,
            next_game_inputs=next_game_inputs,
            zone_data={
                'player_profile': player_prof,
                'opp_zones': opp_zones,
                'league_zones': league_zones,
                'zone_score': zone_score
            },
            pace_data={
                'opp_pace': opp_pace,
                'league_pace': league_pace,
                'expected_extra_poss': expected_extra_poss
            },
            reversion_data={
                'last_5': actual_last_5_pts,
                'season_avg': actual_season_avg,
                'diff': actual_recent_vs_season
            },
            importance_pairs=importance_pairs,
            matchup_info=matchup_info
        )
            
    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()
