import { mkdirSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test, type Page } from "@playwright/test";

// Real HTTP routes, normalizer, auth/session and planner; only external transport is synthetic.
async function connect(page: Page, league = 123) {
  await page.goto("/fantasy");
  await expect(page.getByRole("tab", { name: "Dashboard" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await page.getByLabel("League ID", { exact: true }).fill(String(league));
  await page.getByLabel("Season ending year").fill("2027");
  await page.getByRole("button", { name: "Connect ESPN", exact: true }).click();
  if (league !== 126) {
    await expect(page.getByLabel("Your ESPN team")).toBeEnabled();
    await page.getByLabel("Your ESPN team").selectOption("1");
    await expect(page.getByText("Current opponent: Fixture Team 2", { exact: true })).toBeVisible();
  }
}
test("production chain automatically ranks seven net pickup alternatives and preserves edits", async ({
  page,
}, info) => {
  await connect(page);
  await page.getByRole("tab", { name: "Matchups", exact: true }).click();
  const compared = page.getByLabel("Compare league team");
  await expect(compared.locator("option")).toHaveCount(13);
  await expect(page.getByRole("table").getByRole("row")).toHaveCount(10);
  await expect(
    page.getByRole("row").filter({ has: page.getByRole("rowheader", { name: /TO/ }) }),
  ).toContainText("Leading");
  await compared.selectOption("14");
  await expect(page.getByLabel("0 wins, 0 losses, 9 ties")).toBeVisible();
  await compared.selectOption("2");
  const evidence = resolve(process.cwd(), "../../visual-evidence/fantasy-v2");
  mkdirSync(evidence, { recursive: true });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({
    path: resolve(evidence, `${info.project.name}-matchups-desktop.png`),
    fullPage: true,
  });
  await page.getByRole("tab", { name: "Waiver Wire", exact: true }).click();
  const alternatives = page.getByRole("region", { name: "Ranked pickup alternatives" });
  await expect(alternatives.locator(".pickup-list > li")).toHaveCount(7);
  await expect(page.locator(".category-overview tbody > tr")).toHaveCount(9);
  await expect(page.getByText(/Combined weekly plan/)).toBeVisible();
  await expect(page.locator(".waiver-budget")).toContainText("5 used");
  await page.screenshot({
    path: resolve(evidence, `${info.project.name}-waiver-desktop.png`),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect
    .poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth))
    .toBe(true);
  await page.screenshot({
    path: resolve(evidence, `${info.project.name}-waiver-mobile.png`),
    fullPage: true,
  });
  await page.getByText("Edit availability & roster protection", { exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Protect Fixture Player 1001", exact: true }),
  ).toBeDisabled();
  await page
    .getByRole("button", { name: "Fixture Player 1 availability: Available", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Fixture Player 1 availability: Out", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("status")).toHaveCount(0);
  await page.getByRole("button", { name: "Refresh league", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Fixture Player 1 availability: Out", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Fixture Player 1 availability: Out", exact: true })
    .click();
  await expect(alternatives.locator(".pickup-list > li")).toHaveCount(7);
  await page.getByRole("button", { name: "Protect Fixture Player 1", exact: true }).click();
  await expect(alternatives.locator(".pickup-list > li")).toHaveCount(0);
  await page.getByRole("button", { name: "Protect Fixture Player 1", exact: true }).click();
  await expect(alternatives.locator(".pickup-list > li")).toHaveCount(7);
  await page.route("**/api/fantasy/espn/plan", (route) =>
    route.fulfill({ status: 503, json: { detail: "test busy" } }),
  );
  await page
    .getByRole("button", { name: "Fixture Player 1 availability: Available", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText("Analysis could not be loaded");
  await page.unroute("**/api/fantasy/espn/plan");
  await page.getByRole("button", { name: "Retry analysis", exact: true }).click();
  await expect(page.getByRole("alert")).toHaveCount(0);
  await page.getByRole("tab", { name: "Dashboard", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Your fantasy workspace" })).toBeVisible();
  await page.getByRole("button", { name: "Disconnect ESPN", exact: true }).click();
  await expect(page.getByLabel("League ID", { exact: true })).toBeVisible();
});

test("private cookie flow uses the local session and enforces selectable ownership", async ({
  page,
}) => {
  await page.goto("/fantasy");
  await page.getByLabel("League ID", { exact: true }).fill("123");
  await page.getByLabel("Season ending year").fill("2027");
  await page.getByLabel("Private league", { exact: true }).check();
  await page.getByLabel("SWID", { exact: true }).fill("fixture-owner-0001");
  await page.getByLabel("espn_s2", { exact: true }).fill("synthetic-cookie-test-only");
  await page.getByRole("button", { name: "Connect ESPN", exact: true }).click();
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
  await expect(page.getByRole("status")).toHaveCount(0);
  await expect(
    page.getByRole("region", { name: "Ranked pickup alternatives" }).locator(".pickup-list > li"),
  ).toHaveCount(0);
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
