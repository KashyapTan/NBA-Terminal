import { expect, test } from "@playwright/test";

// Presentation preparation only. Integration acceptance must run actual backend HTTP flows.
test("compact workspace has closed analysis, true net and dismissible keyboard help", async ({
  page,
}) => {
  await page.goto("/e2e/fixtures/waiver-preview.html");
  await expect(page.getByRole("heading", { name: "2 moves to consider" })).toBeVisible();
  await expect(page.locator(".ww-analysis")).not.toHaveAttribute("open");
  await expect(page.locator(".ww-move")).toHaveCount(2);
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
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    const help = page.getByRole("button", { name: "About this waiver plan" });
    await help.tap();
    await expect(page.getByRole("tooltip").first()).toBeVisible();
    await help.tap();
    await expect(page.getByRole("tooltip").first()).toBeHidden();
  } finally {
    await context.close();
  }
});
