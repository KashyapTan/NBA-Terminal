import sys
import os
import threading
import pandas as pd
import numpy as np
import pickle
import time
import traceback
from datetime import datetime, timedelta

# PyQt6 Imports for the modern GUI
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QLineEdit, QPushButton, QScrollArea, QFrame, 
    QGridLayout, QProgressBar, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor

# ML Imports (XGBoost & Scikit-learn)
try:
    import xgboost as xgb
    from sklearn.model_selection import TimeSeriesSplit
    from sklearn.metrics import mean_absolute_error
except ImportError as e:
    print(f"Error: Missing required package. {e}")
    print("Please install them using: pip install xgboost scikit-learn")
    sys.exit(1)

# NBA API and Helper Imports
from nba_api.stats.static import players, teams
from nba_api.stats.endpoints import (
    playergamelog, 
    leaguedashteamstats, 
    leaguedashteamshotlocations, 
    playerdashboardbyshootingsplits
)
import helper.get_matchup_info as get_matchup_info

# --- CONFIGURATION & CONSTANTS ---
SEASONS = ["2024-25", "2025-26"]
CACHE_FILE = "nba_stats_cache.pkl"
CACHE_EXPIRY_HOURS = 24 

# Zone point values for weighted scoring
ZONE_POINT_VALUES = {
    'Restricted Area': 2.0,
    'In The Paint (Non-RA)': 2.0,
    'Mid-Range': 2.0,
    'Corner 3': 3.0,
    'Above the Break 3': 3.0
}

# Standard zones to track
STANDARD_ZONES = ['Restricted Area', 'In The Paint (Non-RA)', 'Mid-Range', 'Corner 3', 'Above the Break 3']

# --- MODERN COLOR PALETTE ---
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

# --- MODEL LOGIC CLASS ---

class NBAPredictor:
    """
    Handles data fetching, feature engineering, and training.
    """
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
            raise ValueError(f"Player '{player_name}' not found")
        return player_list[0]['id']

    def fetch_player_profile(self, player_id):
        try:
            season = SEASONS[-1]
            splits = playerdashboardbyshootingsplits.PlayerDashboardByShootingSplits(
                player_id=player_id,
                season=season,
                per_mode_detailed='PerGame'
            )
            data_frames = splits.get_data_frames()
            if not data_frames or len(data_frames) < 4:
                raise ValueError("Could not find shooting split data for this player.")
                
            area_df = data_frames[3]
            total_fga = area_df['FGA'].sum()
            profile = {}
            raw_fga = {str(row['GROUP_VALUE']): row['FGA'] for _, row in area_df.iterrows()}
            
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
            self.save_cache()
        except Exception as e:
            raise RuntimeError(f"Failed to fetch player profile: {e}")

    def fetch_game_logs(self, player_id, seasons):
        if not self.player_profile or self.player_profile_id != player_id:
            self.fetch_player_profile(player_id)
        
        all_logs = []
        for season in seasons:
            try:
                log = playergamelog.PlayerGameLog(player_id=player_id, season=season)
                df = log.get_data_frames()[0]
                if df.empty: continue
                df['SEASON_ID'] = season 
                all_logs.append(df)
                self.fetch_season_team_stats(season)
                time.sleep(0.6) 
            except Exception:
                continue
        
        if not all_logs:
            raise ValueError("No game logs found.")
        
        full_df = pd.concat(all_logs, ignore_index=True)
        full_df['GAME_DATE'] = pd.to_datetime(full_df['GAME_DATE'])
        full_df = full_df.sort_values('GAME_DATE').reset_index(drop=True)
        return full_df

    def fetch_season_team_stats(self, season):
        if season in self.team_stats_cache: return

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
                if tid not in id_to_abbrev: continue
                abbrev = id_to_abbrev[tid]
                if abbrev not in season_stats: continue
                
                team_zones = {}
                corner_pcts = []
                for col in zone_df.columns:
                    if len(col) == 2:
                        zone_name, stat_type = str(col[0]), str(col[1])
                        if stat_type == 'OPP_FG_PCT':
                            pct = row[col]
                            if pd.notna(pct):
                                if 'Corner 3' in zone_name and zone_name != 'Corner 3':
                                    corner_pcts.append(pct)
                                elif zone_name in STANDARD_ZONES:
                                    team_zones[zone_name] = pct
                
                if corner_pcts: team_zones['Corner 3'] = np.mean(corner_pcts)
                
                final_zones = {}
                for z in STANDARD_ZONES:
                    if z in team_zones:
                        final_zones[z] = team_zones[z]
                        zone_sums[z] += team_zones[z]
                        zone_counts[z] += 1
                    else:
                        final_zones[z] = 0.45
                
                season_stats[abbrev]['ZONE_DEFENSE'] = final_zones

            league_avgs = {z: (zone_sums[z] / zone_counts[z] if zone_counts[z] > 0 else 0.45) for z in STANDARD_ZONES}
            self.league_zone_stats[season] = league_avgs
            self.team_stats_cache[season] = season_stats
            self.save_cache()
        except Exception:
            pass

    def get_opponent_stats(self, row):
        matchup = row['MATCHUP']
        # Try to find abbreviation in the matchup string
        parts = matchup.split(' ')
        opp_abbrev = parts[-1]
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
                        if zone not in STANDARD_ZONES or zone not in opp_zones: continue
                        pts_val = ZONE_POINT_VALUES.get(zone, 2.0)
                        opp_pct = opp_zones[zone]
                        league_pct = league_zones[zone]
                        zone_score += freq * (opp_pct * pts_val - league_pct * pts_val) * 100
            
            opp_pace = stats.get('PACE', 100.0)
            league_pace = self.league_avg_pace.get(season, 100.0)
            return pd.Series([stats.get('DEF_RATING', 112.0), opp_pace - league_pace, zone_score])
        return pd.Series([112.0, 0, 0])

    def feature_engineering(self, df):
        df['Target_PTS'] = df['PTS']
        df['Home_Away'] = df['MATCHUP'].apply(lambda x: 1 if 'vs.' in x else 0)
        df['Rest_Days'] = (df['GAME_DATE'].diff().dt.days - 1).fillna(3).apply(lambda x: max(0, min(5, x)))
        
        df['Last_5_PTS'] = df['PTS'].shift(1).rolling(window=5).mean()
        df['Last_10_PTS'] = df['PTS'].shift(1).rolling(window=10).mean()
        df['Season_Avg_PTS'] = df.groupby('SEASON_ID')['PTS'].transform(lambda x: x.shift(1).expanding().mean())
        df['Recent_vs_Season'] = df['Last_5_PTS'] - df['Season_Avg_PTS']
        
        df[['Opponent_Def_Rating', 'Extra_Poss_Per_48', 'Zone_Matchup_Score']] = df.apply(self.get_opponent_stats, axis=1)
        df['Expected_Extra_Poss'] = df['Extra_Poss_Per_48'].astype(float) * (df['MIN'].astype(float) / 48.0)
        df['Proj_Minutes'] = df['MIN'].astype(float)
        
        return df.dropna()

    def train(self, df):
        features = [
            'Proj_Minutes', 'Season_Avg_PTS', 'Last_5_PTS', 'Last_10_PTS',
            'Recent_vs_Season', 'Home_Away', 'Rest_Days', 
            'Opponent_Def_Rating', 'Expected_Extra_Poss', 'Zone_Matchup_Score'
        ]
        self.feature_columns = features
        self.training_season_avg = df['Season_Avg_PTS'].mean()
        self.training_pts_std = df['Target_PTS'].std()
        
        X = df[features].astype(float)
        y = df['Target_PTS'].astype(float)
        
        tscv = TimeSeriesSplit(n_splits=5)
        for train_index, test_index in tscv.split(X):
            self.model.fit(X.iloc[train_index], y.iloc[train_index], eval_set=[(X.iloc[test_index], y.iloc[test_index])], verbose=False)
        
        self.model.set_params(early_stopping_rounds=None)
        self.model.fit(X, y, verbose=False)

    def predict_next_game(self, inputs):
        input_df = pd.DataFrame([inputs])[self.feature_columns]
        raw_pred = self.model.predict(input_df)[0]
        season_avg = inputs.get('Season_Avg_PTS', self.training_season_avg)
        lower = max(5, season_avg - 2 * self.training_pts_std)
        upper = season_avg + 2 * self.training_pts_std
        return float(np.clip(raw_pred, lower, upper))

# --- WORKER THREAD ---

class PredictionWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    status = pyqtSignal(str)

    def __init__(self, predictor, player_name, proj_minutes):
        super().__init__()
        self.predictor = predictor
        self.player_name = player_name
        self.proj_minutes = proj_minutes

    def run(self):
        try:
            self.status.emit(f"Finding player ID for {self.player_name}...")
            pid = self.predictor.get_player_id(self.player_name)
            
            self.status.emit("Fetching game logs...")
            df = self.predictor.fetch_game_logs(pid, SEASONS)
            
            self.status.emit("Engineering features...")
            df_processed = self.predictor.feature_engineering(df)
            
            self.status.emit("Training model...")
            self.predictor.train(df_processed)
            
            self.status.emit("Getting matchup information...")
            matchup_info = get_matchup_info.get_game_info()
            
            actual_last_5_pts = df['PTS'].tail(5).mean()
            actual_last_10_pts = df['PTS'].tail(10).mean()
            current_season = SEASONS[-1]
            actual_season_avg = df[df['SEASON_ID'] == current_season]['PTS'].mean()
            league_zones = self.predictor.league_zone_stats.get(current_season, {})
            opp_zones = matchup_info.get('Opponent_Zone_Stats', {z: 0.45 for z in STANDARD_ZONES})
            
            zone_score = 0
            for zone, freq in self.predictor.player_profile.items():
                if zone in STANDARD_ZONES and zone in opp_zones and zone in league_zones:
                    pts_val = ZONE_POINT_VALUES.get(zone, 2.0)
                    zone_score += freq * (opp_zones[zone] * pts_val - league_zones[zone] * pts_val) * 100
            
            opp_pace = matchup_info.get('Opponent_Pace', 100.0)
            league_pace = self.predictor.league_avg_pace.get(current_season, 100.0)
            expected_extra_poss = (opp_pace - league_pace) * (self.proj_minutes / 48.0)
            
            next_game_inputs = {
                'Proj_Minutes': self.proj_minutes,
                'Season_Avg_PTS': actual_season_avg,
                'Last_5_PTS': actual_last_5_pts,
                'Last_10_PTS': actual_last_10_pts,
                'Recent_vs_Season': actual_last_5_pts - actual_season_avg,
                'Home_Away': matchup_info.get('Home_Away', 1), 
                'Rest_Days': matchup_info.get('Rest_Days', 2), 
                'Opponent_Def_Rating': matchup_info.get('Opponent_Def_Rating', 112.0),
                'Expected_Extra_Poss': expected_extra_poss,
                'Zone_Matchup_Score': zone_score
            }
            
            prediction = self.predictor.predict_next_game(next_game_inputs)
            
            importances = self.predictor.model.feature_importances_
            importance_pairs = sorted(zip(self.predictor.feature_columns, importances), key=lambda x: x[1], reverse=True)
            
            result_data = {
                'prediction': prediction,
                'inputs': next_game_inputs,
                'zone_data': {
                    'player_profile': self.predictor.player_profile,
                    'opp_zones': opp_zones,
                    'league_zones': league_zones,
                    'zone_score': zone_score
                },
                'pace_data': {
                    'opp_pace': opp_pace,
                    'league_pace': league_pace,
                    'expected_extra_poss': expected_extra_poss
                },
                'reversion_data': {
                    'last_5': actual_last_5_pts,
                    'season_avg': actual_season_avg,
                    'diff': actual_last_5_pts - actual_season_avg
                },
                'importance_pairs': importance_pairs,
                'matchup_info': matchup_info
            }
            self.finished.emit(result_data)
        except Exception as e:
            traceback.print_exc()
            self.error.emit(str(e))

# --- CUSTOM UI COMPONENTS ---

class MetricBox(QFrame):
    """Small card showing a single metric"""
    def __init__(self, label, value):
        super().__init__()
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_card']};
                border-radius: 12px;
                border: 1px solid {COLORS['border']};
            }}
            QLabel {{ border: none; }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 15, 20, 15)
        
        lbl = QLabel(label.upper())
        lbl.setStyleSheet(f"color: {COLORS['text_tertiary']}; font-weight: bold; font-size: 13px;")
        layout.addWidget(lbl)
        
        val = QLabel(str(value))
        val.setStyleSheet(f"color: {COLORS['text_primary']}; font-weight: bold; font-size: 32px;")
        layout.addWidget(val)

class MatchupRow(QWidget):
    """A row in the Matchup Context card"""
    def __init__(self, label, value, sub_value=None, color=None):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 5)
        
        lbl = QLabel(label)
        lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 15px;")
        layout.addWidget(lbl)
        
        layout.addStretch()
        
        val_str = str(value)
        if sub_value:
            val_str += f" • {sub_value}"
        
        val = QLabel(val_str)
        val_color = color if color else COLORS['text_primary']
        val.setStyleSheet(f"color: {val_color}; font-weight: bold; font-size: 15px;")
        layout.addWidget(val)

class ZoneRow(QFrame):
    """A single row in the Zone Matchup table"""
    def __init__(self, zone, freq, pts, opp_pct, lg_pct, diff, score):
        super().__init__()
        bg = COLORS['bg_card']
        if score > 0.5: bg = '#0d1f14'
        elif score < -0.5: bg = '#1f0d0d'
        
        self.setStyleSheet(f"QFrame {{ background-color: {bg}; border-radius: 4px; border: none; }} QLabel {{ border: none; }}")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        diff_color = COLORS['success'] if diff > 1 else (COLORS['danger'] if diff < -1 else COLORS['text_secondary'])
        score_color = COLORS['success'] if score > 0.5 else (COLORS['danger'] if score < -0.5 else COLORS['text_secondary'])

        def create_lbl(txt, color=COLORS['text_primary'], bold=False, width=None, align=Qt.AlignmentFlag.AlignCenter):
            l = QLabel(txt)
            l.setStyleSheet(f"color: {color}; font-weight: {'bold' if bold else 'normal'}; font-size: 15px;")
            if width: l.setFixedWidth(width)
            l.setAlignment(align)
            return l

        layout.addWidget(create_lbl(zone, width=160, align=Qt.AlignmentFlag.AlignLeft))
        layout.addWidget(create_lbl(f"{freq:.2f}", COLORS['text_secondary'], width=50))
        layout.addWidget(create_lbl(f"{pts:.0f}", COLORS['text_secondary'], width=40))
        layout.addWidget(create_lbl(f"{opp_pct:.1%}", width=60))
        layout.addWidget(create_lbl(f"{lg_pct:.1%}", COLORS['text_secondary'], width=60))
        layout.addWidget(create_lbl(f"{diff:+.1f}%", diff_color, True, width=60))
        layout.addWidget(create_lbl(f"{score:+.2f}", score_color, True, width=70, align=Qt.AlignmentFlag.AlignRight))

# --- MAIN WINDOW ---

class NBAPredictionApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.predictor = NBAPredictor()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("NBA Points Predictor")
        self.resize(800, 1000)
        self.setStyleSheet(f"background-color: {COLORS['bg_primary']}; color: white; border: none;")

        # Set up global scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        # Add basic scrollbar styling
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{ border: none; background-color: transparent; }}
            QScrollBar:vertical {{
                background: {COLORS['bg_primary']};
                width: 10px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {COLORS['bg_hover']};
                min-height: 30px;
                border-radius: 5px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
        """)
        self.setCentralWidget(self.scroll_area)

        # Main container for all content
        self.main_container = QWidget()
        self.scroll_area.setWidget(self.main_container)
        
        self.main_layout = QVBoxLayout(self.main_container)
        # Added extra right margin (40) for spacing from scrollbar
        self.main_layout.setContentsMargins(25, 25, 40, 25)
        self.main_layout.setSpacing(20)

        # Header
        header_lbl = QLabel("NBA PLAYER PROP PREDICTOR")
        header_lbl.setStyleSheet(f"color: {COLORS['text_tertiary']}; font-weight: bold; font-size: 13px; letter-spacing: 1.5px; border: none;")
        self.main_layout.addWidget(header_lbl)

        # Input Card
        input_card = QFrame()
        input_card.setStyleSheet(f"QFrame {{ background-color: {COLORS['bg_card']}; border: 1px solid {COLORS['border']}; border-radius: 12px; }} QLabel {{ border: none; }}")
        input_layout = QHBoxLayout(input_card)
        input_layout.setContentsMargins(25, 25, 25, 25)
        input_layout.setSpacing(20)

        p_layout = QVBoxLayout()
        p_label = QLabel("PLAYER NAME")
        p_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #555;")
        p_layout.addWidget(p_label)
        self.player_input = QLineEdit()
        self.player_input.setPlaceholderText("e.g. Stephen Curry")
        self.player_input.setStyleSheet(f"background: {COLORS['bg_elevated']}; border: 1px solid {COLORS['divider']}; padding: 12px; border-radius: 8px; color: white; font-size: 15px;")
        p_layout.addWidget(self.player_input)
        input_layout.addLayout(p_layout, 2)

        m_layout = QVBoxLayout()
        m_label = QLabel("PROJ MIN")
        m_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #555;")
        m_layout.addWidget(m_label)
        self.minutes_input = QLineEdit()
        self.minutes_input.setPlaceholderText("34.0")
        self.minutes_input.setStyleSheet(f"background: {COLORS['bg_elevated']}; border: 1px solid {COLORS['divider']}; padding: 12px; border-radius: 8px; color: white; font-size: 15px;")
        m_layout.addWidget(self.minutes_input)
        input_layout.addLayout(m_layout, 1)

        self.predict_btn = QPushButton("ANALYZE")
        self.predict_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.predict_btn.setFixedWidth(140)
        self.predict_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['accent']};
                color: white;
                font-weight: bold;
                font-size: 14px;
                padding: 15px;
                border-radius: 8px;
                margin-top: 18px;
            }}
            QPushButton:hover {{ background-color: {COLORS['accent_soft']}; }}
        """)
        self.predict_btn.clicked.connect(self.start_prediction)
        input_layout.addWidget(self.predict_btn)

        self.main_layout.addWidget(input_card)

        # Progress
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setStyleSheet(f"""
            QProgressBar {{ border: none; background-color: {COLORS['bg_elevated']}; height: 2px; border-radius: 1px; }}
            QProgressBar::chunk {{ background-color: {COLORS['accent']}; }}
        """)
        self.main_layout.addWidget(self.progress)
        
        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet(f"color: {COLORS['text_tertiary']}; font-size: 11px; border: none;")
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(self.status_lbl)

        # Results area (directly in the main layout now)
        self.results_container = QWidget()
        self.results_layout = QVBoxLayout(self.results_container)
        self.results_layout.setContentsMargins(0, 0, 0, 0)
        self.results_layout.setSpacing(20)
        self.main_layout.addWidget(self.results_container)
        
        # Add a stretch to keep everything at the top initially
        self.main_layout.addStretch()

    def start_prediction(self):
        player = self.player_input.text().strip()
        mins = self.minutes_input.text().strip()
        
        if not player or not mins:
            self.status_lbl.setText("Missing player name or minutes.")
            return
            
        try:
            mins_val = float(mins)
        except ValueError:
            self.status_lbl.setText("Invalid minutes value.")
            return

        self.predict_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.clear_layout(self.results_layout)

        self.worker = PredictionWorker(self.predictor, player, mins_val)
        self.worker.status.connect(lambda s: self.status_lbl.setText(s))
        self.worker.finished.connect(self.display_results)
        self.worker.error.connect(self.handle_error)
        self.worker.start()

    def handle_error(self, err):
        self.predict_btn.setEnabled(True)
        self.progress.setVisible(False)
        self.status_lbl.setText(f"Error: {err}")

    def display_results(self, data):
        self.predict_btn.setEnabled(True)
        self.progress.setVisible(False)
        self.status_lbl.setText("Finished.")

        # Hero
        hero = QFrame()
        hero.setStyleSheet("border: none;")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(0, 0, 0, 0)
        
        name_lbl = QLabel(self.player_input.text().upper())
        name_lbl.setStyleSheet("font-size: 42px; font-weight: bold; border: none;")
        hero_layout.addWidget(name_lbl)
        
        m_info = data['matchup_info']
        opp_name = m_info.get('Opponent_Name', 'OPPONENT')
        loc = "HOME" if data['inputs']['Home_Away'] == 1 else "AWAY"
        sub_lbl = QLabel(f"VS {opp_name} • {loc} • {data['inputs']['Proj_Minutes']} MIN")
        sub_lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 14px; font-weight: bold; border: none;")
        hero_layout.addWidget(sub_lbl)
        
        pred_box = QHBoxLayout()
        pred_val = QLabel(f"{data['prediction']:.1f}")
        pred_val.setStyleSheet(f"color: {COLORS['accent']}; font-size: 84px; font-weight: bold; border: none;")
        pred_box.addWidget(pred_val)
        pts_lbl = QLabel("PTS")
        pts_lbl.setStyleSheet(f"color: {COLORS['text_tertiary']}; font-size: 24px; font-weight: bold; margin-bottom: 12px; border: none;")
        pred_box.addWidget(pts_lbl, 0, Qt.AlignmentFlag.AlignBottom)
        pred_box.addStretch()
        hero_layout.addLayout(pred_box)
        
        self.results_layout.addWidget(hero)

        # Metrics
        m_grid = QHBoxLayout()
        m_grid.setSpacing(15)
        m_grid.addWidget(MetricBox("Season Avg", f"{data['inputs']['Season_Avg_PTS']:.1f}"))
        m_grid.addWidget(MetricBox("Last 5 G", f"{data['inputs']['Last_5_PTS']:.1f}"))
        m_grid.addWidget(MetricBox("Last 10 G", f"{data['inputs']['Last_10_PTS']:.1f}"))
        self.results_layout.addLayout(m_grid)

        # Matchup Context Card
        context_card = QFrame()
        context_card.setStyleSheet(f"QFrame {{ background-color: {COLORS['bg_card']}; border-radius: 12px; border: 1px solid {COLORS['border']}; }} QLabel {{ border: none; }}")
        c_layout = QVBoxLayout(context_card)
        c_layout.setContentsMargins(20, 20, 20, 20)
        
        c_header = QLabel("MATCHUP CONTEXT")
        c_header.setStyleSheet(f"color: {COLORS['text_tertiary']}; font-weight: bold; font-size: 13px; margin-bottom: 10px;")
        c_layout.addWidget(c_header)
        
        def get_def_label(rtg):
            if rtg < 110: return "Elite", COLORS['danger']    # Low rating is good defense, bad for points
            if rtg < 114: return "Good", COLORS['warning']
            return "Poor", COLORS['success']
        
        def_rtg = data['inputs']['Opponent_Def_Rating']
        def_label, def_color = get_def_label(def_rtg)
        
        c_layout.addWidget(MatchupRow("Defense Rating", f"{def_rtg:.1f}", def_label, def_color))
        c_layout.addWidget(MatchupRow("Projected Minutes", int(data['inputs']['Proj_Minutes'])))
        c_layout.addWidget(MatchupRow("Rest Days", int(data['inputs']['Rest_Days'])))
        
        extra_poss = data['pace_data']['expected_extra_poss']
        poss_color = COLORS['success'] if extra_poss > 0 else COLORS['danger']
        c_layout.addWidget(MatchupRow("Extra Possessions", f"{extra_poss:+.1f}", None, poss_color))
        
        self.results_layout.addWidget(context_card)

        # Zone Card
        zone_card = QFrame()
        zone_card.setStyleSheet(f"QFrame {{ background-color: {COLORS['bg_card']}; border-radius: 12px; border: 1px solid {COLORS['border']}; }} QLabel {{ border: none; }}")
        z_layout = QVBoxLayout(zone_card)
        z_layout.setContentsMargins(25, 25, 25, 25)
        
        z_header = QLabel("ZONE MATCHUP ANALYSIS")
        z_header.setStyleSheet(f"color: {COLORS['text_secondary']}; font-weight: bold; font-size: 15px; margin-bottom: 15px; border: none;")
        z_layout.addWidget(z_header)
        
        # Table Header
        t_head = QHBoxLayout()
        t_head.setContentsMargins(10, 0, 10, 10)
        def h_lbl(t, w, align=Qt.AlignmentFlag.AlignCenter):
            l = QLabel(t)
            l.setStyleSheet(f"color: {COLORS['text_tertiary']}; font-weight: bold; font-size: 13px; border: none;")
            l.setFixedWidth(w); l.setAlignment(align)
            return l
        t_head.addWidget(h_lbl("ZONE", 160, Qt.AlignmentFlag.AlignLeft))
        t_head.addWidget(h_lbl("FREQ", 50))
        t_head.addWidget(h_lbl("PTS", 40))
        t_head.addWidget(h_lbl("OPP%", 60))
        t_head.addWidget(h_lbl("LG%", 60))
        t_head.addWidget(h_lbl("DIFF", 60))
        t_head.addWidget(h_lbl("SCORE", 70, Qt.AlignmentFlag.AlignRight))
        z_layout.addLayout(t_head)

        line = QFrame(); line.setFixedHeight(1); line.setStyleSheet(f"background: {COLORS['divider']};"); z_layout.addWidget(line)

        z_data = data['zone_data']
        for zone in STANDARD_ZONES:
            freq = z_data['player_profile'].get(zone, 0)
            if freq < 0.01: continue
            
            pts = ZONE_POINT_VALUES.get(zone, 2.0)
            opp_pct = z_data['opp_zones'].get(zone, 0.45)
            lg_pct = z_data['league_zones'].get(zone, 0.45)
            diff = (opp_pct - lg_pct) * 100
            score = freq * (opp_pct * pts - lg_pct * pts) * 100
            z_layout.addWidget(ZoneRow(zone, freq, pts, opp_pct, lg_pct, diff, score))

        z_foot = QHBoxLayout()
        z_foot.setContentsMargins(10, 15, 10, 5)
        total_lbl = QLabel("AGGREGATE ZONE SCORE")
        total_lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-weight: bold; font-size: 15px; border: none;")
        z_foot.addWidget(total_lbl)
        z_foot.addStretch()
        
        zs = z_data['zone_score']
        score_val = QLabel(f"{zs:+.2f}")
        color = COLORS['success'] if zs > 0.8 else (COLORS['danger'] if zs < -0.8 else COLORS['text_secondary'])
        score_val.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 36px; border: none;")
        z_foot.addWidget(score_val)
        z_layout.addLayout(z_foot)
        
        self.results_layout.addWidget(zone_card)

        # Pace & Trends
        row2 = QHBoxLayout()
        row2.setSpacing(20)
        
        # Pace
        p_card = QFrame()
        p_card.setStyleSheet(f"QFrame {{ background-color: {COLORS['bg_card']}; border: 1px solid {COLORS['border']}; border-radius: 12px; }} QLabel {{ border: none; }}")
        p_lyt = QVBoxLayout(p_card)
        p_lyt.setContentsMargins(20, 20, 20, 20)
        p_header = QLabel("PACE MATCHUP")
        p_header.setStyleSheet("color: #555; font-size: 13px; font-weight: bold; border: none; margin-bottom: 5px;")
        p_lyt.addWidget(p_header)
        
        def add_stat_line(lyt, l, v, c=None):
            h = QHBoxLayout()
            label = QLabel(l)
            label.setStyleSheet("color: #888; font-size: 15px; border: none;")
            h.addWidget(label)
            val = QLabel(v)
            val.setStyleSheet(f"color: {c if c else 'white'}; font-weight: bold; font-size: 17px; border: none;")
            h.addStretch(); h.addWidget(val)
            lyt.addLayout(h)
        
        pd_val = data['pace_data']
        add_stat_line(p_lyt, "Opponent Pace", f"{pd_val['opp_pace']:.1f}")
        add_stat_line(p_lyt, "League Avg", f"{pd_val['league_pace']:.1f}")
        diff = pd_val['opp_pace'] - pd_val['league_pace']
        add_stat_line(p_lyt, "Pace Delta", f"{diff:+.1f}", COLORS['success'] if diff > 0 else COLORS['danger'])
        row2.addWidget(p_card)

        # Trend
        t_card = QFrame()
        t_card.setStyleSheet(f"QFrame {{ background-color: {COLORS['bg_card']}; border: 1px solid {COLORS['border']}; border-radius: 12px; }} QLabel {{ border: none; }}")
        t_lyt = QVBoxLayout(t_card)
        t_lyt.setContentsMargins(20, 20, 20, 20)
        t_header = QLabel("TREND ANALYSIS")
        t_header.setStyleSheet("color: #555; font-size: 13px; font-weight: bold; border: none; margin-bottom: 5px;")
        t_lyt.addWidget(t_header)
        
        rev = data['reversion_data']
        add_stat_line(t_lyt, "L5 Average", f"{rev['last_5']:.1f}")
        add_stat_line(t_lyt, "Season Average", f"{rev['season_avg']:.1f}")
        status = "Hot" if rev['diff'] > 3 else ("Cold" if rev['diff'] < -3 else "Stable")
        add_stat_line(t_lyt, "Momentum", status, COLORS['warning'] if abs(rev['diff']) > 3 else COLORS['success'])
        row2.addWidget(t_card)

        self.results_layout.addLayout(row2)

        # Importance
        imp_card = QFrame()
        imp_card.setStyleSheet(f"QFrame {{ background-color: {COLORS['bg_card']}; border: 1px solid {COLORS['border']}; border-radius: 12px; }} QLabel {{ border: none; }}")
        imp_lyt = QVBoxLayout(imp_card)
        imp_lyt.setContentsMargins(25, 25, 25, 25)
        imp_header = QLabel("MODEL FEATURE IMPORTANCE")
        imp_header.setStyleSheet("color: #555; font-size: 13px; font-weight: bold; border: none; margin-bottom: 15px;")
        imp_lyt.addWidget(imp_header)
        
        for name, imp in data['importance_pairs']:
            r = QHBoxLayout()
            name_lbl = QLabel(name.replace('_', ' ').title())
            name_lbl.setStyleSheet("font-size: 15px; color: #aaa; border: none;")
            r.addWidget(name_lbl, 2)
            pb = QProgressBar()
            pb.setFixedHeight(6)
            pb.setRange(0, 100)
            pb.setValue(int(imp * 100))
            pb.setTextVisible(False)
            pb.setStyleSheet(f"QProgressBar {{ border: none; background: #222; border-radius: 3px; }} QProgressBar::chunk {{ background: {COLORS['accent']}; }}")
            r.addWidget(pb, 3)
            val_lbl = QLabel(f"{imp:.1%}")
            val_lbl.setStyleSheet("font-size: 13px; color: #555; border: none;")
            r.addWidget(val_lbl, 1)
            imp_lyt.addLayout(r)
        
        self.results_layout.addWidget(imp_card)

    def clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w: w.deleteLater()
            elif item.layout(): self.clear_layout(item.layout())

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 12))
    window = NBAPredictionApp()
    window.show()
    sys.exit(app.exec())
