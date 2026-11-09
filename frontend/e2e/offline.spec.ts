import { expect, test } from "@playwright/test";

import { ADMIN, signIn } from "./helpers/auth.ts";

/** Light offline mode (Foundations: On the phone like an app). The service worker keeps the app shell
 * and the Hub's API answers; offline, the Hub still renders from them, marked as offline with
 * "Last updated" stamps. Chromium runs service workers in the default context, and setOffline applies to
 * the worker's own fetches too, so this is a real offline reload, not a mocked one. */

const HUB_HEADING = /(Good (morning|afternoon|evening|night)|Welcome back), Jamie/;

test("the Hub still renders offline from the service worker's cache", async ({ page, context }) => {
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(err.message));

  await signIn(page, ADMIN);
  await expect(page.getByRole("heading", { level: 1, name: HUB_HEADING })).toBeVisible();

  // Wait for the worker to take control, then load the Hub once more *through* it so the shell's chunks
  // and the Hub's API answers go into its caches (the first load's requests happened before it existed).
  await page.evaluate(() => navigator.serviceWorker.ready);
  await expect.poll(() => page.evaluate(() => !!navigator.serviceWorker.controller), { timeout: 10_000 }).toBe(true);
  const hubCalls = Promise.all([
    page.waitForResponse((r) => r.url().includes("/api/hub") && r.ok()),
    page.waitForResponse((r) => r.url().includes("/api/news/today") && r.ok()),
    page.waitForResponse((r) => r.url().includes("/api/news/next") && r.ok()),
  ]);
  await page.reload();
  await hubCalls;
  await expect(page.getByRole("heading", { level: 1, name: HUB_HEADING })).toBeVisible();
  // The lazy cards below the fold (market data, streak, bests) mount when scrolled near: bring them in.
  await page.mouse.wheel(0, 4000);
  await expect(page.getByRole("region", { name: "Showing up" })).toBeVisible();
  await expect.poll(() => page.evaluate(async () => (await caches.open("tp-api-v1")).keys().then((k) => k.length)), { timeout: 10_000 }).toBeGreaterThanOrEqual(3);

  await context.setOffline(true);
  const cachedHub = page.waitForResponse((r) => r.url().includes("/api/hub"));
  const offlineLoad = await page.reload();
  // Proof it was the worker, not the network: the document came from its fetch handler and the Hub answer
  // carries the stored-at stamp the worker adds only to cached copies.
  expect(offlineLoad?.fromServiceWorker()).toBe(true);
  expect((await cachedHub).headers()["x-tp-cached-at"]).toMatch(/^\d{4}-\d{2}-\d{2}T/);

  await expect(page.getByRole("heading", { level: 1, name: HUB_HEADING })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("You’re offline")).toBeVisible();
  await expect(page.getByText(/Last updated \d{2}:\d{2}/).first()).toBeVisible({ timeout: 15_000 });
  expect(errors).toEqual([]);

  await context.setOffline(false);
  await page.reload();
  await expect(page.getByRole("heading", { level: 1, name: HUB_HEADING })).toBeVisible();
  await expect(page.getByText("You’re offline")).toHaveCount(0);
});

test("a cold offline load of a tool shows an offline state, not an endless skeleton", async ({ page, context }) => {
  await signIn(page, ADMIN);
  await page.evaluate(() => navigator.serviceWorker.ready);
  await expect.poll(() => page.evaluate(() => !!navigator.serviceWorker.controller), { timeout: 10_000 }).toBe(true);
  // Visit once online so the journal's chunk is in the worker's asset cache (its API answers never are).
  await page.goto("/journal");
  await expect(page.locator('main a[href^="/journal/strategies/"]').first()).toBeVisible();
  await page.waitForLoadState("networkidle");

  await context.setOffline(true);
  await page.goto("/journal");
  await expect(page.getByText("You’re offline")).toBeVisible({ timeout: 15_000 }); // the shell's banner
  await expect(page.getByText("The strategy list loads when you're back online.")).toBeVisible({ timeout: 15_000 });
  await expect(page.locator(".skeleton")).toHaveCount(0);
  await context.setOffline(false);
});

test("the service worker never caches private routes", async ({ page }) => {
  await signIn(page, ADMIN);
  await page.evaluate(() => navigator.serviceWorker.ready);
  await expect.poll(() => page.evaluate(() => !!navigator.serviceWorker.controller), { timeout: 10_000 }).toBe(true);
  await page.goto("/settings");
  await page.goto("/journal");
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
  const keys = await page.evaluate(async () => {
    const names = (await caches.keys()).filter((n) => n.startsWith("tp-"));
    const all: string[] = [];
    for (const n of names) for (const req of await (await caches.open(n)).keys()) all.push(new URL(req.url).pathname);
    return all;
  });
  expect(keys.filter((p) => p.startsWith("/api/auth/") && p !== "/api/auth/me")).toEqual([]);
  expect(keys.filter((p) => p.startsWith("/api/admin/") || p.startsWith("/api/me/") || p.startsWith("/api/screenshots/"))).toEqual([]);
  expect(keys.filter((p) => p.startsWith("/api/strategies") || p.startsWith("/api/trades"))).toEqual([]);
});

test("/sw.js is served as JavaScript and not cached for long", async ({ request }) => {
  const res = await request.get("/sw.js");
  expect(res.ok()).toBe(true);
  expect(res.headers()["content-type"]).toMatch(/javascript/);
  // No Cache-Control at all (FileResponse) is fine: browsers always revalidate the worker script itself.
  const cc = res.headers()["cache-control"] ?? "";
  const maxAge = /max-age=(\d+)/.exec(cc);
  expect(maxAge ? Number(maxAge[1]) : 0).toBeLessThanOrEqual(86_400);
  expect(cc).not.toMatch(/immutable/);
});
