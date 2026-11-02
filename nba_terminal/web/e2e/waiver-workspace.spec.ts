import { expect, test } from "@playwright/test";

// Presentation preparation only. Integration acceptance must run actual backend HTTP flows.
test("compact workspace has closed analysis, true net and dismissible keyboard help", async ({
  page,
}) => {
  await page.goto("/e2e/fixtures/waiver-preview.html");
  await expect(page.getByRole("heading", { name: "2 moves to consider" })).toBeVisible();
  await expect(page.locator(".ww-analysis")).not.toHaveAttribute("open");
  await expect(page.locator(".ww-move")).toHaveCount(2);
  await expect(page.locator(".ww-forecast-table tbody tr")).toHaveCount(9);
  await expect(page.locator('.ww-forecast [data-focus="true"]')).toHaveCount(5);
  const sections = await page
    .locator(".ww-plan, .ww-forecast, .ww-analysis")
    .evaluateAll((nodes) => nodes.map((node) => node.className));
  expect(sections).toEqual(["ww-plan", "ww-forecast", "ww-analysis"]);
  await expect(page.locator(".ww-move").first()).toContainText("28.4 MPG · 5 GP / 6 team games");
  await expect(page.locator(".ww-loss").first()).toContainText("Net -6Loss");
  const help = page.getByRole("button", { name: "About this waiver plan" });
  await help.hover();
  await expect(page.getByRole("tooltip").first()).toBeVisible();
  await page.mouse.move(0, 0);
  await help.focus();
  await expect(page.getByRole("tooltip").first()).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(help).toBeFocused();
  await expect(page.getByRole("tooltip").first()).toBeHidden();
  const forecastHelp = page.getByRole("button", { name: "About the matchup forecast" });
  await forecastHelp.focus();
  await expect(page.getByRole("tooltip").last()).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("tooltip").last()).toBeHidden();
  const gamesHelp = page.getByRole("button", { name: "Games and usable starts for move 1" });
  await gamesHelp.focus();
  const gamesTooltip = page.locator(`#${await gamesHelp.getAttribute("aria-describedby")}`);
  await expect(gamesTooltip).toBeVisible();
  await expect(gamesTooltip).toContainText("slot limits");
  await page.keyboard.press("Escape");
  await expect(gamesTooltip).toBeHidden();
  await page.screenshot({
    path: "../../docs/evidence/v7-forecast-prep/desktop.png",
    fullPage: true,
  });
});
test("mobile saved result retains compact cards and touch help", async ({ browser }) => {
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    hasTouch: true,
    isMobile: true,
  });
  const page = await context.newPage();
  try {
    await page.goto(
      "http://127.0.0.1:" +
        (process.env.E2E_PORT || "4173") +
        "/e2e/fixtures/waiver-preview.html?failure",
    );
    await expect(page.getByRole("button", { name: "Retry" })).toBeVisible();
    await expect(page.locator(".ww-move")).toHaveCount(2);
    await expect(page.locator(".ww-forecast-table tbody tr")).toHaveCount(9);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    const help = page.getByRole("button", { name: "About this waiver plan" });
    await help.tap();
    await expect(page.getByRole("tooltip").first()).toBeVisible();
    await help.tap();
    await expect(page.getByRole("tooltip").first()).toBeHidden();
    const forecastHelp = page.getByRole("button", { name: "About the matchup forecast" });
    await forecastHelp.tap();
    const tooltip = page.getByRole("tooltip").last();
    await expect(tooltip).toBeVisible();
    const bounds = await tooltip.boundingBox();
    expect(bounds!.x).toBeGreaterThanOrEqual(0);
    expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(390);
    await forecastHelp.tap();
    await expect(tooltip).toBeHidden();
    const gamesHelp = page.getByRole("button", { name: "Games and usable starts for move 1" });
    await gamesHelp.tap();
    const gamesTooltip = page.locator(`#${await gamesHelp.getAttribute("aria-describedby")}`);
    await expect(gamesTooltip).toBeVisible();
    await gamesHelp.tap();
    await expect(gamesTooltip).toBeHidden();
    await page.screenshot({
      path: "../../docs/evidence/v7-forecast-prep/mobile.png",
      fullPage: true,
    });
    await page.setViewportSize({ width: 320, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    const cellsFit = await page
      .locator(".ww-forecast-table td, .ww-forecast-table th")
      .evaluateAll((cells) => cells.every((cell) => cell.scrollWidth <= cell.clientWidth));
    expect(cellsFit).toBe(true);
    await page.screenshot({
      path: "../../docs/evidence/v7-forecast-prep/mobile-320.png",
      fullPage: true,
    });
  } finally {
    await context.close();
  }
});
