from nba_terminal.analytics import (
    consistency_label,
    defense_rank_tier,
    flatten_consistency_results,
    format_percentage,
    format_signed,
    league_averages,
    normalize_bet_direction,
    parse_pick_date_from_name,
    safe_float,
    sort_confident_bets,
    sort_team_defense,
    summarize_consistency,
)


def test_safe_float_handles_bad_values():
    assert safe_float("12.5") == 12.5
    assert safe_float(None, default=3.0) == 3.0
    assert safe_float(float("nan"), default=2.0) == 2.0
    assert safe_float(float("inf"), default=7.0) == 7.0


def test_format_helpers():
    assert format_percentage(0.456) == "45.6%"
    assert format_percentage("bad") == "0.0%"
    assert format_signed(1.234) == "+1.2"
    assert format_signed(-1.234, digits=2) == "-1.23"


def test_defense_rank_tiers_and_validation():
    assert defense_rank_tier(1) == ("Elite", "success")
    assert defense_rank_tier(10) == ("Good", "accent")
    assert defense_rank_tier(18) == ("Average", "text_primary")
    assert defense_rank_tier(24) == ("Below Avg", "warning")
    assert defense_rank_tier(30) == ("Poor", "danger")
    try:
        defense_rank_tier(0)
    except ValueError as exc:
        assert "rank" in str(exc)
    else:
        raise AssertionError("rank validation did not run")


def test_team_defense_sort_and_averages():
    data = [
        {"Team": "B", "OPP_FG_PCT": 0.5, "OPP_FG3_PCT": 0.4},
        {"Team": "A", "OPP_FG_PCT": 0.4, "OPP_FG3_PCT": 0.3},
    ]
    ranked = sort_team_defense(data)
    assert [row["Team"] for row in ranked] == ["A", "B"]
    averages = league_averages(ranked)
    assert averages["OPP_FG_PCT"] == 0.45
    assert averages["Corner 3"] == 0.0
    assert league_averages([])["OPP_FG_PCT"] == 0.0


def test_consistency_helpers():
    assert consistency_label(0.2) == ("Elite", "success")
    assert consistency_label(0.4) == ("Good", "accent")
    assert consistency_label(0.6) == ("Average", "warning")
    assert consistency_label(0.8) == ("Variable", "danger")

    results = {
        10: {
            "Points": [
                {"name": "High", "cv": 0.5, "mean": 12, "std": 6},
                {"name": "Low", "cv": 0.2, "mean": 10, "std": 2},
            ]
        }
    }
    rows = flatten_consistency_results(results, 10, "Points")
    assert [row["name"] for row in rows] == ["Low", "High"]
    assert len(flatten_consistency_results(results, 10, "Points", limit=None)) == 2
    assert rows[0]["rank"] == 1
    assert rows[0]["cv_percent"] == 20
    assert summarize_consistency(rows) == {
        "count": 2,
        "best_player": "Low",
        "best_cv": 20,
        "avg_cv": 35,
    }
    assert summarize_consistency([])["best_player"] == "N/A"
    assert flatten_consistency_results(results, 5, "Points") == []


def test_bet_helpers_and_pick_date_parsing():
    bets = [
        {"player_name": "A", "diff": -3.1},
        {"player_name": "B", "diff": 5.2},
    ]
    sorted_bets = sort_confident_bets(bets)
    assert [row["player_name"] for row in sorted_bets] == ["B", "A"]
    assert [row["direction"] for row in sorted_bets] == ["OVER", "UNDER"]
    assert normalize_bet_direction(0) == "UNDER"

    assert parse_pick_date_from_name("12_31_2025.MD") == (2025, 12, 31)
    assert parse_pick_date_from_name("1_2_2026.md") == (2026, 1, 2)
    assert parse_pick_date_from_name("bad.md") is None
    assert parse_pick_date_from_name("13_2_2026.md") is None
