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
    baseURL: "http://127.0.0.1:3000",
    trace: "retain-on-failure",
  },
  webServer: {
    command: "npm run dev -- --hostname 127.0.0.1 --port 3000",
    cwd: frontendDir,
    env: {
      ...process.env,
      NODE_PATH: path.join(frontendDir, "node_modules"),
    },
    url: "http://127.0.0.1:3000",
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
