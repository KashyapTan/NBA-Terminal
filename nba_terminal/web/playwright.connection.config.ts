import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  testMatch: "connection-lifecycle.spec.ts",
  workers: 1,
  timeout: 90000,
  use: { ...devices["Desktop Chrome"], baseURL: "http://127.0.0.1:4212" },
  webServer: [
    {
      command: "uv run python ../../tests/connection_e2e_server.py",
      url: "http://127.0.0.1:8212/__test__/connection-control",
      reuseExistingServer: false,
    },
    {
      command:
        "VITE_API_TARGET=http://127.0.0.1:8212 bun x vite --host 127.0.0.1 --port 4212 --strictPort",
      url: "http://127.0.0.1:4212",
      reuseExistingServer: false,
    },
  ],
});
