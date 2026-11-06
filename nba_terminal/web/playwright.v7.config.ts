import { defineConfig, devices } from "@playwright/test";
const apiPort = process.env.FANTASY_E2E_PORT || "8217";
const vitePort = process.env.E2E_PORT || "4217";
export default defineConfig({
  testDir: "./e2e",
  testMatch: "v7-integration.spec.ts",
  workers: 1,
  timeout: 90000,
  use: { ...devices["Desktop Chrome"] },
  projects: [
    { name: "vite-proxy", use: { baseURL: `http://127.0.0.1:${vitePort}` } },
    { name: "production-build", use: { baseURL: `http://127.0.0.1:${apiPort}` } },
  ],
  webServer: [
    {
      command: `FANTASY_E2E_PORT=${apiPort} uv run python ../../tests/v7_e2e_server.py`,
      url: `http://127.0.0.1:${apiPort}/api/meta`,
      reuseExistingServer: false,
      gracefulShutdown: { signal: "SIGTERM", timeout: 5000 },
    },
    {
      command: `VITE_API_TARGET=http://127.0.0.1:${apiPort} bun x vite --host 127.0.0.1 --port ${vitePort} --strictPort`,
      url: `http://127.0.0.1:${vitePort}`,
      reuseExistingServer: false,
      gracefulShutdown: { signal: "SIGTERM", timeout: 5000 },
    },
  ],
});
