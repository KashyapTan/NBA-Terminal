import { mkdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test, type Page } from "@playwright/test";
const root = "/api/fantasy/espn";
const headers = { "X-Fantasy-Request": "1" };
const config = { league_id: 123, season_id: 2027, team_id: 1 };
const privateFixture = {
  league_id: 123,
  season_id: 2027,
  swid: "fixture-owner-0001",
  espn_s2: "synthetic-secret",
};
async function bridge(page: Page, state?: string) {
  const ticket = await page.request.post(`${root}/bridge/challenge`, { headers, data: {} });
  expect(ticket.ok()).toBe(true);
  const nonce = (await ticket.json()).nonce;
  const result = await page.request.post(`${root}/bridge/refresh`, {
    headers,
    data: state ? { ...config, nonce, state } : { ...privateFixture, nonce },
  });
  await page.evaluate(() => window.dispatchEvent(new Event("nba-espn-bridge")));
  return result;
}
async function stats(page: Page) {
  return (
    await (await page.request.get("http://127.0.0.1:8212/__test__/connection-control")).json()
  ).calls;
}
async function control(page: Page, data: { delay?: number; failures?: number[] }) {
  await page.request.post("http://127.0.0.1:8212/__test__/connection-control", { data });
}
for (const target of ["proxy", "production"] as const) {
  test.describe(target, () => {
    test.use({ baseURL: `http://127.0.0.1:${target === "production" ? 8212 : 4212}` });
    test(`${target}: real-route sustained renewal, failure recovery and authoritative revocation`, async ({
      page,
    }) => {
      if (target === "production") await page.goto("http://127.0.0.1:8212/fantasy");
      else await page.goto("/fantasy");
      await page.clock.install();
      await page.request.post(`${root}/bridge/pair`, { headers, data: config });
      expect((await bridge(page)).ok()).toBe(true);
      await expect(page.getByLabel("Your ESPN team")).toHaveValue("1");
      const initialPlan = page.waitForResponse((r) => r.url().endsWith(`${root}/plan`) && r.ok());
      await page.getByRole("tab", { name: "Waiver Wire", exact: true }).click();
      await initialPlan;
      await expect(
        page.getByText("Analyzing current rates, remaining games and your opponent…"),
      ).toHaveCount(0);
      await expect(page.locator(".waiver-verdict")).toBeVisible();
      await page.getByText("Edit availability & roster protection", { exact: true }).click();
      const protection = page.getByRole("button", { name: /Protect / }).first();
      const label = await protection.getAttribute("aria-label");
      const protectionPlan = page.waitForResponse(
        (r) => r.url().endsWith(`${root}/plan`) && r.ok(),
      );
      await protection.click();
      await protectionPlan;
      await expect(page.getByRole("button", { name: label!, exact: true })).toHaveAttribute(
        "aria-pressed",
        "true",
      );
      // MutationObserver proves existing strategy instance survives normal refresh.
      await page.evaluate(() => {
        const panel = document.querySelector(".league-waiver")!;
        (window as unknown as { lostStrategy: boolean }).lostStrategy = false;
        new MutationObserver(() => {
          if (!panel.isConnected)
            (window as unknown as { lostStrategy: boolean }).lostStrategy = true;
        }).observe(document.body, { childList: true, subtree: true });
      });
      await expect.poll(async () => (await stats(page))[`${root}/plan`]).toBeGreaterThan(0);
      const baselineSource = await (await page.request.get(`${root}/snapshot`)).json();
      const before = await stats(page);
      const status = await (await page.request.get(`${root}/status`)).json();
      for (let cycle = 0; cycle < 3; cycle++) {
        expect((await bridge(page)).ok()).toBe(true);
        expect((await (await page.request.get(`${root}/status`)).json()).context_id).toBe(
          status.context_id,
        );
        const snapshotDone = page.waitForResponse(
          (r) => r.url().includes(`${root}/snapshot?refresh=true`) && r.ok(),
        );
        await page.clock.fastForward(61000);
        await snapshotDone;
        await page.evaluate(() => {
          window.dispatchEvent(new Event("focus"));
          document.dispatchEvent(new Event("visibilitychange"));
        });
        await expect(page.getByRole("button", { name: label!, exact: true })).toHaveAttribute(
          "aria-pressed",
          "true",
        );
      }
      const after = await stats(page);
      const finalSource = await (await page.request.get(`${root}/snapshot`)).json();
      const debugDir = resolve(process.cwd(), "../../docs/evidence/v6-connection");
      writeFileSync(
        resolve(debugDir, `${target}-source-debug.json`),
        JSON.stringify({ baselineSource, finalSource, before, after }, null, 2),
      );
      expect(after[`${root}/snapshot`] - before[`${root}/snapshot`]).toBe(3);
      expect(after[`${root}/plan`] - before[`${root}/plan`]).toBe(0);
      expect(
        await page.evaluate(() => (window as unknown as { lostStrategy: boolean }).lostStrategy),
      ).toBe(false);
      // Real provider 503/429/timeout: API refuses success, prior UI remains.
      for (const failure of [503, 429, 504]) {
        await control(page, { failures: [failure] });
        const failed = page.waitForResponse(
          (r) => r.url().includes(`${root}/snapshot?refresh=true`) && r.status() === failure,
        );
        await page.getByRole("button", { name: "Refresh league", exact: true }).click();
        await failed;
        await expect(page.locator(".league-waiver")).toBeVisible();
        await expect(page.locator("[data-result-state='stale']")).toBeVisible();
        await control(page, {});
        await page.getByRole("button", { name: "Refresh league", exact: true }).click();
        await expect(page.locator("[data-result-state='stale']")).toHaveCount(0);
      }
      expect((await bridge(page, "error")).ok()).toBe(true);
      await expect(page.locator("[data-result-state='stale']")).toBeVisible();
      expect((await bridge(page)).ok()).toBe(true);
      await page.getByRole("button", { name: "Refresh league", exact: true }).click();
      await expect(page.locator("[data-result-state='stale']")).toHaveCount(0);
      // Slow snapshot, duplicate refresh and focus: one request, no lost selection.
      await control(page, { delay: 0.5 });
      const pending = page.waitForResponse(
        (r) => r.url().includes(`${root}/snapshot?refresh=true`) && r.ok(),
      );
      await page.getByRole("button", { name: "Refresh league", exact: true }).click();
      await page.evaluate(() => {
        window.dispatchEvent(new Event("focus"));
        window.dispatchEvent(new Event("nba-espn-bridge"));
      });
      await expect(page.getByRole("button", { name: label!, exact: true })).toBeVisible();
      await pending;
      await control(page, {});
      const evidence = resolve(process.cwd(), "../../docs/evidence/v6-connection");
      mkdirSync(evidence, { recursive: true });
      writeFileSync(
        resolve(evidence, `${target}-counts.json`),
        JSON.stringify({ before, after, final: await stats(page) }, null, 2),
      );
      await page.screenshot({ path: resolve(evidence, `${target}-retained.png`) });
      // Definitive provider 401 revokes the actual server session.
      await control(page, { failures: [401] });
      await page.getByRole("button", { name: "Refresh league", exact: true }).click();
      await expect(page.getByRole("alert").filter({ hasText: "Reconnect to ESPN" })).toBeVisible();
      expect((await (await page.request.get(`${root}/status`)).json()).connected).toBe(false);
      await control(page, {});
      await page.request.post(`${root}/bridge/pair`, { headers, data: config });
      await bridge(page);
      await page.getByRole("tab", { name: "Dashboard", exact: true }).click();
      await expect(page.getByLabel("Your ESPN team")).toHaveValue("1");
      await bridge(page, "account_changed");
      await expect(
        page.getByRole("button", { name: "Retry ESPN connection", exact: true }),
      ).toBeVisible();
      expect((await (await page.request.get(`${root}/status`)).json()).connected).toBe(false);
    });
  });
}

test("real-route slow/out-of-order responses, rapid team and planner edits", async ({ page }) => {
  await page.goto("/fantasy");
  await page.request.post(`${root}/connect`, { headers, data: config });
  await page.evaluate(() => window.dispatchEvent(new Event("nba-espn-bridge")));
  await expect(page.getByLabel("Your ESPN team")).toHaveValue("1");
  // Hold an old snapshot response while the selected context changes.
  await page.request.post("http://127.0.0.1:8212/__test__/connection-control", {
    data: { snapshot_delays: [0.8] },
  });
  const oldSnapshot = page.waitForRequest((r) => r.url().includes(`${root}/snapshot?refresh=true`));
  await page.getByRole("button", { name: "Refresh league", exact: true }).click();
  await oldSnapshot;
  await page.getByLabel("Your ESPN team").evaluate((element) => {
    const select = element as HTMLSelectElement;
    for (const id of ["2", "3", "4"]) {
      select.value = id;
      select.dispatchEvent(new Event("change", { bubbles: true }));
    }
  });
  await expect(page.getByLabel("Your ESPN team")).toHaveValue("4");
  await expect
    .poll(async () => (await (await page.request.get(`${root}/status`)).json()).team_id)
    .toBe(4);
  await expect
    .poll(async () => (await (await page.request.get(`${root}/snapshot`)).json()).selected_team_id)
    .toBe(4);
  await control(page, {});
  const initialPlan = page.waitForResponse((r) => r.url().endsWith(`${root}/plan`) && r.ok());
  await page.getByRole("tab", { name: "Waiver Wire", exact: true }).click();
  await initialPlan;
  await expect(
    page.getByText("Analyzing current rates, remaining games and your opponent…"),
  ).toHaveCount(0);
  const cards = page.getByRole("region", { name: "Recommended ordered plan" });
  const previous = await cards.textContent();
  await page.request.post("http://127.0.0.1:8212/__test__/connection-control", {
    data: { plan_delays: [0.8, 0] },
  });
  const firstRequest = page.waitForRequest((r) => r.url().endsWith(`${root}/plan`));
  await page.getByRole("checkbox", { name: "Allow core-player drops for this analysis" }).check();
  await firstRequest;
  await expect(cards).toHaveText(previous!);
  await expect(page.locator("[data-result-state='refreshing']")).toBeVisible();
  const latest = page.waitForResponse(
    (r) =>
      r.url().endsWith(`${root}/plan`) &&
      r.ok() &&
      r.request().postDataJSON().allow_core_drops === false,
  );
  await page.getByRole("checkbox", { name: "Allow core-player drops for this analysis" }).uncheck();
  await latest;
  await expect(page.locator("[data-result-state]")).toHaveCount(0);
  // Backend work/response continues even when the browser aborts an obsolete request.
  await expect
    .poll(async () => {
      const result = await page.request.get(`${root}/status`);
      return result.ok();
    })
    .toBe(true);
  await page.waitForTimeout(1000); // Deliberately exceed the controlled old-response delay.
  await expect(page.locator("[data-result-state]")).toHaveCount(0);
  await expect(
    page.getByRole("checkbox", { name: "Allow core-player drops for this analysis" }),
  ).not.toBeChecked();
  await expect(cards).toHaveText(previous!);
  await control(page, {});
});

test("three-minute wall-clock real-route poll soak retains the same completed strategy", async ({
  page,
}) => {
  test.setTimeout(210000);
  await page.goto("/fantasy");
  await page.request.post(`${root}/connect`, { headers, data: config });
  await page.evaluate(() => window.dispatchEvent(new Event("nba-espn-bridge")));
  await expect(page.getByLabel("Your ESPN team")).toHaveValue("1");
  const initial = page.waitForResponse((r) => r.url().endsWith(`${root}/plan`) && r.ok());
  await page.getByRole("tab", { name: "Waiver Wire", exact: true }).click();
  await initial;
  await expect(
    page.getByText("Analyzing current rates, remaining games and your opponent…"),
  ).toHaveCount(0);
  await page.evaluate(() => {
    const strategy = document.querySelector(".league-waiver")!;
    (window as unknown as { soakLost: boolean }).soakLost = false;
    new MutationObserver(() => {
      if (!strategy.isConnected) (window as unknown as { soakLost: boolean }).soakLost = true;
    }).observe(document.body, { childList: true, subtree: true });
  });
  const before = await stats(page);
  const startedAt = Date.now();
  for (let i = 0; i < 3; i++) {
    await page.waitForResponse((r) => r.url().includes(`${root}/snapshot?refresh=true`) && r.ok(), {
      timeout: 75000,
    });
    await page.evaluate(() => {
      window.dispatchEvent(new Event("focus"));
      document.dispatchEvent(new Event("visibilitychange"));
    });
    await expect(page.locator(".waiver-verdict")).toBeVisible();
  }
  const after = await stats(page);
  expect(Date.now() - startedAt).toBeGreaterThan(175000);
  expect(after[`${root}/plan`] - before[`${root}/plan`]).toBe(0);
  expect(await page.evaluate(() => (window as unknown as { soakLost: boolean }).soakLost)).toBe(
    false,
  );
  writeFileSync(
    resolve(process.cwd(), "../../docs/evidence/v6-connection/wall-clock-soak.json"),
    JSON.stringify(
      { elapsedMs: Date.now() - startedAt, before, after, strategyUnmounted: false },
      null,
      2,
    ),
  );
});
