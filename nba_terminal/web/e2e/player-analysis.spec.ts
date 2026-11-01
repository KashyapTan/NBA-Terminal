import { expect, test } from "@playwright/test";

for (const width of [390, 1440]) {
  test(`independent player profile fits ${width}px and retains keyboard game links`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.route("**/api/players**", (route) => {
      const path = new URL(route.request().url()).pathname;
      if (path === "/api/players")
        return route.fulfill({
          json: { players: [{ player_id: 7, name: "Test Player", active: true }] },
        });
      return route.fulfill({
        json: {
          player_id: 7,
          player_name: "Test Player",
          season: "2025-26",
          phase: "Playoffs",
          advanced: {
            GP: 20,
            MIN: 35.2,
            TS_PCT: 0.65,
            USG_PCT: 0.31,
            NET_RATING: 5.2,
            PIE: 0.19,
            POSS: 80,
            PACE: 98,
          },
          advanced_state: "available",
          advanced_note: "",
          advanced_source: "LeagueDashPlayerStats · Advanced · PerGame",
          shooting: {
            efg_pct: { value: 0.6, games: 20 },
            ts_pct: { value: 0.65, games: 20 },
            fg3a_rate: { value: 0.45, games: 20 },
            fta_rate: { value: 0.3, games: 20 },
          },
          history: {
            state: "available",
            note: "",
            season: "2025-26",
            phase: "Playoffs",
            opponent: null,
            games_played: 20,
            opponent_games_played: 0,
            opponent_games: [],
            summary: Object.fromEntries(
              ["PTS", "REB", "AST", "STL", "BLK", "FG3M", "PRA"].map((key) => [
                key,
                {
                  label: key,
                  mean: 21,
                  std: 6.5,
                  consistency_cv: 0.31,
                  games: 20,
                  last_5: 25,
                  last_5_games: 5,
                  last_10: 23,
                  last_10_games: 10,
                  last_20: 21,
                  last_20_games: 20,
                },
              ]),
            ),
            games: Array.from({ length: 20 }, (_, index) => ({
              game_id: String(42400407 - index).padStart(10, "0"),
              game_date: `2025-06-${String(22 - index).padStart(2, "0")}`,
              matchup: "OKC vs. IND",
              wl: "W",
              min: 35.2,
              pts: 15 + (index % 15),
              reb: 4,
              ast: 7,
              fgm: 8,
              fga: 17,
              fg3m: 2,
              fg3a: 5,
              ts_pct: 0.65,
            })),
          },
        },
      });
    });
    await page.goto("/e2e/fixtures/player-preview.html");
    await expect(page.getByRole("heading", { name: "Test Player" })).toBeVisible();
    await expect(page.getByText("65.0%", { exact: true }).first()).toBeVisible();
    const dimensions = await page.evaluate(() => ({
      viewport: window.innerWidth,
      page: document.documentElement.scrollWidth,
      charts: Array.from(document.querySelectorAll(".player-analysis__visuals svg")).map((el) => ({
        width: el.getBoundingClientRect().width,
        height: el.getBoundingClientRect().height,
      })),
      table: document.querySelector(".player-analysis__consistency-table")?.getBoundingClientRect()
        .width,
      wrap: document
        .querySelector(".player-analysis__consistency-table")
        ?.parentElement?.getBoundingClientRect().width,
    }));
    expect(dimensions.page).toBeLessThanOrEqual(dimensions.viewport);
    expect(dimensions.charts).toHaveLength(4);
    for (const chart of dimensions.charts) {
      expect(chart.height).toBeGreaterThan(85);
      expect(chart.height).toBeLessThanOrEqual(221);
      expect(chart.width / chart.height).toBeGreaterThan(2.5);
      expect(chart.width / chart.height).toBeLessThan(4);
    }
    if (width > 1000) expect(Math.abs(dimensions.table! - dimensions.wrap!)).toBeLessThanOrEqual(2);
    const link = page.getByRole("link", { name: /Open box score 2025-06-21/ });
    await link.focus();
    await expect(link).toBeFocused();
    await expect(link).toHaveAttribute(
      "href",
      "/game/0042400406?season=2025-26&phase=Playoffs&player=7",
    );
    await page.screenshot({ path: `test-results/player-profile-${width}.png`, fullPage: true });
  });
}
