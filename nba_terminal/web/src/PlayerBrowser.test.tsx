import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { PlayerBrowser, PlayerProfileView } from "./PlayerBrowser";
import { GameLogTable } from "./PlayerAnalysis";
import type { PlayerProfile } from "./player-browser-api";

const profile: PlayerProfile = {
  player_id: 7,
  player_name: "Test Player",
  season: "2025-26",
  phase: "Playoffs",
  history: {
    state: "available",
    note: "",
    season: "2025-26",
    phase: "Playoffs",
    opponent: null,
    games_played: 2,
    opponent_games_played: 0,
    summary: {},
    opponent_games: [],
    games: [
      { game_id: "0042400407", game_date: "2025-06-22", matchup: "OKC vs. IND", pts: 29 },
      { game_id: "0042400406", game_date: "2025-06-19", matchup: "OKC @ IND", pts: 21 },
    ],
  },
  advanced: { TS_PCT: 0.65, USG_PCT: 0.31, NET_RATING: 5, GP: 2 },
  advanced_state: "available",
  advanced_note: "",
  advanced_source: "LeagueDashPlayerStats · Advanced · PerGame",
  shooting: { ts_pct: { value: 0.63, games: 2 } },
};
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
it("searches independently and exposes selected player callback with season/phase request", async () => {
  const select = vi.fn();
  const fetcher = vi.fn(async (input: string) => ({
    ok: true,
    json: async () =>
      input.startsWith("/api/players?")
        ? { players: [{ player_id: 7, name: "Test Player", active: true }] }
        : profile,
  }));
  vi.stubGlobal("fetch", fetcher);
  render(
    <MemoryRouter>
      <PlayerBrowser season="2025-26" phase="Playoffs" onPlayerSelect={select} />
    </MemoryRouter>,
  );
  fireEvent.change(screen.getByLabelText("Search NBA players"), { target: { value: "Test" } });
  await userEvent.click(await screen.findByRole("button", { name: /Test Player/ }));
  expect(select).toHaveBeenCalledWith(7);
  expect(await screen.findByRole("heading", { name: "Test Player" })).toBeInTheDocument();
  expect(fetcher).toHaveBeenCalledWith(
    "/api/players/7?season=2025-26&phase=Playoffs",
    expect.anything(),
  );
  expect(screen.getAllByText("65.0%")[0]).toBeInTheDocument();
  expect(screen.getByText("63.0%")).toBeInTheDocument();
  const link = screen.getAllByRole("link", { name: /Open box score 2025-06-19/ })[0];
  expect(link).toHaveAttribute("href", "/game/0042400406?season=2025-26&phase=Playoffs&player=7");
});
it("renders direct selected profile and distinguishes failed from unavailable advanced data", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string) => ({
      ok: true,
      json: async () =>
        input.startsWith("/api/players?")
          ? { players: [] }
          : { ...profile, advanced_state: "error", advanced_note: "Upstream timed out" },
    })),
  );
  render(
    <MemoryRouter>
      <PlayerBrowser season="2025-26" phase="Playoffs" playerId={7} />
    </MemoryRouter>,
  );
  expect((await screen.findAllByRole("alert"))[0]).toHaveTextContent(
    "Request failed: Upstream timed out",
  );
  expect(screen.getByRole("heading", { name: "Test Player" })).toBeInTheDocument();
  cleanup();
  render(
    <MemoryRouter>
      <PlayerProfileView
        profile={{ ...profile, advanced_state: "unavailable", advanced_note: "No season line" }}
      />
    </MemoryRouter>,
  );
  expect(screen.getAllByRole("status")[0]).toHaveTextContent("Unavailable: No season line");
});
it("game log links use actual IDs, preserve context and support keyboard navigation", async () => {
  render(
    <MemoryRouter>
      <GameLogTable rows={profile.history.games} season="2025-26" phase="Playoffs" playerId={7} />
    </MemoryRouter>,
  );
  const second = screen.getByRole("link", { name: /2025-06-19/ });
  second.focus();
  expect(second).toHaveFocus();
  await userEvent.keyboard("{Enter}");
  expect(second).toHaveAttribute("href", "/game/0042400406?season=2025-26&phase=Playoffs&player=7");
});
it("reloads profile when controlled player or season changes", async () => {
  const fetcher = vi.fn(async (input: string) => ({
    ok: true,
    json: async () => (input.startsWith("/api/players?") ? { players: [] } : profile),
  }));
  vi.stubGlobal("fetch", fetcher);
  const { rerender } = render(
    <MemoryRouter>
      <PlayerBrowser season="2025-26" phase="Playoffs" playerId={7} />
    </MemoryRouter>,
  );
  await screen.findByRole("heading", { name: "Test Player" });
  rerender(
    <MemoryRouter>
      <PlayerBrowser season="2024-25" phase="Regular Season" playerId={8} />
    </MemoryRouter>,
  );
  await waitFor(() =>
    expect(fetcher).toHaveBeenCalledWith(
      "/api/players/8?season=2024-25&phase=Regular+Season",
      expect.anything(),
    ),
  );
});

it("retries a failed profile request without converting failure into an empty season", async () => {
  let attempts = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string) => {
      if (input.startsWith("/api/players?"))
        return { ok: true, json: async () => ({ players: [] }) };
      attempts += 1;
      return attempts === 1 ? { ok: false, status: 502 } : { ok: true, json: async () => profile };
    }),
  );
  render(
    <MemoryRouter>
      <PlayerBrowser season="2025-26" phase="Playoffs" playerId={7} />
    </MemoryRouter>,
  );
  expect(await screen.findByRole("alert")).toHaveTextContent("Player data request failed (502)");
  expect(screen.queryByRole("heading", { name: "Test Player" })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Retry player profile" }));
  expect(await screen.findByRole("heading", { name: "Test Player" })).toBeInTheDocument();
  expect(attempts).toBe(2);
});
