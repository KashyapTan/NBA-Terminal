import { expect, test, type Page } from "@playwright/test";

const away = { id: 1, abbreviation: "CLE", name: "Cleveland Cavaliers", nickname: "Cavaliers" };
const home = { id: 2, abbreviation: "BOS", name: "Boston Celtics", nickname: "Celtics" };
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
const upcomingGame = {
  ...game,
  game_id: "0012500001",
  status: "Scheduled",
  start_time: "7:30 PM ET",
  phase: "Pre Season",
  home_score: null,
  away_score: null,
};
const player = {
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
const historyGame = {
  game_id: game.game_id,
  game_date: game.date,
  matchup: "BOS vs. CLE",
  wl: "W",
  min: 36.2,
  pts: 28,
  reb: 9,
  ast: 5,
  stl: 1,
  blk: 0,
  tov: 3,
  fgm: 9,
  fga: 18,
  fg_pct: 0.5,
  fg3m: 4,
  fg3a: 9,
  fg3_pct: 0.444,
  ft_pct: 0.857,
  pra: 42,
  plus_minus: 11,
  ts_pct: 0.67,
};
const ptsConsistency = { mean: 21, std: 6.56, consistency_cv: 0.312, games: 3 };

async function mockLeagueApi(page: Page, feedError = false, unavailableChart = false) {
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/meta")
      return route.fulfill({
        json: {
          current_season: "2025-26",
          seasons: ["2025-26", "2024-25"],
          supported_from: "1996-97",
        },
      });
    if (path === "/api/upcoming")
      return route.fulfill({ json: { days: ["2025-11-02", "2025-11-03"], games: [upcomingGame] } });
    if (path === "/api/games") {
      if (feedError)
        return route.fulfill({ status: 502, json: { detail: "Mock NBA service error" } });
      return route.fulfill({
        json: {
          season: "2025-26",
          supported: true,
          games: [game],
          phases: ["Pre Season", "Regular Season", "Playoffs"],
        },
      });
    }
    if (path === `/api/games/${game.game_id}`)
      return route.fulfill({
        json: {
          game_id: game.game_id,
          away_team: away,
          home_team: home,
          teams: [
            { team: away, pts: 106 },
            { team: home, pts: 112 },
          ],
          players: [player],
        },
      });
    if (path.startsWith(`/api/games/${game.game_id}/players/`))
      return route.fulfill({
        json: {
          game_id: game.game_id,
          player,
          stats: player,
          shots: unavailableChart
            ? []
            : [
                {
                  x: 10,
                  y: 80,
                  made: true,
                  description: "Jump Shot",
                  shot_type: "3PT Field Goal",
                  period: 1,
                  distance: 12,
                },
                {
                  x: -30,
                  y: 110,
                  made: false,
                  description: "Layup Shot",
                  shot_type: "2PT Field Goal",
                  period: 2,
                  distance: 8,
                },
              ],
          shot_chart_state: unavailableChart ? "unavailable" : "available",
          advanced_stats: {
            off_rating: 119.2,
            def_rating: 108.4,
            net_rating: 10.8,
            ts_pct: 0.64,
            efg_pct: 0.61,
          },
          advanced_stats_state: "available",
          advanced_stats_note: "",
          history: {
            state: "available",
            note: "",
            season: "2025-26",
            phase: "Regular Season",
            opponent: "CLE",
            games_played: 3,
            opponent_games_played: 2,
            summary: {
              PTS: {
                label: "PTS",
                ...ptsConsistency,
                last_5: 21,
                last_5_games: 3,
                last_10: 21,
                last_10_games: 3,
                last_20: 21,
                last_20_games: 3,
              },
            },
            games: [
              historyGame,
              {
                ...historyGame,
                game_id: "0022400002",
                game_date: "2025-10-30",
                pts: 20,
                reb: 6,
                ast: 4,
              },
              {
                ...historyGame,
                game_id: "0022400003",
                game_date: "2025-10-28",
                matchup: "BOS vs. NYK",
                pts: 15,
                reb: 4,
                ast: 6,
              },
            ],
            opponent_games: [
              historyGame,
              {
                ...historyGame,
                game_id: "0022400002",
                game_date: "2025-10-30",
                pts: 20,
                reb: 6,
                ast: 4,
              },
            ],
          },
          history_state: "available",
          game_context: {
            game_id: game.game_id,
            team: home,
            opponent: away,
            team_score: 112,
            opponent_score: 106,
            season: "2025-26",
            phase: "Regular Season",
            game_date: game.date,
            matchup: "BOS vs. CLE",
            result: "W",
            opponent_abbreviation: "CLE",
          },
        },
      });
    return route.fulfill({ status: 404, json: { detail: "No fixture for route" } });
  });
}

test("fans drill from season feed through box score to a player's real shot chart", async ({
  page,
}) => {
  await mockLeagueApi(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Every game, in focus." })).toBeVisible();
  await expect(page.getByText("1 scheduled")).toBeVisible();
  await expect(page.locator(".upcoming-card .game-status")).toContainText("Scheduled");
  await expect(page.locator(".upcoming-card time")).toHaveText("7:30 PM ET");
  await page.getByLabel("Season").selectOption("2024-25");
  await expect(page).toHaveURL(/season=2024-25/);
  await page.getByLabel("Season").selectOption("2025-26");
  await page
    .locator(".feed-block")
    .getByRole("link", { name: "Open Cleveland Cavaliers at Boston Celtics" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Cleveland Cavaliers at Boston Celtics" }),
  ).toBeVisible();
  await expect(page.locator(".team-boxscore")).toHaveCount(2);
  const teamColumns = await page
    .locator(".team-boxscore-grid")
    .evaluate((node) => getComputedStyle(node).gridTemplateColumns.trim().split(/\s+/));
  expect(teamColumns).toHaveLength(2);
  await page.setViewportSize({ width: 390, height: 844 });
  const mobileTeamColumns = await page
    .locator(".team-boxscore-grid")
    .evaluate((node) => getComputedStyle(node).gridTemplateColumns.trim().split(/\s+/));
  expect(mobileTeamColumns).toHaveLength(1);
  await page.getByRole("link", { name: "Jayson Tatum" }).click();
  await expect(page.getByRole("heading", { name: "Jayson Tatum" })).toBeVisible();
  await expect(
    page.getByRole("group", { name: /NBA half court with plotted shot locations/ }),
  ).toBeVisible();
  await expect(page.locator(".shot-chart__mark.is-made")).toHaveCount(1);
  await expect(page.getByRole("button", { name: /Jump Shot/ })).toBeVisible();
});

test("shows an honest unavailable shot chart while retaining player stats", async ({ page }) => {
  await mockLeagueApi(page, false, true);
  await page.goto(`/game/${game.game_id}/player/7?season=2025-26`);
  await expect(page.getByRole("heading", { name: "Jayson Tatum" })).toBeVisible();
  await expect(page.getByText("Shot chart unavailable")).toBeVisible();
  await expect(page.getByText(/No locations are estimated/)).toBeVisible();
  await expect(
    page.locator(".player-analysis__metrics").getByText("28", { exact: true }),
  ).toBeVisible();
});

test("explores player sample comparisons and shot controls", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await mockLeagueApi(page);
  await page.goto("/game/" + game.game_id + "/player/7?season=2025-26");
  await expect(page.getByRole("heading", { name: "Jayson Tatum" })).toBeVisible();
  await expect(page.getByText("Game-level efficiency & impact")).toBeVisible();
  await expect(page.getByText("Coefficient of variation")).toBeVisible();

  await page.getByLabel("Historical sample size").selectOption("5");
  await page.getByLabel("Stat line").fill("30");
  await expect(page.locator(".player-analysis__hit-rate strong")).toHaveText("0%");
  await expect(page.locator(".player-analysis__hit-rate")).toContainText("0 / 3 available games");

  await page.getByLabel("Shot period").selectOption("2");
  await page.getByRole("button", { name: "Misses" }).click();
  await expect(page.locator(".shot-chart__mark")).toHaveCount(1);
  await page.locator(".shot-chart__mark").focus();
  await expect(page.locator(".shot-chart__tooltip")).toContainText("Layup Shot");

  const rotation = page.getByLabel("Court rotation");
  await rotation.focus();
  await rotation.press("End");
  await expect(rotation).toHaveValue("25");
  const tilt = page.getByLabel("Court tilt");
  await tilt.focus();
  await tilt.press("End");
  await expect(tilt).toHaveValue("58");

  await page.getByRole("button", { name: "Reset chart" }).click();
  await expect(page.getByLabel("Shot period")).toHaveValue("all");
  await expect(rotation).toHaveValue("0");
  await expect(tilt).toHaveValue("42");
  await page.locator(".shot-chart").screenshot({ path: "test-results/player-shot-chart.png" });
  await page
    .locator(".player-analysis__history")
    .screenshot({ path: "test-results/player-history.png" });
});

test("renders an honest API failure state", async ({ page }) => {
  await mockLeagueApi(page, true);
  await page.goto("/");
  await expect(page.getByRole("alert")).toContainText("Mock NBA service error");
});
