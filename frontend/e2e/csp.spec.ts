import { expect, test } from "@playwright/test";

import { ADMIN, signIn } from "./helpers/auth.ts";

/** The security headers (backend/app/core/headers.py) must not break the app: the built SPA runs with
 * `script-src 'self'` (no inline script), ECharts canvases, the Monte Carlo Web Worker and the service
 * worker all under the policy. Any violation shows up as a "Refused to …" console error. */

const SCREENS = ["/", "/journal/strategies/3?tab=analytics", "/news", "/settings"];

test("every response carries the security headers", async ({ request }) => {
  for (const path of ["/", "/api/health", "/sw.js", "/site.webmanifest"]) {
    const res = await request.get(path);
    const headers = res.headers();
    expect(headers["content-security-policy"], path).toContain("script-src 'self'");
    expect(headers["content-security-policy"], path).not.toMatch(/script-src[^;]*unsafe-inline/);
    expect(headers["x-frame-options"], path).toBe("DENY");
    expect(headers["x-content-type-options"], path).toBe("nosniff");
    expect(headers["referrer-policy"], path).toBe("strict-origin-when-cross-origin");
    expect(headers["cross-origin-opener-policy"], path).toBe("same-origin");
    expect(headers["permissions-policy"], path).toContain("camera=()");
  }
  expect((await request.get("/sw.js")).headers()["cache-control"]).toBe("no-cache");
  expect((await request.get("/api/auth/csrf")).headers()["cache-control"]).toBe("no-store");
  const index = await request.get("/");
  const assetPath = (await index.text()).match(/src="(\/assets\/[^"]+\.js)"/)?.[1];
  expect(assetPath).toBeTruthy();
  expect((await request.get(assetPath!)).headers()["cache-control"]).toBe("public, max-age=31536000, immutable");
});

test("the CSP blocks nothing the app needs", async ({ page }) => {
  const violations: string[] = [];
  page.on("console", (msg) => {
    const text = msg.text();
    if (/Refused to|Content Security Policy|violates the following/i.test(text)) violations.push(text);
  });
  page.on("pageerror", (err) => violations.push(`pageerror: ${err.message}`));

  await signIn(page, ADMIN);
  for (const path of SCREENS) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
    await page.waitForLoadState("networkidle");
  }
  // The analytics tab draws ECharts canvases (lazily, when a chart scrolls into view) and spins up the
  // Monte Carlo worker: both must run under the policy.
  await page.goto("/journal/strategies/3?tab=analytics");
  const equity = page.getByRole("img", { name: /Equity curve in \$\./ });
  await expect(equity).toBeAttached();
  await equity.scrollIntoViewIfNeeded();
  await expect(equity.locator("canvas").first()).toBeVisible({ timeout: 15_000 });
  await page.waitForLoadState("networkidle");

  expect(violations).toEqual([]);
});
