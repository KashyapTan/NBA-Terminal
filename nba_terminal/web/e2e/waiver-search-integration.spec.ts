import { mkdirSync, writeFileSync } from "node:fs";
import { expect, test } from "@playwright/test";
import type { WaiverPlan } from "../src/league-fantasy-model";

const root = "/api/fantasy/espn";
const headers = { "X-Fantasy-Request": "1" };
const evidence = process.env.EVIDENCE_DIR || "../../docs/evidence/waiver-search";

const rawEvidence = process.env.SEARCH_RAW_EVIDENCE_DIR || "test-results/waiver-search-raw";

for (const adds of [4, 7]) {
  test(`frozen ${adds}-add market continues locally, stays responsive and cancels safely`, async ({
    page,
  }, info) => {
    await page.request.post("http://127.0.0.1:8219/__test__/search-control", { data: { adds } });
    const connected = await page.request.post(`${root}/connect`, {
      headers,
      data: { league_id: 901, season_id: 2027, team_id: 1 },
    });
    expect(connected.ok()).toBe(true);
    const snapshot = await (await page.request.get(`${root}/snapshot`)).json();
    const before = await (
      await page.request.get("http://127.0.0.1:8219/__test__/search-counts")
    ).json();
    const preferences = {
      context: {
        league_id: 901,
        season_id: 2027,
        team_id: 1,
        matchup_period_id: snapshot.period.matchup_period_id,
      },
      selected_categories: ["reb", "ast", "stl", "threes", "to"],
    };
    const legacyResponse = await page.request.post(`${root}/plan`, { headers, data: preferences });
    expect(legacyResponse.ok()).toBe(true);
    const legacy = (await legacyResponse.json()) as WaiverPlan;
    expect(legacy.search!.evaluations).toBeLessThanOrEqual(5000);
    let plan = (await (
      await page.request.post(`${root}/plan`, {
        headers: { ...headers, "X-Fantasy-Search": "progressive" },
        data: preferences,
      })
    ).json()) as WaiverPlan;
    expect(plan.status, JSON.stringify(plan.reasons)).toBe("ready");
    expect(plan.search?.phase).toBe("searching");
    const job = plan.search!.job_id!;
    const firstCount = plan.search!.evaluations;
    expect(plan.actions.length).toBeGreaterThan(0);
    const opponent = plan.projected!.opponent_totals;
    // CI CPU speed changes work per time slice. Complete this finite fixture's
    // local search; the test timeout bounds failures, not an assumed slice count.
    while (plan.search!.phase === "searching") {
      const next = page.request.post(`${root}/plan/${job}`, { headers, data: {} });
      const start = Date.now();
      expect((await page.request.get("/api/meta")).ok()).toBe(true);
      expect(Date.now() - start).toBeLessThan(1500);
      const response = await next;
      expect(response.ok()).toBe(true);
      plan = await response.json();
      expect(plan.actions.length).toBeGreaterThan(0);
      expect(plan.projected!.opponent_totals).toEqual(opponent);
      expect(plan.search!.evaluation_limit).toBeNull();
    }
    expect(plan.search!.complete).toBe(true);
    expect(plan.search!.evaluations).toBeGreaterThan(firstCount);
    expect(plan.search!.evaluations).toBeGreaterThan(5000);
    mkdirSync(rawEvidence, { recursive: true });
    writeFileSync(
      `${rawEvidence}/${info.project.name}-${adds}-snapshot.json`,
      JSON.stringify(snapshot),
    );
    writeFileSync(
      `${rawEvidence}/${info.project.name}-${adds}-counts.json`,
      JSON.stringify(
        {
          providerRequests: before,
          legacyEvaluations: legacy.search!.evaluations,
          progressiveEvaluations: plan.search!.evaluations,
          earlyEvaluations: firstCount,
          phase: plan.search!.phase,
          actions: plan.actions.map((move) => ({
            date: move.date,
            add: move.add_id,
            drop: move.drop_id,
          })),
        },
        null,
        2,
      ),
    );
    expect(
      await (await page.request.get("http://127.0.0.1:8219/__test__/search-counts")).json(),
    ).toEqual(before);
    expect((await page.request.delete(`${root}/plan/${job}`, { headers })).ok()).toBe(true);
    const cancelled = await (
      await page.request.post(`${root}/plan/${job}`, { headers, data: {} })
    ).json();
    expect(cancelled.search.phase).toBe("cancelled");
    expect(cancelled.actions).toEqual(plan.actions);
    await page.request.get(`${root}/snapshot?refresh=true`);
    expect((await page.request.post(`${root}/plan/${job}`, { headers, data: {} })).status()).toBe(
      409,
    );
  });
}

test("desktop and mobile show a usable best result while searching, then cancel", async ({
  page,
}, info) => {
  await page.request.post("http://127.0.0.1:8219/__test__/search-control", { data: { adds: 7 } });
  await page.goto("/fantasy");
  await page.request.post(`${root}/bridge/pair`, {
    headers,
    data: { league_id: 901, season_id: 2027, team_id: 1 },
  });
  const ticket = await (
    await page.request.post(`${root}/bridge/challenge`, { headers, data: {} })
  ).json();
  expect(
    (
      await page.request.post(`${root}/bridge/refresh`, {
        headers,
        data: {
          league_id: 901,
          season_id: 2027,
          swid: "fixture-owner-0001",
          espn_s2: "synthetic-only",
          nonce: ticket.nonce,
        },
      })
    ).ok(),
  ).toBe(true);
  await page.evaluate(() => window.dispatchEvent(new Event("nba-espn-bridge")));
  await expect(page.getByLabel("Your ESPN team")).toHaveValue("1");
  // Hold only the next local progress request to inspect a stable intermediate
  // publication. Every response still comes from the actual planner route.
  let resume!: () => void;
  const held = new Promise<void>((resolve) => {
    resume = resolve;
  });
  await page.route("**/api/fantasy/espn/plan/*", async (route) => {
    if (route.request().method() === "POST") await held;
    await route.continue().catch(() => {});
  });
  const first = page.waitForResponse(
    (response) => response.url().endsWith(`${root}/plan`) && response.ok(),
  );
  await page.getByRole("tab", { name: "Waiver Wire", exact: true }).click();
  expect((await (await first).json()).search.phase).toBe("searching");
  await expect(page.getByRole("button", { name: "Stop search" })).toBeVisible();
  await expect(page.locator(".waiver-workspace")).toHaveAttribute("data-result-state", "connected");
  mkdirSync(evidence, { recursive: true });
  await page.screenshot({
    path: `${evidence}/${info.project.name}-search-desktop.png`,
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole("button", { name: "Stop search" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await page.screenshot({
    path: `${evidence}/${info.project.name}-search-mobile.png`,
    fullPage: true,
  });
  await page.getByRole("button", { name: "Stop search" }).click();
  resume();
  await expect(page.getByRole("status").filter({ hasText: "Search cancelled" })).toBeVisible();
});
