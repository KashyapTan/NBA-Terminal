import { mkdirSync } from "node:fs";
import { resolve } from "node:path";
import { expect, type Page, test } from "@playwright/test";
import { LEAGUE_CATEGORIES, type WaiverPlan } from "../src/league-fantasy-model";

// Real HTTP routes, normalizer, auth/session and planner; only external transport is synthetic.
async function connect(page: Page, league = 123) {
  await page.goto("/fantasy");
  await expect(page.getByRole("tab", { name: "Dashboard" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await page.getByText("Manual or public league fallback", { exact: true }).click();
  await page.getByLabel("Manual league ID", { exact: true }).fill(String(league));
  await page.getByLabel("Manual season ending year").fill("2027");
  await page.getByRole("button", { name: "Connect manually", exact: true }).click();
  if (league !== 126) {
    await expect(page.getByLabel("Your ESPN team")).toBeEnabled();
    await page.getByLabel("Your ESPN team").selectOption("1");
    await expect(page.getByText("Current opponent: Fixture Team 2", { exact: true })).toBeVisible();
  }
}
test("production API returns one coherent pair, visible all-nine arithmetic and rerun controls", async ({
  page,
}, info) => {
  await connect(page);
  await page.getByRole("tab", { name: "Matchups", exact: true }).click();
  const compared = page.getByLabel("Compare league team");
  await expect(compared.locator("option")).toHaveCount(13);
  await expect(page.locator(".category-row")).toHaveCount(9);
  await compared.selectOption("14");
  await expect(page.getByLabel("0 wins, 0 losses, 9 ties")).toBeVisible();
  await compared.selectOption("2");
  const evidence = resolve(
    process.cwd(),
    process.env.V5_EVIDENCE_DIR || "../../code_review/v5_app/generated/fantasy",
  );
  mkdirSync(evidence, { recursive: true });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({
    path: resolve(evidence, `${info.project.name}-matchups-desktop.png`),
    fullPage: true,
  });
  const response = page.waitForResponse(
    (r) => r.url().endsWith("/api/fantasy/espn/plan") && r.ok(),
  );
  await page.getByRole("tab", { name: "Waiver Wire", exact: true }).click();
  const plan = (await (await response).json()) as WaiverPlan;
  expect(plan.status, JSON.stringify(plan.reasons)).toBe("ready");
  expect(plan.recommended_plan!.budget_before).toBe(1);
  expect(plan.recommended_plan!.moves).toHaveLength(1);
  expect(plan.selected_categories).toHaveLength(5);
  const primary = page.getByRole("region", { name: "Recommended ordered plan" });
  await expect(primary.locator(".pickup-list > li")).toHaveCount(1);
  await expect(primary).toContainText("0 acquisitions left");
  const move = plan.recommended_plan!.moves[0];
  expect(move.drop_id).not.toBe("1001");
  expect(Object.keys(move.arithmetic!.primitives)).toHaveLength(11);
  for (const primitive of Object.values(move.arithmetic!.primitives)) {
    expect(primitive.before + primitive.add - primitive.drop + primitive.spillover).toBeCloseTo(
      primitive.after,
      8,
    );
    expect(primitive.after - primitive.before).toBeCloseTo(primitive.net, 8);
  }
  const calculation = primary.getByRole("region", { name: "All nine move calculations" });
  await expect(calculation.locator("tbody tr")).toHaveCount(9);
  for (const { key, label } of LEAGUE_CATEGORIES) {
    const row = calculation.getByRole("row").filter({
      has: page.getByRole("rowheader", { name: key === "to" ? "TO ↓" : label, exact: true }),
    });
    await expect(row).toBeVisible();
    await expect(row).not.toContainText("Unavailable");
    await expect(row).not.toContainText("?");
  }
  await expect(
    primary.getByRole("region", { name: "Overall plan category changes" }).locator("tbody tr"),
  ).toHaveCount(9);
  await expect(primary).toContainText("rate sample:");
  await expect(page.locator(".waiver-budget")).toContainText("6 used");
  await expect(page.locator(".waiver-budget b")).toHaveText("1");
  await expect(page.locator(".category-strategy-grid article")).toHaveCount(9);
  await expect(page.getByText(/Optional competing single-move alternatives/)).toBeVisible();
  await page.screenshot({
    path: resolve(evidence, `${info.project.name}-waiver-desktop.png`),
    fullPage: true,
  });
  await primary.screenshot({ path: resolve(evidence, `${info.project.name}-plan-desktop.png`) });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect
    .poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth))
    .toBe(true);
  await page.screenshot({
    path: resolve(evidence, `${info.project.name}-waiver-mobile.png`),
    fullPage: true,
  });
  await primary.screenshot({ path: resolve(evidence, `${info.project.name}-plan-mobile.png`) });
  await primary
    .getByRole("heading", { name: "Best explored add/drop sequence" })
    .scrollIntoViewIfNeeded();
  await page.screenshot({ path: resolve(evidence, `${info.project.name}-mobile-viewport.png`) });
  const coreResponse = page.waitForResponse(
    (r) => r.url().endsWith("/plan") && r.request().postDataJSON()?.allow_core_drops === true,
  );
  await page.getByLabel("Allow core-player drops for this analysis").check();
  expect((await coreResponse).status()).toBe(200);
  await page.getByText("Edit availability & roster protection", { exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Protect Fixture Player 1001", exact: true }),
  ).toBeDisabled();
  const availabilityResponse = page.waitForResponse(
    (r) =>
      r.url().endsWith("/plan") &&
      r.request().postDataJSON()?.player_overrides?.["1"]?.injured === true,
  );
  await page
    .getByRole("button", { name: "Fixture Player 1 availability: Available", exact: true })
    .click();
  expect((await availabilityResponse).status()).toBe(200);
  await page.route("**/api/fantasy/espn/plan", (route) =>
    route.fulfill({ status: 503, json: { detail: "test busy" } }),
  );
  await page
    .getByRole("button", { name: "Fixture Player 1 availability: Out", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText("Analysis could not be loaded");
  await page.unroute("**/api/fantasy/espn/plan");
  await page.getByRole("button", { name: "Retry analysis", exact: true }).click();
  await expect(primary.locator(".pickup-list > li")).toHaveCount(1);
  await page.getByRole("tab", { name: "Dashboard", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Your fantasy workspace" })).toBeVisible();
});

test("private cookie flow uses the local session and enforces selectable ownership", async ({
  page,
}) => {
  await page.goto("/fantasy");
  await page.getByText("Manual or public league fallback", { exact: true }).click();
  await page.getByLabel("Manual league ID", { exact: true }).fill("123");
  await page.getByLabel("Manual season ending year").fill("2027");
  await page.getByLabel("Private league", { exact: true }).check();
  await page.getByLabel("SWID", { exact: true }).fill("fixture-owner-0001");
  await page.getByLabel("espn_s2", { exact: true }).fill("synthetic-cookie-test-only");
  await page.getByRole("button", { name: "Connect manually", exact: true }).click();
  await expect(page.getByLabel("Your ESPN team")).toBeEnabled();
  await expect(page.getByLabel("Your ESPN team").locator('option[value="2"]')).toHaveAttribute(
    "disabled",
    "",
  );
  await page.getByLabel("Your ESPN team").selectOption("1");
  await expect(page.getByText(/Team ownership verified/)).toBeVisible();
  const wrongTeam = await page.request.put("/api/fantasy/espn/team", {
    headers: { "X-Fantasy-Request": "1" },
    data: { team_id: 2 },
  });
  expect(wrongTeam.status()).toBe(403);
  const denied = await page.request.post("/api/fantasy/espn/plan", {
    headers: { Origin: "http://evil.test", "X-Fantasy-Request": "1" },
    data: {},
  });
  expect(denied.status()).toBe(403);
  expect(await page.evaluate(() => JSON.stringify(localStorage))).not.toContain("synthetic-cookie");
  expect(await page.evaluate(() => document.cookie)).not.toContain("nba_espn_session");
  await page.getByRole("button", { name: "Disconnect ESPN" }).click();
});

test("missing schedules, unsupported formats and failed connections stay honest", async ({
  page,
}) => {
  await connect(page, 124);
  await page.getByRole("tab", { name: "Waiver Wire", exact: true }).click();
  await expect(
    page.getByRole("region", { name: "Recommended ordered plan" }).locator(".pickup-list > li"),
  ).toHaveCount(0);
  await expect(page.getByRole("region", { name: "Waiver evaluation status" })).toContainText(
    "not yet determinable",
  );
  await page.getByText(/Evaluation diagnostics/).click();
  await expect(page.getByText(/matchup_calendar: ESPN scoring-date anchor/).first()).toBeVisible();
  const fallbackSnapshot = await (await page.request.get("/api/fantasy/espn/snapshot")).json();
  expect(fallbackSnapshot.free_agents[0].schedule_source).toBe("nba_schedule");
  expect(fallbackSnapshot.free_agents[0].current_rates_source).toBe("nba_stats");
  await page.getByRole("tab", { name: "Dashboard", exact: true }).click();
  await page.getByRole("button", { name: "Disconnect ESPN", exact: true }).click();
  await connect(page, 125);
  await page.getByRole("tab", { name: "Waiver Wire", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Only head-to-head standard nine-category");
  await page.getByRole("tab", { name: "Dashboard", exact: true }).click();
  await page.getByRole("button", { name: "Disconnect ESPN", exact: true }).click();
  await connect(page, 126);
  await expect(page.getByRole("alert")).toContainText("could not be loaded");
  await expect(page.getByLabel("Your ESPN team")).toHaveCount(0);
});

test("selected-five edits and saved league cap fallback use actual planner routes", async ({
  page,
}) => {
  await connect(page, 129);
  await page.getByRole("tab", { name: "Waiver Wire", exact: true }).click();
  await expect(page.locator(".waiver-budget")).toContainText("League fallback cap (7)");
  await expect(page.locator(".waiver-budget b")).toHaveText("1");
  await page.getByText("Edit selected five categories", { exact: true }).click();
  const desired = ["pts", "reb", "ast", "stl", "to"];
  for (const category of LEAGUE_CATEGORIES) {
    await page
      .locator(".category-picker")
      .getByRole("checkbox", { name: category.label, exact: true })
      .setChecked(desired.includes(category.key));
  }
  const selection = page.waitForResponse(
    (r) =>
      r.url().endsWith("/plan") &&
      r.ok() &&
      r.request().postDataJSON()?.selected_categories?.length === 5,
  );
  await page.getByRole("button", { name: "Recalculate selected five" }).click();
  expect((await (await selection).json()).selected_categories.sort()).toEqual(desired.sort());
  await page.reload();
  await expect(page.locator(".waiver-budget b")).toHaveText("1");
  expect(
    await page.evaluate(() => localStorage.getItem("nba-terminal:matchup-cap:129:2027")),
  ).toBeNull();
  expect(
    await page.evaluate(() => localStorage.getItem("nba-terminal:matchup-cap:123:2027")),
  ).toBeNull();
});

test("real routes preserve two-move ownership and nonzero 30-PTS drop arithmetic", async ({
  page,
}) => {
  await connect(page, 131);
  const initial = page.waitForResponse((r) => r.url().endsWith("/plan") && r.ok());
  await page.getByRole("tab", { name: "Waiver Wire", exact: true }).click();
  const multi = (await (await initial).json()) as WaiverPlan;
  expect(multi.recommended_plan!.budget_before).toBe(2);
  expect(multi.recommended_plan!.moves).toHaveLength(2);
  const owned = new Set(
    (await (await page.request.get("/api/fantasy/espn/snapshot")).json()).teams[0].roster.map(
      (p: { id: string }) => p.id,
    ),
  );
  for (const move of multi.recommended_plan!.moves) {
    expect(owned.has(move.drop_id)).toBe(true);
    expect(owned.has(move.add_id)).toBe(false);
    owned.delete(move.drop_id);
    owned.add(move.add_id);
  }
  await expect(
    page.getByRole("region", { name: "Recommended ordered plan" }).locator(".pickup-list > li"),
  ).toHaveCount(2);
  await page.getByRole("tab", { name: "Dashboard", exact: true }).click();
  await page.getByRole("button", { name: "Disconnect ESPN", exact: true }).click();
  await connect(page, 132);
  const coreBaseline = page.waitForResponse((r) => r.url().endsWith("/plan") && r.ok());
  await page.getByRole("tab", { name: "Waiver Wire", exact: true }).click();
  await coreBaseline;
  await page.getByText("Edit selected five categories", { exact: true }).click();
  const desired = ["ast", "reb", "stl", "blk", "to"];
  for (const category of LEAGUE_CATEGORIES) {
    await page
      .locator(".category-picker")
      .getByRole("checkbox", { name: category.label, exact: true })
      .setChecked(desired.includes(category.key));
  }
  const selected = page.waitForResponse(
    (r) =>
      r.url().endsWith("/plan") && r.request().postDataJSON()?.selected_categories?.length === 5,
  );
  await page.getByRole("button", { name: "Recalculate selected five" }).click();
  const protectedPlan = (await (await selected).json()) as WaiverPlan;
  expect(protectedPlan.recommended_plan!.moves).toHaveLength(0);
  expect(protectedPlan.protected_players!["1"]).toContain("Default core protection");
  const overrideResponse = page.waitForResponse(
    (r) => r.url().endsWith("/plan") && r.request().postDataJSON()?.allow_core_drops === true,
  );
  await page.getByLabel("Allow core-player drops for this analysis").check();
  const result = (await (await overrideResponse).json()) as WaiverPlan;
  expect(result.recommended_plan!.moves).toHaveLength(1);
  const move = result.recommended_plan!.moves[0];
  expect(move.drop_starts).toBeGreaterThan(0);
  expect(move.calculation!.pts!.drop_rate).toBe(30);
  expect(move.calculation!.pts!.add_rate).toBe(0);
  expect(move.arithmetic!.categories.pts.net).toBeLessThan(0);
  expect(move.arithmetic!.categories.ast.net).toBeGreaterThan(0);
  const primary = page.getByRole("region", { name: "Recommended ordered plan" });
  const pts = primary
    .getByRole("region", { name: "All nine move calculations" })
    .getByRole("row", { name: /PTS/ });
  await expect(pts).toContainText(`30 × ${move.drop_starts} lost starts`);
  await expect(pts.locator(".league-losing")).toContainText(
    String(move.arithmetic!.categories.pts.net),
  );
});

test("unknown budget displays conditional pairs without a false no-benefit conclusion", async ({
  page,
}, info) => {
  await connect(page, 130);
  await page.getByRole("tab", { name: "Waiver Wire", exact: true }).click();
  const status = page.getByRole("region", { name: "Waiver evaluation status" });
  await expect(status).toContainText("Acquisition budget unknown");
  await expect(status).toContainText("no transaction is confirmed");
  await expect(
    page.getByText(
      "No materially beneficial legal ordered plan passed the selected-category guards.",
      { exact: true },
    ),
  ).toHaveCount(0);
  await expect(page.locator(".secondary-alternatives")).toHaveAttribute("open", "");
  await expect(page.locator(".secondary-alternatives .pickup-list > li").first()).toBeVisible();
  const evidence = resolve(
    process.cwd(),
    process.env.V5_EVIDENCE_DIR || "../../code_review/v5_app/generated/fantasy",
  );
  mkdirSync(evidence, { recursive: true });
  for (const [name, width, height] of [
    ["desktop", 1440, 1000],
    ["mobile", 390, 844],
  ] as const) {
    await page.setViewportSize({ width, height });
    await expect
      .poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth))
      .toBe(true);
    await page.screenshot({
      path: resolve(evidence, `${info.project.name}-conditional-${name}.png`),
      fullPage: true,
    });
    await status.screenshot({ path: resolve(evidence, `${info.project.name}-status-${name}.png`) });
  }
  await page.getByRole("button", { name: "Review missing inputs & recovery controls" }).click();
  await expect(page.getByLabel("Use my verified matchup counts")).toBeVisible();
});
