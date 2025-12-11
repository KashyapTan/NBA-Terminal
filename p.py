import pandas as pd
import numpy as np
import sys
import pickle
import os
from datetime import datetime, timedelta
from tqdm import tqdm

# Check for required packages
try:
    import xgboost as xgb
    from sklearn.model_selection import TimeSeriesSplit
    from sklearn.metrics import mean_absolute_error
except ImportError as e:
    print(f"Error: Missing required package. {e}")
    print("Please install them using: pip install xgboost scikit-learn")
    sys.exit(1)

from nba_api.stats.static import players, teams
from nba_api.stats.endpoints import playergamelog, leaguedashteamstats, teamdashboardbyshootingsplits, playerdashboardbyshootingsplits
import time
import get_matchup_info

# --- Configuration ---
TARGET_PLAYER = "Shai Gilgeous-Alexander"  # Player to predict
SEASONS = ["2024-25", "2025-26"]
CACHE_FILE = "nba_stats_cache.pkl"
CACHE_EXPIRY_HOURS = 24 # Cache expires after 24 hours
Proj_Minutes = 27.0 # Projected minutes for the next game

class NBAPredictor:
    def __init__(self):
        self.model = xgb.XGBRegressor(
            n_estimators=1000,
            learning_rate=0.05,
            max_depth=5,
            early_stopping_rounds=50,
            n_jobs=-1
        )
        self.feature_columns = []
        self.team_stats_cache = {} # (Season, Team_Abbrev) -> {Def_Rating, Pace, Zone_Stats}
        self.player_profile = {} # {Zone: Frequency}
        self.player_profile_id = None # Track which player's profile is cached
        self.league_zone_stats = {} # Season -> {Zone: Avg_FG_Pct}
        self.league_avg_pace = {} # Season -> Avg Pace
        self.load_cache()

    def load_cache(self):
        if os.path.exists(CACHE_FILE):
            try:
                # Check file age
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
            # Frame 3 is Shot Area (verified from actual API response)
            # Actual Order: 0=Overall, 1=Shot5FT, 2=Shot8FT, 3=ShotArea, 4=AssistedShot, 5=ShotTypeSummary, 6=ShotTypeDetail
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
            
            # Calculate frequencies from normalized FGA
            for zone, fga in normalized_fga.items():
                profile[zone] = fga / total_fga if total_fga > 0 else 0
            
            self.player_profile = profile
            self.player_profile_id = player_id  # Track which player this is for
            print(f"Player Profile: {profile}")
            self.save_cache()
            
        except Exception as e:
            print(f"Error fetching player profile: {e}")
            # Fallback profile
            self.player_profile = {
                'Restricted Area': 0.3, 'In The Paint (Non-RA)': 0.2, 
                'Mid-Range': 0.1, 'Corner 3': 0.1, 'Above the Break 3': 0.3
            }

    def fetch_game_logs(self, player_id, seasons):
        # Refresh player profile if it's for a different player
        if not self.player_profile or self.player_profile_id != player_id:
            self.fetch_player_profile(player_id)
        
        all_logs = []
        for season in seasons:
            print(f"Fetching game logs for season {season}...")
            try:
                log = playergamelog.PlayerGameLog(player_id=player_id, season=season)
                df = log.get_data_frames()[0]
                df['SEASON_ID'] = season 
                all_logs.append(df)
                
                # Pre-fetch team stats for this season
                self.fetch_season_team_stats(season)
                
                time.sleep(0.6) 
            except Exception as e:
                print(f"Error fetching logs for {season}: {e}")
        
        if not all_logs:
            raise ValueError("No game logs found.")
            
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
            
            # Create lookup dict for this season
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
                        'ZONE_DEFENSE': {} # Will populate below
                    }
                    pace_values.append(row['PACE'])
            
            # Store league average pace for this season
            self.league_avg_pace[season] = np.mean(pace_values) if pace_values else 100.0
            
            # 2. Fetch Zone Defense Stats (Heavy Operation)
            print("Fetching detailed zone defense stats (this may take a moment)...")
            zone_sums = {}
            zone_counts = {}
            
            # Filter teams that need updating
            teams_to_fetch = []
            for team in nba_teams:
                abbrev = team['abbreviation']
                # If we already have zone stats for this team in this season, skip
                if abbrev in season_stats and 'ZONE_DEFENSE' in season_stats[abbrev] and season_stats[abbrev]['ZONE_DEFENSE']:
                    # Add to sums for league avg calculation
                    zones = season_stats[abbrev]['ZONE_DEFENSE']
                    for z, pct in zones.items():
                        if z not in zone_sums: zone_sums[z] = 0; zone_counts[z] = 0
                        zone_sums[z] += pct
                        zone_counts[z] += 1
                    continue
                
                if abbrev in season_stats:
                    teams_to_fetch.append(team)

            if teams_to_fetch:
                print(f"Fetching zone stats for {len(teams_to_fetch)} teams...")
                for team in tqdm(teams_to_fetch, desc=f"Zone Stats {season}"):
                    tid = team['id']
                    abbrev = team['abbreviation']
                    
                    try:
                        splits = teamdashboardbyshootingsplits.TeamDashboardByShootingSplits(
                            team_id=tid,
                            season=season,
                            measure_type_detailed_defense='Opponent',
                            per_mode_detailed='PerGame',
                            timeout=30
                        )
                        # Frame 3 is Shot Area (verified from actual API response)
                        area_df = splits.get_data_frames()[3]
                        
                        team_zones = {}
                        corner_pcts = []  # Collect corner 3 FG_PCT values
                        
                        for _, row in area_df.iterrows():
                            zone = row['GROUP_VALUE']
                            pct = row['FG_PCT']
                            
                            # Normalize zone name for storage
                            if 'Corner 3' in zone:
                                corner_pcts.append(pct)
                            else:
                                team_zones[zone] = pct
                                # Accumulate for League Avg with original zone name
                                if zone not in zone_sums:
                                    zone_sums[zone] = 0
                                    zone_counts[zone] = 0
                                zone_sums[zone] += pct
                                zone_counts[zone] += 1
                        
                        # Combine corner 3s
                        if corner_pcts:
                            team_zones['Corner 3'] = np.mean(corner_pcts)
                            if 'Corner 3' not in zone_sums:
                                zone_sums['Corner 3'] = 0
                                zone_counts['Corner 3'] = 0
                            zone_sums['Corner 3'] += np.mean(corner_pcts)
                            zone_counts['Corner 3'] += 1
                        
                        # Normalize Team Zones - team_zones already has combined Corner 3
                        final_zones = {}
                        for z in ['Restricted Area', 'In The Paint (Non-RA)', 'Mid-Range', 'Above the Break 3', 'Corner 3']:
                            final_zones[z] = team_zones.get(z, 0.45 if z != 'Corner 3' else 0.38)
                        
                        season_stats[abbrev]['ZONE_DEFENSE'] = final_zones
                        time.sleep(0.6)  # Delay to avoid NBA API rate limiting
                        
                    except Exception as e:
                        # print(f"Failed zone stats for {abbrev}: {e}")
                        pass
            else:
                print("All team zone stats found in cache.")

            # Calculate League Averages
            league_avgs = {}
            for z, total in zone_sums.items():
                league_avgs[z] = total / zone_counts[z] if zone_counts[z] > 0 else 0.45
            
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
            
            if season in self.team_stats_cache and opp_abbrev in self.team_stats_cache[season]:
                stats = self.team_stats_cache[season][opp_abbrev]
                
                # Calculate Zone Matchup Score
                zone_score = 0
                if 'ZONE_DEFENSE' in stats and season in self.league_zone_stats:
                    opp_zones = stats['ZONE_DEFENSE']
                    league_zones = self.league_zone_stats[season]
                    
                    for zone, freq in self.player_profile.items():
                        # Zone names should already be consistent (Corner 3, not Left/Right)
                        if zone in opp_zones:
                            opp_pct = opp_zones[zone]
                            
                            # League Avg - also uses consistent zone names now
                            league_pct = league_zones.get(zone, 0.45)
                            
                            # Relative Def: (Opp Allowed - League Avg)
                            # Positive = Opponent allows MORE than avg (Good for player)
                            rel_def = opp_pct - league_pct
                            
                            zone_score += freq * rel_def * 100 # Scale up
                
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
                # Fallback
                return pd.Series([112.0, 0.0, 0.0]) 
        except:
            return pd.Series([112.0, 0.0, 0.0])

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
        
        # 5. Opponent Stats
        df[['Opponent_Def_Rating', 'Extra_Poss_Per_48', 'Zone_Matchup_Score']] = df.apply(self.get_opponent_stats, axis=1)
        
        # 6. Calculate Expected Extra Possessions based on actual minutes
        # Formula: (Opp_Pace - League_Avg_Pace) * (Minutes / 48)
        df['Expected_Extra_Poss'] = df['Extra_Poss_Per_48'] * (df['MIN'] / 48.0)

        # 7. Projected Minutes (Using actual minutes for training)
        df['Proj_Minutes'] = df['MIN']
        
        # Drop NaNs created by rolling windows
        df = df.dropna()
        
        return df

    def train(self, df):
        features = [
            'Proj_Minutes', 'Season_Avg_PTS',
            'Last_5_PTS', 'Last_5_FGA', 
            'Last_10_PTS', 'Last_10_FGA',
            'Home_Away', 'Rest_Days', 
            'Opponent_Def_Rating', 'Expected_Extra_Poss',
            'Zone_Matchup_Score'
        ]
        self.feature_columns = features
        
        X = df[features]
        y = df['Target_PTS']
        
        print(f"Training on {len(df)} games...")
        
        tscv = TimeSeriesSplit(n_splits=5)
        fold = 1
        mae_scores = []
        
        for train_index, test_index in tscv.split(X):
            X_train, X_test = X.iloc[train_index], X.iloc[test_index]
            y_train, y_test = y.iloc[train_index], y.iloc[test_index]
            
            self.model.fit(
                X_train, y_train,
                eval_set=[(X_test, y_test)],
                verbose=False
            )
            
            preds = self.model.predict(X_test)
            mae = mean_absolute_error(y_test, preds)
            print(f"Fold {fold} MAE: {mae:.2f} points")
            mae_scores.append(mae)
            fold += 1
            
        print(f"Average MAE: {np.mean(mae_scores):.2f}")
        
        # Final fit
        # Disable early stopping for final fit as we use all data
        self.model.set_params(early_stopping_rounds=None)
        self.model.fit(X, y, verbose=False)
        print("Final model trained.")

    def predict_next_game(self, inputs):
        input_df = pd.DataFrame([inputs])
        input_df = input_df[self.feature_columns]
        pred = self.model.predict(input_df)[0]
        return pred

if __name__ == "__main__":
    predictor = NBAPredictor()
    
    try:
        print(f"Starting prediction pipeline for {TARGET_PLAYER}...")
        pid = predictor.get_player_id(TARGET_PLAYER)
        df = predictor.fetch_game_logs(pid, SEASONS)
        
        df_processed = predictor.feature_engineering(df)
        
        predictor.train(df_processed)
        
        # Example Prediction
        last_game = df_processed.iloc[-1]
        print("\n--- Prediction Example ---")
        print(f"Predicting for {TARGET_PLAYER} next game...")
        
        # Fetch Matchup Info
        matchup_info = get_matchup_info.get_game_info()
        
        # Calculate Zone Matchup Score for Next Game
        # We need the League Average for the current season (2025-26)
        current_season = SEASONS[-1]
        league_zones = predictor.league_zone_stats.get(current_season, {})
        player_prof = predictor.player_profile
        
        # Opponent Zone Stats from get_matchup_info
        opp_zones = matchup_info['Opponent_Zone_Stats']
        
        print("\n--- Zone Matchup Score Calculation ---")
        print(f"{'Zone':<25} | {'Freq':<6} | {'Opp%':<6} | {'Lg%':<6} | {'Rel%':<6} | {'Score'}")
        print("-" * 70)
        
        zone_score = 0
        for zone, freq in player_prof.items():
            # Zone names are now consistent (Corner 3, not Left/Right)
            opp_pct = opp_zones.get(zone, 0.45)
            league_pct = league_zones.get(zone, 0.45)
                
            rel_def = opp_pct - league_pct
            score_contrib = freq * rel_def * 100
            zone_score += score_contrib
            
            print(f"{zone:<25} | {freq:.3f}  | {opp_pct:.3f}  | {league_pct:.3f}  | {rel_def:+.3f}  | {score_contrib:+.2f}")
            
        print("-" * 70)
        print(f"Total Zone Matchup Score: {zone_score:.2f}")

        # Calculate Expected Extra Possessions for prediction
        opp_pace = matchup_info['Opponent_Pace']
        league_pace = predictor.league_avg_pace.get(current_season, 100.0)
        expected_extra_poss = (opp_pace - league_pace) * (Proj_Minutes / 48.0)
        print(f"\nPace Analysis: Opp={opp_pace:.1f}, League Avg={league_pace:.1f}, Extra Poss={expected_extra_poss:+.1f}")
        
        # Construct inputs from matchup_info
        next_game_inputs = {
            'Proj_Minutes': Proj_Minutes,
            'Season_Avg_PTS': last_game['Season_Avg_PTS'],
            'Last_5_PTS': last_game['Last_5_PTS'],
            'Last_5_FGA': last_game['Last_5_FGA'],
            'Last_10_PTS': last_game['Last_10_PTS'],
            'Last_10_FGA': last_game['Last_10_FGA'],
            'Home_Away': matchup_info['Home_Away'], 
            'Rest_Days': matchup_info['Rest_Days'], 
            'Opponent_Def_Rating': matchup_info['Opponent_Def_Rating'],
            'Expected_Extra_Poss': expected_extra_poss,
            'Zone_Matchup_Score': zone_score
        }
        
        prediction = predictor.predict_next_game(next_game_inputs)
        print(f"Inputs: {next_game_inputs}")
        print(f"Predicted Points: {prediction:.1f}")
        
        print("\nFeature Importance:")
        importances = predictor.model.feature_importances_
        for name, imp in zip(predictor.feature_columns, importances):
            print(f"{name}: {imp* 100:.2f}%")
            
    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()
