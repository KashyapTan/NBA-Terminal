import { mkdirSync, writeFileSync } from "node:fs";
import { expect, type Page, test } from "@playwright/test";
import { LEAGUE_CATEGORIES, type WaiverPlan } from "../src/league-fantasy-model";
import { forecastValue } from "../src/MatchupForecast";
const root = "/api/fantasy/espn";
const headers = { "X-Fantasy-Request": "1" };
const rawEvidence = process.env.OPPONENT_RAW_EVIDENCE_DIR || "test-results/opponent-raw";
function save(name: string, data: unknown) {
  mkdirSync(rawEvidence, { recursive: true });
  writeFileSync(`${rawEvidence}/${name}.json`, JSON.stringify(data, null, 2));
}
let preferences: Record<string, unknown>;
async function open(page: Page) {
  await page.request.post("http://127.0.0.1:8219/__test__/opponent-control", {
    data: { bench: true, count: 8, rate_change: false },
  });
  await page.request.post("http://127.0.0.1:8219/__test__/connection-control", { data: {} });
  await page.goto("/fantasy");
  await page.waitForLoadState("networkidle");
  expect(
    (
      await page.request.post(`${root}/bridge/pair`, {
        headers,
        data: { league_id: 701, season_id: 2027, team_id: 1 },
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
          league_id: 701,
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
  const selectedResponse = await selected;
  preferences = selectedResponse.request().postDataJSON();
  const plan = (await selectedResponse.json()) as WaiverPlan;
  await page.getByText("Edit targets", { exact: true }).click();
  await expect(page.locator(".waiver-workspace")).toHaveAttribute("data-result-state", "connected");
  return plan;
}

async function refresh(page: Page, state: object) {
  expect(
    (
      await page.request.post("http://127.0.0.1:8219/__test__/opponent-control", { data: state })
    ).ok(),
  ).toBe(true);
  const response = page.waitForResponse((r) => r.url().includes(`${root}/snapshot`) && r.ok());
  await page.getByRole("button", { name: "Refresh league", exact: true }).click();
  const snapshot = await (await response).json();
  // An equivalent snapshot correctly reuses the browser cache. Explicitly replay
  // the real planner route as well, with the UI's original confirmed inputs.
  preferences.context = { ...(preferences.context as object), fetched_at: snapshot.fetched_at };
  const planned = await page.request.post(`${root}/plan`, { headers, data: preferences });
  expect(planned.ok()).toBe(true);
  return (await planned.json()) as WaiverPlan;
}
function ledger(plan: WaiverPlan) {
  return plan.baseline!.starts!.filter((s) => s.owner === "opponent");
}
function reconcile(plan: WaiverPlan) {
  expect(plan.status, JSON.stringify(plan.reasons)).toBe("ready");
  const all = LEAGUE_CATEGORIES.map((c) => c.key);
  for (const f of [plan.baseline!, plan.projected!]) {
    const days = f.daily_lineups!.filter((d) => d.owner === "opponent");
    for (const day of days) {
      expect(day.focus).toEqual(all);
      const starts = day.players.filter((p) => p.state === "start");
      expect(starts.length).toBeLessThanOrEqual(10);
      expect(
        starts.every(
          (p) =>
            p.playing && (p.assigned_slot === "UTIL" || p.positions.includes(p.assigned_slot!)),
        ),
      ).toBe(true);
      expect(starts.map((p) => p.player_id).sort()).toEqual(
        f
          .starts!.filter((s) => s.owner === "opponent" && s.date === day.date)
          .map((s) => s.player_id)
          .sort(),
      );
    }
    for (const k of [
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
      const production = days
        .flatMap((d) => d.players.filter((p) => p.state === "start"))
        .reduce((n, p) => n + (p.rates[k] ?? 0), 0);
      expect(f.opponent_totals![k]).toBeCloseTo(f.actual_primitives!.opponent[k]! + production, 8);
    }
    for (const key of all)
      expect(f.categories![key].opponent).toBeCloseTo(forecastValue(f.opponent_totals, key)!, 8);
  }
  expect(plan.projected!.opponent_totals).toEqual(plan.baseline!.opponent_totals);
}
test("future opponent bench and starters agree; focus, refresh, rates and position capacity", async ({
  page,
}, info) => {
  const bench = await open(page);
  reconcile(bench);
  expect(ledger(bench)).toHaveLength(24); // eight players on three real schedule dates
  const snap = await (await page.request.get(`${root}/snapshot`)).json();
  expect(
    snap.teams
      .find((t: { id: number }) => t.id === 2)
      .roster.every((p: { lineup_slot: string }) => p.lineup_slot === "BENCH"),
  ).toBe(true);
  expect(snap.teams.find((t: { id: number }) => t.id === 2).roster[0].rate_provenance.source).toBe(
    "nba_stats",
  );
  const starters = await refresh(page, { bench: false });
  reconcile(starters);
  expect(ledger(starters)).toEqual(ledger(bench));
  expect(starters.baseline!.opponent_totals).toEqual(bench.baseline!.opponent_totals);
  await page.getByText("Edit targets", { exact: true }).click();
  for (const key of ["PTS", "REB", "AST", "BLK"]) {
    const box = page.getByRole("checkbox", { name: key, exact: true });
    if (await box.isChecked()) await box.uncheck();
  }
  for (const key of ["STL", "3PM", "TO", "FG%", "FT%"])
    await page.getByRole("checkbox", { name: key, exact: true }).check();
  const response = page.waitForResponse((r) => r.url().endsWith(`${root}/plan`) && r.ok());
  await page.getByRole("button", { name: "Apply five" }).click();
  const focusedResponse = await response;
  preferences = focusedResponse.request().postDataJSON();
  const changedFocus = (await focusedResponse.json()) as WaiverPlan;
  reconcile(changedFocus);
  expect(ledger(changedFocus)).toEqual(ledger(bench));
  expect(changedFocus.baseline!.opponent_totals).toEqual(bench.baseline!.opponent_totals);
  await page.getByText("Edit targets", { exact: true }).click();
  const identical = await refresh(page, {});
  expect(identical.baseline!.opponent_totals).toEqual(bench.baseline!.opponent_totals);
  const rates = await refresh(page, { rate_change: true });
  reconcile(rates);
  expect(rates.baseline!.opponent_totals!.pts! - bench.baseline!.opponent_totals!.pts!).toBeCloseTo(
    240,
    8,
  );
  const crowded = await refresh(page, { count: 12, bench: true, rate_change: false });
  reconcile(crowded);
  expect(ledger(crowded)).toHaveLength(30);
  await page.getByRole("button", { name: "About the matchup forecast" }).click();
  await expect(page.getByRole("tooltip")).toContainText(
    "Opponent future lineups use all nine categories",
  );
  save(`${info.project.name}-provider-normalized`, snap);
  save(`${info.project.name}-plans`, { bench, starters, changedFocus, identical, rates, crowded });
  await page.screenshot({
    path: `test-results/opponent-${info.project.name}-desktop.png`,
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({
    path: `test-results/opponent-${info.project.name}-mobile.png`,
    fullPage: true,
  });
});
