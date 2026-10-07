from nba_terminal.services.game_center import phase_for_game_id


def test_known_nba_game_id_prefixes_provide_phase_labels():
    assert phase_for_game_id("0012600001") == "Pre Season"
    assert phase_for_game_id("0022600001") == "Regular Season"
    assert phase_for_game_id("0032600001") == "All Star"
    assert phase_for_game_id("0042600001") == "Playoffs"
    assert phase_for_game_id("0052600001") == "Play In"
    assert phase_for_game_id("0062600001") == "NBA Cup Final"


def test_unrecognized_game_id_does_not_guess_a_phase():
    assert phase_for_game_id("unknown") == "Phase unavailable"
    assert phase_for_game_id("") == "Phase unavailable"
