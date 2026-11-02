import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  testMatch: "week-reset.spec.ts",
  workers: 1,
  use: { ...devices["Desktop Chrome"], baseURL: "http://127.0.0.1:8196" },
  webServer: {
    command: "uv run python ../../tests/week_reset_e2e_server.py",
    url: "http://127.0.0.1:8196/api/meta",
    reuseExistingServer: false,
    timeout: 30000,
  },
});
