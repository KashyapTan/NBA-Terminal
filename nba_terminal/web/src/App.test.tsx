import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AppRoutes, MetaProvider } from "./App";

const team = (id: number, abbreviation: string, name: string) => ({
  id,
  abbreviation,
  name,
  nickname: name.split(" ").at(-1) || name,
});
const away = team(1, "CLE", "Cleveland Cavaliers");
const home = team(2, "BOS", "Boston Celtics");
const game = {
  game_id: "0022400001",
  date: "2025-11-02",
  status: "Final",
  phase: "Regular Season",
  home_team: home,
  away_team: away,
  home_score: 112,
  away_score: 106,
};
const meta = {
  current_season: "2025-26",
  seasons: ["2025-26", "2024-25", "1995-96"],
  supported_from: "1996-97",
};
const line = {
  player_id: 7,
  player_name: "Jayson Tatum",
  team_id: 2,
  team: home,
  starter: 1,
  min: "36:11",
  pts: 28,
  reb: 9,
  ast: 5,
  stl: 1,
  blk: 0,
  tov: 3,
  fgm: 9,
  fga: 18,
  fg3m: 4,
  fg3a: 9,
  ftm: 6,
  fta: 7,
  oreb: 1,
  dreb: 8,
  pf: 2,
  plus_minus: 11,
};
const box = {
  game_id: game.game_id,
  teams: [
    { team: away, pts: 106 },
    { team: home, pts: 112 },
  ],
  players: [line],
};
const analysis = {
  game_id: game.game_id,
  player: line,
  stats: line,
  shots: [{ x: 10, y: 80, made: true, description: "Jump Shot", period: 1, distance: 12 }],
  shot_chart_state: "available",
};

function mount(path = "/", responder?: (url: string) => unknown) {
  const fetch = vi.fn().mockImplementation(async (input: RequestInfo | URL) => {
    const url = String(input);
    const payload = responder ? responder(url) : defaultPayload(url);
    if (payload instanceof Error) throw payload;
    return { ok: true, status: 200, json: async () => payload };
  });
  vi.stubGlobal("fetch", fetch);
  const result = render(
    <MemoryRouter initialEntries={[path]}>
      <MetaProvider>
        <AppRoutes />
      </MetaProvider>
    </MemoryRouter>,
  );
  return { ...result, fetch };
}

function defaultPayload(url: string): unknown {
  if (url === "/api/meta") return meta;
  if (url === "/api/upcoming") return { days: ["2025-11-02", "2025-11-03"], games: [] };
  if (url.startsWith("/api/games?"))
    return {
      season: "2025-26",
      supported: true,
      games: [game],
      phases: ["Pre Season", "Regular Season", "Playoffs"],
    };
  if (url === `/api/games/${game.game_id}`) return box;
  if (url.startsWith(`/api/games/${game.game_id}/players/`)) return analysis;
  throw new Error(`Unexpected API path: ${url}`);
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("NBA Terminal screens", () => {
  it("loads the dashboard, filters the season, then opens a game and player analysis", async () => {
    const user = userEvent.setup();
    const { fetch } = mount();
    expect(
      await screen.findByRole("heading", { name: "Every game, in focus." }),
    ).toBeInTheDocument();
    expect(
      await screen.findByText("No games scheduled in this two-day window"),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "2025-26 season" })).toBeInTheDocument();
    expect(screen.getByText("Boston Celtics")).toBeInTheDocument();

    await user.selectOptions(screen.getByRole("combobox", { name: "Season" }), "2024-25");
    await waitFor(() => expect(fetch).toHaveBeenCalledWith("/api/games?season=2024-25"));
    await screen.findByRole("heading", { name: "2024-25 season" });

    await user.click(
      screen.getByRole("link", { name: /Open Cleveland Cavaliers at Boston Celtics/ }),
    );
    expect(
      await screen.findByRole("heading", { name: "Cleveland Cavaliers at Boston Celtics" }),
    ).toBeInTheDocument();
    const table = screen.getByRole("table");
    expect(within(table).getByRole("link", { name: "Jayson Tatum" })).toBeInTheDocument();
    await user.click(within(table).getByRole("link", { name: "Jayson Tatum" }));
    expect(await screen.findByRole("heading", { name: "Jayson Tatum" })).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: "NBA shot locations plotted on a half-court" }),
    ).toBeInTheDocument();
    expect(document.querySelectorAll(".shot.made")).toHaveLength(1);
  });

  it("shows upcoming matchups, empty history, and the unsupported-history state", async () => {
    const user = userEvent.setup();
    mount("/?season=1995-96", (url) => {
      if (url === "/api/meta") return meta;
      if (url === "/api/upcoming")
        return {
          days: ["2025-11-02", "2025-11-03"],
          games: [
            {
              ...game,
              game_id: "scheduled",
              status: "Scheduled",
              start_time: "7:00 PM ET",
              phase: "Pre Season",
            },
          ],
        };
      return url.endsWith("1995-96")
        ? { season: "1995-96", supported: false, games: [], phases: [] }
        : { season: "2024-25", supported: true, games: [], phases: [] };
    });
    expect(await screen.findByText("Cleveland Cavaliers")).toBeInTheDocument();
    expect(screen.getByText(/Scheduled · 7:00 PM ET/)).toBeInTheDocument();
    expect(screen.getByText("History is not available in this view")).toBeInTheDocument();
    await user.selectOptions(screen.getByRole("combobox", { name: "Season" }), "2024-25");
    expect(await screen.findByText("No completed games returned")).toBeInTheDocument();
  });

  it("keeps schedule and game-feed errors separate, with a retry action", async () => {
    const user = userEvent.setup();
    let gameCalls = 0;
    mount("/", (url) => {
      if (url === "/api/meta") return meta;
      if (url === "/api/upcoming") throw new Error("schedule down");
      if (url.startsWith("/api/games?")) {
        gameCalls += 1;
        if (gameCalls === 1) throw new Error("history down");
        return { season: "2025-26", supported: true, games: [], phases: [] };
      }
      return defaultPayload(url);
    });
    expect(await screen.findByText("Schedule unavailable")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("history down");
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("No completed games returned")).toBeInTheDocument();
  });

  it("shows loading and a clear application-level metadata failure", async () => {
    let release: (value: unknown) => void = () => undefined;
    const promise = new Promise((resolve) => {
      release = resolve;
    });
    mount("/", (url) => (url === "/api/meta" ? promise : defaultPayload(url)));
    expect(screen.getByRole("status")).toHaveTextContent("Preparing the current season view");
    release(meta);
    expect(
      await screen.findByRole("heading", { name: "Every game, in focus." }),
    ).toBeInTheDocument();
    cleanup();
    mount("/", (url) => (url === "/api/meta" ? new Error("metadata down") : defaultPayload(url)));
    expect(await screen.findByRole("alert")).toHaveTextContent("metadata down");
  });

  it("handles box-score failures, empty player rows, player failures, and unavailable charts", async () => {
    const user = userEvent.setup();
    mount(`/game/${game.game_id}?season=2025-26`, (url) => {
      if (url === "/api/meta") return meta;
      if (url === `/api/games/${game.game_id}`) return { ...box, players: [], teams: [] };
      return defaultPayload(url);
    });
    expect(await screen.findByText("Box score not available")).toBeInTheDocument();

    cleanup();
    mount(`/game/${game.game_id}/player/7?season=2025-26`, (url) => {
      if (url === "/api/meta") return meta;
      if (url.startsWith(`/api/games/${game.game_id}/players/`))
        return { ...analysis, shots: [], shot_chart_state: "unavailable" };
      return defaultPayload(url);
    });
    expect(await screen.findByText("Shot chart unavailable")).toBeInTheDocument();
    expect(screen.getByText(/No locations are estimated/)).toBeInTheDocument();

    cleanup();
    mount(`/game/${game.game_id}/player/7?season=2025-26`, (url) => {
      if (url === "/api/meta") return meta;
      if (url.startsWith(`/api/games/${game.game_id}/players/`)) throw new Error("analysis down");
      return defaultPayload(url);
    });
    expect(await screen.findByRole("alert")).toHaveTextContent("analysis down");
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("analysis down");
  });

  it("shows a chart-service failure distinctly and renders unknown routes", async () => {
    mount(`/game/${game.game_id}/player/7?season=2025-26`, (url) => {
      if (url === "/api/meta") return meta;
      if (url.startsWith(`/api/games/${game.game_id}/players/`))
        return { ...analysis, shots: [], shot_chart_state: "error" };
      return defaultPayload(url);
    });
    expect(await screen.findByText("Shot chart could not be loaded")).toBeInTheDocument();
    cleanup();
    mount("/unknown");
    expect(await screen.findByRole("heading", { name: "Page not found" })).toBeInTheDocument();
  });
});
