import { mkdirSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test } from "@playwright/test";
import { testPlayer, testSnapshot } from "../src/league-fantasy.test-fixtures";
import { LEAGUE_CATEGORIES, type WaiverPlan } from "../src/league-fantasy-model";

test("strategy hierarchy, score and five-category remaining-total alternatives remain usable on mobile", async ({
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
  snapshot.free_agents = Array.from({ length: 15 }, (_, i) =>
    testPlayer(`free${i}`, { name: `Synthetic pickup ${i + 1}` }),
  );
  const plan: WaiverPlan = {
    selected_categories: ["ast", "pts", "reb", "to", "blk"],
    safe_categories: ["reb", "blk"],
    improvement_categories: ["ast", "pts", "to"],
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
      gains: { ast: 8, pts: 12 },
      probability_gain: null,
      calculation: {
        ast: {
          add_rate: 12,
          add_starts: 4,
          drop_rate: 10,
          drop_starts: 4,
          added_total: 48,
          lost_total: 40,
          lineup_other_net: 0,
          net_total: 8,
        },
      },
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
        : path.endsWith("/bridge/status")
          ? { enabled: false }
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
  const evidence = resolve(process.cwd(), "../../code_review/v5_app/generated/league-strategy-ui");
  mkdirSync(evidence, { recursive: true });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/fantasy?fantasyTab=matchups");
  await expect(page.getByLabel("4 wins, 5 losses, 0 ties")).toBeVisible();
  await page.screenshot({ path: resolve(evidence, "ui-matchups-desktop.png"), fullPage: true });
  await page.getByRole("tab", { name: "Waiver Wire", exact: true }).click();
  await page.getByText(/Optional competing single-move alternatives/).click();
  await expect(page.locator(".pickup-list > li")).toHaveCount(12);
  await expect(page.getByText(/Conditional alternatives:/)).toBeVisible();
  await expect(page.getByText("15 beneficial alternatives")).toBeVisible();
  await page.getByRole("button", { name: /Show more alternatives/ }).click();
  await expect(page.locator(".pickup-list > li")).toHaveCount(15);
  await expect(
    page.getByRole("row", { name: /AST.*12 × 4 starts.*10 × 4 lost starts.*\+8/ }).first(),
  ).toBeVisible();
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

test("browser setup and consented pairing states work without exposing cookie inputs", async ({
  page,
}) => {
  let paired = false;
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/bridge/pair")) {
      paired = true;
      return route.fulfill({ json: { enabled: true, state: "waiting_extension" } });
    }
    const json = path.endsWith("/bridge/status")
      ? { enabled: paired, state: "waiting_extension" }
      : path.endsWith("/status")
        ? { connected: false }
        : path === "/api/meta"
          ? { current_season: "2026-27", seasons: ["2026-27"], supported_from: "1996-97" }
          : path === "/api/fantasy/players"
            ? { season: "2026-27", supported: true, players: [] }
            : {};
    return route.fulfill({ json });
  });
  const evidence = resolve(process.cwd(), "../../code_review/v5_app/generated/league-strategy-ui");
  mkdirSync(evidence, { recursive: true });
  await page.goto("/fantasy");
  await page.getByText("One-time browser setup", { exact: true }).click();
  await expect(page.getByRole("link", { name: "Firefox extension" })).toHaveAttribute(
    "href",
    "/api/fantasy/espn/bridge/setup/firefox.zip",
  );
  await page.getByLabel("League ID", { exact: true }).fill("123");
  await page.getByLabel("Season ending year", { exact: true }).fill("2027");
  await page.getByRole("button", { name: "Connect ESPN", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Waiting for the extension");
  await expect(page.getByLabel("SWID", { exact: true })).not.toBeVisible();
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({ path: resolve(evidence, "ui-login-desktop.png"), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect
    .poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth))
    .toBe(true);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: resolve(evidence, "ui-login-mobile.png"), fullPage: true });
});
