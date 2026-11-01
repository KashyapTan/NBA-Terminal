import { readFileSync } from "node:fs";
import { expect, test } from "@playwright/test";

const home = {
  id: 1610612738,
  abbreviation: "BOS",
  name: "Boston Celtics",
  nickname: "Celtics",
  logo_url: "https://cdn.nba.com/logos/nba/1610612738/primary/L/logo.svg",
};
const away = {
  id: 1610612739,
  abbreviation: "CLE",
  name: "Cleveland Cavaliers",
  nickname: "Cavaliers",
  logo_url: "https://cdn.nba.com/logos/nba/1610612739/primary/L/logo.svg",
};

for (const width of [1440, 390]) {
  test(`compact three-date schedule and brand navigation at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    // Deliberately fail one logo to exercise the production text fallback.
    await page.route("https://cdn.nba.com/logos/**", (route) =>
      route.request().url().includes("1610612739")
        ? route.abort()
        : route.fulfill({
            contentType: "image/svg+xml",
            body: readFileSync(new URL("./fixtures/celtics-logo.svg", import.meta.url), "utf8"),
          }),
    );
    await page.route("**/api/**", (route) => {
      const path = new URL(route.request().url()).pathname;
      if (path === "/api/meta")
        return route.fulfill({
          json: { current_season: "2025-26", seasons: ["2025-26"], supported_from: "1996-97" },
        });
      if (path === "/api/upcoming")
        return route.fulfill({
          json: {
            days: ["2025-11-02", "2025-11-03", "2025-11-04"],
            games: [2, 1, 3].map((status, index) => ({
              game_id: `002250000${index}`,
              date: `2025-11-0${index + 2}`,
              start_time: "2025-11-04T00:30:00Z",
              status_id: status,
              status: status === 2 ? "Q3 4:21" : status === 3 ? "Final/OT" : "Scheduled",
              phase: "Regular Season",
              home_team: home,
              away_team: away,
              home_score: status === 1 ? 0 : 82,
              away_score: status === 1 ? 0 : 79,
            })),
          },
        });
      if (path === "/api/games") return route.fulfill({ json: { games: [], supported: true } });
      return route.fulfill({ status: 404, json: { detail: "No fixture for route" } });
    });
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Today + next two days" })).toBeVisible();
    await expect(page.locator(".date-group")).toHaveCount(3);
    await expect(page.locator(".game-card--live")).toContainText("Q3 4:21");
    await expect(page.locator(".game-card--final")).toContainText("Final/OT");
    await expect(page.locator(".game-card--scheduled .score").first()).toHaveText("—");
    await expect(page.locator(".team-badge [title='Cleveland Cavaliers']").first()).toHaveText(
      "CLE",
    );
    await expect(page.getByRole("img", { name: "Boston Celtics logo" }).first()).toBeVisible();
    const card = await page.locator(".game-card").first().boundingBox();
    expect(card?.height).toBeLessThan(115);
    expect(card?.width).toBeGreaterThan(width === 390 ? 310 : 400);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(
      width,
    );
    await page.screenshot({ path: `test-results/game-center-${width}.png`, fullPage: true });
    const collapse = page.getByRole("button", { name: "Collapse sidebar" });
    await collapse.focus();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("button", { name: "Expand sidebar" })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    await expect(page.getByRole("link", { name: "Fantasy", exact: true })).toBeVisible();
    await expect(page.locator(".sidebar-toggle")).toHaveCount(0);
    await page.reload();
    await expect(page.getByRole("button", { name: "Expand sidebar" })).toBeVisible();
    await page.getByRole("button", { name: "Expand sidebar" }).focus();
    await page.keyboard.press("Space");
    await expect(page.getByRole("button", { name: "Collapse sidebar" })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
  });
}
