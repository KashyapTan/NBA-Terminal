"""
NBA Points Prediction Model Backtest Evaluation
================================================
Evaluates the XGBoost points prediction model using walk-forward validation
on all NBA starters with 30+ games from 2025-26 season start to 1/27/2026.

Metrics:
- MAE (Mean Absolute Error)
- RMSE (Root Mean Squared Error)
- Within ±2.5 points accuracy (typical betting margin)
- Within ±5 points accuracy
- Over/Under accuracy (vs season average line)
- Directional accuracy (predicting hot/cold streaks)
"""

import pandas as pd
import numpy as np
import time
import os
import pickle
import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta
from tqdm import tqdm
from collections import defaultdict

try:
    import xgboost as xgb
    from sklearn.metrics import mean_absolute_error, mean_squared_error, accuracy_score, f1_score, precision_score, recall_score
except ImportError as e:
    print(f"Missing required packages: {e}")
    print("Install with: pip install xgboost scikit-learn")
    exit(1)

from nba_api.stats.static import players, teams
from nba_api.stats.endpoints import (
    playergamelog, 
    leaguedashteamstats, 
    leaguedashteamshotlocations,
    commonteamroster,
    playerdashboardbyshootingsplits,
    leaguedashplayerstats
)

# ============= CONFIGURATION =============
SEASONS = ["2024-25", "2025-26"]       # Both seasons for training (like p.py)
CURRENT_SEASON = "2025-26"
PREV_SEASON = "2024-25"
SEASON_START = datetime(2025, 10, 22)  # 2025-26 NBA season start
EVAL_END = datetime(2026, 1, 27)       # Today's date for evaluation
MIN_GAMES_FOR_EVAL = 30                # Minimum games in current season
MIN_GAMES_PREV_SEASON = 20             # Minimum games in previous season (filters rookies)
MIN_GAMES_FOR_TRAINING = 10            # Minimum games before we start predicting
MIN_MINUTES_AVG = 25                   # Minimum average minutes (starter threshold)
CACHE_FILE = "eval_cache.pkl"

# Zone configurations (from p.py)
ZONE_POINT_VALUES = {
    'Restricted Area': 2.0,
    'In The Paint (Non-RA)': 2.0,
    'Mid-Range': 2.0,
    'Corner 3': 3.0,
    'Above the Break 3': 3.0
}
STANDARD_ZONES = ['Restricted Area', 'In The Paint (Non-RA)', 'Mid-Range', 'Corner 3', 'Above the Break 3']


class EvalCache:
    """Simple cache for API data to avoid rate limits"""
    def __init__(self):
        self.team_stats = {}      # season -> {abbrev: stats}
        self.league_zones = {}    # season -> {zone: avg}
        self.league_pace = {}     # season -> pace
        self.player_profiles = {} # player_id -> {zone: freq}
        self.player_games = {}    # player_id -> DataFrame (game logs)
        self.eligible_players = None  # Cached eligible players list
        self.load()
    
    def load(self):
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, 'rb') as f:
                    data = pickle.load(f)
                    self.team_stats = data.get('team_stats', {})
                    self.league_zones = data.get('league_zones', {})
                    self.league_pace = data.get('league_pace', {})
                    self.player_profiles = data.get('player_profiles', {})
                    self.player_games = data.get('player_games', {})
                    self.eligible_players = data.get('eligible_players', None)
                print(f"Loaded eval cache ({len(self.player_profiles)} player profiles, {len(self.player_games)} game logs)")
            except Exception as e:
                print(f"Cache load error: {e}")
    
    def save(self):
        with open(CACHE_FILE, 'wb') as f:
            pickle.dump({
                'team_stats': self.team_stats,
                'league_zones': self.league_zones,
                'league_pace': self.league_pace,
                'player_profiles': self.player_profiles,
                'player_games': self.player_games,
                'eligible_players': self.eligible_players
            }, f)


class BacktestEvaluator:
    def __init__(self):
        self.cache = EvalCache()
        self.results = []  # Store all predictions: {player, game_date, predicted, actual, ...}
        
    def get_eligible_players(self):
        """Get all non-rookie players with 30+ games and 25+ min avg in 2025-26"""
        # Check cache first
        if self.cache.eligible_players is not None:
            print(f"\n📋 Using cached eligible players ({len(self.cache.eligible_players)} players)")
            return self.cache.eligible_players
        
        print("\n📋 Fetching eligible players (30+ games, 25+ min avg, non-rookies)...")
        
        # Get current season stats
        player_stats = leaguedashplayerstats.LeagueDashPlayerStats(
            season=CURRENT_SEASON,
            per_mode_detailed='PerGame'
        )
        df = player_stats.get_data_frames()[0]
        
        # Filter: 30+ games AND 25+ minutes average in current season
        eligible = df[(df['GP'] >= MIN_GAMES_FOR_EVAL) & (df['MIN'] >= MIN_MINUTES_AVG)]
        
        # Get previous season stats to filter out rookies
        print("   Checking for previous season data (filtering rookies)...")
        time.sleep(0.6)
        prev_stats = leaguedashplayerstats.LeagueDashPlayerStats(
            season=PREV_SEASON,
            per_mode_detailed='PerGame'
        )
        prev_df = prev_stats.get_data_frames()[0]
        
        # Players with 20+ games last season
        prev_players = set(prev_df[prev_df['GP'] >= MIN_GAMES_PREV_SEASON]['PLAYER_ID'].values)
        
        players_list = []
        rookies_filtered = 0
        
        for _, row in eligible.iterrows():
            # Skip rookies (no previous season data)
            if row['PLAYER_ID'] not in prev_players:
                rookies_filtered += 1
                continue
                
            players_list.append({
                'id': row['PLAYER_ID'],
                'name': row['PLAYER_NAME'],
                'team': row['TEAM_ABBREVIATION'],
                'games': row['GP'],
                'ppg': row['PTS'],
                'mpg': row['MIN']
            })
        
        print(f"   Found {len(players_list)} eligible players ({rookies_filtered} rookies filtered)")
        
        # Save to cache
        self.cache.eligible_players = players_list
        self.cache.save()
        
        return players_list
    
    def fetch_team_defense_stats(self):
        """Fetch all team defensive stats for both seasons"""
        for season in SEASONS:
            if season in self.cache.team_stats:
                continue
            
            print(f"\n🛡️  Fetching team defense stats for {season}...")
            
            # Advanced stats (Def Rating, Pace)
            adv = leaguedashteamstats.LeagueDashTeamStats(
                season=season, 
                measure_type_detailed_defense='Advanced'
            )
            adv_df = adv.get_data_frames()[0]
            
            nba_teams = teams.get_teams()
            id_to_abbrev = {t['id']: t['abbreviation'] for t in nba_teams}
            
            team_stats = {}
            pace_values = []
            
            for _, row in adv_df.iterrows():
                tid = row['TEAM_ID']
                if tid in id_to_abbrev:
                    abbrev = id_to_abbrev[tid]
                    team_stats[abbrev] = {
                        'DEF_RATING': row['DEF_RATING'],
                        'PACE': row['PACE'],
                        'ZONE_DEFENSE': {}
                    }
                    pace_values.append(row['PACE'])
            
            self.cache.league_pace[season] = np.mean(pace_values)
            
            # Zone defense stats - only for current season (matches p.py behavior)
            if season == CURRENT_SEASON:
                print("   Fetching zone defense stats...")
                time.sleep(0.6)
                
                try:
                    shot_locs = leaguedashteamshotlocations.LeagueDashTeamShotLocations(
                        season=season,
                        per_mode_detailed='PerGame',
                        distance_range='By Zone',
                        measure_type_simple='Opponent',
                        timeout=60
                    )
                    zone_df = shot_locs.get_data_frames()[0]
                    
                    zone_sums = {z: 0 for z in STANDARD_ZONES}
                    zone_counts = {z: 0 for z in STANDARD_ZONES}
                    
                    for _, row in zone_df.iterrows():
                        tid = row.iloc[0]
                        if tid not in id_to_abbrev:
                            continue
                        abbrev = id_to_abbrev[tid]
                        if abbrev not in team_stats:
                            continue
                        
                        team_zones = {}
                        corner_pcts = []
                        
                        for col in zone_df.columns:
                            if len(col) == 2:
                                zone_name, stat_type = col
                                zone_name = str(zone_name)
                                stat_type = str(stat_type)
                                
                                if stat_type == 'OPP_FG_PCT':
                                    pct = row[col]
                                    if pd.notna(pct):
                                        if 'Corner 3' in zone_name and zone_name != 'Corner 3':
                                            corner_pcts.append(pct)
                                        elif zone_name in STANDARD_ZONES:
                                            team_zones[zone_name] = pct
                        
                        if corner_pcts:
                            team_zones['Corner 3'] = np.mean(corner_pcts)
                        
                        for z in STANDARD_ZONES:
                            if z in team_zones:
                                team_stats[abbrev]['ZONE_DEFENSE'][z] = team_zones[z]
                                zone_sums[z] += team_zones[z]
                                zone_counts[z] += 1
                            else:
                                team_stats[abbrev]['ZONE_DEFENSE'][z] = 0.45
                    
                    # League averages
                    league_zones = {}
                    for z in STANDARD_ZONES:
                        league_zones[z] = zone_sums[z] / zone_counts[z] if zone_counts[z] > 0 else 0.45
                    
                    self.cache.league_zones[season] = league_zones
                    
                except Exception as e:
                    print(f"   Warning: Zone stats fetch failed: {e}")
                    self.cache.league_zones[season] = {z: 0.45 for z in STANDARD_ZONES}
                    for abbrev in team_stats:
                        team_stats[abbrev]['ZONE_DEFENSE'] = {z: 0.45 for z in STANDARD_ZONES}
            else:
                # Previous season - no zone stats (matches p.py behavior)
                for abbrev in team_stats:
                    team_stats[abbrev]['ZONE_DEFENSE'] = {}
            
            self.cache.team_stats[season] = team_stats
            self.cache.save()
            print(f"   Cached stats for {len(team_stats)} teams")
            time.sleep(0.6)
    
    def fetch_player_profile(self, player_id):
        """Fetch player's shooting zone profile"""
        if player_id in self.cache.player_profiles:
            return self.cache.player_profiles[player_id]
        
        try:
            splits = playerdashboardbyshootingsplits.PlayerDashboardByShootingSplits(
                player_id=player_id,
                season=CURRENT_SEASON,
                per_mode_detailed='PerGame'
            )
            area_df = splits.get_data_frames()[3]
            
            total_fga = area_df['FGA'].sum()
            profile = {}
            
            raw_fga = {}
            for _, row in area_df.iterrows():
                zone = row['GROUP_VALUE']
                raw_fga[zone] = row['FGA']
            
            # Normalize corner 3s
            normalized_fga = {}
            corner_3_fga = 0
            for zone, fga in raw_fga.items():
                if 'Corner 3' in zone:
                    corner_3_fga += fga
                else:
                    normalized_fga[zone] = fga
            
            if corner_3_fga > 0:
                normalized_fga['Corner 3'] = corner_3_fga
            
            for zone, fga in normalized_fga.items():
                if zone in STANDARD_ZONES:
                    profile[zone] = fga / total_fga if total_fga > 0 else 0
            
            for zone in STANDARD_ZONES:
                if zone not in profile:
                    profile[zone] = 0.0
            
            self.cache.player_profiles[player_id] = profile
            time.sleep(0.5)
            return profile
            
        except Exception as e:
            # Return default profile on error
            return {z: 0.2 for z in STANDARD_ZONES}
    
    def fetch_player_games(self, player_id):
        """Fetch all games for a player across both seasons"""
        # Check cache first
        if player_id in self.cache.player_games:
            return self.cache.player_games[player_id].copy()
        
        all_logs = []
        
        for season in SEASONS:
            try:
                log = playergamelog.PlayerGameLog(player_id=player_id, season=season)
                df = log.get_data_frames()[0]
                
                if not df.empty:
                    df['SEASON_ID'] = season
                    all_logs.append(df)
                
                time.sleep(0.3)
            except Exception:
                continue
        
        if not all_logs:
            return None
        
        df = pd.concat(all_logs, ignore_index=True)
        df['GAME_DATE'] = pd.to_datetime(df['GAME_DATE'])
        df = df.sort_values('GAME_DATE').reset_index(drop=True)
        
        # Save to cache
        self.cache.player_games[player_id] = df
        
        return df
    
    def get_eval_games(self, df):
        """Get only games within the evaluation period (2025-26 season)"""
        return df[(df['GAME_DATE'] >= SEASON_START) & (df['GAME_DATE'] <= EVAL_END)]
    
    def calculate_zone_score(self, player_profile, opp_abbrev, season):
        """Calculate zone matchup score for a game (only for current season)"""
        # Zone score is 0 for previous season games (matches p.py behavior)
        if season != CURRENT_SEASON:
            return 0
        
        if CURRENT_SEASON not in self.cache.team_stats:
            return 0
        
        team_stats = self.cache.team_stats[CURRENT_SEASON].get(opp_abbrev, {})
        opp_zones = team_stats.get('ZONE_DEFENSE', {})
        league_zones = self.cache.league_zones.get(CURRENT_SEASON, {})
        
        zone_score = 0
        for zone, freq in player_profile.items():
            if zone not in STANDARD_ZONES or zone not in opp_zones:
                continue
            
            pts_value = ZONE_POINT_VALUES.get(zone, 2.0)
            opp_pct = opp_zones.get(zone, 0.45)
            league_pct = league_zones.get(zone, 0.45)
            
            opp_expected_pts = opp_pct * pts_value
            league_expected_pts = league_pct * pts_value
            pts_differential = opp_expected_pts - league_expected_pts
            
            zone_score += freq * pts_differential * 100
        
        return zone_score
    
    def engineer_features(self, df, player_profile):
        """Create features for a player's game log"""
        df = df.copy()
        
        # Basic features
        df['Home_Away'] = df['MATCHUP'].apply(lambda x: 1 if 'vs.' in x else 0)
        
        # Rest days
        df['Rest_Days'] = df['GAME_DATE'].diff().dt.days - 1
        df['Rest_Days'] = df['Rest_Days'].fillna(3)
        df['Rest_Days'] = df['Rest_Days'].apply(lambda x: max(0, min(x, 5)))
        
        # Rolling averages (shifted to avoid leakage)
        df['Last_5_PTS'] = df['PTS'].shift(1).rolling(window=5, min_periods=1).mean()
        df['Last_10_PTS'] = df['PTS'].shift(1).rolling(window=10, min_periods=1).mean()
        df['Last_5_MIN'] = df['MIN'].shift(1).rolling(window=5, min_periods=1).mean()
        
        # Season average - calculate per season (matches p.py)
        df['Season_Avg_PTS'] = df.groupby('SEASON_ID')['PTS'].transform(
            lambda x: x.shift(1).expanding().mean()
        )
        
        # Mean reversion signal
        df['Recent_vs_Season'] = df['Last_5_PTS'] - df['Season_Avg_PTS']
        
        # Opponent stats
        def get_opp_stats(row):
            matchup = row['MATCHUP']
            opp_abbrev = matchup.split(' ')[-1]
            season = row['SEASON_ID']
            
            team_stats = self.cache.team_stats.get(season, {}).get(opp_abbrev, {})
            def_rating = team_stats.get('DEF_RATING', 112.0)
            pace = team_stats.get('PACE', 100.0)
            league_pace = self.cache.league_pace.get(season, 100.0)
            
            zone_score = self.calculate_zone_score(player_profile, opp_abbrev, season)
            
            return pd.Series([def_rating, pace - league_pace, zone_score, opp_abbrev])
        
        df[['Opponent_Def_Rating', 'Extra_Poss_Per_48', 'Zone_Matchup_Score', 'Opp_Abbrev']] = df.apply(get_opp_stats, axis=1)
        
        # Expected extra possessions
        df['Expected_Extra_Poss'] = df['Extra_Poss_Per_48'] * (df['MIN'].astype(float) / 48.0)
        
        # Projected minutes (use last 5 avg for prediction)
        df['Proj_Minutes'] = df['Last_5_MIN']
        
        # Target
        df['Target_PTS'] = df['PTS']
        
        return df
    
    def run_player_backtest(self, player_info):
        """Run walk-forward backtest for a single player"""
        player_id = player_info['id']
        player_name = player_info['name']
        
        # Fetch game log (both seasons)
        df = self.fetch_player_games(player_id)
        if df is None or len(df) < MIN_GAMES_FOR_TRAINING:
            return []
        
        # Fetch player shooting profile
        player_profile = self.fetch_player_profile(player_id)
        
        # Engineer features
        df = self.engineer_features(df, player_profile)
        
        # Drop rows with NaN in critical columns
        feature_cols = ['Proj_Minutes', 'Season_Avg_PTS', 'Last_5_PTS', 'Last_10_PTS',
                        'Recent_vs_Season', 'Home_Away', 'Rest_Days', 
                        'Opponent_Def_Rating', 'Expected_Extra_Poss', 'Zone_Matchup_Score']
        
        df = df.dropna(subset=feature_cols + ['Target_PTS'])
        
        if len(df) < MIN_GAMES_FOR_TRAINING + 5:
            return []
        
        # Find first game in evaluation period (2025-26 season)
        eval_mask = (df['GAME_DATE'] >= SEASON_START) & (df['GAME_DATE'] <= EVAL_END)
        eval_indices = df[eval_mask].index.tolist()
        
        if len(eval_indices) < 5:
            return []
        
        # Walk-forward evaluation - only predict on 2025-26 games
        predictions = []
        
        for idx in eval_indices:
            # Get position in dataframe
            pos = df.index.get_loc(idx)
            
            # Need at least MIN_GAMES_FOR_TRAINING games before this one
            if pos < MIN_GAMES_FOR_TRAINING:
                continue
            
            # Training data: all games before this game (includes 2024-25)
            train_df = df.iloc[:pos]
            test_row = df.loc[idx]
            
            X_train = train_df[feature_cols].astype(float)
            y_train = train_df['Target_PTS'].astype(float)
            
            # Train model
            model = xgb.XGBRegressor(
                n_estimators=100,
                learning_rate=0.05,
                max_depth=3,
                min_child_weight=5,
                reg_alpha=1.0,
                reg_lambda=2.0,
                subsample=0.8,
                colsample_bytree=0.8,
                n_jobs=-1,
                verbosity=0
            )
            
            model.fit(X_train, y_train, verbose=False)
            
            # Predict
            X_test = pd.DataFrame([test_row[feature_cols].astype(float)])
            raw_pred = model.predict(X_test)[0]
            
            # Apply bounds (from p.py logic)
            season_avg = test_row['Season_Avg_PTS']
            pts_std = train_df['Target_PTS'].std()
            lower_bound = max(5, season_avg - 2 * pts_std)
            upper_bound = season_avg + 2 * pts_std
            prediction = np.clip(raw_pred, lower_bound, upper_bound)
            
            actual = test_row['Target_PTS']
            
            predictions.append({
                'player_id': player_id,
                'player_name': player_name,
                'game_date': test_row['GAME_DATE'],
                'predicted': prediction,
                'actual': actual,
                'season_avg': season_avg,
                'last_5_avg': test_row['Last_5_PTS'],
                'opponent': test_row['Opp_Abbrev'],
                'home_away': test_row['Home_Away'],
                'minutes': test_row['MIN'],
                'training_games': len(train_df)
            })
        
        return predictions
    
    def run_full_backtest(self):
        """Run backtest on all eligible players"""
        print("\n" + "=" * 70)
        print("🏀 NBA POINTS PREDICTION MODEL - BACKTEST EVALUATION")
        print("=" * 70)
        print(f"   Training Seasons: {', '.join(SEASONS)}")
        print(f"   Eval Period:      {SEASON_START.strftime('%Y-%m-%d')} to {EVAL_END.strftime('%Y-%m-%d')}")
        print(f"   Min Games (curr): {MIN_GAMES_FOR_EVAL} | Min Games (prev): {MIN_GAMES_PREV_SEASON}")
        print(f"   Min MPG:          {MIN_MINUTES_AVG}")
        print("=" * 70)
        
        # Fetch team stats first
        self.fetch_team_defense_stats()
        time.sleep(1)
        
        # Get eligible players
        players_list = self.get_eligible_players()
        time.sleep(1)
        
        # Run backtest for each player
        print(f"\n🔄 Running walk-forward backtest on {len(players_list)} players...")
        print("   (This may take several minutes due to API rate limits)\n")
        
        all_predictions = []
        
        for i, player in enumerate(tqdm(players_list, desc="Evaluating players")):
            try:
                preds = self.run_player_backtest(player)
                all_predictions.extend(preds)
                
                # Save cache periodically (every 10 players) to preserve progress
                if (i + 1) % 10 == 0:
                    self.cache.save()
                
                time.sleep(0.6)  # Rate limit
            except Exception as e:
                tqdm.write(f"   ⚠️  Error for {player['name']}: {e}")
                continue
        
        self.results = all_predictions
        self.cache.save()
        
        return all_predictions
    
    def calculate_metrics(self):
        """Calculate all evaluation metrics"""
        if not self.results:
            print("No results to evaluate!")
            return
        
        df = pd.DataFrame(self.results)
        
        predicted = df['predicted'].values
        actual = df['actual'].values
        season_avg = df['season_avg'].values
        last_5 = df['last_5_avg'].values
        
        # ============= REGRESSION METRICS =============
        mae = mean_absolute_error(actual, predicted)
        rmse = np.sqrt(mean_squared_error(actual, predicted))
        
        # Errors
        errors = predicted - actual
        
        # ============= RANGE-BASED ACCURACY =============
        within_2_5 = np.mean(np.abs(errors) <= 2.5) * 100
        within_5 = np.mean(np.abs(errors) <= 5) * 100
        within_7_5 = np.mean(np.abs(errors) <= 7.5) * 100
        
        # ============= OVER/UNDER ACCURACY =============
        # Using season average as the "line"
        pred_over_avg = (predicted > season_avg).astype(int)
        actual_over_avg = (actual > season_avg).astype(int)
        ou_accuracy = accuracy_score(actual_over_avg, pred_over_avg) * 100
        ou_f1 = f1_score(actual_over_avg, pred_over_avg) * 100
        ou_precision = precision_score(actual_over_avg, pred_over_avg, zero_division=0) * 100
        ou_recall = recall_score(actual_over_avg, pred_over_avg, zero_division=0) * 100
        
        # ============= DIRECTIONAL ACCURACY =============
        # Did we correctly predict if player would beat their last 5 avg?
        pred_over_recent = (predicted > last_5).astype(int)
        actual_over_recent = (actual > last_5).astype(int)
        dir_accuracy = accuracy_score(actual_over_recent, pred_over_recent) * 100
        dir_f1 = f1_score(actual_over_recent, pred_over_recent) * 100
        
        # ============= BETTING LINE SIMULATION =============
        # Simulate betting with different margins
        # If we predict X, would betting OVER X-2 or UNDER X+2 be profitable?
        
        # Conservative: only bet when prediction differs from season avg by 3+ points
        confident_mask = np.abs(predicted - season_avg) >= 3
        if confident_mask.sum() > 0:
            confident_preds = predicted[confident_mask]
            confident_actual = actual[confident_mask]
            confident_avg = season_avg[confident_mask]
            
            # When we predict OVER (pred > avg + 3), was actual > avg?
            over_bets = confident_preds > confident_avg
            over_wins = (confident_actual[over_bets] > confident_avg[over_bets]).sum() if over_bets.sum() > 0 else 0
            over_total = over_bets.sum()
            
            # When we predict UNDER (pred < avg - 3), was actual < avg?
            under_bets = confident_preds < confident_avg
            under_wins = (confident_actual[under_bets] < confident_avg[under_bets]).sum() if under_bets.sum() > 0 else 0
            under_total = under_bets.sum()
            
            confident_wins = over_wins + under_wins
            confident_total = over_total + under_total
            confident_accuracy = (confident_wins / confident_total * 100) if confident_total > 0 else 0
        else:
            confident_accuracy = 0
            confident_total = 0
        
        # ============= PRINT RESULTS =============
        print("\n" + "=" * 70)
        print("📊 BACKTEST RESULTS")
        print("=" * 70)
        print(f"   Total Predictions: {len(df):,}")
        print(f"   Unique Players:    {df['player_name'].nunique()}")
        print(f"   Date Range:        {df['game_date'].min().strftime('%Y-%m-%d')} to {df['game_date'].max().strftime('%Y-%m-%d')}")
        
        print("\n" + "-" * 70)
        print("📏 REGRESSION METRICS")
        print("-" * 70)
        print(f"   Mean Absolute Error (MAE):     {mae:.2f} points")
        print(f"   Root Mean Squared Error:       {rmse:.2f} points")
        print(f"   Mean Error (Bias):             {np.mean(errors):+.2f} points")
        
        print("\n" + "-" * 70)
        print("🎯 RANGE ACCURACY (How often prediction is within X points)")
        print("-" * 70)
        print(f"   Within ±2.5 points:  {within_2_5:.1f}%")
        print(f"   Within ±5 points:    {within_5:.1f}%")
        print(f"   Within ±7.5 points:  {within_7_5:.1f}%")
        
        print("\n" + "-" * 70)
        print("📈 OVER/UNDER ACCURACY (vs Season Average)")
        print("-" * 70)
        print(f"   Accuracy:   {ou_accuracy:.1f}%")
        print(f"   Precision:  {ou_precision:.1f}%")
        print(f"   Recall:     {ou_recall:.1f}%")
        print(f"   F1 Score:   {ou_f1:.1f}%")
        
        print("\n" + "-" * 70)
        print("🔄 DIRECTIONAL ACCURACY (vs Last 5 Games Avg)")
        print("-" * 70)
        print(f"   Accuracy:   {dir_accuracy:.1f}%")
        print(f"   F1 Score:   {dir_f1:.1f}%")
        
        print("\n" + "-" * 70)
        print("💰 CONFIDENT BETS (When prediction differs 3+ pts from avg)")
        print("-" * 70)
        print(f"   Total Confident Predictions: {confident_total}")
        print(f"   Win Rate:                    {confident_accuracy:.1f}%")
        
        print("\n" + "=" * 70)
        print("📋 INTERPRETATION GUIDE")
        print("=" * 70)
        print("   • MAE < 5:    Excellent - model is very accurate")
        print("   • MAE 5-7:    Good - typical for points prediction")
        print("   • MAE > 7:    Needs improvement")
        print()
        print("   • O/U Accuracy > 55%: Potentially profitable for betting")
        print("   • O/U Accuracy > 52%: Break-even considering vig")
        print("   • O/U Accuracy < 50%: No edge")
        print()
        print("   • Within ±5 > 60%: Strong prediction consistency")
        print("=" * 70)
        
        # ============= PER-PLAYER ANALYSIS =============
        print("\n" + "=" * 70)
        print("👤 TOP 10 PLAYERS BY PREDICTION ACCURACY (Most Games)")
        print("=" * 70)
        
        player_stats = df.groupby('player_name').agg({
            'predicted': 'count',
            'actual': 'mean'
        }).rename(columns={'predicted': 'games', 'actual': 'avg_pts'})
        
        player_mae = df.groupby('player_name').apply(
            lambda x: mean_absolute_error(x['actual'], x['predicted'])
        ).rename('mae')
        
        player_within_5 = df.groupby('player_name').apply(
            lambda x: (np.abs(x['predicted'] - x['actual']) <= 5).mean() * 100
        ).rename('within_5_pct')
        
        player_summary = player_stats.join(player_mae).join(player_within_5)
        player_summary = player_summary.sort_values('games', ascending=False).head(10)
        
        print(f"   {'Player':<25} {'Games':>6} {'PPG':>6} {'MAE':>6} {'±5pts':>8}")
        print("   " + "-" * 55)
        for name, row in player_summary.iterrows():
            print(f"   {name:<25} {int(row['games']):>6} {row['avg_pts']:>6.1f} {row['mae']:>6.2f} {row['within_5_pct']:>7.1f}%")
        
        # ============= TOP 20 MOST ACCURATE PLAYERS BY THRESHOLD =============
        print("\n" + "=" * 70)
        print("🏆 TOP 20 MOST ACCURATE PLAYERS (By Point Threshold)")
        print("=" * 70)
        
        # Calculate accuracy at different thresholds for each player
        player_within_1 = df.groupby('player_name').apply(
            lambda x: (np.abs(x['predicted'] - x['actual']) <= 1).mean() * 100
        ).rename('within_1_pct')
        
        player_within_3 = df.groupby('player_name').apply(
            lambda x: (np.abs(x['predicted'] - x['actual']) <= 3).mean() * 100
        ).rename('within_3_pct')
        
        player_within_5_full = df.groupby('player_name').apply(
            lambda x: (np.abs(x['predicted'] - x['actual']) <= 5).mean() * 100
        ).rename('within_5_pct')
        
        player_within_7 = df.groupby('player_name').apply(
            lambda x: (np.abs(x['predicted'] - x['actual']) <= 7).mean() * 100
        ).rename('within_7_pct')
        
        player_games = df.groupby('player_name')['predicted'].count().rename('games')
        
        accuracy_df = pd.concat([player_games, player_within_1, player_within_3, 
                                  player_within_5_full, player_within_7], axis=1)
        
        # Filter to players with at least 10 games for meaningful stats
        accuracy_df = accuracy_df[accuracy_df['games'] >= 10]
        
        # Top 20 by ±1 point accuracy
        print("\n   📌 TOP 20 BY ±1 POINT ACCURACY (Min 10 games)")
        print(f"   {'Player':<28} {'Games':>6} {'±1pt':>8}")
        print("   " + "-" * 45)
        top_1pt = accuracy_df.sort_values('within_1_pct', ascending=False).head(20)
        for name, row in top_1pt.iterrows():
            print(f"   {name:<28} {int(row['games']):>6} {row['within_1_pct']:>7.1f}%")
        
        # Top 20 by ±3 point accuracy
        print("\n   📌 TOP 20 BY ±3 POINT ACCURACY (Min 10 games)")
        print(f"   {'Player':<28} {'Games':>6} {'±3pts':>8}")
        print("   " + "-" * 45)
        top_3pt = accuracy_df.sort_values('within_3_pct', ascending=False).head(20)
        for name, row in top_3pt.iterrows():
            print(f"   {name:<28} {int(row['games']):>6} {row['within_3_pct']:>7.1f}%")
        
        # Top 20 by ±5 point accuracy
        print("\n   📌 TOP 20 BY ±5 POINT ACCURACY (Min 10 games)")
        print(f"   {'Player':<28} {'Games':>6} {'±5pts':>8}")
        print("   " + "-" * 45)
        top_5pt = accuracy_df.sort_values('within_5_pct', ascending=False).head(20)
        for name, row in top_5pt.iterrows():
            print(f"   {name:<28} {int(row['games']):>6} {row['within_5_pct']:>7.1f}%")
        
        # Top 20 by ±7 point accuracy
        print("\n   📌 TOP 20 BY ±7 POINT ACCURACY (Min 10 games)")
        print(f"   {'Player':<28} {'Games':>6} {'±7pts':>8}")
        print("   " + "-" * 45)
        top_7pt = accuracy_df.sort_values('within_7_pct', ascending=False).head(20)
        for name, row in top_7pt.iterrows():
            print(f"   {name:<28} {int(row['games']):>6} {row['within_7_pct']:>7.1f}%")
        
        # Combined view - Top 20 overall (by average ranking across thresholds)
        print("\n   📌 TOP 20 OVERALL (Combined Accuracy - All Thresholds)")
        print(f"   {'Player':<25} {'Games':>5} {'±1pt':>7} {'±3pts':>7} {'±5pts':>7} {'±7pts':>7}")
        print("   " + "-" * 65)
        accuracy_df['combined_score'] = (accuracy_df['within_1_pct'] + 
                                          accuracy_df['within_3_pct'] + 
                                          accuracy_df['within_5_pct'] + 
                                          accuracy_df['within_7_pct']) / 4
        top_combined = accuracy_df.sort_values('combined_score', ascending=False).head(20)
        for name, row in top_combined.iterrows():
            print(f"   {name:<25} {int(row['games']):>5} {row['within_1_pct']:>6.1f}% {row['within_3_pct']:>6.1f}% {row['within_5_pct']:>6.1f}% {row['within_7_pct']:>6.1f}%")
        
        # ============= SAVE DETAILED RESULTS =============
        output_file = f"backtest_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df.to_csv(output_file, index=False)
        print(f"\n💾 Detailed results saved to: {output_file}")
        
        # ============= SHOW GUI =============
        show_accuracy_gui(
            accuracy_df=accuracy_df,
            metrics={
                'mae': mae,
                'rmse': rmse,
                'within_2_5': within_2_5,
                'within_5': within_5,
                'within_7_5': within_7_5,
                'ou_accuracy': ou_accuracy,
                'dir_accuracy': dir_accuracy,
                'total_predictions': len(df),
                'unique_players': df['player_name'].nunique(),
                'date_range': (df['game_date'].min(), df['game_date'].max())
            }
        )
        
        return {
            'mae': mae,
            'rmse': rmse,
            'within_2_5': within_2_5,
            'within_5': within_5,
            'within_7_5': within_7_5,
            'ou_accuracy': ou_accuracy,
            'ou_f1': ou_f1,
            'ou_precision': ou_precision,
            'ou_recall': ou_recall,
            'dir_accuracy': dir_accuracy,
            'dir_f1': dir_f1,
            'confident_accuracy': confident_accuracy,
            'total_predictions': len(df),
            'unique_players': df['player_name'].nunique()
        }


def show_accuracy_gui(accuracy_df, metrics):
    """Display top 20 most accurate players in a modern GUI"""
    
    # ===== MODERN COLOR PALETTE (matching p.py and stats.py) =====
    COLORS = {
        'bg_primary': '#0f0f0f',
        'bg_card': '#1a1a1a',
        'bg_elevated': '#242424',
        'bg_hover': '#2a2a2a',
        'text_primary': '#ffffff',
        'text_secondary': '#8b8b8b',
        'text_tertiary': '#5c5c5c',
        'accent': '#6366f1',
        'accent_soft': '#4f46e5',
        'success': '#10b981',
        'warning': '#f59e0b',
        'danger': '#ef4444',
        'border': '#2a2a2a',
        'divider': '#1f1f1f',
    }
    
    root = tk.Tk()
    root.title("NBA Points Prediction • Backtest Results")
    root.geometry("1100x900")
    root.configure(bg=COLORS['bg_primary'])
    
    # Configure ttk styles
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
    
    # Content container
    content_frame = tk.Frame(scrollable_frame, bg=COLORS['bg_primary'])
    content_frame.pack(fill="both", expand=True, padx=32, pady=32)
    
    # ===== HERO SECTION =====
    hero_frame = tk.Frame(content_frame, bg=COLORS['bg_primary'])
    hero_frame.pack(fill="x", pady=(0, 32))
    
    tk.Label(hero_frame, text="BACKTEST EVALUATION", 
             bg=COLORS['bg_primary'], fg=COLORS['text_tertiary'], 
             font=('Segoe UI', 10, 'bold')).pack(anchor='w')
    
    tk.Label(hero_frame, text="Top 20 Most Accurate Players", 
             bg=COLORS['bg_primary'], fg=COLORS['text_primary'], 
             font=('Segoe UI', 28, 'bold')).pack(anchor='w', pady=(4, 0))
    
    date_min, date_max = metrics['date_range']
    tk.Label(hero_frame, text=f"{date_min.strftime('%Y-%m-%d')} to {date_max.strftime('%Y-%m-%d')}  •  {metrics['total_predictions']:,} predictions  •  {metrics['unique_players']} players", 
             bg=COLORS['bg_primary'], fg=COLORS['text_secondary'], 
             font=('Segoe UI', 11)).pack(anchor='w', pady=(4, 0))
    
    # ===== OVERALL METRICS ROW =====
    metrics_frame = tk.Frame(content_frame, bg=COLORS['bg_primary'])
    metrics_frame.pack(fill="x", pady=(0, 24))
    
    def create_metric_box(parent, label, value, is_pct=False):
        box = tk.Frame(parent, bg=COLORS['bg_card'])
        box.pack(side='left', fill='both', expand=True, padx=4)
        inner = tk.Frame(box, bg=COLORS['bg_card'])
        inner.pack(fill="x", padx=16, pady=16)
        tk.Label(inner, text=label, bg=COLORS['bg_card'], fg=COLORS['text_tertiary'],
                 font=('Segoe UI', 9, 'bold')).pack(anchor='w')
        val_text = f"{value:.1f}%" if is_pct else f"{value:.2f}"
        tk.Label(inner, text=val_text, bg=COLORS['bg_card'], fg=COLORS['accent'],
                 font=('Segoe UI', 24, 'bold')).pack(anchor='w', pady=(4, 0))
    
    create_metric_box(metrics_frame, "MAE", metrics['mae'])
    create_metric_box(metrics_frame, "RMSE", metrics['rmse'])
    create_metric_box(metrics_frame, "±5 PTS", metrics['within_5'], True)
    create_metric_box(metrics_frame, "O/U ACC", metrics['ou_accuracy'], True)
    create_metric_box(metrics_frame, "DIR ACC", metrics['dir_accuracy'], True)
    
    # Helper function to create cards
    def create_card(parent, title=None):
        card = tk.Frame(parent, bg=COLORS['bg_card'])
        card.pack(fill="x", pady=(0, 16))
        inner = tk.Frame(card, bg=COLORS['bg_card'])
        inner.pack(fill="x", padx=24, pady=20)
        if title:
            tk.Label(inner, text=title, bg=COLORS['bg_card'], fg=COLORS['text_tertiary'],
                     font=('Segoe UI', 10, 'bold')).pack(anchor='w', pady=(0, 16))
        return inner
    
    # Helper to create player table
    def create_player_table(parent, title, data_df, value_col, threshold_label):
        card = create_card(parent, title)
        
        # Table header
        header_row = tk.Frame(card, bg=COLORS['bg_card'])
        header_row.pack(fill="x", pady=(0, 8))
        
        tk.Label(header_row, text="#", bg=COLORS['bg_card'], fg=COLORS['text_secondary'],
                 font=('Segoe UI', 9, 'bold'), width=3, anchor='w').pack(side='left')
        tk.Label(header_row, text="Player", bg=COLORS['bg_card'], fg=COLORS['text_secondary'],
                 font=('Segoe UI', 9, 'bold'), width=25, anchor='w').pack(side='left')
        tk.Label(header_row, text="Games", bg=COLORS['bg_card'], fg=COLORS['text_secondary'],
                 font=('Segoe UI', 9, 'bold'), width=8, anchor='center').pack(side='left')
        tk.Label(header_row, text=threshold_label, bg=COLORS['bg_card'], fg=COLORS['text_secondary'],
                 font=('Segoe UI', 9, 'bold'), width=10, anchor='e').pack(side='right')
        
        # Divider
        tk.Frame(card, bg=COLORS['divider'], height=1).pack(fill='x', pady=(0, 8))
        
        # Data rows
        for i, (name, row) in enumerate(data_df.iterrows(), 1):
            row_frame = tk.Frame(card, bg=COLORS['bg_card'])
            row_frame.pack(fill="x", pady=2)
            
            # Rank with medal for top 3
            rank_color = COLORS['warning'] if i <= 3 else COLORS['text_tertiary']
            rank_text = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"{i}"
            tk.Label(row_frame, text=rank_text, bg=COLORS['bg_card'], fg=rank_color,
                     font=('Segoe UI', 10), width=3, anchor='w').pack(side='left')
            
            tk.Label(row_frame, text=name, bg=COLORS['bg_card'], fg=COLORS['text_primary'],
                     font=('Segoe UI', 10), width=25, anchor='w').pack(side='left')
            
            tk.Label(row_frame, text=str(int(row['games'])), bg=COLORS['bg_card'], 
                     fg=COLORS['text_secondary'], font=('Segoe UI', 10), width=8, anchor='center').pack(side='left')
            
            # Value with color coding
            val = row[value_col]
            val_color = COLORS['success'] if val >= 70 else (COLORS['warning'] if val >= 50 else COLORS['text_primary'])
            tk.Label(row_frame, text=f"{val:.1f}%", bg=COLORS['bg_card'], fg=val_color,
                     font=('Segoe UI', 10, 'bold'), width=10, anchor='e').pack(side='right')
    
    # ===== COMBINED VIEW (ALL THRESHOLDS) =====
    combined_card = create_card(content_frame, "🏆 TOP 20 OVERALL (Combined Accuracy - All Thresholds)")
    
    # Table header for combined
    header_row = tk.Frame(combined_card, bg=COLORS['bg_card'])
    header_row.pack(fill="x", pady=(0, 8))
    
    headers = [("#", 3), ("Player", 22), ("Games", 6), ("±1pt", 8), ("±3pts", 8), ("±5pts", 8), ("±7pts", 8)]
    for text, width in headers:
        anchor = 'w' if text in ["#", "Player"] else 'center'
        tk.Label(header_row, text=text, bg=COLORS['bg_card'], fg=COLORS['text_secondary'],
                 font=('Segoe UI', 9, 'bold'), width=width, anchor=anchor).pack(side='left', padx=2)
    
    tk.Frame(combined_card, bg=COLORS['divider'], height=1).pack(fill='x', pady=(0, 8))
    
    # Sort by combined score
    accuracy_df['combined_score'] = (accuracy_df['within_1_pct'] + 
                                      accuracy_df['within_3_pct'] + 
                                      accuracy_df['within_5_pct'] + 
                                      accuracy_df['within_7_pct']) / 4
    top_combined = accuracy_df.sort_values('combined_score', ascending=False).head(20)
    
    for i, (name, row) in enumerate(top_combined.iterrows(), 1):
        row_frame = tk.Frame(combined_card, bg=COLORS['bg_card'])
        row_frame.pack(fill="x", pady=2)
        
        rank_color = COLORS['warning'] if i <= 3 else COLORS['text_tertiary']
        rank_text = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"{i}"
        tk.Label(row_frame, text=rank_text, bg=COLORS['bg_card'], fg=rank_color,
                 font=('Segoe UI', 10), width=3, anchor='w').pack(side='left', padx=2)
        
        tk.Label(row_frame, text=name[:22], bg=COLORS['bg_card'], fg=COLORS['text_primary'],
                 font=('Segoe UI', 10), width=22, anchor='w').pack(side='left', padx=2)
        
        tk.Label(row_frame, text=str(int(row['games'])), bg=COLORS['bg_card'], 
                 fg=COLORS['text_secondary'], font=('Segoe UI', 10), width=6, anchor='center').pack(side='left', padx=2)
        
        for col, threshold in [('within_1_pct', 30), ('within_3_pct', 50), ('within_5_pct', 70), ('within_7_pct', 85)]:
            val = row[col]
            val_color = COLORS['success'] if val >= threshold else (COLORS['warning'] if val >= threshold * 0.7 else COLORS['text_primary'])
            tk.Label(row_frame, text=f"{val:.1f}%", bg=COLORS['bg_card'], fg=val_color,
                     font=('Segoe UI', 10), width=8, anchor='center').pack(side='left', padx=2)
    
    # ===== INDIVIDUAL THRESHOLD TABLES (2x2 GRID) =====
    grid_frame = tk.Frame(content_frame, bg=COLORS['bg_primary'])
    grid_frame.pack(fill="x", pady=(8, 0))
    
    # Left column
    left_col = tk.Frame(grid_frame, bg=COLORS['bg_primary'])
    left_col.pack(side='left', fill='both', expand=True, padx=(0, 8))
    
    # Right column
    right_col = tk.Frame(grid_frame, bg=COLORS['bg_primary'])
    right_col.pack(side='right', fill='both', expand=True, padx=(8, 0))
    
    # Top 20 by ±1 point
    top_1pt = accuracy_df.sort_values('within_1_pct', ascending=False).head(20)
    create_player_table(left_col, "📌 TOP 20 BY ±1 POINT ACCURACY", top_1pt, 'within_1_pct', "±1pt")
    
    # Top 20 by ±3 points
    top_3pt = accuracy_df.sort_values('within_3_pct', ascending=False).head(20)
    create_player_table(right_col, "📌 TOP 20 BY ±3 POINT ACCURACY", top_3pt, 'within_3_pct', "±3pts")
    
    # Top 20 by ±5 points
    top_5pt = accuracy_df.sort_values('within_5_pct', ascending=False).head(20)
    create_player_table(left_col, "📌 TOP 20 BY ±5 POINT ACCURACY", top_5pt, 'within_5_pct', "±5pts")
    
    # Top 20 by ±7 points
    top_7pt = accuracy_df.sort_values('within_7_pct', ascending=False).head(20)
    create_player_table(right_col, "📌 TOP 20 BY ±7 POINT ACCURACY", top_7pt, 'within_7_pct', "±7pts")
    
    # ===== FOOTER =====
    footer = tk.Frame(content_frame, bg=COLORS['bg_primary'])
    footer.pack(fill="x", pady=(24, 0))
    
    close_btn = tk.Button(footer, text="Close", command=root.destroy,
                          bg=COLORS['bg_elevated'], fg=COLORS['text_secondary'],
                          font=('Segoe UI', 10), padx=24, pady=10,
                          relief=tk.FLAT, cursor='hand2', bd=0,
                          activebackground=COLORS['bg_hover'],
                          activeforeground=COLORS['text_primary'])
    close_btn.pack()
    
    # Center window
    root.update_idletasks()
    x = (root.winfo_screenwidth() // 2) - (1100 // 2)
    y = (root.winfo_screenheight() // 2) - (900 // 2)
    root.geometry(f"1100x900+{x}+{y}")
    
    root.mainloop()


def main():
    evaluator = BacktestEvaluator()
    
    try:
        # Run full backtest
        evaluator.run_full_backtest()
        
        # Calculate and display metrics
        metrics = evaluator.calculate_metrics()
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Evaluation interrupted by user")
        if evaluator.results:
            print(f"   Partial results: {len(evaluator.results)} predictions")
            evaluator.calculate_metrics()
    except Exception as e:
        print(f"\n❌ Error during evaluation: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
