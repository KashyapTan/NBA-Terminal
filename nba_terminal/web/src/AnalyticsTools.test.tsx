import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AnalyticsTools } from "./AnalyticsTools";
import { getAnalyticsTool, getToolsMeta, type ToolResult } from "./analytics-tools-api";
vi.mock("./analytics-tools-api", () => ({ getToolsMeta: vi.fn(), getAnalyticsTool: vi.fn() }));
const base: ToolResult = {
  state: "ready",
  errors: [],
  fetched_at: "2026-11-01T12:00:00Z",
  resources: {},
};
const meta = {
  season: "2026-27",
  today: "2026-11-01",
  teams: [
    { id: 1, abbreviation: "ATL", full_name: "Atlanta Hawks" },
    { id: 2, abbreviation: "BOS", full_name: "Boston Celtics" },
  ],
  players: [{ id: 30, full_name: "Stephen Curry" }],
};
afterEach(cleanup);
beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(getToolsMeta).mockResolvedValue(meta);
});
async function run() {
  const button = screen.getByRole("button", { name: "Run analysis" });
  await waitFor(() => expect(button).toBeEnabled());
  fireEvent.click(button);
}
describe("standalone tools", () => {
  it("submits selected predictor context and discloses partial estimates", async () => {
    vi.mocked(getAnalyticsTool).mockResolvedValue({
      ...base,
      state: "partial",
      projection: null,
      baseline: 20,
      valid_games: 4,
      last_5_fallback: true,
      last_10_fallback: true,
      missing_context: ["pace"],
      context: { pace: null, rest_days: 3 },
      context_sources: { rest_days: "User estimate override" },
    });
    render(<AnalyticsTools />);
    await screen.findByRole("option", { name: "Stephen Curry" });
    fireEvent.change(screen.getByLabelText("Player", { exact: true }), { target: { value: "30" } });
    fireEvent.change(screen.getByLabelText("Rest off-days (0–5)"), { target: { value: "3" } });
    await run();
    expect(await screen.findByText("Projection incomplete")).toBeInTheDocument();
    expect(screen.getByText("User estimate override")).toBeInTheDocument();
    expect(screen.getByText(/Missing context: Opponent pace/)).toBeInTheDocument();
    expect(getAnalyticsTool).toHaveBeenCalledWith(
      "predictor",
      expect.objectContaining({
        player_id: "30",
        season: "2026-27",
        day: "2026-11-01",
        rest_days: "3",
      }),
    );
    expect(screen.getByText(/L5 falls back/)).toBeInTheDocument();
  });
  it("ranks CV with valid count and meaningful exclusions", async () => {
    vi.mocked(getAnalyticsTool).mockResolvedValue({
      ...base,
      roster_players: 12,
      ranked_players: 1,
      excluded: { zero_mean_or_sd: 2 },
      rows: [
        {
          player_id: 1,
          rank: 1,
          player: "A",
          cv: 0.2,
          mean: 20,
          sd: 4,
          valid_games: 4,
          window: 5,
          tier: "Elite",
        },
      ],
    });
    render(<AnalyticsTools initialTool="consistency" />);
    fireEvent.change(screen.getByLabelText("Game window"), { target: { value: "5" } });
    await run();
    expect(await screen.findByText("20.0%")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Valid games" })).toBeInTheDocument();
    expect(screen.getByText(/zero mean or sd: 2/)).toBeInTheDocument();
    expect(getAnalyticsTool).toHaveBeenCalledWith(
      "consistency",
      expect.objectContaining({ window: "5", stat: "PTS" }),
    );
  });
  it("renders defense missing zones as unknown and league sample counts", async () => {
    vi.mocked(getAnalyticsTool).mockResolvedValue({
      ...base,
      state: "partial",
      rows: [{ team_id: 1, team: "ATL", OPP_FG_PCT: 0.45, "Corner 3": null }],
      league_means: { "Corner 3": null },
      league_counts: { "Corner 3": 0 },
      errors: ["zones unavailable"],
    });
    render(<AnalyticsTools initialTool="defense" />);
    await run();
    expect(await screen.findByText(/Partial data/)).toBeInTheDocument();
    expect(screen.getAllByText("Unknown").length).toBeGreaterThan(0);
    expect(screen.getByText("zones unavailable")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Available teams" })).toBeInTheDocument();
  });
  it("distinguishes evaluated no-threshold slate from source errors", async () => {
    vi.mocked(getAnalyticsTool).mockResolvedValue({
      ...base,
      rows: [],
      games: [],
      qualified_players: 3,
      evaluated_players: 3,
      missing_players: 0,
      insufficient_players: 0,
    });
    render(<AnalyticsTools initialTool="slate" />);
    await run();
    expect(await screen.findByText(/No evaluated players met/)).toBeInTheDocument();
    expect(screen.getByText(/3 qualified · 3 evaluated/)).toBeInTheDocument();
    vi.mocked(getAnalyticsTool).mockRejectedValueOnce(new Error("Upstream unavailable"));
    await run();
    expect(await screen.findByRole("alert")).toHaveTextContent("Upstream unavailable");
    expect(screen.queryByText(/No evaluated players met/)).not.toBeInTheDocument();
  });
  it("searches and opens read-only notes as text", async () => {
    vi.mocked(getAnalyticsTool)
      .mockResolvedValueOnce({ ...base, files: [{ filename: "10_31_2026.MD", preview: "Curry" }] })
      .mockResolvedValueOnce({
        ...base,
        filename: "10_31_2026.MD",
        content: "<script>bad()</script>\n# Curry",
      });
    const { container } = render(<AnalyticsTools initialTool="picks" />);
    fireEvent.change(screen.getByLabelText("Search notes"), { target: { value: "Curry" } });
    fireEvent.click(screen.getByRole("button", { name: "Search / browse" }));
    fireEvent.click(await screen.findByRole("button", { name: "10_31_2026.MD" }));
    expect(await screen.findByText(/<script>bad/)).toBeInTheDocument();
    expect(container.querySelector("script")).toBeNull();
    expect(getAnalyticsTool).toHaveBeenLastCalledWith("picks", {
      q: "Curry",
      filename: "10_31_2026.MD",
    });
    expect(screen.queryByRole("button", { name: /save/i })).not.toBeInTheDocument();
  });
  it("shows catalog parameters, installed schema and no execution", async () => {
    vi.mocked(getAnalyticsTool).mockResolvedValue({
      ...base,
      version: "1.11",
      endpoints: [
        {
          name: "PlayerGameLogs",
          category: "Game Logs",
          parameters: { season_nullable: "" },
          datasets: { PlayerGameLogs: ["PLAYER_ID", "PTS"] },
        },
      ],
    });
    render(<AnalyticsTools initialTool="catalog" />);
    fireEvent.change(screen.getByLabelText("Search endpoints / parameters / schema"), {
      target: { value: "PTS" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Search / browse" }));
    expect(await screen.findByText(/Installed nba_api 1.11/)).toBeInTheDocument();
    expect(screen.getByText("season_nullable")).toBeInTheDocument();
    expect(screen.getByText(/PLAYER_ID/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /execute/i })).not.toBeInTheDocument();
  });
  it("discards stale requests when switching tools", async () => {
    let resolve: (value: ToolResult) => void = () => {};
    vi.mocked(getAnalyticsTool).mockReturnValue(
      new Promise((r) => {
        resolve = r;
      }),
    );
    render(<AnalyticsTools initialTool="defense" />);
    await run();
    fireEvent.click(screen.getByRole("button", { name: "Picks Archive" }));
    resolve({ ...base, rows: [{ team: "STALE" }] });
    await waitFor(() => expect(screen.queryByRole("status")).not.toBeInTheDocument());
    expect(screen.queryByText("STALE")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Picks Archive" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });
  it("allows offline tools even if setup fails", async () => {
    vi.mocked(getToolsMeta).mockRejectedValueOnce(new Error("Setup failed"));
    vi.mocked(getAnalyticsTool).mockResolvedValue({ ...base, files: [] });
    render(<AnalyticsTools />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Setup failed");
    fireEvent.click(screen.getByRole("button", { name: "Picks Archive" }));
    fireEvent.click(screen.getByRole("button", { name: "Search / browse" }));
    expect(await screen.findByText("0 matching files")).toBeInTheDocument();
  });
});

it("uses an explicit away/zero-rest estimate and preserves submitted selection context", async () => {
  vi.mocked(getAnalyticsTool).mockResolvedValue({
    ...base,
    projection: 25.5,
    baseline: 24,
    minutes_estimated: true,
    context: { is_home: false, rest_days: 0 },
    context_sources: { is_home: "User estimate override", rest_days: "User estimate override" },
  });
  render(<AnalyticsTools />);
  await screen.findByRole("option", { name: "Stephen Curry" });
  fireEvent.change(screen.getByLabelText("Find player"), { target: { value: "Curry" } });
  fireEvent.change(screen.getByLabelText("Player", { exact: true }), { target: { value: "30" } });
  fireEvent.change(screen.getByLabelText("Season"), { target: { value: "2025-26" } });
  fireEvent.change(screen.getByLabelText("Phase"), { target: { value: "Playoffs" } });
  fireEvent.change(screen.getByLabelText("Game date (NBA Eastern)"), {
    target: { value: "2026-04-20" },
  });
  fireEvent.change(screen.getByLabelText("Projected minutes (estimate)"), {
    target: { value: "36" },
  });
  fireEvent.change(screen.getByLabelText("Rest off-days (0–5)"), { target: { value: "0" } });
  fireEvent.change(screen.getByLabelText("Home game"), { target: { value: "false" } });
  await run();
  expect(await screen.findByText("25.5 estimated points")).toBeInTheDocument();
  expect(screen.getByText(/Stephen Curry vs BOS · 36 projected MIN/)).toBeInTheDocument();
  expect(screen.getByText(/minutes factor estimated as 1/)).toBeInTheDocument();
  expect(getAnalyticsTool).toHaveBeenCalledWith(
    "predictor",
    expect.objectContaining({
      season: "2025-26",
      phase: "Playoffs",
      day: "2026-04-20",
      minutes: "36",
      is_home: "false",
      rest_days: "0",
    }),
  );
  fireEvent.change(screen.getByLabelText("Projected minutes (estimate)"), {
    target: { value: "40" },
  });
  expect(screen.getByText(/36 projected MIN/)).toBeInTheDocument();
});

it("keeps zero evaluated samples distinct from an evaluated no-trend result", async () => {
  vi.mocked(getAnalyticsTool).mockResolvedValue({
    ...base,
    state: "partial",
    rows: [],
    qualified_players: 3,
    evaluated_players: 0,
    missing_players: 3,
    insufficient_players: 0,
    errors: ["logs unavailable"],
  });
  render(<AnalyticsTools initialTool="slate" />);
  await run();
  expect(
    await screen.findByText("No qualifying player samples could be evaluated."),
  ).toBeInTheDocument();
  expect(screen.queryByText(/No evaluated players met/)).not.toBeInTheDocument();
  expect(screen.getByText(/3 missing player samples/)).toBeInTheDocument();
});

it("returns from a text note to the same searched file list", async () => {
  vi.mocked(getAnalyticsTool)
    .mockResolvedValueOnce({ ...base, files: [{ filename: "10_31_2026.MD", preview: "Curry" }] })
    .mockResolvedValueOnce({ ...base, filename: "10_31_2026.MD", content: "# Curry" })
    .mockResolvedValueOnce({ ...base, files: [] });
  render(<AnalyticsTools initialTool="picks" />);
  fireEvent.change(screen.getByLabelText("Search notes"), { target: { value: "Curry" } });
  fireEvent.click(screen.getByRole("button", { name: "Search / browse" }));
  fireEvent.click(await screen.findByRole("button", { name: "10_31_2026.MD" }));
  fireEvent.click(await screen.findByRole("button", { name: "Back to matching files" }));
  expect(await screen.findByText("0 matching files")).toBeInTheDocument();
  expect(getAnalyticsTool).toHaveBeenLastCalledWith("picks", { q: "Curry" });
});
