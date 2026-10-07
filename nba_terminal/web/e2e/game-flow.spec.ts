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

async function mockLeagueApi(page: Page, feedError = false) {
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
      return route.fulfill({ json: { days: ["2025-11-02", "2025-11-03"], games: [] } });
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
          shots: [{ x: 10, y: 80, made: true, description: "Jump Shot", period: 1, distance: 12 }],
          shot_chart_state: "available",
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
  await page.getByLabel("Season").selectOption("2024-25");
  await expect(page).toHaveURL(/season=2024-25/);
  await page.getByLabel("Season").selectOption("2025-26");
  await page.getByRole("link", { name: "Open Cleveland Cavaliers at Boston Celtics" }).click();
  await expect(
    page.getByRole("heading", { name: "Cleveland Cavaliers at Boston Celtics" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Jayson Tatum" }).click();
  await expect(page.getByRole("heading", { name: "Jayson Tatum" })).toBeVisible();
  await expect(
    page.getByRole("img", { name: "NBA shot locations plotted on a half-court" }),
  ).toBeVisible();
  await expect(page.getByTitle("Jump Shot · 12 ft")).toBeAttached();
});

test("renders an honest API failure state", async ({ page }) => {
  await mockLeagueApi(page, true);
  await page.goto("/");
  await expect(page.getByRole("alert")).toContainText("Mock NBA service error");
});
