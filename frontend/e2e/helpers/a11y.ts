import AxeBuilder from "@axe-core/playwright";
import { expect, type Page } from "@playwright/test";

export async function expectNoAxeViolations(page: Page) {
  // A first-load stagger (components/ui/Stagger.tsx) fades cards in over about half a second; axe would read
  // half-faded text as a contrast failure, so let any entrance finish first.
  await expect(page.locator('[data-stagger="entering"]')).toHaveCount(0);
  // @axe-core/playwright resolves its own playwright-core copy; the Page shapes match at runtime.
  type AxePage = ConstructorParameters<typeof AxeBuilder>[0]["page"];
  const results = await new AxeBuilder({ page: page as unknown as AxePage }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`)).toEqual([]);
}

export async function expectNoHorizontalScroll(page: Page) {
  const { overflow, innerWidth } = await page.evaluate(() => ({
    overflow: document.documentElement.scrollWidth - window.innerWidth,
    innerWidth: window.innerWidth,
  }));
  expect(overflow).toBeLessThanOrEqual(0);
  // Mobile emulation widens the layout viewport to fit overflowing content instead of scrolling; catch that too.
  expect(innerWidth).toBeLessThanOrEqual(page.viewportSize()?.width ?? innerWidth);
}

export async function expectTapTargets(page: Page) {
  const small = await page.$$eval("a[href], button, input, select", (els) =>
    els
      .filter((el) => (el as HTMLElement).offsetParent !== null && !el.closest("[hidden]"))
      .filter((el) => !(el instanceof HTMLInputElement && (el.type === "checkbox" || el.type === "radio")))
      .map((el) => ({ name: el.getAttribute("aria-label") ?? el.textContent?.trim(), r: el.getBoundingClientRect() }))
      .filter(({ r }) => r.width > 0 && (r.width < 44 || r.height < 44))
      .map(({ name, r }) => `${name} ${Math.round(r.width)}×${Math.round(r.height)}`),
  );
  expect(small).toEqual([]);
}

/**
 * Lets a screen finish loading: network quiet, every lazily mounted card and chart scrolled into view once
 * (they start when near the viewport), every `.skeleton` resolved and any first-load stagger finished.
 * Ends scrolled back to the top.
 */
export async function settle(page: Page, { allowSkeleton = false } = {}) {
  await page.waitForLoadState("networkidle");
  await page.evaluate(() => document.fonts.ready);
  await page.evaluate(async () => {
    for (let y = 0; y < document.documentElement.scrollHeight; y += window.innerHeight * 0.8) {
      window.scrollTo(0, y);
      await new Promise((r) => setTimeout(r, 80));
    }
    window.scrollTo(0, 0);
  });
  await page.waitForLoadState("networkidle");
  if (!allowSkeleton) await expect(page.locator(".skeleton")).toHaveCount(0, { timeout: 15_000 });
  await expect(page.locator('[data-stagger="entering"]')).toHaveCount(0);
}

/** The three checks every screen must pass, after `settle`. */
export async function expectScreenAccessible(page: Page) {
  await expectNoHorizontalScroll(page);
  await expectTapTargets(page);
  await expectNoAxeViolations(page);
}
