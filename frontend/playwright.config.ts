import { defineConfig, devices } from "@playwright/test";
import path from "node:path";

const frontendDir = path.resolve(__dirname);

export default defineConfig({
  testDir: "./tests",
  globalTimeout: 90_000,
  timeout: 60_000,
  expect: {
    timeout: 10_000,
  },
  use: {
    baseURL: "http://localhost:80",
    trace: "retain-on-failure",
  },
  webServer: {
    command: "docker compose up -d",
    cwd: path.resolve(__dirname, ".."),
    url: "http://localhost:80/up",
    reuseExistingServer: true,
    timeout: 120_000,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
