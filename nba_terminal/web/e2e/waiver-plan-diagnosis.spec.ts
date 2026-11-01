import { mkdirSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test } from "@playwright/test";
import { testSnapshot } from "../src/league-fantasy.test-fixtures";
import type { WaiverPlan } from "../src/league-fantasy-model";

// Synthetic UI proof only: these are not the user's private ESPN fields.
test("empty ordered plan names its budget blocker inline on desktop and mobile", async ({
  page,
}) => {
  const snapshot = testSnapshot();
  const plan: WaiverPlan = {
    status: "incomplete",
    evaluation_state: "conditional_opportunities",
    reasons: [
      "Acquisition budget unknown; alternatives are conditional and no ordered moves are confirmed.",
    ],
    data_gaps: [
      "Current matchup acquisitions used unknown: ESPN's current-matchup counter is unavailable or invalid. Season/day totals and yesterday's count are not substitutes.",
    ],
    remaining_adds: null,
    baseline: null,
    projected: null,
    actions: [],
    assumptions: [],
    limitations: [],
    recommendations: [
      {
        add_id: "free",
        drop_id: "rostered",
        date: "2026-11-01",
        gains: { ast: 8 },
        probability_gain: null,
        games_gain: 1,
        minutes_gain: 24,
        season_cost: 0,
        net_score: 1,
        target_categories: ["ast"],
        rationale: "Synthetic conditional comparison.",
      },
    ],
    search: {
      candidate_pool: 1,
      evaluations: 2,
      evaluation_limit_reached: false,
      evaluated_drop_ids: ["rostered"],
      legal_drop_ids: ["rostered"],
    },
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
                : { season: "2026-27", supported: true, players: [] };
    return route.fulfill({ json });
  });
  await page.goto("/fantasy?fantasyTab=waiver");
  const section = page.getByRole("region", { name: "Recommended ordered plan" });
  await expect(
    section.getByText("Ordered plan withheld: acquisition budget unverified"),
  ).toBeVisible();
  await expect(section.getByText(/Current matchup acquisitions used unknown/)).toBeVisible();
  await expect(section.getByText(/1 beneficial conditional alternative found/)).toBeVisible();
  await expect(section.getByText(/Yesterday’s usage is not current confirmation/)).toBeVisible();
  await expect(section.getByText(/See the evaluation status/)).toHaveCount(0);
  const evidence = resolve(process.cwd(), "../../docs/evidence/waiver_plan_diagnosis");
  mkdirSync(evidence, { recursive: true });
  for (const [name, width, height] of [
    ["desktop", 1440, 1000],
    ["mobile", 390, 844],
  ] as const) {
    await page.setViewportSize({ width, height });
    await expect
      .poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth))
      .toBe(true);
    await page.screenshot({ fullPage: true, path: resolve(evidence, `${name}.png`) });
  }
  await section
    .getByRole("button", { name: "Review acquisition counts & required inputs" })
    .click();
  await expect(page.getByLabel("Matchup acquisitions used", { exact: true })).toBeVisible();
  await expect(page.locator("details.waiver-advanced")).toHaveAttribute("open", "");
});
