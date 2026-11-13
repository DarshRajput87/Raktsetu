import { defineConfig, devices } from "@playwright/test";

/**
 * Browser tests for the search flow. Playwright starts its own API (port 8001,
 * database raktsetu_e2e, seeded with the fixed synthetic city) and a production
 * build of the frontend (port 3100, built into .next-e2e), so results do not
 * depend on the developer's data or dev server. Needs MongoDB running.
 */
const API = "http://127.0.0.1:8001";

export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: "http://localhost:3100",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "phone", use: { ...devices["Pixel 7"], browserName: "chromium" } },
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 900 } } },
  ],
  webServer: [
    {
      command: "node e2e/backend.mjs",
      url: `${API}/health`,
      timeout: 120_000,
      reuseExistingServer: false,
      stdout: "ignore",
    },
    {
      command: "npx next build && npx next start -p 3100",
      url: "http://localhost:3100",
      timeout: 240_000,
      reuseExistingServer: false,
      env: { NEXT_PUBLIC_API_URL: API, NEXT_DIST_DIR: ".next-e2e" },
      stdout: "ignore",
    },
  ],
});
