import { expect, test } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import type { ToolResult } from "../src/analytics-tools-api";
const base: ToolResult = {
  state: "ready",
  errors: [],
  fetched_at: "2026-11-01T12:00:00Z",
  resources: { logs: { state: "ready", fetched_at: "2026-11-01T11:55:00Z" } },
};
const fixtures: Record<string, ToolResult> = {
  predictor: {
    ...base,
    projection: 27.2,
    baseline: 25,
    season_avg: 24,
    last_5: 28,
    last_10: 22,
    valid_games: 20,
    avg_minutes: 30,
    minute_factor: 1.067,
    minutes_adjustment: 1.67,
    defense_adjustment: 0.4,
    pace_adjustment: 0.13,
    rest_adjustment: -0.4,
    home_adjustment: 0.35,
    context: {
      rest_days: 1,
      is_home: true,
      def_rating: 114,
      league_def_rating: 110,
      pace: 102,
      league_pace: 100,
    },
    context_sources: {
      rest_days: "NBA returned sample",
      is_home: "NBA schedule",
      def_rating: "NBA returned sample",
      league_def_rating: "NBA returned sample",
      pace: "NBA returned sample",
      league_pace: "NBA returned sample",
    },
  },
  consistency: {
    ...base,
    roster_players: 15,
    ranked_players: 3,
    excluded: { insufficient_games: 8, missing_stat: 1, zero_mean_or_sd: 3 },
    rows: [
      {
        player_id: 1,
        rank: 1,
        player: "Fixture Player A",
        cv: 0.22,
        mean: 25,
        sd: 5.5,
        valid_games: 10,
        window: 10,
        tier: "Elite",
        color: "success",
      },
      {
        player_id: 2,
        rank: 2,
        player: "Fixture Player B",
        cv: 0.51,
        mean: 18,
        sd: 9.18,
        valid_games: 8,
        window: 10,
        tier: "Average",
        color: "warning",
      },
      {
        player_id: 3,
        rank: 3,
        player: "Fixture Player C",
        cv: 0.75,
        mean: 8,
        sd: 6,
        valid_games: 10,
        window: 10,
        tier: "Variable",
        color: "danger",
      },
    ],
  },
  defense: {
    ...base,
    state: "partial",
    errors: ["zones unavailable (Timeout); retry shortly."],
    league_means: { OPP_FG_PCT: 0.46, OPP_FG3_PCT: 0.35, "Restricted Area": null },
    league_counts: { OPP_FG_PCT: 30, OPP_FG3_PCT: 30, "Restricted Area": 0 },
    rows: [
      {
        team_id: 1,
        rank: 1,
        team: "ATL",
        tier: "Elite",
        OPP_FG_PCT: 0.44,
        OPP_FG3_PCT: 0.34,
        color: "success",
      },
      {
        team_id: 2,
        rank: 2,
        team: "BOS",
        tier: "Elite",
        OPP_FG_PCT: 0.45,
        OPP_FG3_PCT: 0.35,
        color: "success",
      },
    ],
  },
  slate: {
    ...base,
    qualified_players: 10,
    evaluated_players: 8,
    missing_players: 1,
    insufficient_players: 1,
    state: "partial",
    games: [
      {
        game_id: "0022600001",
        home_team: { abbreviation: "ATL" },
        away_team: { abbreviation: "BOS" },
        status: "7:00 pm ET",
      },
    ],
    rows: [
      {
        player_id: 1,
        player: "Fixture Player A",
        team: "ATL",
        opponent: "BOS",
        direction: "Above season",
        season_avg: 20,
        last_5: 27,
        last_10: 24,
        projection: 25.2,
        difference: 5.2,
        minutes: 32,
        recent_valid_games: 5,
      },
    ],
  },
  picks: {
    ...base,
    files: [
      {
        filename: "10_31_2026.MD",
        preview: "Historical fixture note — search and inspect read-only Markdown.",
      },
    ],
  },
  catalog: {
    ...base,
    version: "fixture",
    endpoints: [
      {
        name: "PlayerGameLogs",
        category: "Game Logs & Finders",
        parameters: { season_nullable: "", season_type_nullable: "", timeout: "30" },
        datasets: { PlayerGameLogs: ["PLAYER_ID", "GAME_DATE", "PTS", "MIN"] },
      },
    ],
  },
};
test("all six standalone tools are usable, compact and accessible", async ({ page }, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.route("**/api/tools/**", async (route) => {
    const url = new URL(route.request().url());
    const tool = url.pathname.split("/").at(-1) ?? "";
    const data =
      tool === "meta"
        ? {
            today: "2026-11-01",
            season: "2026-27",
            teams: [
              { id: 1610612737, abbreviation: "ATL", full_name: "Atlanta Hawks" },
              { id: 1610612738, abbreviation: "BOS", full_name: "Boston Celtics" },
            ],
            players: [{ id: 30, full_name: "Fixture Player" }],
          }
        : tool === "picks" && url.searchParams.has("filename")
          ? {
              ...base,
              filename: "10_31_2026.MD",
              content: "# Historical fixture\n<script>must remain text</script>",
            }
          : fixtures[tool];
    await route.fulfill({ json: data });
  });
  await page.goto("/e2e/analytics-tools.html");
  await page.getByRole("combobox", { name: "Player", exact: true }).selectOption("30");
  const evidence = "../../code_review/v5_app/generated/legacy-harness";
  await mkdir(evidence, { recursive: true });
  for (const [tool, title] of [
    ["predictor", "Points Predictor"],
    ["consistency", "Team Consistency"],
    ["defense", "Team Defense"],
    ["slate", "Slate Scanner"],
    ["picks", "Picks Archive"],
    ["catalog", "Stats / API Reference"],
  ]) {
    await page.getByRole("button", { name: title, exact: true }).click();
    await page
      .getByRole("button", {
        name: tool === "picks" || tool === "catalog" ? "Search / browse" : "Run analysis",
        exact: true,
      })
      .click();
    await expect(page.getByRole("region", { name: "Analysis result" })).toBeVisible();
    if (tool === "predictor") await expect(page.getByText("27.2 estimated points")).toBeVisible();
    if (tool === "defense") await expect(page.getByText("Unknown").first()).toBeVisible();
    if (tool === "catalog") {
      await page.getByText("PlayerGameLogs · Game Logs & Finders", { exact: true }).click();
      await expect(page.getByText("season_nullable", { exact: true })).toBeVisible();
    }
    await expect(page.locator("body")).toHaveJSProperty(
      "scrollWidth",
      await page.evaluate(() => document.documentElement.clientWidth),
    );
    await page.screenshot({
      path: `${evidence}/${testInfo.project.name}-${tool}.png`,
      fullPage: true,
    });
  }
  await page.getByRole("button", { name: "Picks Archive", exact: true }).click();
  await page.getByRole("button", { name: "Search / browse" }).click();
  await page.getByRole("button", { name: "10_31_2026.MD" }).click();
  await expect(page.locator("pre.at-note")).toContainText("<script>must remain text</script>");
  expect(errors).toEqual([]);
});
