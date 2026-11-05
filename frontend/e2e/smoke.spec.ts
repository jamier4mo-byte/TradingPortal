import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("API is healthy", async ({ request }) => {
  const body = await (await request.get("/api/health")).json();
  expect(body.db_ok).toBe(true);
});

test("Hub renders the greeting and both launch islands", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(/Good (morning|afternoon|evening|night)/);
  await expect(page.getByRole("link", { name: "Open Replay Journal" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Open News Room" })).toBeVisible();
});

test("no horizontal scroll", async ({ page }) => {
  await page.goto("/");
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});

test("tap targets are at least 44px", async ({ page }) => {
  await page.goto("/");
  const small = await page.$$eval("a[href], button", (els) =>
    els
      .filter((el) => (el as HTMLElement).offsetParent !== null)
      .map((el) => ({ name: el.getAttribute("aria-label") ?? el.textContent?.trim(), r: el.getBoundingClientRect() }))
      .filter(({ r }) => r.width < 44 || r.height < 44)
      .map(({ name, r }) => `${name} ${Math.round(r.width)}×${Math.round(r.height)}`),
  );
  expect(small).toEqual([]);
});

test("no WCAG 2.2 AA violations on the Hub", async ({ page }) => {
  await page.goto("/");
  // @axe-core/playwright can resolve its own playwright-core copy; the Page shapes match at runtime.
  type AxePage = ConstructorParameters<typeof AxeBuilder>[0]["page"];
  const results = await new AxeBuilder({ page: page as unknown as AxePage }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.length}`)).toEqual([]);
});
