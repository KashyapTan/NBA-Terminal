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
async function constraints(page: Page) {
  await page.getByRole("tab", { name: "Waiver Wire", exact: true }).click();
  await page.getByLabel("Verified weekly cap").fill("7");
  await page.getByLabel("Verified adds used").fill("5");
  await page.getByLabel("Verified adds remaining").fill("2");
  await page.getByLabel("I verified these weekly counts").check();
  await page.getByLabel(/Fixture Player 1 · Lock unknown/).check();
  await page.getByRole("button", { name: "Shortlist Fixture Player 100", exact: true }).click();
  await page.getByLabel("I verified the shortlisted players").check();
}
async function sensitivity(page: Page) {
  await page.getByLabel("Uncertainty mode").selectOption("sensitivity");
  const fields = page.getByLabel(/margin standard deviation/);
  for (let index = 0; index < 9; index++) await fields.nth(index).fill(index >= 7 ? "0.05" : "5");
}

test("production chain connects, compares 14 teams and calculates an editable plan", async ({
  page,
}, info) => {
  await connect(page);
  await expect(page.getByText(/Team ownership unverified/)).toBeVisible();
  await page.getByRole("tab", { name: "Matchups", exact: true }).click();
  const compared = page.getByLabel("Compare league team");
  await expect(compared.locator("option")).toHaveCount(13);
  await expect(page.getByText("Fixture Player 1", { exact: true })).toBeVisible();
  await expect(page.getByText("Fixture Player 2", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("row").filter({ has: page.getByRole("rowheader", { name: /TO/ }) }),
  ).toContainText("winning");
  await expect(page.getByRole("table").getByRole("row")).toHaveCount(10);
  await compared.selectOption("14");
  await expect(
    page.getByText("Hypothetical comparison: 0 winning · 9 tied · 0 losing · 0 unknown"),
  ).toBeVisible();
  await compared.selectOption("2");
  await constraints(page);
  await page.getByRole("button", { name: "Calculate recommendation" }).click();
  await expect(page.getByRole("heading", { name: "Recommendation · incomplete" })).toBeVisible();
  await expect(page.getByText(/Insufficient historical variance/).first()).toBeVisible();
  await sensitivity(page);
  await expect(page.getByRole("heading", { name: "Recommendation · incomplete" })).toHaveCount(0);
  await page.getByRole("button", { name: "Calculate recommendation" }).click();
  await expect(page.getByRole("heading", { name: "Recommendation · ready" })).toBeVisible();
  await expect(page.getByText(/add Fixture Player 100, drop Fixture Player 1/)).toBeVisible();
  const evidence = resolve(process.cwd(), "../../code_review/fantasy-integration-evidence");
  mkdirSync(evidence, { recursive: true });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({
    path: resolve(evidence, `${info.project.name}-waiver-desktop.png`),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect
    .poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth))
    .toBe(true);
  await page.screenshot({
    path: resolve(evidence, `${info.project.name}-waiver-mobile.png`),
    fullPage: true,
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.getByRole("button", { name: "Remove Fixture Player 100", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Recommendation · ready" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Calculate recommendation" })).toBeDisabled();
  await page.getByRole("button", { name: "Shortlist Fixture Player 100", exact: true }).click();
  await page.getByLabel("I verified the shortlisted players").check();
  await page.route("**/api/fantasy/espn/plan", (route) =>
    route.fulfill({ status: 503, json: { detail: "test-only busy" } }),
  );
  await page.getByRole("button", { name: "Calculate recommendation" }).click();
  await expect(page.getByRole("alert")).toContainText("could not be calculated");
  await page.unroute("**/api/fantasy/espn/plan");
  await page.getByRole("button", { name: "Refresh league" }).click();
  await expect(page.getByLabel("Verified adds used")).toHaveValue("");
  await expect(page.getByLabel("I verified the shortlisted players")).not.toBeChecked();
  await page.getByRole("tab", { name: "Leaders", exact: true }).click();
  await page.getByLabel("Minimum minutes per game", { exact: true }).fill("33");
  await expect(page.getByRole("table").first().getByText("Synthetic season starter")).toHaveCount(
    0,
  );
  await page.getByLabel("Minimum minutes per game", { exact: true }).fill("30");
  await expect(page.getByRole("table").first().getByText("Synthetic season starter")).toBeVisible();
  await page.getByRole("tab", { name: "Dashboard", exact: true }).click();
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.getByRole("button", { name: "Collapse sidebar" }).click();
  await expect(page.getByRole("button", { name: "Expand sidebar" })).toHaveAttribute(
    "aria-expanded",
    "false",
  );
  await page.screenshot({
    path: resolve(evidence, `${info.project.name}-connected-desktop.png`),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    page
      .getByRole("navigation", { name: "Workspace" })
      .getByRole("link", { name: "Fantasy", exact: true }),
  ).toBeVisible();
  await expect
    .poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth))
    .toBe(true);
  await page.screenshot({
    path: resolve(evidence, `${info.project.name}-connected-mobile.png`),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Disconnect ESPN" }).click();
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

test("missing schedules recover explicitly; unsupported and failed connections stay honest", async ({
  page,
}) => {
  await connect(page, 124);
  await constraints(page);
  await sensitivity(page);
  await page.getByRole("button", { name: "Calculate recommendation" }).click();
  await expect(page.getByRole("heading", { name: "Recommendation · incomplete" })).toBeVisible();
  await expect(page.getByText(/remaining schedule is unknown/).first()).toBeVisible();
  await expect(page.getByText(/No actions are available/)).toBeVisible();
  await page.getByText("Complete missing schedules and availability", { exact: true }).click();
  await page.getByLabel("Verified remaining matchup dates").fill("2026-11-01");
  for (const id of [1, 2, 100]) {
    await page
      .getByLabel(`I am supplying Fixture Player ${id} remaining unstarted game dates`, {
        exact: true,
      })
      .check();
    await page
      .getByLabel(`Fixture Player ${id} verified game dates`, { exact: false })
      .fill("2026-11-01");
  }
  await page.getByRole("button", { name: "Calculate recommendation" }).click();
  await expect(page.getByRole("heading", { name: "Recommendation · ready" })).toBeVisible();
  await page.getByRole("tab", { name: "Dashboard", exact: true }).click();
  await page.getByRole("button", { name: "Disconnect ESPN" }).click();
  await connect(page, 125);
  await page.getByRole("tab", { name: "Waiver Wire", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Only head-to-head standard nine-category");
  await expect(page.getByRole("button", { name: "Calculate recommendation" })).toBeDisabled();
  await page.getByRole("tab", { name: "Dashboard", exact: true }).click();
  await page.getByRole("button", { name: "Disconnect ESPN" }).click();
  await connect(page, 126);
  await expect(page.getByRole("alert")).toContainText("could not be loaded");
  await expect(page.getByLabel("Your ESPN team")).toHaveCount(0);
});
