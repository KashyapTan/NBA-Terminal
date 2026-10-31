import { mkdirSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test } from "@playwright/test";
import { testPlayer, testSnapshot } from "../src/league-fantasy.test-fixtures";
import { LEAGUE_CATEGORIES, type WaiverPlan } from "../src/league-fantasy-model";

test("strategy hierarchy, score and seven conditional alternatives remain usable on mobile", async ({
  page,
}) => {
  const snapshot = testSnapshot();
  snapshot.teams[0].totals = {
    pts: 399,
    reb: 132,
    ast: 81,
    stl: 11,
    blk: 12,
    threes: 49,
    to: 42,
    fgm: 140,
    fga: 307,
    ftm: 62,
    fta: 75,
  };
  snapshot.teams[1].totals = {
    pts: 485,
    reb: 117,
    ast: 97,
    stl: 32,
    blk: 6,
    threes: 67,
    to: 50,
    fgm: 180,
    fga: 364,
    ftm: 50,
    fta: 70,
  };
  snapshot.free_agents = Array.from({ length: 7 }, (_, i) =>
    testPlayer(`free${i}`, { name: `Synthetic pickup ${i + 1}` }),
  );
  const plan: WaiverPlan = {
    status: "incomplete",
    reasons: [],
    remaining_adds: null,
    baseline: null,
    projected: null,
    actions: [],
    assumptions: [],
    limitations: [],
    data_gaps: [],
    recommendations: snapshot.free_agents.map((player, i) => ({
      add_id: player.id,
      drop_id: "rostered",
      date: "2026-11-01",
      gains: { ast: 8 - i, pts: 12 },
      probability_gain: 0.03,
      games_gain: 1,
      minutes_gain: 24,
      season_cost: 0.2,
      net_score: 1,
      target_categories: ["ast"],
      rationale:
        "Adds assists in the closest winnable category while preserving your scoring core.",
    })),
    strategy: Object.fromEntries(
      LEAGUE_CATEGORIES.map(({ key }, i) => [
        key,
        {
          classification: key === "ast" || i % 3 === 0 ? "swing" : i % 3 === 1 ? "favored" : "punt",
          explanation:
            key === "ast" || i % 3 === 0
              ? "One productive pickup could close this gap."
              : i % 3 === 1
                ? "Protect this lead before chasing other categories."
                : "A large deficit makes other categories better targets.",
          projected_margin: key.endsWith("pct") ? (i - 3) / 100 : i - 3,
          historical_margin: key.endsWith("pct") ? (i - 2) / 100 : i - 2,
          target_priority: i,
        },
      ]),
    ),
  };
  await page.route("**/api/**", (route) => {
    const path = new URL(route.request().url()).pathname;
    const json =
      path === "/api/meta"
        ? { current_season: "2026-27", seasons: ["2026-27"], supported_from: "1996-97" }
        : path.endsWith("/status")
          ? { connected: true, team_id: 1 }
          : path.endsWith("/plan")
            ? plan
            : path.endsWith("/snapshot")
              ? snapshot
              : path === "/api/fantasy/players"
                ? { season: "2026-27", supported: true, phase: "Regular Season", players: [] }
                : {};
    return route.fulfill({ json });
  });
  const evidence = resolve(process.cwd(), "../../visual-evidence/fantasy-v2");
  mkdirSync(evidence, { recursive: true });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/fantasy?fantasyTab=matchups");
  await expect(page.getByLabel("4 wins, 5 losses, 0 ties")).toBeVisible();
  await page.screenshot({ path: resolve(evidence, "ui-matchups-desktop.png"), fullPage: true });
  await page.getByRole("tab", { name: "Waiver Wire", exact: true }).click();
  await expect(page.locator(".pickup-list > li")).toHaveCount(7);
  await expect(page.getByText(/Conditional alternatives:/)).toBeVisible();
  await page.screenshot({ path: resolve(evidence, "ui-waiver-desktop.png"), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect
    .poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth))
    .toBe(true);
  await page.screenshot({ path: resolve(evidence, "ui-waiver-mobile.png"), fullPage: true });
  await page.getByRole("tab", { name: "Matchups", exact: true }).click();
  await expect(page.getByLabel("4 wins, 5 losses, 0 ties")).toBeVisible();
  await expect
    .poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth))
    .toBe(true);
  await page.screenshot({ path: resolve(evidence, "ui-matchups-mobile.png"), fullPage: true });
});
