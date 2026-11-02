"""Coverage checks shared by NBA and ESPN schedule observations.

An endpoint name or 30 dictionary keys alone cannot attest full season coverage.
The Cup initially leaves two games per team unassigned; its open window stays unknown.
"""

from __future__ import annotations

from datetime import date, timedelta


def coverage(schedules: dict, year: int, dates=()) -> dict:
    reasons = []
    teams = set(range(1, 31))
    if set(schedules) != teams:
        reasons.append("All 30 NBA team schedules are required")
    counts = {team: len({str(g.get("game_id")) for g in games}) for team, games in schedules.items()}
    if any(n < 80 or n > 82 for n in counts.values()) or not counts:
        reasons.append("Season inventory must contain 80–82 distinct regular-season games per team")
    invalid = {team for team, n in counts.items() if not 80 <= n <= 82}
    if dates and any(date.fromisoformat(d) >= date(year - 1, 12, 20) for d in dates):
        incomplete_cup = {team for team, n in counts.items() if n < 82}
        if incomplete_cup:
            reasons.append("After the NBA Cup, all 82 regular-season game assignments are required")
            invalid.update(incomplete_cup)
    observations = {}
    anchors = set()
    try:
        for team, games in schedules.items():
            for g in games:
                day = date.fromisoformat(g["date"])
                if not date(year - 1, 7, 1) <= day < date(year, 7, 1):
                    reasons.append("Schedule season/date mismatch")
                    invalid.add(team)
                anchors.add(day - timedelta(days=g["scoring_period_id"]))
                key = (str(g["game_id"]), g["start_at"])
                observations.setdefault(key, set()).add((team, g["opponent_pro_team_id"]))
                if g.get("game_id") is None:
                    reasons.append("Missing game identity")
                    invalid.add(team)
        for pairs in observations.values():
            if len(pairs) != 2 or any((other, team) not in pairs for team, other in pairs):
                reasons.append("Missing reciprocal team/game observation")
                invalid.update(team for pair in pairs for team in pair)
        if len(anchors) != 1:
            reasons.append("Conflicting scoring calendar anchors")
            invalid.update(schedules)
        # 80 assigned games are legitimate outside the as-yet-undecided Cup gap.
        # Refuse a zero-game assertion within any long late-Nov/Dec schedule hole.
        if dates and any(n < 82 for n in counts.values()):
            for team, games in schedules.items():
                days = sorted({date.fromisoformat(g["date"]) for g in games})
                for first, last in zip(days, days[1:]):
                    if first.month in (11, 12) and (last - first).days > 5:
                        if any(first < date.fromisoformat(d) < last for d in dates):
                            reasons.append("NBA Cup dates/opponents are not yet fully assigned")
                            invalid.add(team)
    except (KeyError, ValueError, TypeError):
        reasons.append("Malformed schedule observation")
        invalid.update(schedules)
    reasons = list(dict.fromkeys(reasons))
    return {
        "complete": not reasons,
        "reason": "; ".join(reasons) or "Verified full-season reciprocal game inventory",
        "team_game_counts": counts,
        "verified_team_ids": sorted(set(schedules) - invalid),
    }
