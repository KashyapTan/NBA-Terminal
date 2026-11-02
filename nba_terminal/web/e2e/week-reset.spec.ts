import { mkdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test } from "@playwright/test";
import type { WaiverPlan } from "../src/league-fantasy-model";

// Test-only provider boundary with public field shapes. Browser executes production
// bundle against real HTTP routes, normalization, adapter and bounded optimizer.
test("new matchup dailyTrue/raw1/user7/0 without counter yields ordered plan", async ({ page }) => {
  let planCalls = 0;
  page.on("request", (request) => {
    if (request.url().endsWith("/api/fantasy/espn/plan")) planCalls++;
  });
  await page.clock.install({ time: new Date("2026-11-02T17:42:30Z") });
  await page.goto("/fantasy");
  await page.getByText("Manual or public league fallback", { exact: true }).click();
  await page.getByLabel("Manual league ID", { exact: true }).fill("604550749");
  await page.getByLabel("Manual season ending year").fill("2027");
  await page.getByRole("button", { name: "Connect manually", exact: true }).click();
  await page.getByLabel("Your ESPN team").selectOption("1");
  const response = page.waitForResponse(
    (r) => r.url().endsWith("/api/fantasy/espn/plan") && r.ok(),
  );
  await page.getByRole("tab", { name: "Waiver Wire", exact: true }).click();
  const plan = (await (await response).json()) as WaiverPlan;
  const currentSnapshot = await (await page.request.get("/api/fantasy/espn/snapshot")).json();
  expect(currentSnapshot.fetched_at).not.toContain("17:02:22");
  expect(
    currentSnapshot.teams.find(
      (team: { id: number }) => team.id === currentSnapshot.selected_team_id,
    ).name,
  ).toBe("Kashyap's Team");
  expect(plan.evaluation_state, JSON.stringify(plan)).toBe("confirmed_ordered_plan");
  expect(plan.acquisition_budget?.used).toBe(0);
  expect(plan.acquisition_budget?.usage_source).toBe("scoped user-declared current matchup usage");
  expect(plan.recommended_plan!.budget_before).toBe(7);
  expect(plan.plan!.length).toBeGreaterThan(0);
  const region = page.getByRole("region", { name: "Ordered pickup plan" });
  await expect(region.locator(".ww-moves > li")).not.toHaveCount(0);
  await expect(page.locator(".ww-analysis")).not.toHaveAttribute("open");
  await page.getByText("Full analysis & data", { exact: true }).click();
  await expect(
    page.getByRole("region", { name: "All nine move calculations" }).first().locator("tbody tr"),
  ).toHaveCount(9);
  await page.getByText("Full analysis & data", { exact: true }).click();
  for (const move of plan.plan!) {
    for (const row of Object.values(move.arithmetic!.primitives)) {
      expect(row.net).toBeCloseTo(row.add - row.drop + row.spillover, 8);
    }
  }
  await expect(
    page.getByText("Ordered plan withheld: daily acquisition ledger missing"),
  ).toHaveCount(0);
  await expect(page.locator(".ww-analysis")).not.toHaveAttribute("open");
  const evidence = resolve(
    process.cwd(),
    process.env.EVIDENCE_DIR || "../../docs/evidence/v6-integrated/week-reset",
  );
  mkdirSync(evidence, { recursive: true });
  writeFileSync(resolve(evidence, "synthetic-plan.json"), JSON.stringify(plan, null, 2));
  for (const [name, width, height] of [
    ["desktop", 1440, 1000],
    ["mobile", 390, 844],
  ] as const) {
    await page.setViewportSize({ width, height });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    await page.screenshot({ path: resolve(evidence, `${name}.png`), fullPage: true });
  }
  // Same facts at a later observation time retain the plan and original lease.
  const beforeRefresh = planCalls;
  await page.request.post("/__test__/week-clock?seconds=60");
  const refreshed = page.waitForResponse(
    (r) => r.url().includes("/api/fantasy/espn/snapshot?refresh=true") && r.ok(),
  );
  await page.getByRole("button", { name: "Refresh league", exact: true }).click();
  const refreshedSnapshot = await (await refreshed).json();
  await expect(page.locator(".waiver-workspace")).toHaveAttribute("data-result-state", "connected");
  expect(refreshedSnapshot.fetched_at).not.toBe(currentSnapshot.fetched_at);
  expect(planCalls).toBe(beforeRefresh);
  expect(
    (plan as WaiverPlan & { provenance: { usage_declaration: { confirmed_at: string } } })
      .provenance.usage_declaration.confirmed_at,
  ).toBe("2026-11-02T17:02:22.264988Z");
  // A known acquisition consumes the bootstrap, even if a later source loses its map.
  await page.request.post("/__test__/week-counter?used=1");
  const positive = page.waitForResponse(
    (r) => r.url().endsWith("/api/fantasy/espn/plan") && r.ok(),
  );
  await page.getByRole("button", { name: "Refresh league", exact: true }).click();
  const current = await (await positive).json();
  expect(current.acquisition_budget.used).toBe(1);
  expect(current.acquisition_budget.usage_source).toBe("espn_matchup_acquisition_totals");
  await page.request.post("/__test__/week-counter");
  const missing = page.waitForResponse((r) => r.url().endsWith("/api/fantasy/espn/plan") && r.ok());
  await page.getByRole("button", { name: "Refresh league", exact: true }).click();
  const afterMissing = await (await missing).json();
  expect(afterMissing.acquisition_budget.used).toBeNull();
  expect(afterMissing.plan).toHaveLength(0);
});
