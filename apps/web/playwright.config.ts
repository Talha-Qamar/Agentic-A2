import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  expect: { timeout: 60_000 },
  workers: 1,
  reporter: [["list"], ["html", { open: "never" }]],
  use: { baseURL: "http://localhost:8000", trace: "retain-on-failure", screenshot: "only-on-failure" },
  webServer: {
    command: "python ../../scripts/e2e_server.py",
    url: "http://localhost:8000/api/health",
    reuseExistingServer: true,
    timeout: 120_000,
  },
});
