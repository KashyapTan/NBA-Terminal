import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  testMatch: "opponent-integration.spec.ts",
  workers: 1,
  timeout: 90000,
  use: { ...devices["Desktop Chrome"] },
  projects: [
    { name: "vite-proxy", use: { baseURL: "http://127.0.0.1:4219" } },
    { name: "production-build", use: { baseURL: "http://127.0.0.1:8219" } },
  ],
  webServer: [
    {
      command: "uv run python ../../tests/opponent_e2e_server.py",
      url: "http://127.0.0.1:8219/api/meta",
      reuseExistingServer: false,
      gracefulShutdown: { signal: "SIGTERM", timeout: 5000 },
    },
    {
      command:
        "VITE_API_TARGET=http://127.0.0.1:8219 bun x vite --host 127.0.0.1 --port 4219 --strictPort",
      url: "http://127.0.0.1:4219",
      reuseExistingServer: false,
      gracefulShutdown: { signal: "SIGTERM", timeout: 5000 },
    },
  ],
});
