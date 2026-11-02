import { mkdirSync, writeFileSync } from "node:fs";
import { expect, type Page, test } from "@playwright/test";

const root = "/api/fantasy/espn";
const headers = { "X-Fantasy-Request": "1" };
const evidence = "../../docs/evidence/v6-integrated";
async function pair(page: Page, league_id = 601) {
  await page.request.post("http://127.0.0.1:8214/__test__/v6-reset", { data: { league_id } });
  await page.goto("/fantasy");
  await page.waitForLoadState("networkidle");
  expect(
    (
      await page.request.post(`${root}/bridge/pair`, {
        headers,
        data: { league_id, season_id: 2027, team_id: 1 },
      })
    ).ok(),
  ).toBe(true);
  const ticket = await (
    await page.request.post(`${root}/bridge/challenge`, { headers, data: {} })
  ).json();
  expect(
    (
      await page.request.post(`${root}/bridge/refresh`, {
        headers,
        data: {
          league_id,
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
}
async function openPlan(page: Page, league = 601, five = ["PTS", "REB", "AST", "STL", "BLK"]) {
  await pair(page, league);
  const initial = page.waitForResponse((r) => r.url().endsWith(`${root}/plan`) && r.ok(), {
    timeout: 15000,
  });
  await page.getByRole("tab", { name: "Waiver Wire", exact: true }).click();
  await initial;
  await page.getByText("Edit targets", { exact: true }).click();
  for (const key of ["PTS", "REB", "AST", "STL", "BLK", "3PM", "TO", "FG%", "FT%"].filter(
    (key) => !five.includes(key),
  ))
    if (await page.getByRole("checkbox", { name: key, exact: true }).isChecked())
      await page.getByRole("checkbox", { name: key, exact: true }).uncheck();
  for (const key of five) await page.getByRole("checkbox", { name: key, exact: true }).check();
  const next = page.waitForResponse((r) => r.url().endsWith(`${root}/plan`) && r.ok(), {
    timeout: 15000,
  });
  await page.getByRole("button", { name: "Apply five" }).click();
  const plan = await (await next).json();
  await page.getByText("Edit targets", { exact: true }).click();
  await expect(page.locator(".waiver-workspace")).toHaveAttribute("data-result-state", "connected");
  return plan;
}
async function stats(page: Page) {
  return (
    await (await page.request.get("http://127.0.0.1:8214/__test__/connection-control")).json()
  ).calls;
}
async function control(page: Page, data: object) {
  await page.request.post("http://127.0.0.1:8214/__test__/connection-control", { data });
}

test("real provider chain: multi-move, all data displayed, compact desktop/mobile help", async ({
  page,
}, info) => {
  mkdirSync(evidence, { recursive: true });
  const plan = await openPlan(page);
  const snapshot = await (await page.request.get(`${root}/snapshot`)).json();
  writeFileSync(`${evidence}/${info.project.name}-plan.json`, JSON.stringify(plan, null, 2));
  writeFileSync(
    `${evidence}/${info.project.name}-snapshot.json`,
    JSON.stringify(snapshot, null, 2),
  );
  expect(plan.pickup_filter_summary.thresholds).toEqual({
    min_minutes: 15,
    min_games: 2,
    min_participation: 0.5,
  });
  expect(plan.pickup_filter_summary.qualified).toBe(2);
  expect(plan.pickup_filter_summary.exclusions).toContainEqual(
    expect.objectContaining({
      player_id: "199",
      reasons: expect.arrayContaining([
        "below_min_minutes",
        "below_min_games",
        "below_min_participation",
      ]),
    }),
  );
  expect(snapshot.teams[0].actuals.official.source).toBe("espn_official");
  expect(snapshot.teams[0].actuals.forecast_complete).toBe(true);
  expect(plan.status).toBe("ready");
  for (const move of plan.recommended_plan.moves) {
    for (const [key, row] of Object.entries(move.arithmetic.categories) as [
      string,
      {
        before: number;
        after: number;
        net: number;
        add: number;
        drop: number;
        spillover: number;
        makes?: { after: number };
        attempts?: { after: number };
      },
    ][]) {
      expect(row.after - row.before).toBeCloseTo(row.net, 10);
      if (!key.endsWith("pct")) expect(row.add - row.drop + row.spillover).toBeCloseTo(row.net, 10);
      else if (row.makes && row.attempts && row.attempts.after > 0)
        expect(row.after).toBeCloseTo(row.makes.after / row.attempts.after, 10);
    }
  }
  expect(plan.recommended_plan.moves).toHaveLength(2);
  expect(new Set(plan.actions.map((m: { add_id: string }) => m.add_id)).size).toBe(2);
  expect(plan.actions[0].score_after).toBe(plan.actions[1].score_before);
  await expect(page.locator(".ww-move")).toHaveCount(2);
  await expect(page.locator(".ww-target")).toHaveCount(5);
  await expect(page.locator(".ww-analysis")).not.toHaveAttribute("open");
  await expect(page.locator(".ww-move").first()).toContainText("15 MPG · 2 GP / 4 team games");
  await expect(page.locator(".ww-move").first()).not.toContainText("Low sample");
  expect(
    await page
      .locator(".ww-move")
      .first()
      .evaluate((el) => el.getBoundingClientRect().height),
  ).toBeLessThan(260);
  await page.screenshot({ path: `${evidence}/${info.project.name}-desktop.png`, fullPage: true });
  const help = page.getByRole("button", { name: "About full-team net" });
  await help.focus();
  await expect(page.getByRole("tooltip").filter({ hasText: "Net includes pickup" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(help).toBeFocused();
  await expect(page.getByRole("tooltip").filter({ hasText: "Net includes pickup" })).toBeHidden();
  await page.getByText("Full analysis & data", { exact: true }).click();
  for (const move of plan.recommended_plan.moves)
    expect(Object.keys(move.arithmetic.categories)).toHaveLength(9);
  const arithmetic = page.getByRole("region", { name: "All nine move calculations" });
  await expect(arithmetic).toHaveCount(2);
  await expect(arithmetic.first().getByRole("row")).toHaveCount(10);
  await expect(page.locator(".ww-analysis")).toContainText(
    "Low sample 11 minutes: below_min_minutes, below_min_games, below_min_participation",
  );
  await expect(page.locator(".ww-analysis")).toContainText("source_coverage");
  await expect(page.locator(".ww-analysis")).toContainText("selected_plan_stop_reason");
  await page.getByText("Full analysis & data", { exact: true }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.evaluate(() => window.scrollTo(0, 0));
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: `${evidence}/${info.project.name}-mobile.png`, fullPage: true });
  // Every displayed primary value must come from the paired backend arithmetic.
  const first = plan.recommended_plan.moves[0];
  for (const key of ["pts", "reb", "ast", "stl", "blk", "to"]) {
    const row = first.arithmetic.categories[key];
    if (row.net !== 0)
      expect(await page.locator(".ww-move").first().textContent()).toContain(
        `Net ${row.net > 0 ? "+" : ""}${row.net}`,
      );
  }
});

test("actual HTTP plan scenarios: one, exhausted, empty, unknown denominator, required failure, no benefit", async ({
  page,
}, info) => {
  const records = [];
  for (const [league, moves, state] of [
    [602, 1, "confirmed_ordered_plan"],
    [603, 0, "known_zero_acquisitions"],
    [604, 0, "no_qualified_pickups"],
    [605, 0, "no_qualified_pickups"],
    [606, 0, "required_inputs_unknown"],
    [608, 0, "evaluated_no_material_benefit"],
  ] as const) {
    const plan = await openPlan(page, league);
    expect(plan.actions).toHaveLength(moves);
    expect(plan.evaluation_state).toBe(state);
    await expect(page.locator(".ww-move")).toHaveCount(moves);
    if (league === 602) {
      expect(plan.search.selected_plan_stop_reason).toBe("best_beneficial_explored_continuation");
      await expect(page.getByText("No further beneficial move found in this search")).toBeVisible();
    }
    if (league === 605)
      expect(plan.pickup_filter_summary.exclusions[0].reasons).toContain(
        "completed_team_games_unknown",
      );
    if (league === 606) {
      await expect(page.getByText("Plan needs updated data").first()).toBeVisible();
      await page.screenshot({
        path: `${evidence}/${info.project.name}-required-data-failure.png`,
        fullPage: true,
      });
    }
    records.push({ league, plan });
    await page.request.delete(`${root}/connection`, { headers });
  }
  writeFileSync(
    `${evidence}/${info.project.name}-scenarios.json`,
    JSON.stringify(records, null, 2),
  );
});

test("filters, availability, protection, opponent/team and manual HTTP refresh are wired", async ({
  page,
}, info) => {
  await openPlan(page);
  await page.getByText("Pickup filters", { exact: true }).click();
  for (const [label, value, key, expected] of [
    ["Min MPG", "10", "min_minutes", 10],
    ["Min games", "1", "min_games", 1],
    ["Participation %", "25", "min_participation", 0.25],
  ] as const) {
    const result = page.waitForResponse((r) => r.url().endsWith(`${root}/plan`) && r.ok());
    await page.getByLabel(label, { exact: true }).fill(value);
    const response = await result;
    expect(response.request().postDataJSON().pickup_filters[key]).toBe(expected);
    if (key === "min_participation")
      expect((await response.json()).pickup_filter_summary.qualified).toBe(3);
  }
  await page.getByText("Pickup filters", { exact: true }).click();
  await page.getByText("Roster settings", { exact: true }).click();
  const protection = page.getByRole("button", { name: "Protect Fixture Player 1", exact: true });
  const updated = page.waitForResponse((r) => r.url().endsWith(`${root}/plan`) && r.ok());
  await protection.click();
  const protectedPlan = await (await updated).json();
  expect(protectedPlan.search.legal_drop_ids).not.toContain("1");
  const out = page.waitForResponse((r) => r.url().endsWith(`${root}/plan`) && r.ok());
  await page
    .getByRole("button", { name: "Second roster drop availability: Available", exact: true })
    .click();
  expect((await out).request().postDataJSON().player_overrides["9001"].injured).toBe(true);
  const core = page.waitForResponse((r) => r.url().endsWith(`${root}/plan`) && r.ok());
  await page.getByLabel("Allow core-player drops").check();
  expect((await core).request().postDataJSON().allow_core_drops).toBe(true);
  await page.getByText("Roster settings", { exact: true }).click();
  const refresh = page.waitForResponse(
    (r) => r.url().includes(`${root}/snapshot?refresh=true`) && r.ok(),
  );
  await page.getByRole("button", { name: "Refresh league", exact: true }).click();
  await refresh;
  await page.getByRole("tab", { name: "Matchups", exact: true }).click();
  await expect(page.getByRole("heading", { name: /Current opponent/ })).toBeVisible();
  await page.getByLabel("Compare league team").selectOption("3");
  const comparison = await page.request.get(`${root}/snapshot?compare_team_id=3`);
  expect(comparison.ok()).toBe(true);
  expect((await comparison.json()).teams.some((team: { id: number }) => team.id === 3)).toBe(true);
  // Public fallback session has explicitly unverified ownership; exercises team route legally.
  await page.request.delete(`${root}/connection`, { headers });
  const connected = await page.request.post(`${root}/connect`, {
    headers,
    data: { league_id: 601, season_id: 2027, team_id: 1 },
  });
  expect(connected.ok()).toBe(true);
  const switched = await page.request.put(`${root}/team`, { headers, data: { team_id: 2 } });
  expect(switched.ok()).toBe(true);
  const snapshot = await (await page.request.get(`${root}/snapshot`)).json();
  expect(snapshot.selected_team_id).toBe(2);
  writeFileSync(
    `${evidence}/${info.project.name}-route-counts.json`,
    JSON.stringify(await stats(page), null, 2),
  );
});

test("saved cards survive sustained refresh, failure recovery and slow/out-of-order responses", async ({
  page,
}, info) => {
  const sources: unknown[] = [];
  page.on("response", async (response) => {
    if (response.url().includes(`${root}/snapshot`) && response.ok())
      sources.push(await response.json());
  });
  test.setTimeout(210000);
  await openPlan(page);
  await page.evaluate(() => {
    const el = document.querySelector(".waiver-workspace")!;
    (window as unknown as { lost: boolean }).lost = false;
    new MutationObserver(() => {
      if (!el.isConnected) (window as unknown as { lost: boolean }).lost = true;
    }).observe(document.body, { childList: true, subtree: true });
  });
  const before = await stats(page);
  for (let cycle = 0; cycle < 3; cycle++) {
    const pending = page.waitForResponse(
      (r) => r.url().includes(`${root}/snapshot?refresh=true`) && r.ok(),
      { timeout: 70000 },
    );
    // Actual wall-clock interval; no client timer replacement.
    const refreshed = await (await pending).json();
    writeFileSync(
      `${evidence}/${info.project.name}-cycle-${cycle}.json`,
      JSON.stringify(refreshed, null, 2),
    );
    await expect(page.locator(".waiver-workspace")).toHaveAttribute(
      "data-result-state",
      "connected",
    );
    await expect(page.locator(".ww-move")).toHaveCount(2);

    await page.evaluate(() => {
      window.dispatchEvent(new Event("focus"));
      document.dispatchEvent(new Event("visibilitychange"));
    });
  }
  const after = await stats(page);
  writeFileSync(
    `${evidence}/${info.project.name}-lifecycle-sources.json`,
    JSON.stringify(sources, null, 2),
  );
  expect(after[`${root}/plan`]).toBe(before[`${root}/plan`]);
  for (const code of [503, 429, 504]) {
    await control(page, { failures: [code] });
    const pending = page.waitForResponse(
      (r) => r.url().includes(`${root}/snapshot?refresh=true`) && r.status() === code,
    );
    await page.getByRole("button", { name: "Refresh league", exact: true }).click();
    await pending;
    await expect(page.locator(".waiver-workspace")).toHaveAttribute("data-result-state", "stale");
    await expect(page.locator(".ww-move")).toHaveCount(2);
    await page.screenshot({
      path: `${evidence}/${info.project.name}-saved-${code}.png`,
      fullPage: true,
    });
    await control(page, {});
    const recovery = page.waitForResponse(
      (r) => r.url().includes(`${root}/snapshot?refresh=true`) && r.ok(),
    );
    await page.getByRole("button", { name: "Refresh league", exact: true }).click();
    await recovery;
    await expect(page.locator(".waiver-workspace")).toHaveAttribute(
      "data-result-state",
      "connected",
    );
  }
  await control(page, { snapshot_delays: [0.5] });
  const slow = page.waitForResponse(
    (r) => r.url().includes(`${root}/snapshot?refresh=true`) && r.ok(),
  );
  await page.getByRole("button", { name: "Refresh league", exact: true }).click();
  await expect(page.locator(".ww-move")).toHaveCount(2);
  await slow;
  await control(page, { plan_delays: [0.6, 0] });
  await page.getByText("Pickup filters", { exact: true }).click();
  const first = page.waitForRequest((r) => r.url().endsWith(`${root}/plan`));
  await page.getByLabel("Min MPG", { exact: true }).fill("16");
  await first;
  const latest = page.waitForResponse(
    (r) =>
      r.url().endsWith(`${root}/plan`) &&
      r.ok() &&
      r.request().postDataJSON().pickup_filters.min_minutes === 15,
  );
  await page.getByLabel("Min MPG", { exact: true }).fill("15");
  await latest;
  await page.waitForTimeout(800);
  await expect(page.locator(".ww-move")).toHaveCount(2);
  expect(await page.evaluate(() => (window as unknown as { lost: boolean }).lost)).toBe(false);
  await control(page, { failures: [401] });
  const invalid = page.waitForResponse(
    (r) => r.url().includes(`${root}/snapshot?refresh=true`) && r.status() === 401,
  );
  await page.getByText("Pickup filters", { exact: true }).click();
  await page.getByRole("button", { name: "Refresh league", exact: true }).click();
  await invalid;
  await expect(page.locator(".ww-move")).toHaveCount(0);
  writeFileSync(
    `${evidence}/${info.project.name}-cycles.json`,
    JSON.stringify({ before, after, lostStrategy: false }, null, 2),
  );
});

test("qualification boundaries and unknown budget pass through authenticated actual routes", async ({
  page,
}, info) => {
  const records = [];
  for (const [league, reason] of [
    [609, "below_min_minutes"],
    [610, "below_min_games"],
    [611, "below_min_participation"],
    [612, "current_observed_sample_unknown"],
    [613, "unknown_budget"],
  ] as const) {
    const plan = await openPlan(page, league);
    if (league === 613) {
      expect(plan.acquisition_budget.remaining).toBeNull();
      await expect(page.getByText("Available adds need verification")).toBeVisible();
    } else {
      expect(plan.pickup_filter_summary.qualified).toBe(0);
      expect(
        plan.pickup_filter_summary.exclusions.find(
          (row: { player_id: string }) => row.player_id === "100",
        ).reasons,
      ).toContain(reason);
    }
    records.push({ league, reason, plan });
    await page.request.delete(`${root}/connection`, { headers });
  }
  writeFileSync(
    `${evidence}/${info.project.name}-boundaries.json`,
    JSON.stringify(records, null, 2),
  );
});

test("actual mobile touch help and concise failure state", async ({ browser }, info) => {
  const context = await browser.newContext({
    baseURL: info.project.use.baseURL,
    viewport: { width: 390, height: 844 },
    isMobile: true,
    hasTouch: true,
  });
  const page = await context.newPage();
  try {
    await openPlan(page);
    const help = page.getByRole("button", { name: "About full-team net" });
    await help.tap();
    await expect(
      page.getByRole("tooltip").filter({ hasText: "Net includes pickup" }),
    ).toBeVisible();
    await page.screenshot({ path: `${evidence}/${info.project.name}-mobile-touch.png` });
    await help.tap();
    await expect(page.getByRole("tooltip").filter({ hasText: "Net includes pickup" })).toBeHidden();
    await page.getByText("Pickup filters", { exact: true }).tap();
    await page.getByRole("button", { name: "About pickup qualification" }).tap();
    const qualification = page
      .getByRole("tooltip")
      .filter({ hasText: "Current regular-season sample only" });
    await expect(qualification).toBeVisible();
    const bounds = await qualification.boundingBox();
    expect(bounds!.x).toBeGreaterThanOrEqual(0);
    expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(390);
    await page.screenshot({ path: `${evidence}/${info.project.name}-mobile-filter-help.png` });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    await expect(page.locator(".ww-analysis")).not.toHaveAttribute("open");
  } finally {
    await context.close();
  }
});

test("bounded continuation and real active-drop tradeoffs remain honest and visible", async ({
  page,
}, info) => {
  const bounded = await openPlan(page, 614);
  expect(bounded.search.layer_pruned).toBe(true);
  expect(bounded.search.selected_plan_stop_reason).toBe("best_beneficial_explored_continuation");
  expect(bounded.recommended_plan.moves.length).toBeGreaterThan(0);
  await expect(page.getByText("Search limit reached · more moves may help")).toBeVisible();
  writeFileSync(`${evidence}/${info.project.name}-bounded.json`, JSON.stringify(bounded, null, 2));
  await page.request.delete(`${root}/connection`, { headers });
  const active = await openPlan(page, 615, ["PTS", "AST", "STL", "BLK", "3PM"]);
  expect(active.recommended_plan.moves).toHaveLength(2);
  for (const move of active.recommended_plan.moves) {
    expect(move.drop_starts).toBeGreaterThan(0);
    expect(move.arithmetic.categories.reb.net).toBe(-4);
    expect(move.arithmetic.categories.reb.add).toBe(6);
    expect(move.arithmetic.categories.reb.drop).toBe(10);
    expect(Object.keys(move.arithmetic.categories)).toHaveLength(9);
  }
  await expect(page.locator(".ww-move").first()).toContainText("REBAdd 6Drop 10Net -4Loss");
  await expect(page.locator(".ww-analysis")).not.toHaveAttribute("open");
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: `${evidence}/${info.project.name}-active-tradeoffs-desktop.png`,
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: `${evidence}/${info.project.name}-active-tradeoffs-mobile.png`,
    fullPage: true,
  });
  writeFileSync(
    `${evidence}/${info.project.name}-active-tradeoffs.json`,
    JSON.stringify(active, null, 2),
  );
});
test("definitive source auth loss exposes a direct reconnect destination", async ({ page }) => {
  await openPlan(page);
  await control(page, { failures: [401] });
  const invalid = page.waitForResponse(
    (r) => r.url().includes(`${root}/snapshot?refresh=true`) && r.status() === 401,
  );
  await page.getByRole("button", { name: "Refresh league", exact: true }).click();
  await invalid;
  await expect(page.locator(".ww-move")).toHaveCount(0);
  await page.getByRole("link", { name: "Connect ESPN", exact: true }).click();
  await expect(page.getByRole("tab", { name: "Dashboard", exact: true })).toHaveAttribute(
    "aria-selected",
    "true",
  );
});
test("provider cache renewal changes observations without reanalyzing unchanged facts", async ({
  page,
}, info) => {
  await openPlan(page);
  const before = await stats(page);
  const observations = [];
  for (let renewal = 0; renewal < 3; renewal++) {
    await page.request.post("http://127.0.0.1:8214/__test__/v6-reset", {
      data: { league_id: 601 },
    });
    const refreshed = page.waitForResponse(
      (r) => r.url().includes(`${root}/snapshot?refresh=true`) && r.ok(),
    );
    await page.getByRole("button", { name: "Refresh league", exact: true }).click();
    const data = await (await refreshed).json();
    observations.push({
      sample: data.free_agents[0].pickup_sample.sample_as_of,
      denominator: data.free_agents[0].pickup_sample.as_of,
      teamBatch: data.enrichment.team_games_fetched_at,
    });
    await expect(page.locator(".waiver-workspace")).toHaveAttribute(
      "data-result-state",
      "connected",
    );
    await expect(page.locator(".ww-move")).toHaveCount(2);
  }
  const after = await stats(page);
  expect(new Set(observations.map((row) => row.teamBatch)).size).toBe(3);
  expect(after[`${root}/plan`]).toBe(before[`${root}/plan`]);
  writeFileSync(
    `${evidence}/${info.project.name}-cache-renewal.json`,
    JSON.stringify({ before, after, observations }, null, 2),
  );
});
test("confirmed cap fallback stays scoped and does not supply unknown usage", async ({
  page,
}, info) => {
  await openPlan(page, 616);
  await expect(page.getByText("Available adds need verification")).toBeVisible();
  await page.getByText("Full analysis & data", { exact: true }).click();
  await page.getByText("Advanced inputs & data notes", { exact: true }).click();
  const updated = page.waitForResponse((r) => r.url().endsWith(`${root}/plan`) && r.ok());
  await page.getByLabel("My league’s matchup cap fallback", { exact: false }).fill("7");
  const response = await updated;
  const plan = await response.json();
  expect(response.request().postDataJSON().matchup_add_limit_fallback).toBe(7);
  expect(response.request().postDataJSON().used_adds).toBeUndefined();
  expect(plan.acquisition_budget.used).toBe(5);
  expect(plan.acquisition_budget.remaining).toBe(2);
  expect(plan.recommended_plan.moves).toHaveLength(2);
  writeFileSync(
    `${evidence}/${info.project.name}-confirmed-cap.json`,
    JSON.stringify(plan, null, 2),
  );
  await page.request.delete(`${root}/connection`, { headers });
  const other = await openPlan(page, 617);
  expect(other.acquisition_budget.matchup_cap).toBeNull();
  await expect(page.getByText("Available adds need verification")).toBeVisible();
});
test("private manual session and ownership denial use real authenticated routes", async ({
  page,
}) => {
  await pair(page);
  const denied = await page.request.put(`${root}/team`, { headers, data: { team_id: 2 } });
  expect(denied.status()).toBe(403);
  expect((await (await page.request.get(`${root}/status`)).json()).connected).toBe(true);
  await page.request.delete(`${root}/connection`, { headers });
  const connected = await page.request.post(`${root}/connect`, {
    headers,
    data: {
      league_id: 601,
      season_id: 2027,
      team_id: 1,
      swid: "fixture-owner-0001",
      espn_s2: "synthetic-only",
    },
  });
  expect(connected.ok()).toBe(true);
  const status = await connected.json();
  expect(status.ownership_verified).toBe(true);
  expect(status.teams.find((team: { id: number }) => team.id === 2).selectable).toBe(false);
  const rejected = await page.request.put(`${root}/team`, { headers, data: { team_id: 2 } });
  expect(rejected.status()).toBe(403);
  expect((await (await page.request.get(`${root}/status`)).json()).connected).toBe(true);
});
