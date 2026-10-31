import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  testMatch: "league-production.spec.ts",
  fullyParallel: true,
  reporter: "list",
  use: { ...devices["Desktop Chrome"] },
  projects: [
    { name: "vite-proxy", use: { baseURL: "http://127.0.0.1:4198" } },
    { name: "production-build", use: { baseURL: "http://127.0.0.1:8197" } },
  ],
  webServer: [
    {
      command: "uv run python ../../tests/fantasy_e2e_server.py",
      url: "http://127.0.0.1:8197/api/meta",
      reuseExistingServer: false,
      timeout: 30_000,
    },
    {
      command: "bun run vite --host 127.0.0.1 --port 4198 --strictPort",
      env: { VITE_API_TARGET: "http://127.0.0.1:8197" },
      url: "http://127.0.0.1:4198",
      reuseExistingServer: false,
      timeout: 30_000,
    },
  ],
});
