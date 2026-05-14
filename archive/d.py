from archive.c import clear_charts_folder
from helper.formula import print_player_season_stats, print_player_vs_team_stats
from helper.percentile import print_player_percentile, print_player_percentile_vs_team


def get_stats(player, team):
    print_player_season_stats(player, '2024-25')
    print_player_season_stats(player, '2025-26')
    print_player_vs_team_stats(player, '2024-25', team)
    print_player_vs_team_stats(player, '2025-26', team)
    print_player_percentile(player, "2024-25")
    print_player_percentile_vs_team(player, "2024-25", team)
    print_player_percentile(player, "2025-26")
    print_player_percentile_vs_team(player, "2025-26", team)
    

player = 'James Harden'
team = '76ers'

clear_charts_folder()
get_stats(player, team)
