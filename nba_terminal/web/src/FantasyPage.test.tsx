import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AppRoutes, MetaProvider } from "./App";

const meta = {
  current_season: "2025-26",
  seasons: ["2025-26", "2024-25", "1995-96"],
  supported_from: "1996-97",
};

const players = [
  {
    player_id: 1,
    player_name: "Jayson Tatum",
    team_id: 2,
    team_abbreviation: "BOS",
    team_name: "Boston Celtics",
    games: 10,
    minutes_total: 360,
    points: 300,
    rebounds: 100,
    assists: 60,
    steals: 15,
    blocks: 10,
    turnovers: 25,
    threes_made: 40,
    three_attempts: 100,
    field_goals_made: 100,
    field_goal_attempts: 200,
    free_throws_made: 60,
    free_throw_attempts: 70,
  },
  {
    player_id: 2,
    player_name: "Luka Doncic",
    team_id: 3,
    team_abbreviation: "DAL",
    team_name: "Dallas Mavericks",
    games: 10,
    minutes_total: 340,
    points: 280,
    rebounds: 90,
    assists: 100,
    steals: 10,
    blocks: 5,
    turnovers: 45,
    threes_made: 30,
    three_attempts: 100,
    field_goals_made: 95,
    field_goal_attempts: 190,
    free_throws_made: 50,
    free_throw_attempts: 60,
  },
  {
    player_id: 3,
    player_name: "Rookie Sample",
    team_id: 4,
    team_abbreviation: "SEA",
    team_name: "Seattle Team",
    games: 10,
    minutes_total: 150,
    points: 120,
    rebounds: 50,
    assists: 30,
    steals: 5,
    blocks: 3,
    turnovers: 10,
    threes_made: 5,
    three_attempts: 15,
    field_goals_made: 40,
    field_goal_attempts: 100,
    free_throws_made: 30,
    free_throw_attempts: 35,
  },
];

function mount(path = "/fantasy", payload = players) {
  const fetch = vi.fn().mockImplementation(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url === "/api/meta") return response(meta);
    if (url === "/api/upcoming") return response({ days: [], games: [] });
    if (url.startsWith("/api/games?"))
      return response({ season: "2025-26", supported: true, games: [], phases: [] });
    if (url.startsWith("/api/fantasy/players?")) {
      const season = new URL(url, "http://test").searchParams.get("season") || "2025-26";
      return response({ season, supported: true, phase: "Regular Season", players: payload });
    }
    throw new Error(`Unexpected API path: ${url}`);
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

function response(value: unknown) {
  return { ok: true, status: 200, json: async () => value };
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  window.localStorage.clear();
});

describe("Fantasy workspace", () => {
  it("opens from the navigation, loads a season and supports sortable searchable category views", async () => {
    const user = userEvent.setup();
    const { fetch } = mount("/");
    await screen.findByRole("heading", { name: "Every game, in focus." });
    await user.click(screen.getByRole("link", { name: "✳ Fantasy" }));

    expect(
      await screen.findByRole("heading", { name: "Find your next edge." }),
    ).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith("/api/fantasy/players?season=2025-26");
    const table = screen.getByRole("table", { name: "" });
    expect(within(table).getAllByRole("row")[1]).toHaveTextContent("Jayson Tatum");
    expect(within(table).getAllByRole("row")[1]).toHaveTextContent("30");

    await user.click(screen.getByRole("tab", { name: "FG%" }));
    expect(screen.getByText("Field-goal percentage", { selector: "strong" })).toBeInTheDocument();
    await user.type(screen.getByRole("spinbutton", { name: "Minimum field-goal attempts" }), "150");
    expect(screen.queryByText("Rookie Sample")).not.toBeInTheDocument();
    expect(screen.getByText("2 players")).toBeInTheDocument();

    await user.type(screen.getByRole("searchbox", { name: "Search players or teams" }), "luka");
    expect(screen.getByText("Luka Doncic")).toBeInTheDocument();
    expect(within(table).queryByText("Jayson Tatum")).not.toBeInTheDocument();
    expect(screen.getByText("50.0%", { selector: ".fantasy-value" })).toBeInTheDocument();
  });

  it("switches seasons, stat view and customizable points weights", async () => {
    const user = userEvent.setup();
    const { fetch } = mount();
    await screen.findByRole("button", { name: "Add Jayson Tatum to comparison" });
    await user.selectOptions(screen.getByRole("combobox", { name: "Fantasy season" }), "2024-25");
    await waitFor(() => expect(fetch).toHaveBeenCalledWith("/api/fantasy/players?season=2024-25"));

    await user.click(screen.getByRole("button", { name: "Season totals" }));
    expect(screen.getByText("300", { selector: ".fantasy-value" })).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Points scoring" }));
    expect(screen.getByText("532.5", { selector: ".fantasy-value" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Scoring weights/ }));
    const pointsWeight = screen.getByRole("spinbutton", { name: "PTS scoring weight" });
    await user.clear(pointsWeight);
    await user.type(pointsWeight, "2");
    expect(screen.getByText("832.5", { selector: ".fantasy-value" })).toBeInTheDocument();
    expect(window.localStorage.getItem("nba-terminal.fantasy.preferences.v1")).toContain(
      '"points":2',
    );

    cleanup();
    mount();
    await screen.findByRole("button", { name: "Add Jayson Tatum to comparison" });
    expect(screen.getByRole("button", { name: "Season totals" })).toHaveClass("selected");
    await user.click(screen.getByRole("button", { name: /Scoring weights/ }));
    expect(screen.getByRole("spinbutton", { name: "PTS scoring weight" })).toHaveValue(2);
    const fieldGoalWeight = screen.getByRole("spinbutton", { name: "FG% scoring weight" });
    await user.clear(fieldGoalWeight);
    await user.type(fieldGoalWeight, "1");
    const weightedAttemptLimit = screen.getByRole("spinbutton", {
      name: "Minimum attempts for weighted percentage scoring",
    });
    await user.clear(weightedAttemptLimit);
    await user.type(weightedAttemptLimit, "200");
    const pointsTable = screen.getByRole("table");
    expect(within(pointsTable).getByText("Jayson Tatum")).toBeInTheDocument();
    expect(within(pointsTable).queryByText("Luka Doncic")).not.toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "TO" }));
    const rows = within(screen.getByRole("table")).getAllByRole("row");
    expect(rows[1]).toHaveTextContent("Rookie Sample");
    expect(rows[1]).toHaveTextContent("10");
  });

  it("compares selected players, explains rank context and retains the local shortlist", async () => {
    const user = userEvent.setup();
    mount();
    await screen.findByRole("button", { name: "Add Jayson Tatum to comparison" });
    await user.click(screen.getByRole("button", { name: "Add Jayson Tatum to comparison" }));
    await user.click(screen.getByRole("button", { name: "Add Jayson Tatum to shortlist" }));
    await user.click(screen.getByRole("button", { name: "Add Luka Doncic to comparison" }));

    expect(await screen.findByRole("heading", { name: "Compare players" })).toBeInTheDocument();
    expect(
      screen.getByText(/Strength and gap compare current season category ranks/),
    ).toBeInTheDocument();
    const comparisonTable = screen.getAllByRole("table").at(-1)!;
    expect(within(comparisonTable).getByText("Jayson Tatum")).toBeInTheDocument();
    expect(within(comparisonTable).getByText("Luka Doncic")).toBeInTheDocument();
    expect(screen.getByText("1 saved")).toBeInTheDocument();
    expect(window.localStorage.getItem("nba-terminal.fantasy.preferences.v1")).toContain(
      '"shortlist":[1]',
    );
    await user.click(screen.getByRole("button", { name: "Remove Jayson Tatum from shortlist" }));
    expect(screen.getByText("0 saved")).toBeInTheDocument();
    expect(window.localStorage.getItem("nba-terminal.fantasy.preferences.v1")).toContain(
      '"shortlist":[]',
    );
  });

  it("distinguishes a current season with no stats from a fetch error and retries", async () => {
    const user = userEvent.setup();
    mount("/fantasy", []);
    expect(
      await screen.findByText("2025-26 season stats are not available yet"),
    ).toBeInTheDocument();

    cleanup();
    let requests = 0;
    const fetch = vi.fn().mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/meta") return response(meta);
      if (url.startsWith("/api/fantasy/players?")) {
        requests += 1;
        if (requests === 1)
          return {
            ok: false,
            status: 502,
            json: async () => ({ detail: "Stats source offline." }),
          };
        return response({ season: "2025-26", supported: true, phase: "Regular Season", players });
      }
      throw new Error(`Unexpected API path: ${url}`);
    });
    vi.stubGlobal("fetch", fetch);
    render(
      <MemoryRouter initialEntries={["/fantasy"]}>
        <MetaProvider>
          <AppRoutes />
        </MetaProvider>
      </MemoryRouter>,
    );
    expect(await screen.findByRole("alert")).toHaveTextContent("Stats source offline.");
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(
      await screen.findByRole("button", { name: "Add Jayson Tatum to comparison" }),
    ).toBeInTheDocument();
  });
});
