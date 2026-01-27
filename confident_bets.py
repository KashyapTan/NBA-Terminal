"""
Confident Bets Scanner
Scans all players playing today and identifies "confident bets" where |prediction - season_avg| >= 3
Uses the same model as p.py
"""

import pandas as pd
import numpy as np
import sys
import pickle
import os
import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta
from tqdm import tqdm

# Fix Unicode encoding for Windows console
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

try:
    import xgboost as xgb
    from sklearn.model_selection import TimeSeriesSplit
    from sklearn.metrics import mean_absolute_error
except ImportError as e:
    print(f"Error: Missing required package. {e}")
    print("Please install them using: pip install xgboost scikit-learn")
    sys.exit(1)

from nba_api.stats.static import players, teams
from nba_api.stats.endpoints import (
    playergamelog, leaguedashteamstats, leaguedashteamshotlocations, 
    playerdashboardbyshootingsplits, scoreboardv2, commonteamroster, leaguegamefinder,
    leaguedashplayerstats
)
import time

# --- Configuration ---
SEASONS = ["2024-25", "2025-26"]
CACHE_FILE = "nba_stats_cache.pkl"
PLAYER_CACHE_FILE = "player_stats_cache.pkl"  # Separate cache for player data
CACHE_EXPIRY_HOURS = 24
DATE_TODAY = datetime.today().strftime('%Y-%m-%d')
CONFIDENT_THRESHOLD = 3  # |prediction - season_avg| >= 3
MIN_MINUTES_THRESHOLD = 25  # Filter players with 25+ min avg

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
    """Same model as p.py - XGBoost with zone matchup scoring"""
    
    def __init__(self):
        self.model = xgb.XGBRegressor(
            n_estimators=200,
            learning_rate=0.05,
            max_depth=3,
            min_child_weight=5,        
            reg_alpha=1.0,
            reg_lambda=2.0,
            subsample=0.8,
            colsample_bytree=0.8,
            early_stopping_rounds=30,
            n_jobs=-1
        )
        self.feature_columns = []
        self.team_stats_cache = {}
        self.player_profile = {}
        self.player_profile_id = None
        self.league_zone_stats = {}
        self.league_avg_pace = {}
        self.training_season_avg = 0
        self.training_pts_std = 10
        self.load_cache()

    def load_cache(self):
        if os.path.exists(CACHE_FILE):
            try:
                file_time = datetime.fromtimestamp(os.path.getmtime(CACHE_FILE))
                if datetime.now() - file_time > timedelta(hours=CACHE_EXPIRY_HOURS):
                    return

                with open(CACHE_FILE, 'rb') as f:
                    data = pickle.load(f)
                    self.team_stats_cache = data.get('team_stats', {})
                    self.league_zone_stats = data.get('league_zones', {})
                    self.player_profile = data.get('player_profile', {})
                    self.player_profile_id = data.get('player_profile_id', None)
                    self.league_avg_pace = data.get('league_avg_pace', {})
            except Exception:
                pass

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
        except Exception:
            pass

    def get_player_id(self, player_name):
        player_list = players.find_players_by_full_name(player_name)
        if not player_list:
            return None
        return player_list[0]['id']

    def fetch_player_profile(self, player_id):
        """Fetch player's shooting zone profile"""
        try:
            season = SEASONS[-1]
            splits = playerdashboardbyshootingsplits.PlayerDashboardByShootingSplits(
                player_id=player_id,
                season=season,
                per_mode_detailed='PerGame'
            )
            area_df = splits.get_data_frames()[3]
            
            total_fga = area_df['FGA'].sum()
            profile = {}
            
            raw_fga = {}
            for _, row in area_df.iterrows():
                zone = row['GROUP_VALUE']
                raw_fga[zone] = row['FGA']
            
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
            
            self.player_profile = profile
            self.player_profile_id = player_id
            return profile
            
        except Exception:
            return {z: 0.2 for z in STANDARD_ZONES}  # Default profile

    def fetch_game_logs(self, player_id, seasons):
        """Fetch player game logs"""
        if not self.player_profile or self.player_profile_id != player_id:
            self.fetch_player_profile(player_id)
        
        all_logs = []
        
        for season in seasons:
            try:
                log = playergamelog.PlayerGameLog(player_id=player_id, season=season)
                df = log.get_data_frames()[0]
                
                if df.empty:
                    continue
                    
                df['SEASON_ID'] = season 
                all_logs.append(df)
                
                self.fetch_season_team_stats(season)
                time.sleep(0.4)
            except Exception:
                continue
        
        if not all_logs:
            return None
            
        full_df = pd.concat(all_logs, ignore_index=True)
        full_df['GAME_DATE'] = pd.to_datetime(full_df['GAME_DATE'])
        full_df = full_df.sort_values('GAME_DATE').reset_index(drop=True)
        return full_df

    def fetch_season_team_stats(self, season):
        """Fetch team defensive stats for a season"""
        if season in self.team_stats_cache:
            return

        try:
            adv_stats = leaguedashteamstats.LeagueDashTeamStats(season=season, measure_type_detailed_defense='Advanced')
            adv_df = adv_stats.get_data_frames()[0]
            
            nba_teams = teams.get_teams()
            id_to_abbrev = {t['id']: t['abbreviation'] for t in nba_teams}
            
            season_stats = {}
            pace_values = []
            
            for _, row in adv_df.iterrows():
                tid = row['TEAM_ID']
                if tid in id_to_abbrev:
                    abbrev = id_to_abbrev[tid]
                    season_stats[abbrev] = {
                        'DEF_RATING': row['DEF_RATING'],
                        'PACE': row['PACE'],
                        'ZONE_DEFENSE': {}
                    }
                    pace_values.append(row['PACE'])
            
            self.league_avg_pace[season] = np.mean(pace_values) if pace_values else 100.0
            
            current_season = SEASONS[-1]
            if season != current_season:
                self.team_stats_cache[season] = season_stats
                self.save_cache()
                return
            
            zone_sums = {z: 0 for z in STANDARD_ZONES}
            zone_counts = {z: 0 for z in STANDARD_ZONES}
            
            try:
                shot_locs = leaguedashteamshotlocations.LeagueDashTeamShotLocations(
                    season=season,
                    per_mode_detailed='PerGame',
                    distance_range='By Zone',
                    measure_type_simple='Opponent',
                    timeout=60
                )
                
                zone_df = shot_locs.get_data_frames()[0]
                
                for _, row in zone_df.iterrows():
                    tid = row.iloc[0]
                    if tid not in id_to_abbrev:
                        continue
                    abbrev = id_to_abbrev[tid]
                    
                    if abbrev not in season_stats:
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
                    
                    final_zones = {}
                    for z in STANDARD_ZONES:
                        if z in team_zones:
                            final_zones[z] = team_zones[z]
                            zone_sums[z] += team_zones[z]
                            zone_counts[z] += 1
                        else:
                            final_zones[z] = 0.45
                    
                    season_stats[abbrev]['ZONE_DEFENSE'] = final_zones
                    
            except Exception:
                for abbrev in season_stats:
                    if 'ZONE_DEFENSE' not in season_stats[abbrev] or not season_stats[abbrev]['ZONE_DEFENSE']:
                        season_stats[abbrev]['ZONE_DEFENSE'] = {z: 0.45 for z in STANDARD_ZONES}

            league_avgs = {}
            for z in STANDARD_ZONES:
                league_avgs[z] = zone_sums[z] / zone_counts[z] if zone_counts[z] > 0 else 0.45
            
            self.league_zone_stats[season] = league_avgs
            self.team_stats_cache[season] = season_stats
            self.save_cache()
            
        except Exception:
            pass

    def get_opponent_stats(self, row):
        """Get opponent stats for a game"""
        try:
            matchup = row['MATCHUP']
            opp_abbrev = matchup.split(' ')[-1]
            season = row['SEASON_ID']
            
            current_season = SEASONS[-1]
            
            if season in self.team_stats_cache and opp_abbrev in self.team_stats_cache[season]:
                stats = self.team_stats_cache[season][opp_abbrev]
                
                zone_score = 0
                
                if season == current_season:
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
                                continue
                            league_pct = league_zones[zone]
                            
                            opp_expected_pts = opp_pct * pts_value
                            league_expected_pts = league_pct * pts_value
                            pts_differential = opp_expected_pts - league_expected_pts
                            zone_score += freq * pts_differential * 100
                
                opp_pace = stats.get('PACE', 100.0)
                league_pace = self.league_avg_pace.get(season, 100.0)
                extra_poss_per_48 = opp_pace - league_pace
                
                return pd.Series([
                    stats.get('DEF_RATING', 112.0), 
                    extra_poss_per_48,
                    zone_score
                ])
            else:
                return pd.Series([112.0, 0, 0])
        except Exception:
            return pd.Series([112.0, 0, 0])

    def feature_engineering(self, df):
        """Engineer features for model training"""
        df = df.copy()
        
        df['Target_PTS'] = df['PTS']
        df['Home_Away'] = df['MATCHUP'].apply(lambda x: 1 if 'vs.' in x else 0)
        
        df['Rest_Days'] = df['GAME_DATE'].diff().dt.days - 1
        df['Rest_Days'] = df['Rest_Days'].fillna(3) 
        df['Rest_Days'] = df['Rest_Days'].apply(lambda x: 0 if x < 0 else (x if x < 5 else 5))
        
        df['Last_5_PTS'] = df['PTS'].shift(1).rolling(window=5).mean()
        df['Last_5_MIN'] = df['MIN'].shift(1).rolling(window=5).mean()
        df['Last_5_FGA'] = df['FGA'].shift(1).rolling(window=5).mean()
        
        df['Last_10_PTS'] = df['PTS'].shift(1).rolling(window=10).mean()
        df['Last_10_MIN'] = df['MIN'].shift(1).rolling(window=10).mean()
        df['Last_10_FGA'] = df['FGA'].shift(1).rolling(window=10).mean()
        
        df['Season_Avg_PTS'] = df.groupby('SEASON_ID')['PTS'].transform(
            lambda x: x.shift(1).expanding().mean()
        )
        
        df['Recent_vs_Season'] = df['Last_5_PTS'] - df['Season_Avg_PTS']
        
        df[['Opponent_Def_Rating', 'Extra_Poss_Per_48', 'Zone_Matchup_Score']] = df.apply(self.get_opponent_stats, axis=1)
        
        df['Expected_Extra_Poss'] = pd.to_numeric(df['Extra_Poss_Per_48'], errors='coerce') * (pd.to_numeric(df['MIN'], errors='coerce') / 48.0)
        df['Proj_Minutes'] = pd.to_numeric(df['MIN'], errors='coerce')
        
        numeric_cols = ['Opponent_Def_Rating', 'Extra_Poss_Per_48', 'Zone_Matchup_Score', 
                        'Expected_Extra_Poss', 'Proj_Minutes']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        df = df.dropna()
        return df

    def train(self, df):
        """Train the model"""
        features = [
            'Proj_Minutes', 'Season_Avg_PTS',
            'Last_5_PTS', 'Last_10_PTS',
            'Recent_vs_Season',
            'Home_Away', 'Rest_Days', 
            'Opponent_Def_Rating', 'Expected_Extra_Poss',
            'Zone_Matchup_Score'
        ]
        self.feature_columns = features
        
        self.training_season_avg = df['Season_Avg_PTS'].mean()
        self.training_pts_std = df['Target_PTS'].std()
        
        X = df[features].copy()
        y = df['Target_PTS'].copy()
        
        for col in X.columns:
            X[col] = pd.to_numeric(X[col], errors='coerce')
        y = pd.to_numeric(y, errors='coerce')
        
        valid_mask = X.notna().all(axis=1) & y.notna()
        X = X[valid_mask]
        y = y[valid_mask]
        
        if len(X) < 10:
            return False
        
        self.model.set_params(early_stopping_rounds=None)
        self.model.fit(X, y, verbose=False)
        return True

    def predict_next_game(self, inputs):
        """Make prediction for next game"""
        input_df = pd.DataFrame([inputs])
        input_df = input_df[self.feature_columns]
        raw_pred = self.model.predict(input_df)[0]
        
        season_avg = inputs.get('Season_Avg_PTS', self.training_season_avg)
        lower_bound = max(5, season_avg - 2 * self.training_pts_std)
        upper_bound = season_avg + 2 * self.training_pts_std
        
        bounded_pred = np.clip(raw_pred, lower_bound, upper_bound)
        return bounded_pred


def get_todays_games():
    """Get all games scheduled for today"""
    try:
        sb = scoreboardv2.ScoreboardV2(game_date=DATE_TODAY)
        games_df = sb.game_header.get_data_frame()
        
        if games_df.empty:
            return []
        
        nba_teams = teams.get_teams()
        id_to_team = {t['id']: t for t in nba_teams}
        
        games = []
        for _, row in games_df.iterrows():
            home_id = row['HOME_TEAM_ID']
            away_id = row['VISITOR_TEAM_ID']
            
            if home_id in id_to_team and away_id in id_to_team:
                games.append({
                    'home_team': id_to_team[home_id],
                    'away_team': id_to_team[away_id]
                })
        
        return games
    except Exception as e:
        print(f"Error fetching today's games: {e}")
        return []


def get_team_roster(team_id):
    """Get active roster for a team"""
    try:
        roster = commonteamroster.CommonTeamRoster(team_id=team_id, season=SEASONS[-1])
        roster_df = roster.get_data_frames()[0]
        
        players_list = []
        for _, row in roster_df.iterrows():
            players_list.append({
                'id': row['PLAYER_ID'],
                'name': row['PLAYER'],
                'position': row.get('POSITION', 'N/A')
            })
        
        return players_list
    except Exception as e:
        print(f"Error fetching roster: {e}")
        return []


def get_matchup_info_for_team(team, opponent, is_home, adv_df_cache=None, zone_df_cache=None):
    """Get matchup info for a team vs opponent - uses cached dataframes to avoid repeat API calls"""
    try:
        nba_teams = teams.get_teams()
        team_id = team['id']
        id_to_abbrev = {t['id']: t['abbreviation'] for t in nba_teams}
        
        # Get rest days
        gamefinder = leaguegamefinder.LeagueGameFinder(team_id_nullable=team_id)
        games = gamefinder.get_data_frames()[0]
        games['GAME_DATE'] = pd.to_datetime(games['GAME_DATE'])
        games = games.sort_values('GAME_DATE', ascending=False)
        
        completed_games = games.dropna(subset=['WL'])
        if not completed_games.empty:
            last_game_date = completed_games.iloc[0]['GAME_DATE']
            today_dt = pd.to_datetime(DATE_TODAY)
            rest_days = (today_dt - last_game_date).days - 1
            rest_days = max(0, min(rest_days, 5))
        else:
            rest_days = 3
        
        # Use cached adv_df if provided
        if adv_df_cache is not None:
            adv_df = adv_df_cache
        else:
            adv_stats = leaguedashteamstats.LeagueDashTeamStats(season=SEASONS[-1], measure_type_detailed_defense='Advanced')
            adv_df = adv_stats.get_data_frames()[0]
        
        adv_df['TEAM_ABBREVIATION'] = adv_df['TEAM_ID'].map(id_to_abbrev)
        
        opp_abbrev = opponent['abbreviation']
        team_adv = adv_df[adv_df['TEAM_ABBREVIATION'] == opp_abbrev]
        
        if team_adv.empty:
            return None
            
        team_adv = team_adv.iloc[0]
        def_rating = team_adv['DEF_RATING']
        pace = team_adv['PACE']
        
        # Use cached zone_df if provided
        zone_stats = {}
        if zone_df_cache is not None:
            zone_df = zone_df_cache
        else:
            try:
                shot_locs = leaguedashteamshotlocations.LeagueDashTeamShotLocations(
                    season=SEASONS[-1],
                    per_mode_detailed='PerGame',
                    distance_range='By Zone',
                    measure_type_simple='Opponent'
                )
                zone_df = shot_locs.get_data_frames()[0]
            except Exception:
                zone_df = None
        
        if zone_df is not None:
            opp_id = opponent['id']
            opp_row = zone_df[zone_df.iloc[:, 0] == opp_id]
            
            if not opp_row.empty:
                opp_row = opp_row.iloc[0]
                corner_pcts = []
                
                for col in zone_df.columns:
                    if len(col) == 2:
                        zone_name, stat_type = col
                        zone_name = str(zone_name)
                        stat_type = str(stat_type)
                        
                        if stat_type == 'OPP_FG_PCT':
                            pct = opp_row[col]
                            if pd.notna(pct):
                                if 'Corner 3' in zone_name and zone_name != 'Corner 3':
                                    corner_pcts.append(pct)
                                elif zone_name in STANDARD_ZONES:
                                    zone_stats[zone_name] = pct
                
                if corner_pcts:
                    zone_stats['Corner 3'] = np.mean(corner_pcts)
        
        if not zone_stats:
            zone_stats = {z: 0.45 for z in STANDARD_ZONES}
        
        return {
            'Home_Away': 1 if is_home else 0,
            'Rest_Days': rest_days,
            'Opponent_Name': opponent['full_name'],
            'Opponent_Abbrev': opp_abbrev,
            'Opponent_Def_Rating': def_rating,
            'Opponent_Pace': pace,
            'Opponent_Zone_Stats': zone_stats
        }
        
    except Exception as e:
        print(f"Error getting matchup info: {e}")
        return None


def get_players_with_min_minutes(team_ids):
    """
    Efficiently get all players with 25+ min avg using a single batch API call.
    Returns dict: {player_id: {'name': str, 'team_id': int, 'avg_min': float, 'avg_pts': float}}
    """
    try:
        print("Fetching league-wide player stats (single API call)...")
        
        # Single API call to get ALL players' stats for the season
        player_stats = leaguedashplayerstats.LeagueDashPlayerStats(
            season=SEASONS[-1],
            per_mode_detailed='PerGame',
            timeout=60
        )
        df = player_stats.get_data_frames()[0]
        
        # Filter by teams playing today and minutes threshold
        df_filtered = df[
            (df['TEAM_ID'].isin(team_ids)) & 
            (df['MIN'] >= MIN_MINUTES_THRESHOLD) &
            (df['GP'] >= 5)  # At least 5 games played
        ]
        
        players_dict = {}
        for _, row in df_filtered.iterrows():
            players_dict[row['PLAYER_ID']] = {
                'name': row['PLAYER_NAME'],
                'team_id': row['TEAM_ID'],
                'avg_min': row['MIN'],
                'avg_pts': row['PTS'],
                'games_played': row['GP']
            }
        
        print(f"Found {len(players_dict)} players with {MIN_MINUTES_THRESHOLD}+ min avg")
        return players_dict
        
    except Exception as e:
        print(f"Error fetching player stats: {e}")
        return {}


def scan_all_players():
    """Scan all players playing today and find confident bets - OPTIMIZED to reduce API calls"""
    print("\n" + "=" * 60)
    print("   CONFIDENT BETS SCANNER")
    print(f"   Date: {DATE_TODAY}")
    print("=" * 60)
    print()
    
    # Get today's games
    print("Fetching today's games...")
    games = get_todays_games()
    
    if not games:
        print("No games scheduled for today.")
        return []
    
    print(f"Found {len(games)} games today:")
    for game in games:
        print(f"  - {game['away_team']['full_name']} @ {game['home_team']['full_name']}")
    print()
    
    # Collect team IDs and build team lookup
    team_ids = set()
    team_lookup = {}  # team_id -> (team, opponent, is_home)
    
    for game in games:
        home_team = game['home_team']
        away_team = game['away_team']
        team_ids.add(home_team['id'])
        team_ids.add(away_team['id'])
        team_lookup[home_team['id']] = (home_team, away_team, True)
        team_lookup[away_team['id']] = (away_team, home_team, False)
    
    # OPTIMIZATION 1: Single API call to get all qualifying players
    print(f"\nFiltering players with {MIN_MINUTES_THRESHOLD}+ minutes avg...")
    qualified_players = get_players_with_min_minutes(team_ids)
    
    if not qualified_players:
        print("No qualifying players found.")
        return []
    
    # OPTIMIZATION 2: Pre-fetch team stats once (instead of per-player)
    print("\nPre-fetching team defensive stats (single API call)...")
    try:
        adv_stats = leaguedashteamstats.LeagueDashTeamStats(season=SEASONS[-1], measure_type_detailed_defense='Advanced')
        adv_df_cache = adv_stats.get_data_frames()[0]
        time.sleep(0.5)
    except Exception as e:
        print(f"Error fetching team stats: {e}")
        adv_df_cache = None
    
    # OPTIMIZATION 3: Pre-fetch zone stats once
    print("Pre-fetching zone defense stats (single API call)...")
    try:
        shot_locs = leaguedashteamshotlocations.LeagueDashTeamShotLocations(
            season=SEASONS[-1],
            per_mode_detailed='PerGame',
            distance_range='By Zone',
            measure_type_simple='Opponent',
            timeout=60
        )
        zone_df_cache = shot_locs.get_data_frames()[0]
        time.sleep(0.5)
    except Exception as e:
        print(f"Error fetching zone stats: {e}")
        zone_df_cache = None
    
    print(f"\nTotal players to analyze: {len(qualified_players)}")
    print("\n" + "=" * 60)
    print("   RUNNING PREDICTIONS")
    print("=" * 60)
    
    confident_bets = []
    predictor = NBAPredictor()
    
    # Cache matchup info per team pair
    matchup_cache = {}
    
    for player_id, player_info in tqdm(qualified_players.items(), desc="Analyzing players"):
        try:
            team_id = player_info['team_id']
            if team_id not in team_lookup:
                continue
                
            team, opponent, is_home = team_lookup[team_id]
            
            # Get or cache matchup info (only fetches rest days per team)
            cache_key = (team['id'], opponent['id'])
            if cache_key not in matchup_cache:
                matchup_cache[cache_key] = get_matchup_info_for_team(
                    team, opponent, is_home, 
                    adv_df_cache=adv_df_cache, 
                    zone_df_cache=zone_df_cache
                )
                time.sleep(0.4)  # Rate limit for rest days lookup
            
            matchup_info = matchup_cache[cache_key]
            if matchup_info is None:
                continue
            
            # Fetch player profile
            predictor.fetch_player_profile(player_id)
            time.sleep(0.4)
            
            # Fetch game logs
            df = predictor.fetch_game_logs(player_id, SEASONS)
            if df is None or len(df) < 15:
                continue
            
            # Process and train
            df_processed = predictor.feature_engineering(df)
            if len(df_processed) < 10:
                continue
            
            if not predictor.train(df_processed):
                continue
            
            # Calculate prediction inputs
            actual_last_5_pts = df['PTS'].tail(5).mean()
            actual_last_10_pts = df['PTS'].tail(10).mean()
            
            current_season = SEASONS[-1]
            current_season_games = df[df['SEASON_ID'] == current_season]
            if len(current_season_games) < 5:
                continue
                
            actual_season_avg = current_season_games['PTS'].mean()
            actual_recent_vs_season = actual_last_5_pts - actual_season_avg
            
            # Calculate zone score
            zone_score = 0
            opp_zones = matchup_info['Opponent_Zone_Stats']
            league_zones = predictor.league_zone_stats.get(current_season, {})
            
            for zone, freq in predictor.player_profile.items():
                if zone not in STANDARD_ZONES or zone not in opp_zones:
                    continue
                pts_value = ZONE_POINT_VALUES.get(zone, 2.0)
                opp_pct = opp_zones.get(zone, 0.45)
                league_pct = league_zones.get(zone, 0.45)
                opp_expected_pts = opp_pct * pts_value
                league_expected_pts = league_pct * pts_value
                pts_differential = opp_expected_pts - league_expected_pts
                zone_score += freq * pts_differential * 100
            
            # Use pre-fetched avg minutes
            avg_minutes = player_info['avg_min']
            
            # Calculate expected extra possessions
            opp_pace = matchup_info['Opponent_Pace']
            league_pace = predictor.league_avg_pace.get(current_season, 100.0)
            expected_extra_poss = (opp_pace - league_pace) * (avg_minutes / 48.0)
            
            # Build inputs
            next_game_inputs = {
                'Proj_Minutes': avg_minutes,
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
            
            # Make prediction
            prediction = predictor.predict_next_game(next_game_inputs)
            
            # Check if confident bet
            diff = prediction - actual_season_avg
            if abs(diff) >= CONFIDENT_THRESHOLD:
                confident_bets.append({
                    'player_name': player_info['name'],
                    'player_id': player_id,
                    'team': team['full_name'],
                    'team_abbrev': team['abbreviation'],
                    'opponent': opponent['full_name'],
                    'opponent_abbrev': opponent['abbreviation'],
                    'is_home': is_home,
                    'prediction': prediction,
                    'season_avg': actual_season_avg,
                    'diff': diff,
                    'direction': 'OVER' if diff > 0 else 'UNDER',
                    'last_5': actual_last_5_pts,
                    'last_10': actual_last_10_pts,
                    'proj_minutes': avg_minutes,
                    'def_rating': matchup_info['Opponent_Def_Rating'],
                    'zone_score': zone_score,
                    'matchup_info': matchup_info,
                    'inputs': next_game_inputs
                })
                
                print(f"\n[OK] CONFIDENT: {player_info['name']} - Pred: {prediction:.1f} vs Avg: {actual_season_avg:.1f} ({diff:+.1f})")
            
            time.sleep(0.3)  # Rate limiting between players
            
        except Exception as e:
            continue
    
    # Sort by absolute difference
    confident_bets.sort(key=lambda x: abs(x['diff']), reverse=True)
    
    print(f"\n\n" + "=" * 60)
    print(f"   FOUND {len(confident_bets)} CONFIDENT BETS")
    print("=" * 60)
    
    for bet in confident_bets[:20]:
        direction_arrow = "^" if bet['direction'] == 'OVER' else "v"
        print(f"  {direction_arrow} {bet['player_name']:<20} {bet['direction']:<5} {bet['season_avg']:.1f} -> {bet['prediction']:.1f} ({bet['diff']:+.1f})")
    
    return confident_bets


def show_confident_bets_gui(confident_bets):
    """Display confident bets in a modern GUI"""
    
    # ===== MODERN COLOR PALETTE =====
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
        'over': '#10b981',
        'under': '#ef4444'
    }
    
    root = tk.Tk()
    root.title(f"Confident Bets Scanner • {DATE_TODAY}")
    root.geometry("1000x800")
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
    
    # ===== HEADER =====
    header_frame = tk.Frame(content_frame, bg=COLORS['bg_primary'])
    header_frame.pack(fill="x", pady=(0, 32))
    
    tk.Label(header_frame, text="CONFIDENT BETS SCANNER", 
             bg=COLORS['bg_primary'], fg=COLORS['text_tertiary'], 
             font=('Segoe UI', 10, 'bold')).pack(anchor='w')
    
    tk.Label(header_frame, text=f"{DATE_TODAY}", 
             bg=COLORS['bg_primary'], fg=COLORS['text_primary'], 
             font=('Segoe UI', 28, 'bold')).pack(anchor='w', pady=(4, 0))
    
    tk.Label(header_frame, text=f"{len(confident_bets)} confident predictions found  •  |pred - avg| ≥ {CONFIDENT_THRESHOLD}", 
             bg=COLORS['bg_primary'], fg=COLORS['text_secondary'], 
             font=('Segoe UI', 12)).pack(anchor='w', pady=(4, 0))
    
    # ===== SUMMARY STATS =====
    summary_frame = tk.Frame(content_frame, bg=COLORS['bg_primary'])
    summary_frame.pack(fill="x", pady=(0, 24))
    
    over_count = len([b for b in confident_bets if b['direction'] == 'OVER'])
    under_count = len([b for b in confident_bets if b['direction'] == 'UNDER'])
    avg_diff = np.mean([abs(b['diff']) for b in confident_bets]) if confident_bets else 0
    
    def create_summary_box(parent, label, value, color=None):
        box = tk.Frame(parent, bg=COLORS['bg_card'])
        box.pack(side='left', fill='both', expand=True, padx=(0, 8))
        
        inner = tk.Frame(box, bg=COLORS['bg_card'])
        inner.pack(fill="x", padx=20, pady=16)
        
        tk.Label(inner, text=label, bg=COLORS['bg_card'], fg=COLORS['text_tertiary'],
                 font=('Segoe UI', 9)).pack(anchor='w')
        tk.Label(inner, text=value, bg=COLORS['bg_card'], fg=color or COLORS['text_primary'],
                 font=('Segoe UI', 22, 'bold')).pack(anchor='w', pady=(4, 0))
    
    create_summary_box(summary_frame, "TOTAL BETS", str(len(confident_bets)))
    create_summary_box(summary_frame, "OVERS", str(over_count), COLORS['success'])
    create_summary_box(summary_frame, "UNDERS", str(under_count), COLORS['danger'])
    create_summary_box(summary_frame, "AVG DIFF", f"{avg_diff:.1f}")
    
    # Fix padding
    for child in summary_frame.winfo_children():
        child.pack_configure(padx=4)
    summary_frame.winfo_children()[0].pack_configure(padx=(0, 4))
    summary_frame.winfo_children()[-1].pack_configure(padx=(4, 0))
    
    # ===== BETS LIST =====
    list_frame = tk.Frame(content_frame, bg=COLORS['bg_card'])
    list_frame.pack(fill="x", pady=(0, 16))
    
    list_inner = tk.Frame(list_frame, bg=COLORS['bg_card'])
    list_inner.pack(fill="x", padx=24, pady=20)
    
    tk.Label(list_inner, text="CONFIDENT BETS", bg=COLORS['bg_card'], fg=COLORS['text_secondary'],
             font=('Segoe UI', 11, 'bold')).pack(anchor='w', pady=(0, 16))
    
    # Use grid layout for perfect column alignment
    table_frame = tk.Frame(list_inner, bg=COLORS['bg_card'])
    table_frame.pack(fill="x")
    
    # Column configurations: (header, min_width_pixels)
    COL_CONFIG = [
        ('Player', 150),
        ('Team', 55),
        ('vs', 55),
        ('Dir', 65),
        ('Pred', 55),
        ('Avg', 55),
        ('Diff', 60),
        ('L5', 55),
        ('Mins', 50),
        ('Def', 45)
    ]
    
    # Configure grid columns with fixed minimum widths
    for col_idx, (_, min_width) in enumerate(COL_CONFIG):
        table_frame.columnconfigure(col_idx, minsize=min_width)
    
    # Header row
    for col_idx, (header, _) in enumerate(COL_CONFIG):
        tk.Label(table_frame, text=header, bg=COLORS['bg_card'], fg=COLORS['text_tertiary'],
                 font=('Segoe UI', 10, 'bold'), anchor='w').grid(row=0, column=col_idx, sticky='w', pady=(0, 8))
    
    # Divider (spans all columns)
    divider = tk.Frame(table_frame, bg=COLORS['divider'], height=1)
    divider.grid(row=1, column=0, columnspan=len(COL_CONFIG), sticky='ew', pady=(0, 4))
    
    # Data rows
    for row_idx, bet in enumerate(confident_bets, start=2):
        direction_color = COLORS['over'] if bet['direction'] == 'OVER' else COLORS['under']
        row_bg = '#0d1f14' if bet['direction'] == 'OVER' else '#1f0d0d'
        def_rating_color = COLORS['danger'] if bet['def_rating'] < 110 else (COLORS['warning'] if bet['def_rating'] < 114 else COLORS['success'])
        
        # Row data: (text, color, bold)
        cells = [
            (bet['player_name'][:20], COLORS['text_primary'], False),
            (bet['team_abbrev'], COLORS['text_secondary'], False),
            (bet['opponent_abbrev'], COLORS['text_secondary'], False),
            (bet['direction'], direction_color, True),
            (f"{bet['prediction']:.1f}", COLORS['accent'], True),
            (f"{bet['season_avg']:.1f}", COLORS['text_primary'], False),
            (f"{bet['diff']:+.1f}", direction_color, True),
            (f"{bet['last_5']:.1f}", COLORS['text_secondary'], False),
            (f"{bet['proj_minutes']:.0f}", COLORS['text_secondary'], False),
            (f"{bet['def_rating']:.0f}", def_rating_color, False)
        ]
        
        for col_idx, (text, color, bold) in enumerate(cells):
            font = ('Segoe UI', 10, 'bold') if bold else ('Segoe UI', 10)
            cell_frame = tk.Frame(table_frame, bg=row_bg)
            cell_frame.grid(row=row_idx, column=col_idx, sticky='nsew', pady=1)
            tk.Label(cell_frame, text=text, bg=row_bg, fg=color, font=font, anchor='w').pack(anchor='w', padx=2, pady=4)
    
    # ===== FOOTER =====
    footer = tk.Frame(content_frame, bg=COLORS['bg_primary'])
    footer.pack(fill="x", pady=(24, 0))
    
    tk.Label(footer, text="Threshold: |prediction - season_avg| ≥ 3 points", 
             bg=COLORS['bg_primary'], fg=COLORS['text_tertiary'],
             font=('Segoe UI', 9)).pack(side='left')
    
    close_btn = tk.Button(footer, text="Close", command=root.destroy,
                          bg=COLORS['bg_elevated'], fg=COLORS['text_secondary'],
                          font=('Segoe UI', 10), padx=24, pady=10,
                          relief=tk.FLAT, cursor='hand2', bd=0,
                          activebackground=COLORS['bg_hover'],
                          activeforeground=COLORS['text_primary'])
    close_btn.pack(side='right')
    
    # Center window
    root.update_idletasks()
    x = (root.winfo_screenwidth() // 2) - (1000 // 2)
    y = (root.winfo_screenheight() // 2) - (800 // 2)
    root.geometry(f"1000x800+{x}+{y}")
    
    root.mainloop()


if __name__ == "__main__":
    try:
        confident_bets = scan_all_players()
        
        if confident_bets:
            show_confident_bets_gui(confident_bets)
        else:
            print("\nNo confident bets found for today.")
            
    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()
