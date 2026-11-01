import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import {
  PlayerSampleExplorer,
  PlayerSeasonMeasures,
  PlayerShootingBreakdowns,
  summarizePlayerSample,
} from "./PlayerProfileDetails";
import type { PlayerProfile } from "./player-browser-api";

const profile: PlayerProfile = {
  player_id: 7,
  player_name: "Test",
  season: "2025-26",
  phase: "Playoffs",
  advanced: { TS_PCT: 0.65 },
  advanced_state: "available",
  advanced_note: "",
  advanced_source: "NBA Advanced",
  shooting: {},
  history: {
    state: "available",
    note: "",
    season: "2025-26",
    phase: "Playoffs",
    opponent: null,
    games_played: 3,
    opponent_games_played: 0,
    opponent_games: [],
    summary: {},
    games: [
      { game_id: "0042500001", matchup: "BOS vs. CLE", pts: 10 },
      { game_id: "0042500002", matchup: "BOS @ NYK", pts: 20 },
      { game_id: "0042500003", matchup: "BOS @ CLE", pts: 30 },
    ],
  },
};
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
it("defines percentile interpolation, SD, threshold and zero/missing cases", () => {
  const sample = summarizePlayerSample(
    [{ pts: 0 }, { pts: 10 }, { pts: null }, { pts: 20 }, { pts: 30 }],
    "pts",
    20,
  );
  expect(sample).toMatchObject({
    n: 4,
    mean: 15,
    p25: 7.5,
    median: 15,
    p75: 22.5,
    max: 30,
    hits: 2,
    rate: 0.5,
  });
  expect(sample.sd).toBeCloseTo(Math.sqrt(500 / 3));
  expect(summarizePlayerSample([{ pts: 0 }], "pts", 0)).toMatchObject({ sd: 0, cv: 0, rate: 1 });
  expect(summarizePlayerSample([{ pts: null }], "pts", 1)).toMatchObject({
    n: 0,
    mean: null,
    rate: null,
  });
});
it("loads selected measures on demand and shows Usage total minutes", async () => {
  const fetcher = vi.fn(async () => ({
    ok: true,
    json: async () => ({
      state: "available",
      note: "",
      source: "LeagueDashPlayerStats · PerGame",
      season: "2025-26",
      phase: "Playoffs",
      row: { GP: 23, MIN: 851, PTS: 29.9, USG_PCT: 0.322 },
    }),
  }));
  vi.stubGlobal("fetch", fetcher);
  render(<PlayerSeasonMeasures profile={profile} />);
  expect(fetcher).not.toHaveBeenCalled();
  await userEvent.selectOptions(screen.getByLabelText("Season dashboard measure"), "Base");
  expect(await screen.findByText("29.9")).toBeInTheDocument();
  await userEvent.selectOptions(screen.getByLabelText("Season dashboard measure"), "Usage");
  expect(await screen.findByText("32.2%")).toBeInTheDocument();
  expect(screen.getByText(/Total minutes/)).toHaveTextContent("851.0");
  expect(fetcher).toHaveBeenCalledTimes(2);
});
it("loads shooting tables once and distinguishes empty from failed", async () => {
  const fetcher = vi.fn(async () => ({
    ok: true,
    json: async () => ({
      state: "error",
      note: "",
      source: "NBA Totals",
      tables: {
        Overall: {
          state: "available",
          note: "",
          rows: [{ GROUP_VALUE: "Overall", FGA: 504, FG_PCT: 0.462 }],
        },
        "Shot Area": { state: "unavailable", note: "No area rows", rows: [] },
        Assisted: { state: "error", note: "Unexpected schema", rows: [] },
      },
    }),
  }));
  vi.stubGlobal("fetch", fetcher);
  render(<PlayerShootingBreakdowns profile={profile} />);
  expect(fetcher).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "Load shooting breakdowns" }));
  expect(await screen.findByText("46.2%")).toBeInTheDocument();
  await userEvent.selectOptions(screen.getByLabelText("Shooting breakdown"), "Shot Area");
  expect(screen.getByRole("status")).toHaveTextContent("Unavailable: No area rows");
  await userEvent.selectOptions(screen.getByLabelText("Shooting breakdown"), "Assisted");
  expect(screen.getByRole("alert")).toHaveTextContent("Request failed: Unexpected schema");
  expect(fetcher).toHaveBeenCalledTimes(1);
});
it("filters the same opponent independently across two phase-specific seasons", async () => {
  const fetcher = vi.fn(async () => ({
    ok: true,
    json: async () => ({
      ...profile,
      history: {
        ...profile.history,
        season: "2024-25",
        games: [
          { game_id: "0042400001", matchup: "BOS vs. CLE", pts: 40 },
          { game_id: "0042400002", matchup: "BOS vs. NYK", pts: 60 },
        ],
      },
    }),
  }));
  vi.stubGlobal("fetch", fetcher);
  render(
    <MemoryRouter>
      <PlayerSampleExplorer profile={profile} />
    </MemoryRouter>,
  );
  await userEvent.selectOptions(screen.getByLabelText("Profile opponent"), "CLE");
  await userEvent.click(screen.getByRole("button", { name: "Compare season" }));
  const table = screen.getByRole("table", { name: "Season sample comparison" });
  expect(await within(table).findByText("2024-25 · Playoffs")).toBeInTheDocument();
  const rows = within(table).getAllByRole("row");
  expect(within(rows[1]).getByText("50.0%")).toBeInTheDocument();
  expect(within(rows[2]).getByText("100.0%")).toBeInTheDocument();
  expect(within(rows[1]).getByText("1/2")).toBeInTheDocument();
  expect(within(rows[2]).getByText("1/1")).toBeInTheDocument();
  expect(fetcher).toHaveBeenCalledWith(
    "/api/players/7/history?season=2024-25&phase=Playoffs",
    expect.anything(),
  );
});

it("allows an on-demand season-table failure to be retried", async () => {
  let attempts = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => {
      attempts += 1;
      if (attempts === 1) throw new Error("Temporary network failure");
      return {
        ok: true,
        json: async () => ({
          state: "available",
          note: "",
          source: "NBA Base",
          season: "2025-26",
          phase: "Playoffs",
          row: { PTS: 29.9 },
        }),
      };
    }),
  );
  render(<PlayerSeasonMeasures profile={profile} />);
  await userEvent.selectOptions(screen.getByLabelText("Season dashboard measure"), "Base");
  expect(await screen.findByRole("alert")).toHaveTextContent("Temporary network failure");
  await userEvent.click(screen.getByRole("button", { name: "Retry season table" }));
  expect(await screen.findByText("29.9")).toBeInTheDocument();
});
