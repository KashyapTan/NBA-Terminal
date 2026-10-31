import { mkdirSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test } from "@playwright/test";

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
];

test("Fantasy supports season stats, sample filters, player comparison and shortlist", async ({
  page,
}) => {
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === "/api/meta")
      return route.fulfill({
        json: {
          current_season: "2025-26",
          seasons: ["2025-26", "2024-25"],
          supported_from: "1996-97",
        },
      });
    if (url.pathname === "/api/fantasy/players")
      return route.fulfill({
        json: {
          season: url.searchParams.get("season"),
          supported: true,
          phase: "Regular Season",
          players,
        },
      });
    return route.fulfill({ status: 404, json: { detail: "No fixture for route" } });
  });

  await page.goto("/fantasy");
  await expect(page.getByRole("heading", { name: "Find your next edge." })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Dashboard" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(page.getByRole("heading", { name: "Your fantasy workspace" })).toBeVisible();
  await expect(page.getByText("Connect your ESPN league")).toBeVisible();
  const evidenceDir = resolve(process.cwd(), "../../visual-evidence");
  mkdirSync(evidenceDir, { recursive: true });
  await page.setViewportSize({ width: 1600, height: 1100 });
  await page.screenshot({
    path: resolve(evidenceDir, "fantasy-dashboard-desktop.png"),
    fullPage: true,
  });
  const expandedWidth = await page.locator(".main-area").evaluate((node) => node.clientWidth);
  await page.getByRole("button", { name: "Collapse sidebar" }).click();
  await expect(page.getByRole("button", { name: "Expand sidebar" })).toHaveAttribute(
    "aria-expanded",
    "false",
  );
  await expect
    .poll(() => page.locator(".main-area").evaluate((node) => node.clientWidth))
    .toBeGreaterThan(expandedWidth);
  await expect(
    page
      .getByRole("navigation", { name: "Workspace" })
      .getByRole("link", { name: "Fantasy", exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: resolve(evidenceDir, "fantasy-sidebar-collapsed.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Expand sidebar" }).click();
  await page.setViewportSize({ width: 390, height: 1024 });
  await page.screenshot({
    path: resolve(evidenceDir, "fantasy-dashboard-mobile.png"),
    fullPage: true,
  });
  await expect
    .poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth))
    .toBe(true);
  await page.getByRole("tab", { name: "Leaders" }).click();
  await expect(page).toHaveURL(/fantasyTab=leaders/);
  await expect(page.getByRole("table").first().getByText("Jayson Tatum")).toBeVisible();
  await expect(page.getByText("NBA Stats · regular season actuals")).toBeVisible();
  await page.getByRole("button", { name: "Add Jayson Tatum to comparison" }).click();
  await page.getByRole("button", { name: "Add Jayson Tatum to shortlist" }).click();
  await page.getByRole("button", { name: "Add Luka Doncic to comparison" }).click();
  await expect(page.getByRole("table").last().getByText("Jayson Tatum")).toBeVisible();

  await page.evaluate(() => window.scrollTo(0, 0));
  await page.setViewportSize({ width: 1600, height: 1400 });
  await page.screenshot({ path: resolve(evidenceDir, "fantasy-desktop.png") });
  await page.setViewportSize({ width: 390, height: 1024 });
  await page.evaluate(() => window.scrollTo(0, 0));
  await expect(
    page
      .getByRole("navigation", { name: "Workspace" })
      .getByRole("link", { name: "Fantasy", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Collapse sidebar" })).toBeHidden();
  await page.screenshot({ path: resolve(evidenceDir, "fantasy-mobile.png") });

  await page.getByRole("tab", { name: "TO" }).click();
  const leaderboard = page.getByRole("table").first();
  await expect(leaderboard.getByRole("row").nth(1)).toContainText("Jayson Tatum");
  await page.getByRole("tab", { name: "FG%" }).click();
  await expect(page.getByLabel("Minimum field-goal attempts")).toBeVisible();
  await page.getByLabel("Minimum field-goal attempts").fill("200");
  await expect(leaderboard.getByRole("row")).toHaveCount(2);
  await page.getByLabel("Minimum minutes per game", { exact: true }).fill("35");
  await page.getByLabel("Minimum field-goal attempts").fill("0");
  await expect(leaderboard.getByRole("row")).toHaveCount(2);
  await page.reload();
  await expect(page.getByLabel("Minimum minutes per game", { exact: true })).toHaveValue("35");
  await expect(page.getByRole("table").first().getByRole("row")).toHaveCount(2);
  await page.getByRole("tab", { name: "Matchups" }).click();
  await expect(page.getByRole("tab", { name: "Matchups" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await page.getByLabel("Fantasy season").selectOption("2024-25");
  await expect(page).toHaveURL(/fantasyTab=matchups&season=2024-25/);
  await expect(page.getByRole("tabpanel", { name: "Matchups" })).toContainText(
    "No league is linked",
  );
});
