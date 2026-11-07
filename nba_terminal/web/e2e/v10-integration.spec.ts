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
const evidence = process.env.EVIDENCE_DIR || "../../docs/evidence/v10-dated-forecast";
const rawEvidence = process.env.V10_RAW_EVIDENCE_DIR || "test-results/v10-raw";
function save(name: string, data: unknown) {
  mkdirSync(rawEvidence, { recursive: true });
  writeFileSync(`${rawEvidence}/${name}.json`, JSON.stringify(data, null, 2));
}
async function open(page: Page, phase: string, beneficial = false, day = "2026-11-06") {
  await page.request.post("http://127.0.0.1:8219/__test__/v10-control", {
    data: { phase, beneficial, day, now: null },
  });
  await page.request.post("http://127.0.0.1:8219/__test__/connection-control", { data: {} });
  await page.goto("/fantasy");
  await page.waitForLoadState("networkidle");
  expect(
    (
      await page.request.post(`${root}/bridge/pair`, {
        headers,
        data: { league_id: 1001, season_id: 2027, team_id: 1 },
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
          league_id: 1001,
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
  const five = ["REB", "AST", "STL", "3PM", "TO"];
  for (const key of ["PTS", "BLK", "FG%", "FT%"]) {
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
async function control(page: Page, data: object) {
  expect(
    (await page.request.post("http://127.0.0.1:8219/__test__/v10-control", { data })).ok(),
  ).toBe(true);
}
async function refresh(page: Page) {
  const response = page.waitForResponse((r) => r.url().endsWith(`${root}/plan`) && r.ok());
  await page.getByRole("button", { name: "Refresh league", exact: true }).click();
  return (await (await response).json()) as WaiverPlan;
}
function conservation(plan: WaiverPlan) {
  for (const f of [plan.baseline!, plan.projected!]) {
    for (const owner of ["user", "opponent"] as const) {
      const rows = f.daily_lineups!.filter((d) => d.owner === owner);
      const total = owner === "user" ? f.totals : f.opponent_totals!;
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
      ]) {
        const projected = rows
          .flatMap((d) => d.players.filter((p) => p.state === "start"))
          .reduce((n, p) => n + (p.rates[key] ?? 0), 0);
        expect(total[key]).toBeCloseTo(f.actual_primitives![owner][key]! + projected, 8);
      }
      for (const d of rows)
        expect(d.players.filter((p) => p.state === "start").length).toBeLessThanOrEqual(10);
    }
    expect(forecastValue(f.totals, "fg_pct")).not.toBeNull();
    expect(forecastValue(f.totals, "ft_pct")).not.toBeNull();
  }
  expect(plan.projected!.opponent_totals).toEqual(plan.baseline!.opponent_totals);
}
test("Sunday retains interim starts but rejects screenshot four-to-three category result", async ({
  page,
}, info) => {
  const plan = await open(page, "after-first");
  expect(plan.status, JSON.stringify(plan.reasons)).toBe("ready");
  const observed = (await (await page.request.get(`${root}/snapshot`)).json()) as LeagueSnapshot;
  expect(observed.free_agents.find((p) => p.id === "101")!.current_games).toBe(7);
  expect(plan.actions).toHaveLength(0);
  expect(plan.remaining_adds).toBe(1);
  expect(plan.outcome_policy!.baseline.all_nine.wins).toBe(4);
  for (const [key, value] of Object.entries({
    pts: 655.1,
    reb: 200.4,
    ast: 135,
    stl: 41.7,
    blk: 22.3,
    threes: 83.4,
    to: 73.7,
  }))
    expect(plan.baseline!.totals[key]).toBeCloseTo(value, 8);
  for (const [key, value] of Object.entries({
    pts: 686.2,
    reb: 215,
    ast: 130.9,
    stl: 36.8,
    blk: 37.9,
    threes: 80.9,
    to: 74.2,
  }))
    expect(plan.baseline!.opponent_totals![key]).toBeCloseTo(value, 8);
  expect(forecastValue(plan.baseline!.totals, "fg_pct")).toBeCloseTo(0.464, 8);
  expect(forecastValue(plan.baseline!.totals, "ft_pct")).toBeCloseTo(0.696, 8);
  expect(plan.baseline!.totals.to).toBeCloseTo(73.7, 8);
  expect(plan.baseline!.totals.pts).toBeCloseTo(655.1, 8);
  const sunday = plan.outcome_policy!.examples.find((e) => e.actions[0].date === "2026-11-08")!;
  const today = plan.outcome_policy!.examples.find((e) => e.actions[0].date === "2026-11-06")!;
  expect(sunday.all_nine.wins).toBe(3);
  expect(sunday.totals.to).toBeCloseTo(74.8, 8);
  expect(sunday.totals.pts).toBeCloseTo(666.7, 8);
  expect(forecastValue(sunday.totals, "fg_pct")).toBeCloseTo(0.4648, 8);
  expect(forecastValue(sunday.totals, "ft_pct")).toBeCloseTo(0.6958, 8);
  expect(sunday.starts.filter((s) => s.player_id === "100").map((s) => s.date)).toEqual([
    "2026-11-06",
    "2026-11-07",
  ]);
  expect(today.starts.filter((s) => s.player_id === "100")).toHaveLength(0);
  expect(today.totals.to).toBeCloseTo(74.2, 8);
  conservation(plan);
  await expect(page.locator(".ww-stop")).toContainText("Keep current roster");
  await expect(page.locator(".ww-forecast-score")).toContainText("4–5–0");
  await expect(page.locator(".ww-analysis")).not.toHaveAttribute("open");
  await expect(page.locator(".ww-forecast")).toContainText("ESPN schedule · fallback");
  save(`${info.project.name}-screenshot-shape`, plan);
  for (const [label, width, height] of [
    ["desktop", 1440, 1000],
    ["mobile", 390, 844],
  ] as const) {
    await page.setViewportSize({ width, height });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    await page.screenshot({
      path: `${evidence}/${info.project.name}-no-move-${label}.png`,
      fullPage: true,
    });
  }
});
test("executed moves refresh authoritative ownership quota and banking without replaying old plan", async ({
  page,
}, info) => {
  let calls = 0;
  page.on("request", (r) => {
    if (r.url().endsWith(`${root}/plan`)) calls++;
  });
  const before = await open(page, "before");
  save(`${info.project.name}-before-executed`, before);
  expect(before.actions.some((a) => a.add_id === "100" && a.drop_id === "1")).toBe(true);
  await control(page, { phase: "after-first" });
  const after = await refresh(page);
  save(`${info.project.name}-after-first`, after);
  expect(after.actions).toHaveLength(0);
  expect(after.acquisition_budget!.used).toBe(1);
  expect(after.remaining_adds).toBe(1);
  const snapshot = (await (await page.request.get(`${root}/snapshot`)).json()) as LeagueSnapshot;
  save(`${info.project.name}-owned-snapshot`, snapshot);
  const ids = snapshot.teams.find((t) => t.id === 1)!.roster.map((p) => p.id);
  expect(ids).toContain("100");
  expect(ids).not.toContain("1");
  const count = calls;
  const observed = page.waitForResponse(
    (r) => r.url().includes(`${root}/snapshot?refresh=true`) && r.ok(),
  );
  await page.getByRole("button", { name: "Refresh league", exact: true }).click();
  await observed;
  await expect(page.locator(".waiver-workspace")).toHaveAttribute("data-result-state", "connected");
  expect(calls).toBe(count);
  await control(page, { beneficial: true });
  const good = await refresh(page);
  expect(good.actions).toHaveLength(1);
  expect(good.actions[0].date).toBe("2026-11-08");
  expect(good.outcome_policy!.projected.all_nine.wins).toBe(5);
  expect(good.actions[0].realized!.dates).toEqual(["2026-11-08"]);
  expect(good.projected!.starts!.filter((s) => s.player_id === "100").map((s) => s.date)).toEqual([
    "2026-11-06",
    "2026-11-07",
  ]);
  conservation(good);
  const daily = page.getByRole("region", { name: "Daily lineup", exact: true });
  await daily.getByLabel("Lineup day").selectOption("2026-11-08");
  await daily.getByRole("checkbox", { name: "Preview after planned moves" }).check();
  await expect(daily.getByRole("list", { name: "Start players", exact: true })).toContainText(
    "Derrick Jones Jr.",
  );
  await daily.getByLabel("Lineup day").selectOption("2026-11-06");
  await expect(daily.getByRole("list", { name: "Start players", exact: true })).toContainText(
    "Sam Merrill",
  );
  await expect(daily.getByRole("list", { name: "Start players", exact: true })).not.toContainText(
    "Derrick Jones Jr.",
  );
  await daily.getByRole("checkbox", { name: "Preview after planned moves" }).uncheck();
  save(`${info.project.name}-beneficial`, good);
  await expect(page.locator(".ww-moves")).toContainText("Effective 2026-11-08");
  await expect(page.getByRole("region", { name: "Final plan get lose and net" })).toBeVisible();
  for (const [label, width, height] of [
    ["desktop", 1440, 1000],
    ["mobile", 390, 844],
  ] as const) {
    await page.setViewportSize({ width, height });
    await page.screenshot({
      path: `${evidence}/${info.project.name}-beneficial-${label}.png`,
      fullPage: true,
    });
  }
  await control(page, { phase: "after-second", day: "2026-11-08" });
  const completed = await refresh(page);
  expect(completed.acquisition_budget!.used).toBe(2);
  expect(completed.actions).toHaveLength(0);
  expect(completed.remaining_adds).toBe(0);
  expect(completed.baseline!.actual_primitives!.user.to).toBeCloseTo(39.6, 8);
  expect(completed.baseline!.starts!.filter((s) => s.player_id === "100")).toHaveLength(0);
  expect(
    completed.baseline!.starts!.filter((s) => s.player_id === "101").map((s) => s.date),
  ).toEqual(["2026-11-08"]);
  conservation(completed);
  for (const key of ["pts", "reb", "ast", "stl", "blk", "threes", "to", "fgm", "fga", "ftm", "fta"])
    expect(completed.baseline!.totals[key]).toBeCloseTo(good.projected!.totals[key]!, 8);
  expect(completed.baseline!.opponent_totals).toEqual(good.projected!.opponent_totals);
  save(`${info.project.name}-after-executed`, completed);
});

test("ET scoring boundary and started game stay banked with no future duplicate", async ({
  page,
}, info) => {
  await open(page, "after-first");
  await control(page, { now: "2026-11-07T01:00:00+00:00" });
  const live = await refresh(page);
  expect(live.baseline!.actual_primitives!.user.to).toBe(39);
  expect(live.baseline!.starts!.filter((s) => s.player_id === "100").map((s) => s.date)).toEqual([
    "2026-11-07",
  ]);
  const locked = live
    .baseline!.daily_lineups!.flatMap((d) => d.players)
    .filter((p) => p.player_id === "100" && p.state === "locked");
  expect(locked.length).toBeGreaterThan(0);
  conservation(live);
  await control(page, { now: "2026-11-07T05:01:00+00:00", day: "2026-11-07" });
  const midnight = await refresh(page);
  expect(midnight.baseline!.actual_primitives!.user.to).toBeCloseTo(39.3, 8);
  expect(
    midnight.baseline!.starts!.filter((s) => s.player_id === "100").map((s) => s.date),
  ).toEqual(["2026-11-07"]);
  expect(midnight.baseline!.totals.to).toBeCloseTo(73.7, 8);
  conservation(midnight);
  save(`${info.project.name}-et-banking`, midnight);
});
