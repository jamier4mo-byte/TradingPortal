import AxeBuilder from "@axe-core/playwright";
import { expect, type Page } from "@playwright/test";

export async function expectNoAxeViolations(page: Page) {
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
