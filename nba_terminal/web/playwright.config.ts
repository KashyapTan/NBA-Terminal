import { defineConfig, devices } from "@playwright/test";

const port = process.env.E2E_PORT || "4173";

export default defineConfig({
  testDir: "./e2e",
  testIgnore: ["league-production.spec.ts", "v5-integration.spec.ts", "analytics-tools.spec.ts"],
  fullyParallel: true,
  reporter: "list",
  use: { baseURL: "http://127.0.0.1:" + port, ...devices["Desktop Chrome"] },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "bun run vite --host 127.0.0.1 --port " + port + " --strictPort",
    url: "http://127.0.0.1:" + port,
    reuseExistingServer: !process.env.CI,
    gracefulShutdown: { signal: "SIGTERM", timeout: 5_000 },
    timeout: 30_000,
  },
});
