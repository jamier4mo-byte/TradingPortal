import { expect, test } from "@playwright/test";

import { settle } from "./helpers/a11y.ts";
import { ADMIN, signIn } from "./helpers/auth.ts";

/**
 * Charts for screen readers (Accessibility: "each chart has a short text summary and an underlying data
 * table"). Every ECharts instance goes through components/charts/Chart.tsx, which renders the canvas host as
 * role="img" with the summary in its name, a visible one-line summary and a "View data table" toggle that
 * renders a real <table> with column headers. Inline SVG sparklines carry their own aria-label.
 */
test.beforeEach(async ({ page }) => {
  await signIn(page, ADMIN);
});

test("every analytics chart has a summary, a named image and a data table with headers", async ({ page }) => {
  await page.goto("/journal/strategies/3?tab=analytics");
  await settle(page);
  const figures = page.locator("figure").filter({ has: page.locator('[role="img"]') });
  const count = await figures.count();
  expect(count, "the analytics tab draws charts").toBeGreaterThanOrEqual(4);

  const summaries = await page.locator("figure figcaption p").evaluateAll((ps) => ps.map((p) => p.textContent?.trim() ?? ""));
  expect(summaries.length).toBe(count);
  expect(summaries.filter((s) => s.length < 10)).toEqual([]);

  const names = await figures.locator('[role="img"]').evaluateAll((els) => els.map((el) => el.getAttribute("aria-label") ?? ""));
  expect(names.filter((n) => n.length < 10)).toEqual([]);

  const toggles = page.getByRole("button", { name: "View data table" });
  expect(await toggles.count(), "one data-table toggle per chart").toBe(count);
  for (let i = 0; i < count; i++) {
    const toggle = page.getByRole("button", { name: "View data table" }).first();
    await toggle.scrollIntoViewIfNeeded();
    const id = await toggle.getAttribute("aria-controls");
    await toggle.click();
    const table = page.locator(`[id="${id}"] table`);
    await expect(table).toBeVisible();
    expect(await table.locator("thead th[scope=col]").count()).toBeGreaterThanOrEqual(2);
    expect(await table.locator("tbody tr").count()).toBeGreaterThanOrEqual(1);
  }
  expect(await page.getByRole("button", { name: "Hide data table" }).count()).toBe(count);

  // Nothing draws outside the wrapper: every canvas sits inside a named role="img" host.
  const strays = await page.locator("canvas").evaluateAll((cs) => cs.filter((c) => !c.closest('[role="img"][aria-label]')).length);
  expect(strays).toBe(0);
});

for (const route of ["/", "/journal", "/markets"]) {
  test(`${route}: every sparkline and gauge is named or hidden from assistive tech`, async ({ page }) => {
    await page.goto(route);
    await settle(page);
    const unnamed = await page.locator("svg").evaluateAll((svgs) =>
      svgs
        .filter((svg) => {
          if (svg.closest("[aria-hidden='true']") || svg.getAttribute("aria-hidden") === "true") return false;
          if (svg.closest("button, a, [role='img'], [role='timer'], [role='status']")) return false; // named by its parent
          return !(svg.getAttribute("role") === "img" && (svg.getAttribute("aria-label") ?? "").length > 0);
        })
        .map((svg) => `${svg.getAttribute("class") ?? ""} in ${svg.parentElement?.tagName.toLowerCase()}`),
    );
    expect(unnamed).toEqual([]);
    const sparklines = await page.locator('svg[role="img"]').evaluateAll((svgs) => svgs.map((s) => s.getAttribute("aria-label") ?? ""));
    expect(sparklines.filter((l) => l.length === 0)).toEqual([]);
  });
}
