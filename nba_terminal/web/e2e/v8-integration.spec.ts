import { mkdirSync, writeFileSync } from "node:fs";
import { expect, type Page, test } from "@playwright/test";
import {
  LEAGUE_CATEGORIES,
  type LeagueSnapshot,
  type WaiverPlan,
} from "../src/league-fantasy-model";
import { forecastValue } from "../src/MatchupForecast";

const provider = `http://127.0.0.1:${process.env.FANTASY_E2E_PORT || "8218"}`;
const root = "/api/fantasy/espn";
const headers = { "X-Fantasy-Request": "1" };
const evidence = process.env.EVIDENCE_DIR || "../../docs/evidence/v8-lineups";
async function control(page: Page, data: object) {
  expect((await page.request.post(`${provider}/__test__/v7-control`, { data })).ok()).toBe(true);
}
function save(name: string, data: unknown) {
  mkdirSync(evidence, { recursive: true });
  writeFileSync(`${evidence}/${name}.json`, JSON.stringify(data, null, 2));
}
async function open(page: Page, league: number) {
  await control(page, { league });
  await page.request.post(`${provider}/__test__/connection-control`, { data: {} });
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
function reconcile(plan: WaiverPlan) {
  expect(plan.status, JSON.stringify(plan.reasons)).toBe("ready");
  for (const forecast of [plan.baseline!, plan.projected!]) {
    for (const owner of ["user", "opponent"] as const) {
      const rows = forecast.daily_lineups!.filter((d) => d.owner === owner);
      expect(rows.length).toBeGreaterThan(0);
      const production: Record<string, number> = {};
      for (const day of rows) {
        expect(day.capacity).toBe(10);
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
test("real HTTP daily selections reconcile and stay focus-aware across desktop/mobile and refresh", async ({
  page,
}, info) => {
  page.setDefaultTimeout(15000);
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.request.post(`${provider}/__test__/v8-control`, {
    data: { players: 13, out: false, rate_change: false, pickup_boost: false },
  });
  const plan = await open(page, 801);
  reconcile(plan);
  save(`${info.project.name}-plan`, plan);
  const daily = page.getByRole("region", { name: "Daily lineup", exact: true });
  await expect(daily).toContainText("Current roster · no pickups required");
  await expect(page.locator(".ww-forecast tbody tr")).toHaveCount(9);
  const owned = plan.baseline!.daily_lineups!.filter((d) => d.owner === "user");
  const crowded = owned.find((d) => d.players.filter((p) => p.playing).length > 10)!;
  expect(crowded).toBeTruthy();
  await daily.getByLabel("Lineup day").selectOption(crowded.date);
  const names = async () =>
    daily
      .getByRole("list", { name: "Start players", exact: true })
      .locator("li b")
      .allTextContents();
  expect((await names()).sort()).toEqual(
    crowded.players
      .filter((p) => p.state !== "bench")
      .map((p) => p.name)
      .sort(),
  );
  await expect(daily).toContainText("13 available & playing");
  const help = daily.getByRole("button", { name: "About daily lineup" });
  await help.hover();
  await expect(daily.getByRole("tooltip")).toBeVisible();
  await help.focus();
  await page.keyboard.press("Escape");
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.locator(".ww-forecast").scrollIntoViewIfNeeded();
  await page.screenshot({ path: `${evidence}/${info.project.name}-forecast-desktop.png` });
  await daily.scrollIntoViewIfNeeded();
  await page.screenshot({ path: `${evidence}/${info.project.name}-desktop.png` });
  const first = await names();
  const refreshed = page.waitForResponse(
    (r) => r.url().includes(`${root}/snapshot?refresh=true`) && r.ok(),
  );
  await page.getByRole("button", { name: "Refresh league", exact: true }).click();
  await refreshed;
  await expect.poll(names).toEqual(first);
  await expect(daily.getByLabel("Lineup day")).toHaveValue(crowded.date);
  // A legitimate focus edit must change the server decisions, not merely UI badges.
  await page.getByText("Edit targets", { exact: true }).click();
  for (const key of ["AST", "BLK"])
    await page.getByRole("checkbox", { name: key, exact: true }).uncheck();
  for (const key of ["FG%", "FT%"])
    await page.getByRole("checkbox", { name: key, exact: true }).check();
  const changed = page.waitForResponse((r) => r.url().endsWith(`${root}/plan`) && r.ok());
  await page.getByRole("button", { name: "Apply five" }).click();
  const next = (await (await changed).json()) as WaiverPlan;
  reconcile(next);
  save(`${info.project.name}-focus-change`, next);
  await page.getByText("Edit targets", { exact: true }).click();
  const changedDay = next.baseline!.daily_lineups!.find(
    (d) => d.owner === "user" && d.date === crowded.date,
  )!;
  await expect
    .poll(async () => (await names()).sort())
    .toEqual(
      changedDay.players
        .filter((p) => p.state !== "bench")
        .map((p) => p.name)
        .sort(),
    );
  expect((await names()).sort()).not.toEqual([...first].sort());
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator(".ww-forecast").scrollIntoViewIfNeeded();
  await page.screenshot({ path: `${evidence}/${info.project.name}-forecast-mobile.png` });
  await daily.scrollIntoViewIfNeeded();
  await help.click();
  await expect(daily.getByRole("tooltip")).toBeVisible();
  await help.click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: `${evidence}/${info.project.name}-mobile.png` });
  await page.setViewportSize({ width: 320, height: 740 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: `${evidence}/${info.project.name}-320.png` });
  // A controlled stronger pickup yields a real ordered plan after explicit core override.
  await page.request.post(`${provider}/__test__/v8-control`, {
    data: { pickup_boost: true },
  });
  const boostedRefresh = page.waitForResponse((r) => r.url().endsWith(`${root}/plan`) && r.ok());
  await page.getByRole("button", { name: "Refresh league", exact: true }).click();
  await boostedRefresh;
  await page.getByText("Roster settings", { exact: true }).click();
  const planned = page.waitForResponse((r) => r.url().endsWith(`${root}/plan`) && r.ok());
  await page.getByRole("checkbox", { name: "Allow core-player drops", exact: true }).check();
  const withMoves = (await (await planned).json()) as WaiverPlan;
  reconcile(withMoves);
  save(`${info.project.name}-ordered-plan`, withMoves);
  expect(withMoves.actions.length).toBeGreaterThan(0);
  const sequence = page.getByRole("region", { name: "Final plan get lose and net" });
  await expect(sequence).toBeVisible();
  for (const { key } of LEAGUE_CATEGORIES) {
    const row = withMoves.recommended_plan!.realized_impact!.arithmetic.categories[key];
    expect(row.net).toBeCloseTo(withMoves.recommended_plan!.arithmetic.categories[key].net!, 8);
    await expect(sequence.locator(`[data-category="${key}"]`)).toContainText("Lose");
    await expect(sequence.locator(`[data-category="${key}"]`)).toContainText("Net");
  }
  const addIds = new Set(withMoves.actions.map((m) => m.add_id));
  const previewDay = withMoves.projected!.daily_lineups!.find(
    (d) =>
      d.owner === "user" && d.players.some((p) => p.state === "start" && addIds.has(p.player_id)),
  )!;
  expect(previewDay).toBeTruthy();
  await daily.getByLabel("Lineup day").selectOption(previewDay.date);
  await expect(daily).toContainText("Current roster · no pickups required");
  const currentNames = await names();
  expect(currentNames.every((name) => name.startsWith("Owned"))).toBe(true);
  await daily.getByRole("checkbox", { name: "Preview after planned moves" }).check();
  await expect(daily).toContainText("After plan preview · hypothetical");
  expect((await names()).sort()).toEqual(
    previewDay.players
      .filter((p) => p.state !== "bench")
      .map((p) => p.name)
      .sort(),
  );
  await daily.scrollIntoViewIfNeeded();
  await page.screenshot({ path: `${evidence}/${info.project.name}-hypothetical-mobile.png` });
  await daily.getByRole("checkbox", { name: "Preview after planned moves" }).uncheck();
  expect(await names()).toEqual(currentNames);
  // Same production chain, different roster sizes, no fake plan routes.
  for (const count of [11, 12]) {
    await page.request.post(`${provider}/__test__/v8-control`, {
      data: { players: count },
    });
    const snapResponse = await page.request.get(`${root}/snapshot?refresh=true`);
    expect(snapResponse.ok()).toBe(true);
    const snapshot = (await snapResponse.json()) as LeagueSnapshot;
    save(`${info.project.name}-${count}-snapshot`, snapshot);
    const response = await page.request.post(`${root}/plan`, {
      headers,
      data: {
        context: {
          league_id: 801,
          season_id: 2027,
          team_id: 1,
          matchup_period_id: snapshot.period.matchup_period_id,
          fetched_at: snapshot.fetched_at,
        },
        selected_categories: next.selected_categories,
      },
    });
    expect(response.ok()).toBe(true);
    const result = (await response.json()) as WaiverPlan;
    reconcile(result);
    save(`${info.project.name}-${count}-plan`, result);
  }
  expect(errors).toEqual([]);
});
