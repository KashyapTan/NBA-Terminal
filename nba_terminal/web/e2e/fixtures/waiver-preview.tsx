// Test-only visual harness. Final acceptance uses the real integrated route and backend.

import { useState } from "react";
import { createRoot } from "react-dom/client";
import { testPlayer } from "../../src/league-fantasy.test-fixtures";
import {
  type Category,
  LEAGUE_CATEGORIES,
  type PickupRecommendation,
} from "../../src/league-fantasy-model";
import { DEFAULT_PICKUP_FILTERS, WaiverWorkspace } from "../../src/WaiverWorkspace";

function Preview() {
  const [targets, setTargets] = useState<Category[]>(["pts", "ast", "stl", "threes", "ft_pct"]);
  const [filters, setFilters] = useState(DEFAULT_PICKUP_FILTERS);
  const failure = new URLSearchParams(location.search).has("failure");
  const move = (add_id: string, drop_id: string, date: string): PickupRecommendation => ({
    add_id,
    drop_id,
    date,
    probability_gain: null,
    games_gain: 1,
    minutes_gain: null,
    season_cost: null,
    net_score: null,
    gains: {},
    target_categories: targets,
    rationale: "Fixture paired full-roster forecast, with displaced starts accounted for.",
    add_starts: 3,
    arithmetic: {
      primitives: {},
      categories: Object.fromEntries(
        LEAGUE_CATEGORIES.map(({ key }) => [
          key,
          {
            before: key.endsWith("pct") ? 0.7 : 100,
            after: key.endsWith("pct") ? 0.71 : key === "reb" ? 94 : 108,
            net: key.endsWith("pct") ? 0.01 : key === "reb" ? -6 : 8,
            opponent_before: 110,
            opponent_after: 110,
            lower_is_better: key === "to",
            add: 20,
            drop: 9,
            spillover: key === "reb" ? -17 : -3,
            ...(key.endsWith("pct")
              ? {
                  makes: { before: 70, add: 8, drop: 5, spillover: -2, after: 71, net: 1 },
                  attempts: { before: 100, add: 10, drop: 8, spillover: -2, after: 100, net: 0 },
                }
              : {}),
          },
        ]),
      ) as NonNullable<PickupRecommendation["arithmetic"]>["categories"],
    },
  });
  return (
    <main style={{ maxWidth: 1000, padding: "24px 12px", margin: "auto" }}>
      <WaiverWorkspace
        matchup="Metro Owls vs North Stars"
        remainingAddsLabel="3 adds left"
        refreshedLabel="Updated 12:04"
        updating={failure}
        status={
          failure
            ? {
                text: "Showing saved plan · refresh delayed",
                actionLabel: "Retry",
                onAction: () => {},
              }
            : undefined
        }
        targets={targets}
        onTargetsChange={setTargets}
        filters={filters}
        onFiltersChange={setFilters}
        strategy={Object.fromEntries(
          targets.map((key) => [
            key,
            {
              projected_user: key.endsWith("pct") ? 0.78 : 180,
              projected_opponent: key.endsWith("pct") ? 0.77 : 174,
            },
          ]),
        )}
        moves={[move("a", "d", "2026-11-03"), move("b", "e", "2026-11-04")]}
        players={{
          a: testPlayer("a", { name: "Jordan Guard" }),
          b: testPlayer("b", { name: "Morgan Wing" }),
          d: testPlayer("d", { name: "Cameron Center" }),
          e: testPlayer("e", { name: "Taylor Bench" }),
        }}
        samples={{
          a: { minutes: 28.4, games: 5, teamGames: 6 },
          b: { minutes: 23.1, games: 4, teamGames: 6 },
        }}
        stop="search_limit"
        rosterControls={
          <details className="ww-control">
            <summary>Roster settings</summary>
            <div className="ww-popover">Availability and protected players</div>
          </details>
        }
        analysis={
          <p>
            Fixture-only source coverage, exclusions and search diagnostics. Live provider data is
            not used.
          </p>
        }
      />
    </main>
  );
}
createRoot(document.getElementById("root")!).render(<Preview />);
