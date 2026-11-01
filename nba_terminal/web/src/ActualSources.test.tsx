import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { ActualSources } from "./ActualSources";
import { testSnapshot } from "./league-fantasy.test-fixtures";
afterEach(cleanup);
it("keeps official totals distinct from partial NBA reconstruction and exposes historical gaps", () => {
  const team = testSnapshot().teams[0];
  team.actuals = {
    official: { totals: { pts: 132 }, source: "espn", fetched_at: "2026-10-31T12:00:00Z" },
    nba_derived: {
      totals: { pts: 117 },
      complete: false,
      provisional: true,
      expected_player_games: 10,
      covered_player_games: 8,
      gaps: ["Historical active lineup missing for Monday"],
      fetched_at: "2026-10-31T12:01:00Z",
    },
    forecast_source: "espn_official_fallback",
    forecast_totals: { pts: 132 },
    forecast_complete: true,
  };
  render(<ActualSources teams={[team]} />);
  expect(screen.getByRole("row", { name: /PTS 132 117 132/ })).toBeInTheDocument();
  expect(screen.getByText(/NBA-derived partial \/ unavailable · provisional/)).toHaveTextContent(
    "8 / 10",
  );
  expect(screen.getByText(/Historical active lineup missing for Monday/)).toBeInTheDocument();
  expect(screen.getByText(/ESPN official scoring · fetched/)).toHaveTextContent(
    "2026-10-31T12:00:00Z",
  );
  expect(screen.getByText(/Forecast actuals basis/)).toHaveTextContent("espn_official_fallback");
  expect(
    screen.getByText(/today’s roster cannot establish past scoring eligibility/),
  ).toBeInTheDocument();
});
it("never fabricates NBA zeros when actuals metadata is absent", () => {
  render(<ActualSources teams={[testSnapshot().teams[0], undefined]} />);
  expect(
    screen.getByText(/NBA reconstruction and historical scoring-lineup coverage are unverified/),
  ).toBeInTheDocument();
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
});
it("renders exact DATA structured gaps and preserves provider timestamps separately from evaluation", () => {
  const team = testSnapshot().teams[0];
  team.actuals = {
    official: { totals: { pts: 132 }, source: "espn_official", fetched_at: "2026-11-01T03:00:00Z" },
    nba_derived: {
      totals: null,
      complete: false,
      provisional: true,
      expected_player_games: 3,
      covered_player_games: 0,
      gaps: [
        { period: 3, reason: "historical_daily_lineup_missing" },
        { period: 4, player_id: "8", game_id: "002", reason: "nba_player_game_missing" },
      ],
      fetched_at: "2026-11-01T03:00:00Z",
    },
    forecast_source: "espn_official",
    forecast_totals: { pts: 132 },
    forecast_complete: true,
    sources: [
      { source: "nba_player_game_logs", status: "stale", fetched_at: "2026-10-31T20:00:00Z" },
    ],
  };
  render(<ActualSources teams={[team]} />);
  expect(
    screen.getByText(/Historical active scoring lineup missing · scoring day 3/),
  ).toHaveTextContent("NBA player/game production missing · scoring day 4 · player 8 · game 002");
  expect(screen.getByText(/NBA player game logs · stale/)).toHaveTextContent(
    "provider response fetched 2026-10-31T20:00:00Z · provider update time unverified",
  );
  expect(screen.getByRole("row", { name: /PTS 132 Unavailable 132/ })).toBeInTheDocument();
  expect(screen.getByText(/Forecast actuals basis:/).closest("p")).toHaveTextContent(
    "ESPN official scoring (NBA reconstruction fallback) · Complete scoring basis",
  );
});
