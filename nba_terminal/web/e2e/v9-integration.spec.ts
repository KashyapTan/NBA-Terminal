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
const evidence = process.env.EVIDENCE_DIR || "../../docs/evidence/v9-chains";
const rawEvidence = process.env.V9_RAW_EVIDENCE_DIR || "test-results/v9-raw";
function save(name: string, data: unknown) {
  mkdirSync(rawEvidence, { recursive: true });
  writeFileSync(`${rawEvidence}/${name}.json`, JSON.stringify(data, null, 2));
}
async function open(page: Page, league: number, mode = "") {
  await page.request.post("http://127.0.0.1:8219/__test__/v9-control", {
    data: { interim: league, mode },
  });
  await page.request.post("http://127.0.0.1:8219/__test__/connection-control", { data: {} });
  await page.goto("/fantasy");
  await page.waitForLoadState("networkidle");
  expect(
    (
      await page.request.post(`${root}/bridge/pair`, {
        headers,
        data: { league_id: 901, season_id: 2027, team_id: 1 },
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
function reconcile(plan: WaiverPlan) {
  expect(plan.status, JSON.stringify(plan.reasons)).toBe("ready");
  for (const forecast of [plan.baseline!, plan.projected!]) {
    for (const owner of ["user", "opponent"] as const) {
      const rows = forecast.daily_lineups!.filter((d) => d.owner === owner);
      expect(rows.length).toBeGreaterThan(0);
      const production: Record<string, number> = {};
      for (const day of rows) {
        expect(day.capacity).toBe(1);
        expect(day.focus).toEqual(plan.selected_categories);
        const starts = day.players.filter((p) => p.state === "start");
        expect(starts.length).toBeLessThanOrEqual(10);
        expect(new Set(day.players.map((p) => p.player_id)).size).toBe(day.players.length);
        expect(starts.map((p) => p.player_id).sort()).toEqual(
          forecast
            .starts!.filter((s) => s.owner === owner && s.date === day.date)
            .map((s) => s.player_id)
            .sort(),
        );
        for (const p of starts) {
          expect(p.playing).toBe(true);
          expect(p.assigned_slot === "UTIL" || p.positions.includes(p.assigned_slot!)).toBe(true);
          for (const [key, value] of Object.entries(p.rates))
            production[key] = (production[key] ?? 0) + value;
        }
        for (const slot of ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]) {
          expect(starts.filter((p) => p.assigned_slot === slot).length).toBeLessThanOrEqual(
            slot === "UTIL" ? 3 : 1,
          );
        }
      }
      const total = owner === "user" ? forecast.totals : forecast.opponent_totals!;
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
        expect(total[key]).toBeCloseTo(
          forecast.actual_primitives![owner][key]! + (production[key] ?? 0),
          8,
        );
        expect(forecast.remaining_primitives![owner][key]).toBeCloseTo(production[key] ?? 0, 8);
      }
    }
    for (const { key } of LEAGUE_CATEGORIES) {
      const value = forecastValue(forecast.totals, key);
      expect(value).not.toBeNull();
      if (key === "fg_pct") expect(value).toBeCloseTo(forecast.totals.fgm! / forecast.totals.fga!);
      if (key === "ft_pct") expect(value).toBeCloseTo(forecast.totals.ftm! / forecast.totals.fta!);
    }
  }
  for (const { key } of LEAGUE_CATEGORIES) {
    const before = forecastValue(plan.baseline!.totals, key)!;
    const after = forecastValue(plan.projected!.totals, key)!;
    expect(plan.recommended_plan!.arithmetic.categories[key].net).toBeCloseTo(after - before, 8);
  }
}
test("dated direct shortcuts and useful streams through actual provider pipeline", async ({
  page,
}, info) => {
  for (const interim of [0, 0.001, 2]) {
    const plan = await open(page, interim);
    reconcile(plan);
    const moves = plan.recommended_plan!.moves;
    expect(moves.length).toBe(interim === 2 ? 2 : 1);
    expect(plan.recommended_plan!.acquisitions).toBe(moves.length);
    expect(plan.remaining_adds).toBe(2 - moves.length);
    if (interim === 2) {
      expect(moves.map((m) => m.add_id)).toEqual(["100", "101"]);
      expect(moves[0].date).toBe("2026-11-06");
      expect(moves[1].date).toBe("2026-11-08");
      expect(moves[0].chain_reason).toContain("extra acquisition");
      expect(moves[0].direct_comparison).toBeTruthy();
      await expect(page.locator(".ww-moves")).toContainText("extra acquisition");
    } else expect(moves[0].add_id).toBe("101");
    for (const m of moves) {
      const dates = plan
        .projected!.starts!.filter((s) => s.owner === "user" && s.player_id === m.add_id)
        .map((s) => s.date);
      expect(m.realized!.dates).toEqual(dates);
      expect(m.realized!.starts).toBe(dates.length);
    }
    const summary = page.getByRole("region", { name: "Final plan get lose and net" });
    await expect(summary).toBeVisible();
    await expect(summary).toContainText("Get");
    await expect(summary).toContainText("Lose");
    for (const { key } of LEAGUE_CATEGORIES) {
      const row = plan.recommended_plan!.realized_impact!.arithmetic.categories[key];
      const target = summary.locator(`[data-category="${key}"]`);
      await expect(target).toContainText("Net");
      expect(row.net).toBeCloseTo(plan.recommended_plan!.arithmetic.categories[key].net!, 8);
    }
    save(`${info.project.name}-${interim}-plan`, plan);
    await expect(page.locator(".ww-analysis")).not.toHaveAttribute("open");
    await page.screenshot({
      path: `${evidence}/${info.project.name}-${interim}-desktop.png`,
      fullPage: true,
    });
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(page.locator(".ww-moves")).toContainText("Final plan:");
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    ).toBe(true);
    await page.screenshot({
      path: `${evidence}/${info.project.name}-${interim}-mobile.png`,
      fullPage: true,
    });
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.context().clearCookies();
    await page.evaluate(() => localStorage.clear());
  }
});

test("provider ownership, waiver status, quota and immutable locks survive shortcut comparisons", async ({
  page,
}, info) => {
  for (const mode of ["waiver", "other", "quota", "locked", "crowded", "harmful"]) {
    const plan = await open(page, 2, mode);
    const moves = plan.recommended_plan?.moves ?? [];
    if (mode === "locked") expect(moves).toHaveLength(0);
    if (mode === "waiver" || mode === "other")
      expect(moves.every((m) => m.add_id !== "101")).toBe(true);
    if (mode === "quota") expect(moves.length).toBeLessThanOrEqual(1);
    if (mode === "crowded") {
      expect(moves.every((m) => m.add_id !== "100")).toBe(true);
      for (const day of plan.projected!.daily_lineups!)
        expect(day.players.filter((p) => p.state === "start").length).toBeLessThanOrEqual(10);
    }
    if (mode === "harmful" && moves.some((m) => m.add_id === "100")) {
      expect(plan.recommended_plan!.arithmetic.categories.to.net).toBeGreaterThan(0);
      expect(plan.recommended_plan!.arithmetic.categories.fg_pct.net).toBeLessThan(0);
      expect(plan.recommended_plan!.arithmetic.categories.ft_pct.net).toBeLessThan(0);
    }
    expect(new Set(moves.map((m) => m.add_id)).size).toBe(moves.length);
    if (mode === "harmful") {
      const summary = page.getByRole("region", { name: "Final plan get lose and net" });
      await expect(summary).toBeVisible();
      for (const key of ["pts", "fg_pct", "ft_pct", "to"]) {
        await expect(summary.locator(`[data-category="${key}"] .ww-loss`)).toContainText("Loss");
      }
      await expect(page.locator(".ww-analysis")).not.toHaveAttribute("open");
      await page.screenshot({
        path: `${evidence}/${info.project.name}-harmful-desktop.png`,
        fullPage: true,
      });
      await page.setViewportSize({ width: 390, height: 844 });
      await expect(summary.locator('[data-category="pts"]')).toBeVisible();
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
      ).toBe(true);
      await page.screenshot({
        path: `${evidence}/${info.project.name}-harmful-mobile.png`,
        fullPage: true,
      });
      await page.setViewportSize({ width: 1280, height: 900 });
    }
    save(`${info.project.name}-${mode}-plan`, plan);
    await page.context().clearCookies();
    await page.evaluate(() => localStorage.clear());
  }
});
