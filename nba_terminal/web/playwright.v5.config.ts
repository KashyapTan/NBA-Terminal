import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  testMatch: "v5-integration.spec.ts",
  workers: 2,
  reporter: "list",
  use: { ...devices["Desktop Chrome"], baseURL: "http://127.0.0.1:8195" },
  webServer: {
    command: "uv run python ../../tests/v5_app_e2e_server.py",
    url: "http://127.0.0.1:8195/__test__/v5-fixture",
    reuseExistingServer: false,
    timeout: 30000,
  },
});
