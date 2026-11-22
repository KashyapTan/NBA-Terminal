"""Reproducible local performance harness: uv run python -m tests.waiver_search_benchmark.

Synthetic market; no provider requests or private inputs. Not a timing CI gate.
"""

import json
import resource
import sys
from time import monotonic

from nba_terminal.services.fantasy_optimizer import iter_waiver_plans
from tests.test_fantasy_optimizer import fixture, player, rates


def run(adds):
    data = fixture()
    days = ["2026-11-01", "2026-11-02", "2026-11-03", "2026-11-04"]
    data.update(
        dates=days,
        selected_categories=["pts", "reb", "ast", "stl", "blk"],
        used_adds=7 - adds,
        available_adds=adds,
        lineup_slots=["UTIL"] * 10,
        max_stream_slots=2,
    )
    data["players"] = [player(f"d{i}", "user", [], protected=i >= 2) for i in range(10)]
    data["players"] += [
        player(
            f"p{i}",
            schedule=days,
            current_rates=rates(pts=0.5 + (i % 7) / 10, ast=0.5 + (i % 5) / 10, reb=0.5, stl=0.1, blk=0.1),
        )
        for i in range(400)
    ]
    begin, first, publications = monotonic(), None, 0
    for result in iter_waiver_plans(data, progressive=True):
        publications += 1
        if result["actions"] and first is None:
            first = monotonic() - begin
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return {
        "adds": adds,
        "seconds": round(monotonic() - begin, 3),
        "early_plan_seconds": round(first or 0, 3),
        "publications": publications,
        "evaluations": result["search"]["evaluations"],
        "phase": result["search"]["phase"],
        "moves": len(result["actions"]),
        "first_layer": result["search"]["first_layer_complete"],
        "peak_rss_mb": round(rss / (1024 * 1024 if sys.platform == "darwin" else 1024), 2),
    }


if __name__ == "__main__":
    for budget in (4, 7):
        print(json.dumps(run(budget)), flush=True)
