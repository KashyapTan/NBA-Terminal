import { mkdirSync, writeFileSync } from "node:fs";
import { expect, type Page, test } from "@playwright/test";
import {
  LEAGUE_CATEGORIES,
  type LeagueSnapshot,
  type WaiverPlan,
} from "../src/league-fantasy-model";
import { forecastValue } from "../src/MatchupForecast";

const root = "/api/fantasy/espn";
const headers = { "X-Fantasy-Request": "1" };
const evidence = "../../docs/evidence/v7-integrated";
async function control(page: Page, data: object) {
  expect(
    (await page.request.post("http://127.0.0.1:8217/__test__/v7-control", { data })).ok(),
  ).toBe(true);
}
async function counters(page: Page) {
  return (
    await (await page.request.get("http://127.0.0.1:8217/__test__/connection-control")).json()
  ).calls;
}
function save(name: string, data: unknown) {
  mkdirSync(evidence, { recursive: true });
  writeFileSync(`${evidence}/${name}.json`, JSON.stringify(data, null, 2));
}
async function open(page: Page, league: number) {
  await control(page, { league });
  await page.request.post("http://127.0.0.1:8217/__test__/connection-control", { data: {} });
  await page.goto("/fantasy");
  await page.waitForLoadState("networkidle");
  expect(
    (
      await page.request.post(`${root}/bridge/pair`, {
        headers,
        data: { league_id: league, season_id: 2027, team_id: 1 },
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
          league_id: league,
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
  const response = page.waitForResponse((r) => r.url().endsWith(`${root}/plan`) && r.ok());
  await page.getByRole("tab", { name: "Waiver Wire", exact: true }).click();
  await response;
  await page.getByText("Edit targets", { exact: true }).click();
  const five = ["PTS", "REB", "AST", "STL", "BLK"];
  for (const key of ["3PM", "TO", "FG%", "FT%"]) {
    const box = page.getByRole("checkbox", { name: key, exact: true });
    if (await box.isChecked()) await box.uncheck();
  }
  for (const key of five) await page.getByRole("checkbox", { name: key, exact: true }).check();
  const selected = page.waitForResponse((r) => r.url().endsWith(`${root}/plan`) && r.ok());
  await page.getByRole("button", { name: "Apply five" }).click();
  const plan = (await (await selected).json()) as WaiverPlan;
  await page.getByText("Edit targets", { exact: true }).click();
  await expect(page.locator(".waiver-workspace")).toHaveAttribute("data-result-state", "connected");
  return plan;
}
function arithmetic(plan: WaiverPlan) {
  const before = plan.baseline!;
  const after = plan.projected!;
  for (const side of ["user", "opponent"] as const) {
    const total = side === "user" ? before.totals : before.opponent_totals!;
    for (const key of [
      "pts",
      "reb",
      "ast",
      "stl",
      "blk",
      "threes",
      "to",
      "fgm",
      "fga",
      "ftm",
      "fta",
    ] as const)
      expect(total[key]).toBeCloseTo(
        before.actual_primitives![side][key]! + before.remaining_primitives![side][key]!,
        9,
      );
  }
  expect(after.opponent_totals).toEqual(before.opponent_totals);
  for (const key of LEAGUE_CATEGORIES.map((cat) => cat.key)) {
    const delta = forecastValue(after.totals, key)! - forecastValue(before.totals, key)!;
    if (plan.recommended_plan?.moves.length)
      expect(plan.recommended_plan.arithmetic.categories[key].net).toBeCloseTo(delta, 9);
  }
  for (const move of plan.recommended_plan?.moves ?? []) {
    expect(Object.keys(move.arithmetic!.categories)).toHaveLength(9);
    for (const row of Object.values(move.arithmetic!.primitives))
      expect(row.net).toBeCloseTo(row.add - row.drop + row.spillover, 9);
  }
}
async function rendered(page: Page, plan: WaiverPlan) {
  const table = page.locator(".ww-forecast-table");
  await expect(table.locator("tbody tr")).toHaveCount(9);
  for (const { key } of LEAGUE_CATEGORIES) {
    const row = table.locator(`[data-category="${key}"]`);
    const shown = (n: number | null) =>
      n == null
        ? "—"
        : key.endsWith("pct")
          ? `${(n * 100).toFixed(2)}%`
          : n.toLocaleString("en-US", { maximumFractionDigits: 2 });
    await expect(row.locator("td").nth(0).locator("span")).toHaveText(
      shown(forecastValue(plan.baseline?.actual_primitives?.user, key)),
    );
    await expect(row.locator("td").nth(0).locator("small")).toHaveText(
      shown(forecastValue(plan.baseline?.actual_primitives?.opponent, key)),
    );
    await expect(row.locator("td").nth(1).locator("span")).toHaveText(
      shown(forecastValue(plan.baseline?.totals, key)),
    );
    await expect(row.locator("td").nth(1).locator("small")).toHaveText(
      shown(forecastValue(plan.baseline?.opponent_totals, key)),
    );
    await expect(row.locator("td").nth(2).locator("span")).toHaveText(
      plan.recommended_plan?.moves.length ? shown(forecastValue(plan.projected?.totals, key)) : "—",
    );
  }
}

test("real HTTP3/4 schedules, both rosters, weighted all-nine whole-plan net, ordered cards and responsive help", async ({
  page,
  browser,
}, info) => {
  const plan = await open(page, 702);
  const snapshot = (await (await page.request.get(`${root}/snapshot`)).json()) as LeagueSnapshot;
  save(`${info.project.name}-multi-plan`, plan);
  save(`${info.project.name}-multi-snapshot`, snapshot);
  expect(plan.status, JSON.stringify(plan.reasons)).toBe("ready");
  expect(plan.baseline!.games_by_team).toEqual({ user: 6, opponent: 4 });
  expect(plan.baseline!.totals.pts).toBe(48);
  expect(plan.baseline!.opponent_totals!.pts).toBe(100);
  expect(plan.baseline!.schedule_explanations!["1"].full_week_games).toBe(3);
  expect(plan.recommended_plan!.moves).toHaveLength(2);
  expect(plan.actions[0].add_id).not.toBe(plan.actions[1].add_id);
  expect(plan.recommended_plan!.moves[0].score_after).toBe(
    plan.recommended_plan!.moves[1].score_before,
  );
  expect(plan.projected!.totals.pts).toBe(160);
  expect(plan.projected!.totals.fgm! / plan.projected!.totals.fga!).toBe(0.5);
  for (const move of plan.recommended_plan!.moves) {
    expect(move.schedule_explanations!.add.remaining_games).toBe(4);
    expect(move.schedule_explanations!.add.usable_starts).toBe(4);
    expect(move.drop_starts).toBe(3);
  }
  arithmetic(plan);
  await rendered(page, plan);
  await expect(page.locator('.ww-forecast [data-category="to"] .ww-edge-winning')).toHaveText(
    "Win",
  );
  await expect(page.locator('.ww-forecast [data-category="to"] .ww-edge-losing')).toHaveText(
    "Loss",
  );
  await expect(page.locator(".ww-forecast-score")).toContainText("1–8–0 W–L–T");
  await expect(page.locator(".ww-forecast-score")).toContainText("6–3–0 W–L–T");
  await expect(page.locator(".ww-move")).toHaveCount(2);
  await expect(page.locator(".ww-move").first()).toContainText(
    "ADD 4 games left · 4 usable starts",
  );
  await expect(page.locator(".ww-move").first()).toContainText(
    "DROP 3 games left · 3 usable starts",
  );
  await expect(page.locator('.ww-forecast [data-focus="true"]')).toHaveCount(5);
  await expect(page.locator(".ww-analysis")).not.toHaveAttribute("open");
  expect(
    await page
      .locator(".ww-plan, .ww-forecast, .ww-analysis")
      .evaluateAll((els) => els.map((el) => el.className)),
  ).toEqual(["ww-plan", "ww-forecast", "ww-analysis"]);
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 1000 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    expect(
      await page
        .locator(".ww-forecast-table th, .ww-forecast-table td")
        .evaluateAll((els) => els.every((el) => el.scrollWidth <= el.clientWidth)),
    ).toBe(true);
    await page.screenshot({
      path: `${evidence}/${info.project.name}-${width}.png`,
      fullPage: true,
    });
  }
  for (const name of ["About the matchup forecast", "Games and usable starts for move 1"]) {
    const help = page.getByRole("button", { name, exact: true });
    const tooltip = page.locator(`#${await help.getAttribute("aria-describedby")}`);
    await help.focus();
    await expect(tooltip).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(tooltip).toBeHidden();
  }
  const touch = await browser.newContext({
    storageState: await page.context().storageState(),
    hasTouch: true,
    isMobile: true,
    viewport: { width: 390, height: 844 },
  });
  const mobile = await touch.newPage();
  await mobile.goto(`${info.project.use.baseURL}/fantasy?fantasyTab=waiver`);
  await mobile.getByRole("tab", { name: "Waiver Wire", exact: true }).click();
  await expect(mobile.locator(".ww-forecast-table tbody tr")).toHaveCount(9);
  for (const name of ["About the matchup forecast", "Games and usable starts for move 1"]) {
    const help = mobile.getByRole("button", { name, exact: true });
    const tooltip = mobile.locator(`#${await help.getAttribute("aria-describedby")}`);
    await help.tap();
    await expect(tooltip).toBeVisible();
    const box = await tooltip.boundingBox();
    expect(box!.x).toBeGreaterThanOrEqual(0);
    expect(box!.x + box!.width).toBeLessThanOrEqual(390);
    await help.tap();
    await expect(tooltip).toBeHidden();
  }
  await touch.close();
  save(`${info.project.name}-routes`, await counters(page));
});

test("real HTTP no-deal baseline, midweek banking/2starts, zero starts, capacity and partial/fallback evidence", async ({
  page,
}, info) => {
  for (const league of [701, 703, 704, 705, 706, 707, 708, 709, 710]) {
    const plan = await open(page, league);
    const snapshot = (await (await page.request.get(`${root}/snapshot`)).json()) as LeagueSnapshot;
    save(`${info.project.name}-${league}-plan`, plan);
    save(`${info.project.name}-${league}-snapshot`, snapshot);
    if (league === 706) {
      expect(plan.status).toBe("incomplete");
      expect(plan.recommended_plan).toBeNull();
      await expect(page.locator(".ww-forecast-note")).toContainText("unavailable");
      await expect(
        page.locator('.ww-forecast-table [data-category="pts"] td').nth(1),
      ).toContainText("——Unknown");
      await page.setViewportSize({ width: 390, height: 844 });
      await page.screenshot({
        path: `${evidence}/${info.project.name}-partial-mobile.png`,
        fullPage: true,
      });
      continue;
    }
    arithmetic(plan);
    await rendered(page, plan);
    if (league === 701 || league === 705 || league === 707 || league === 708)
      expect(plan.baseline!.games_by_team).toEqual({ user: 3, opponent: 4 });
    if (league === 705 || league === 708) {
      expect(plan.recommended_plan?.moves ?? []).toHaveLength(0);
      await expect(page.locator(".ww-forecast-note")).toContainText("baseline forecast shown");
      if (league === 705)
        await page.screenshot({
          path: `${evidence}/${info.project.name}-no-deals.png`,
          fullPage: true,
        });
    }
    if (league === 703) {
      expect(plan.baseline!.games_by_team).toEqual({ user: 1, opponent: 2 });
      expect(plan.baseline!.actual_primitives!.user.pts).toBe(47);
      expect(plan.baseline!.actual_primitives!.opponent.pts).toBe(47);
      expect(plan.baseline!.totals.pts).toBe(55);
      expect(plan.baseline!.opponent_totals!.pts).toBe(97);
      expect(plan.baseline!.totals.fgm! / plan.baseline!.totals.fga!).toBeCloseTo(10 / 27, 10);
      expect(plan.baseline!.totals.ftm! / plan.baseline!.totals.fta!).toBeCloseTo(10 / 14, 10);
      expect(plan.projected!.totals.fgm! / plan.projected!.totals.fga!).toBeCloseTo(21 / 47, 10);
      expect(plan.projected!.totals.ftm! / plan.projected!.totals.fta!).toBeCloseTo(15 / 20, 10);
      const move = plan.recommended_plan!.moves[0];
      expect(move.schedule_explanations!.add.full_week_games).toBe(4);
      expect(move.schedule_explanations!.add.remaining_games).toBe(2);
      expect(move.add_starts).toBe(2);
      expect(
        move.schedule_explanations!.add.exclusions.some(
          (r) => r.reason === "already_started_or_banked",
        ),
      ).toBe(true);
      await expect(page.locator(".ww-move").first()).toContainText(
        "2 games left · 2 usable starts",
      );
    }
    if (league === 704) {
      expect(plan.baseline!.games_by_team!.user).toBe(0);
      expect(plan.baseline!.schedule_explanations!["1"].remaining_games).toBe(3);
      expect(plan.baseline!.schedule_explanations!["1"].usable_starts).toBe(0);
      expect(
        plan.baseline!.schedule_explanations!["1"].exclusions.some(
          (r) => r.reason === "inactive_or_ir",
        ),
      ).toBe(true);
    }
    if (league === 709 || league === 710) {
      const own = ["1", "9001"].map((id) => plan.baseline!.schedule_explanations![id]);
      expect(own.map((p) => p.usable_starts).sort()).toEqual([0, league === 710 ? 2 : 3]);
      if (league === 710)
        for (const player of own) {
          expect(player.full_week_games).toBe(4);
          expect(player.remaining_games).toBe(2);
        }
      expect(
        own.some((p) => p.exclusions.some((r) => r.reason === "lineup_capacity_or_policy")),
      ).toBe(true);
    }
    if (league === 707) {
      expect(snapshot.period.schedule_coverage!.fallback).toBe(true);
      await expect(page.locator(".ww-forecast")).toContainText("ESPN schedule · fallback");
    }
  }
});

test("actual unchanged observation/cache refresh stays stable; schedule changes recompute; failures keep saved read-only", async ({
  page,
}, info) => {
  const first = await open(page, 702);
  await page.getByText("Pickup filters", { exact: true }).click();
  const filtered = page.waitForResponse((r) => r.url().endsWith(`${root}/plan`) && r.ok());
  await page.getByLabel("Min MPG").fill("16");
  await filtered;
  await expect(page.getByLabel("Min MPG")).toHaveValue("16");
  await page.getByText("Full analysis & data", { exact: true }).click();
  const calls = (await counters(page))[`${root}/plan`];
  const snapshots = [];
  for (const seconds of [60, 120, 360]) {
    await control(page, { seconds });
    const response = page.waitForResponse(
      (r) => r.url().includes(`${root}/snapshot?refresh=true`) && r.ok(),
    );
    await page.getByRole("button", { name: "Refresh league", exact: true }).click();
    snapshots.push(await (await response).json());
    await expect(page.locator(".waiver-workspace")).toHaveAttribute(
      "data-result-state",
      "connected",
    );
    expect((await counters(page))[`${root}/plan`]).toBe(calls);
    await expect(page.getByLabel("Min MPG")).toHaveValue("16");
    await expect(page.locator(".ww-analysis")).toHaveAttribute("open");
    await expect(page.locator(".ww-move")).toHaveCount(2);
  }
  save(`${info.project.name}-refresh-snapshots`, snapshots);
  await control(page, { changed: true, seconds: 720 });
  const response = page.waitForResponse((r) => r.url().endsWith(`${root}/plan`) && r.ok());
  await page.getByRole("button", { name: "Refresh league", exact: true }).click();
  const changed = (await (await response).json()) as WaiverPlan;
  save(`${info.project.name}-changed-plan`, changed);
  expect(changed.projected!.totals.pts).not.toBe(first.projected!.totals.pts);
  expect(changed.projected!.schedule_explanations!["100"].remaining_games).toBe(3);
  await expect(page.locator(".ww-move").filter({ hasText: "4 games left" })).not.toHaveCount(0);
  await expect(page.locator(".ww-analysis")).toHaveAttribute("open");
  await page.request.post("http://127.0.0.1:8217/__test__/connection-control", {
    data: { failures: [503] },
  });
  await page.getByRole("button", { name: "Refresh league", exact: true }).click();
  await expect(page.getByText("Saved plan · read-only", { exact: true })).toBeVisible();
  await expect(page.locator(".ww-move")).toHaveCount(changed.recommended_plan!.moves.length);
  await expect(page.locator(".ww-forecast")).toContainText("Saved · read-only");
  save(`${info.project.name}-refresh-routes`, await counters(page));
});

test("actual ESPN fallback schedule edits and cached-snapshot tipoff locks invalidate the right facts", async ({
  page,
}, info) => {
  const before = await open(page, 707);
  await control(page, { changed: true, seconds: 360 });
  const updated = page.waitForResponse((r) => r.url().endsWith(`${root}/plan`) && r.ok());
  await page.getByRole("button", { name: "Refresh league", exact: true }).click();
  const after = (await (await updated).json()) as WaiverPlan;
  save(`${info.project.name}-espn-changed-plan`, after);
  expect(after.actions[0].add_id).not.toBe(before.actions[0].add_id);
  expect(after.baseline!.schedule_explanations!["100"].remaining_games).toBe(3);
  const ready = await open(page, 701);
  const snapshot = (await (await page.request.get(`${root}/snapshot`)).json()) as LeagueSnapshot;
  await control(page, { seconds: 30000 });
  const lockedResponse = await page.request.post(`${root}/plan`, {
    headers,
    data: {
      context: {
        league_id: 701,
        season_id: 2027,
        team_id: 1,
        matchup_period_id: 3,
        fetched_at: snapshot.fetched_at,
      },
      selected_categories: ready.selected_categories,
    },
  });
  expect(lockedResponse.ok()).toBe(true);
  const locked = (await lockedResponse.json()) as WaiverPlan;
  save(`${info.project.name}-newly-locked-plan`, locked);
  expect(locked.projection_metadata!["newly_started:user"].complete).toBe(false);
  expect(locked.evaluation_state).toBe("required_inputs_unknown");
  expect(locked.actions).toHaveLength(0);
});
