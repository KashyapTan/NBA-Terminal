import { mkdirSync } from "node:fs";
import { expect, test } from "@playwright/test";

// Served production JS/HTML, real API routes/cache/services/normalizers, test-only NBA transport.
// Season/shooting/V3 fixtures include captured public schemas; game logs are synthetic.
for (const width of [1440, 390]) {
  test(`integrated Players profiles, analyses and direct navigation at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/players?season=2024-25&phase=Playoffs");
    const sections = page.getByRole("navigation", { name: "Game Center sections" });
    await expect(sections.getByRole("link", { name: "Players" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    await page.getByRole("searchbox", { name: "Search NBA players" }).fill("Shai");
    await page.getByRole("button", { name: /Shai Gilgeous-Alexander/ }).click();
    await expect(page).toHaveURL(/players\/1628983\?season=2024-25&phase=Playoffs/);
    await expect(
      page.getByRole("heading", { name: "Shai Gilgeous-Alexander", exact: true }),
    ).toBeVisible();
    await page.reload();
    await expect(
      page.getByRole("heading", { name: "Shai Gilgeous-Alexander", exact: true }),
    ).toBeVisible();
    mkdirSync("../../code_review/v5_app/generated/player", { recursive: true });
    await page.screenshot({ path: `../../code_review/v5_app/generated/player/shell-${width}.png` });
    const measure = page.getByLabel("Season dashboard measure");
    for (const name of ["Base", "Misc", "Scoring", "Usage", "Defense", "Advanced"]) {
      const response =
        name === "Advanced"
          ? null
          : page.waitForResponse((r) => r.url().includes(`/measures/${name}?`) && r.ok());
      await measure.selectOption(name);
      if (response) await response;
      if (name === "Usage")
        await expect(
          page.getByRole("region", { name: "Full season profile tables" }),
        ).toContainText("Total minutes 851.0");
    }
    await page.getByRole("button", { name: "Load shooting breakdowns" }).click();
    const shooting = page.getByLabel("Shooting breakdown", { exact: true });
    for (const name of [
      "Overall",
      "Shot Area",
      "Distance 5ft",
      "Distance 8ft",
      "Assisted",
      "Shot Type Summary",
    ]) {
      await shooting.selectOption(name);
      await expect(
        page.getByRole("region", { name: "Shooting breakdowns", exact: true }).getByRole("table"),
      ).toBeVisible();
    }
    await page.getByRole("searchbox", { name: "Find comparison player" }).fill("Nikola Jokic");
    await page
      .getByLabel("Comparison player", { exact: true })
      .selectOption({ label: "Nikola Jokić" });
    await page.getByLabel("Comparison season", { exact: true }).fill("2024-25");
    await page.getByRole("button", { name: "Compare season", exact: true }).click();
    const sample = page.getByRole("table", { name: "Season sample comparison" });
    await expect(sample).toContainText("Nikola Jokić");
    await expect(sample).toContainText("Shai Gilgeous-Alexander");
    await expect
      .poll(() => page.evaluate(() => document.documentElement.scrollWidth))
      .toBeLessThanOrEqual(width);
    const geometry = await page.locator(".player-analysis__visuals svg").evaluateAll((els) =>
      els.map((el) => ({
        width: el.getBoundingClientRect().width,
        height: el.getBoundingClientRect().height,
      })),
    );
    for (const chart of geometry) {
      expect(chart.height).toBeLessThanOrEqual(221);
      expect(chart.width / chart.height).toBeGreaterThan(2.5);
    }
    if (width === 1440) {
      const sizes = await page
        .locator(".player-analysis__consistency-table")
        .evaluate((el) => [
          el.getBoundingClientRect().width,
          el.parentElement!.getBoundingClientRect().width,
        ]);
      expect(Math.abs(sizes[0] - sizes[1])).toBeLessThanOrEqual(2);
    }
    mkdirSync("../../code_review/v5_app/generated/player", { recursive: true });
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({
      path: `../../code_review/v5_app/generated/player/profile-${width}.png`,
      fullPage: true,
    });
    await page
      .getByRole("region", { name: "Opponent and season comparison" })
      .screenshot({ path: `../../code_review/v5_app/generated/player/comparison-${width}.png` });
    const log = page.getByRole("link", { name: /Open box score 2025-06-22/ }).last();
    await log.focus();
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/game\/0042400407\?season=2024-25&phase=Playoffs&player=1628983/);
    await expect(
      page.getByRole("heading", { name: "Indiana Pacers at Oklahoma City Thunder" }),
    ).toBeVisible();
    await page.reload();
    await expect(
      page.getByRole("heading", { name: "Indiana Pacers at Oklahoma City Thunder" }),
    ).toBeVisible();
    await page.getByRole("link", { name: "Shai Gilgeous-Alexander", exact: true }).click();
    await expect(
      page.getByRole("heading", { name: "Shai Gilgeous-Alexander", exact: true }),
    ).toBeVisible();
    await expect(page.getByText("Turnovers / 100 plays", { exact: true })).toBeVisible();
    await expect(page.locator(".player-analysis__game-line")).toBeVisible();
    const gameLine = page.locator(".player-analysis__game-line");
    const turnoverIndex = await gameLine
      .locator("th")
      .evaluateAll((headers) => headers.findIndex((header) => header.textContent === "Turnovers"));
    expect(turnoverIndex).toBeGreaterThanOrEqual(0);
    await expect(gameLine.locator("tbody td").nth(turnoverIndex)).toHaveText("2");
    await page.reload();
    await expect(page.locator(".player-analysis__game-line")).toBeVisible();
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({
      path: `../../code_review/v5_app/generated/player/game-${width}.png`,
      fullPage: true,
    });
    await page.goBack();
    await page.goBack();
    await expect(page).toHaveURL(/players\/1628983/);
    await expect(
      page.getByRole("heading", { name: "Shai Gilgeous-Alexander", exact: true }),
    ).toBeVisible();
  });
}

for (const width of [1440, 390]) {
  test(`all six integrated tools use production routes and survive reload at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.goto("/tools/predictor?season=2024-25&phase=Playoffs");
    for (const [tool, title] of [
      ["predictor", "Points Predictor"],
      ["consistency", "Team Consistency"],
      ["defense", "Team Defense"],
      ["slate", "Slate Scanner"],
      ["picks", "Picks Archive"],
      ["catalog", "Stats / API Reference"],
    ]) {
      await page
        .getByRole("navigation", { name: "Choose analytics tool" })
        .getByRole("button", { name: title, exact: true })
        .click();
      await expect(page).toHaveURL(new RegExp(`/tools/${tool}\\?season=2024-25&phase=Playoffs`));
      await page.reload();
      await expect(page.getByRole("heading", { name: title, exact: true })).toBeVisible();
      const online = tool !== "picks" && tool !== "catalog";
      if (online) {
        await expect(page.getByRole("textbox", { name: "Season", exact: true })).toHaveValue(
          "2024-25",
        );
        await expect(page.getByRole("combobox", { name: "Phase", exact: true })).toHaveValue(
          "Playoffs",
        );
      }
      if (tool === "predictor" || tool === "consistency")
        await page
          .getByRole("combobox", { name: "Player team", exact: true })
          .selectOption("1610612760");
      if (tool === "predictor" || tool === "slate")
        await page.getByLabel("Game date (NBA Eastern)", { exact: true }).fill("2025-06-22");
      if (tool === "predictor") {
        await page
          .getByRole("combobox", { name: "Opponent", exact: true })
          .selectOption("1610612754");
        await page.getByRole("textbox", { name: "Find player", exact: true }).fill("Shai");
        await page.getByRole("combobox", { name: "Player", exact: true }).selectOption("1628983");
      }
      if (tool === "catalog")
        await page
          .getByRole("textbox", { name: "Search endpoints / parameters / schema" })
          .fill("PlayerGameLogs");
      const response = page.waitForResponse(
        (r) => new URL(r.url()).pathname === `/api/tools/${tool}` && r.ok(),
      );
      await page
        .getByRole("button", { name: online ? "Run analysis" : "Search / browse", exact: true })
        .click();
      const result = await (await response).json();
      expect(result.state, JSON.stringify(result.errors)).toBe("ready");
      const region = page.getByRole("region", { name: "Analysis result", exact: true });
      await expect(region).toBeVisible();
      if (tool === "predictor") {
        expect(result.projection).toBeCloseTo(37.04099, 4);
        await expect(region).toContainText("37.0 estimated points");
      }
      if (tool === "consistency") {
        expect(result.rows).toHaveLength(2);
        await expect(region).toContainText("Shai Gilgeous-Alexander");
      }
      if (tool === "defense") {
        expect(result.rows).toHaveLength(2);
        await expect(region).toContainText("OKC");
      }
      if (tool === "slate") {
        expect(result.rows).toHaveLength(2);
        await expect(region).toContainText("2 qualified · 2 evaluated");
      }
      if (tool === "picks") {
        expect(result.files.length).toBeGreaterThan(0);
        const note = result.files.find((file: { filename: string; preview: string }) =>
          file.preview.trim(),
        );
        expect(note).toBeTruthy();
        await region.getByRole("button", { name: note.filename, exact: true }).click();
        await expect(region.locator(".at-note")).toBeVisible();
        await expect(region.getByRole("button", { name: "Back to matching files" })).toBeVisible();
      }
      if (tool === "catalog") {
        expect(result.metadata_only).toBe(true);
        await expect(region).toContainText("PlayerGameLogs");
        await region.getByText("PlayerGameLogs · Game Logs & Finders", { exact: true }).click();
        await expect(region.getByText("season_nullable", { exact: true })).toBeVisible();
      }
      await expect
        .poll(() => page.evaluate(() => document.documentElement.scrollWidth))
        .toBeLessThanOrEqual(width);
      mkdirSync("../../code_review/v5_app/generated/tools", { recursive: true });
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.screenshot({
        path: `../../code_review/v5_app/generated/tools/${tool}-${width}.png`,
        fullPage: true,
      });
    }
    expect(errors).toEqual([]);
    await page
      .getByRole("navigation", { name: "Game Center sections" })
      .getByRole("link", { name: "Players", exact: true })
      .click();
    await expect(page).toHaveURL(/players\?season=2024-25&phase=Playoffs/);
    await expect(page.getByRole("searchbox", { name: "Search NBA players" })).toBeVisible();
  });
}
