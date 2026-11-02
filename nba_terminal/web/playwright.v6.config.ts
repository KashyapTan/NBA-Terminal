import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  testMatch: "v6-integration.spec.ts",
  workers: 1,
  timeout: 90000,
  use: { ...devices["Desktop Chrome"] },
  projects: [
    { name: "vite-proxy", use: { baseURL: "http://127.0.0.1:4214" } },
    { name: "production-build", use: { baseURL: "http://127.0.0.1:8214" } },
  ],
  webServer: [
    {
      command: "uv run python ../../tests/v6_e2e_server.py",
      url: "http://127.0.0.1:8214/api/meta",
      reuseExistingServer: false,
      gracefulShutdown: { signal: "SIGTERM", timeout: 5000 },
    },
    {
      command:
        "VITE_API_TARGET=http://127.0.0.1:8214 bun x vite --host 127.0.0.1 --port 4214 --strictPort",
      url: "http://127.0.0.1:4214",
      reuseExistingServer: false,
      gracefulShutdown: { signal: "SIGTERM", timeout: 5000 },
    },
  ],
});
