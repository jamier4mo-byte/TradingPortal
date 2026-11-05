import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { defineConfig, devices } from "@playwright/test";

/** Smoke suite: a real backend on its own port with a throw-away data folder, serving the
 * built front end (`make smoke` builds first). Set SMOKE_BASE to test an app already running. */
const PORT = Number(process.env.SMOKE_PORT ?? 8766);
const BASE = process.env.SMOKE_BASE ?? `http://127.0.0.1:${PORT}`;
const DATA_DIR = mkdtempSync(join(tmpdir(), "trading-portal-smoke-"));

export default defineConfig({
  testDir: "./e2e",
  timeout: 45_000,
  workers: 1,
  reporter: process.env.CI ? "github" : "list",
  outputDir: "./e2e/.results",
  use: { baseURL: BASE, reducedMotion: "reduce", trace: "retain-on-failure" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } },
    { name: "phone", use: { ...devices["Desktop Chrome"], viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true } },
  ],
  webServer: process.env.SMOKE_BASE
    ? undefined
    : {
        command: `cd ../backend && .venv/bin/python -m app.cli seed-dev && .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port ${PORT}`,
        url: `${BASE}/api/health`,
        reuseExistingServer: false,
        timeout: 60_000,
        env: {
          TRADING_PORTAL_DATA_DIR: DATA_DIR,
          TRADING_PORTAL_ENV: "development",
          TRADING_PORTAL_SECRET_KEY: "smoke-suite-secret-key-not-for-production-0123456789",
          TRADING_PORTAL_LOGIN_RATE_PER_MINUTE: "1000",
        },
      },
});
