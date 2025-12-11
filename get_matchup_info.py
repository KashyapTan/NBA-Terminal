from nba_api.stats.static import teams
from nba_api.stats.endpoints import leaguegamefinder, leaguedashteamstats, scoreboardv2
import pandas as pd
from datetime import datetime

# Constants
PLAYER_TEAM_ABBREV = "OKC" # Spurs
OPPONENT_ABBREV = "PHX"    # Lakers
DATE_TODAY = "2025-12-10"  # Current Date
SEASON = "2025-26"

def get_game_info():
    print(f"Gathering info for {PLAYER_TEAM_ABBREV} vs {OPPONENT_ABBREV} on {DATE_TODAY}...")
    
    # 1. Check Schedule for Home/Away and Rest Days
    nba_teams = teams.get_teams()
    min_team = [t for t in nba_teams if t['abbreviation'] == PLAYER_TEAM_ABBREV][0]
    min_id = min_team['id']
    
    gamefinder = leaguegamefinder.LeagueGameFinder(team_id_nullable=min_id)
    games = gamefinder.get_data_frames()[0]
    games['GAME_DATE'] = pd.to_datetime(games['GAME_DATE'])
    games = games.sort_values('GAME_DATE', ascending=False)
    
    # Find last completed game
    completed_games = games.dropna(subset=['WL'])
    last_game = completed_games.iloc[0]
    last_game_date = last_game['GAME_DATE']
    
    print(f"Last game was on: {last_game_date.strftime('%Y-%m-%d')} vs {last_game['MATCHUP']}")
    
    # Calculate Rest Days
    today_dt = pd.to_datetime(DATE_TODAY)
    rest_days = (today_dt - last_game_date).days - 1
    print(f"Rest Days: {rest_days}")
    
    # Check if Home or Away today
    sb = scoreboardv2.ScoreboardV2(game_date=DATE_TODAY)
    todays_games = sb.game_header.get_data_frame()
    
    min_game = todays_games[(todays_games['HOME_TEAM_ID'] == min_id) | (todays_games['VISITOR_TEAM_ID'] == min_id)]
    
    if not min_game.empty:
        is_home = 1 if min_game.iloc[0]['HOME_TEAM_ID'] == min_id else 0
        print(f"Game found! Home/Away: {'Home' if is_home else 'Away'} ({is_home})")
    else:
        print("No game found for MIN today in Scoreboard. Assuming hypothetical or checking schedule...")
        is_home = 0 
    
    # 2. Get Opponent Stats (PHX)
    print(f"Fetching stats for {OPPONENT_ABBREV}...")
    
    # Advanced Stats
    adv_stats = leaguedashteamstats.LeagueDashTeamStats(season=SEASON, measure_type_detailed_defense='Advanced')
    adv_df = adv_stats.get_data_frames()[0]
    
    # Opponent Shooting Stats (Per Game)
    opp_stats_ep = leaguedashteamstats.LeagueDashTeamStats(
        season=SEASON, 
        measure_type_detailed_defense='Opponent',
        per_mode_detailed='PerGame'
    )
    opp_df = opp_stats_ep.get_data_frames()[0]
    
    # Map ID to Abbrev
    id_to_abbrev = {t['id']: t['abbreviation'] for t in nba_teams}
    adv_df['TEAM_ABBREVIATION'] = adv_df['TEAM_ID'].map(id_to_abbrev)
    opp_df['TEAM_ABBREVIATION'] = opp_df['TEAM_ID'].map(id_to_abbrev)
    
    # Get specific team stats
    team_adv = adv_df[adv_df['TEAM_ABBREVIATION'] == OPPONENT_ABBREV].iloc[0]
    team_opp = opp_df[opp_df['TEAM_ABBREVIATION'] == OPPONENT_ABBREV].iloc[0]
    
    def_rating = team_adv['DEF_RATING']
    pace = team_adv['PACE']
    opp_fg3m = team_opp['OPP_FG3M']
    opp_fgm = team_opp['OPP_FGM']
    
    print(f"Opponent ({OPPONENT_ABBREV}) Stats:")
    print(f"- Def Rating: {def_rating}")
    print(f"- Pace: {pace}")
    print(f"- Opp 3PM/Game: {opp_fg3m}")
    print(f"- Opp FGM/Game: {opp_fgm}")

    # Fetch Zone Stats for Opponent
    print("Fetching Opponent Zone Stats...")
    from nba_api.stats.endpoints import teamdashboardbyshootingsplits
    phx_id = [t for t in nba_teams if t['abbreviation'] == OPPONENT_ABBREV][0]['id']
    splits = teamdashboardbyshootingsplits.TeamDashboardByShootingSplits(
        team_id=phx_id,
        season=SEASON,
        measure_type_detailed_defense='Opponent',
        per_mode_detailed='PerGame'
    )
    # Frame 3 is Shot Area (verified from actual API response)
    area_df = splits.get_data_frames()[3]
    print("Opponent Zone FG% Allowed:")
    zone_stats = {}
    corner_pcts = []
    for _, row in area_df.iterrows():
        zone = row['GROUP_VALUE']
        pct = row['FG_PCT']
        print(f"- {zone}: {pct}")
        
        # Normalize zone names - combine Left/Right Corner 3
        if 'Corner 3' in zone:
            corner_pcts.append(pct)
        else:
            zone_stats[zone] = pct
    
    # Add combined Corner 3 if we have corner data
    if corner_pcts:
        import numpy as np
        zone_stats['Corner 3'] = np.mean(corner_pcts)
        print(f"- Corner 3 (combined): {zone_stats['Corner 3']:.3f}")
    
    return {
        'Home_Away': is_home,
        'Rest_Days': rest_days,
        'Opponent_Def_Rating': def_rating,
        'Opponent_Pace': pace,
        'Opponent_FG3M': opp_fg3m,
        'Opponent_FGM': opp_fgm,
        'Opponent_Zone_Stats': zone_stats
    }

if __name__ == "__main__":
    try:
        info = get_game_info()
        print("\n--- INPUTS FOR P.PY ---")
        print(info)
    except Exception as e:
        print(f"Error: {e}")
