import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  testMatch: "week-reset.spec.ts",
  workers: 1,
  use: { ...devices["Desktop Chrome"], baseURL: "http://127.0.0.1:8214" },
  webServer: {
    command: "FANTASY_E2E_PORT=8214 uv run python ../../tests/week_reset_e2e_server.py",
    gracefulShutdown: { signal: "SIGTERM", timeout: 5000 },
    url: "http://127.0.0.1:8214/api/meta",
    reuseExistingServer: false,
    timeout: 30000,
  },
});
