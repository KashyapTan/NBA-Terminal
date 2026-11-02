// Test-only visual harness. Final acceptance uses the real integrated route and backend.

import { useState } from "react";
import { createRoot } from "react-dom/client";
import { testPlayer } from "../../src/league-fantasy.test-fixtures";
import {
  type Category,
  LEAGUE_CATEGORIES,
  type PickupRecommendation,
  type PlanForecast,
} from "../../src/league-fantasy-model";
import { DEFAULT_PICKUP_FILTERS, WaiverWorkspace } from "../../src/WaiverWorkspace";

function Preview() {
  const [targets, setTargets] = useState<Category[]>(["pts", "ast", "stl", "threes", "ft_pct"]);
  const [filters, setFilters] = useState(DEFAULT_PICKUP_FILTERS);
  const failure = new URLSearchParams(location.search).has("failure");
  const baseline: PlanForecast = {
    basis: "forecast",
    totals: {
      pts: 452,
      reb: 180,
      ast: 94,
      stl: 24,
      blk: 15,
      threes: 56,
      to: 42,
      fgm: 160,
      fga: 330,
      ftm: 76,
      fta: 94,
    },
    opponent_totals: {
      pts: 434,
      reb: 190,
      ast: 94,
      stl: 22,
      blk: 18,
      threes: 52,
      to: 48,
      fgm: 158,
      fga: 340,
      ftm: 76,
      fta: 88,
    },
    actual_primitives: {
      user: {
        pts: 205,
        reb: 82,
        ast: 45,
        stl: 10,
        blk: 7,
        threes: 22,
        to: 20,
        fgm: 75,
        fga: 160,
        ftm: 33,
        fta: 40,
      },
      opponent: {
        pts: 218,
        reb: 92,
        ast: 49,
        stl: 11,
        blk: 9,
        threes: 26,
        to: 24,
        fgm: 80,
        fga: 170,
        ftm: 32,
        fta: 38,
      },
    },
    games: 12,
    minutes: 345,
    probability_five_wins: null,
  };
  const projected: PlanForecast = {
    ...baseline,
    totals: {
      ...baseline.totals,
      pts: 468,
      reb: 168,
      ast: 110,
      stl: 28,
      to: 44,
      fgm: 166,
      fga: 342,
      ftm: 84,
      fta: 102,
    },
  };
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
    drop_starts: 1,
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
        forecast={{ baseline, projected }}
        scheduleCounts={[
          { addRemainingGames: 4, dropRemainingGames: 3 },
          { addRemainingGames: 3, dropRemainingGames: 2 },
        ]}
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
