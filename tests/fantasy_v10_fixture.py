"""Controlled screenshot-shaped totals; synthetic roster aggregation, not private data."""

from nba_terminal.services.fantasy_optimizer import TOTALS

DAYS = ["2026-11-06", "2026-11-07", "2026-11-08"]
FIVE = ["reb", "ast", "stl", "threes", "to"]
ACTUAL = dict(zip(TOTALS, [341, 103, 70, 22, 14, 44, 39, 93, 202, 41, 63]))
THEIR_ACTUAL = dict(zip(TOTALS, [377, 117, 70, 16, 22, 44, 35, 124, 260, 85, 107]))
END = dict(zip(TOTALS, [655.1, 200.4, 135, 41.7, 22.3, 83.4, 73.7, 233.5776, 503.4, 91.2456, 131.1]))
THEIR_END = dict(zip(TOTALS, [686.2, 215, 130.9, 36.8, 37.9, 80.9, 74.2, 241.5, 500, 160.52, 200]))
MERRILL = dict(zip(TOTALS, [8, 3.5, 2.1, 0.9, 0.1, 1.8, 0.3, 2.8, 6.8, 0.3, 0.4])) | {"minutes": 24.4}
JONES = dict(zip(TOTALS, [11.6, 5.3, 1.4, 1.1, 0.9, 2.1, 1.1, 4.4, 8.6, 0.6, 0.9])) | {"minutes": 29.8}


def domain():
    from tests.test_fantasy_optimizer import fixture, player

    data = fixture()
    data.update(
        dates=DAYS,
        selected_categories=FIVE,
        lineup_slots=["UTIL"] * 10,
        current_totals=ACTUAL,
        opponent_totals=THEIR_ACTUAL,
        weekly_add_limit=2,
        used_adds=1,
        available_adds=1,
    )
    data.pop("margin_sd")  # exercise ordinary heuristic scaling
    players = [
        player("100", "user", DAYS[:2], current_rates=MERRILL, name="Sam Merrill"),
        player("101", "free", DAYS[-1:], current_rates=JONES, name="Derrick Jones Jr."),
    ]
    for side, n in [("user", 9), ("opponent", 10)]:
        rates = {
            k: (END[k] - ACTUAL[k] - 2 * MERRILL[k]) / n if side == "user" else (THEIR_END[k] - THEIR_ACTUAL[k]) / n
            for k in TOTALS
        } | {"minutes": 30}
        players.extend(player(f"{side}-{i}", side, DAYS[-1:], current_rates=rates, protected=True) for i in range(n))
    data["players"] = players
    return data


def provider_payload(seed, phase="after-first", day="2026-11-06"):
    """Observed ESPN field shapes with a deliberately controlled authoritative roster."""
    from copy import deepcopy

    from nba_terminal.services import espn_fantasy as espn

    raw = deepcopy(seed)
    league = raw["league"]
    league.update(id=1001, scoringPeriodId=18 + DAYS.index(day))
    league["settings"]["name"] = "Controlled dated outcome fixture"
    league["settings"]["rosterSettings"]["lineupSlotCounts"] = {"11": 10, "12": 3}
    league["teams"] = [t for t in league["teams"] if t["id"] in (1, 2)]
    league["schedule"] = [
        m for m in league["schedule"] if {m.get("home", {}).get("teamId"), m.get("away", {}).get("teamId")} <= {1, 2}
    ]
    source = deepcopy(league["teams"][0]["roster"]["entries"][0])

    def entry(pid, name, team, droppable=False):
        item = deepcopy(source)
        espn.player_body(item).update(
            id=pid,
            fullName=name,
            proTeamId=team,
            eligibleSlots=[11, 12],
            injured=False,
            injuryStatus="ACTIVE",
            droppable=droppable,
        )
        item["lineupSlotId"] = 11
        return item

    for team in league["teams"]:
        own = team["id"] == 1
        entries = [
            entry(500 + i if own else 600 + i, f"{'Owned' if own else 'Opponent'} aggregate {i}", 12)
            for i in range(9 if own else 10)
        ]
        if own:
            pid = 1 if phase == "before" else 101 if phase == "after-second" else 100
            entries.append(
                entry(
                    pid,
                    {1: "Jalen Green", 100: "Sam Merrill", 101: "Derrick Jones Jr."}[pid],
                    11 if pid == 1 else 1 if pid == 100 else 12,
                    True,
                )
            )
        team["roster"]["entries"] = entries
        team["transactionCounter"]["matchupAcquisitionTotals"] = {
            "3": {"before": 0, "after-first": 1, "after-second": 2}[phase]
        }
    seed_pool = deepcopy(raw["pool"]["players"][0])
    pool = []
    for pid in [100, 101] if phase == "before" else [101] if phase == "after-first" else []:
        item = deepcopy(seed_pool)
        item.update(status="FREEAGENT", onTeamId=0)
        espn.player_body(item).update(
            id=pid,
            fullName="Sam Merrill" if pid == 100 else "Derrick Jones Jr.",
            proTeamId=1 if pid == 100 else 12,
            eligibleSlots=[11, 12],
            injured=False,
            injuryStatus="ACTIVE",
            droppable=True,
        )
        pool.append(item)
    raw["pool"]["players"] = pool
    raw["cards"]["players"] = [
        deepcopy(e["playerPoolEntry"]) for t in league["teams"] for e in t["roster"]["entries"]
    ] + deepcopy(pool)
    mapping = {
        "0": "pts",
        "6": "reb",
        "3": "ast",
        "1": "blk",
        "2": "stl",
        "17": "threes",
        "11": "to",
        "13": "fgm",
        "14": "fga",
        "15": "ftm",
        "16": "fta",
    }
    for match in league["schedule"]:
        for side in (match.get("home", {}), match.get("away", {})):
            own = side.get("teamId") == 1
            actual = dict(ACTUAL if own else THEIR_ACTUAL)
            if own:
                for k in TOTALS:
                    actual[k] += MERRILL[k] * sum(d < day for d in DAYS[:2]) if phase != "before" else 0
            for key, value in side.get("cumulativeScore", {}).get("scoreByStat", {}).items():
                value["score"] = actual[mapping[key]] if key in mapping else 0
    return raw


def provider_rates(raw, beneficial=False):
    from nba_terminal.services import espn_fantasy as espn
    from nba_terminal.services import fantasy_nba as nba

    rows = []
    for item in raw["cards"]["players"]:
        p = espn.player_body(item)
        pid = p["id"]
        if pid == 1:
            r = dict.fromkeys(TOTALS, 0) | {"minutes": 24}
        elif pid == 100:
            r = MERRILL
        elif pid == 101:
            r = JONES | ({"reb": 20, "to": 0.1} if beneficial else {})
        else:
            own = 500 <= pid < 600
            r = {
                k: (END[k] - ACTUAL[k] - 2 * MERRILL[k]) / 9 if own else (THEIR_END[k] - THEIR_ACTUAL[k]) / 10
                for k in TOTALS
            } | {"minutes": 30}
        fields = {
            "PTS": "pts",
            "REB": "reb",
            "AST": "ast",
            "STL": "stl",
            "BLK": "blk",
            "FG3M": "threes",
            "TOV": "to",
            "FGM": "fgm",
            "FGA": "fga",
            "FTM": "ftm",
            "FTA": "fta",
            "MIN": "minutes",
        }
        rows.append(
            dict(
                PLAYER_ID=300000 + pid,
                PLAYER_NAME=p["fullName"],
                GP=7 if pid == 101 else 8,
                TEAM_ABBREVIATION=nba.ESPN_TEAMS[p["proTeamId"]],
                TEAM_ID=next(k for k, v in nba.NBA_TO_ESPN.items() if v == p["proTeamId"]),
                **{k: r[v] for k, v in fields.items()},
            )
        )
    return rows
