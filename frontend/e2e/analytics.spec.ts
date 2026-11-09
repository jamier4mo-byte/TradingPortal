import { expect, type Page, test } from "@playwright/test";

import { expectNoAxeViolations, expectNoHorizontalScroll, expectTapTargets } from "./helpers/a11y.ts";
import { ADMIN, MEMBER, signIn } from "./helpers/auth.ts";

/** Seeded by seed-dev: strategy 1 (Jamie, fixture imports), 3 (Jamie, synthetic: 35 ideal + 160 backtest),
 * 4 (Sam, 80 backtest), 5 (Alex, 40 backtest). */
const ROUTES = [
  "/journal/strategies/3?tab=analytics",
  "/journal/strategies/3?tab=analytics&src=ideal",
  "/journal/strategies/3?tab=analytics&src=compare",
  "/journal/strategies/3?tab=analytics&export=1",
  "/journal/analytics?split=1",
];

const isPhone = (page: Page) => (page.viewportSize()?.width ?? 1440) < 600;

async function openFilters(page: Page) {
  if (isPhone(page)) await page.getByRole("button", { name: /^Filters/ }).click();
}

async function closeFilters(page: Page) {
  if (isPhone(page)) await page.getByRole("button", { name: /^Show \d+ trades$/ }).click();
}

test.describe("analytics screens are accessible and fit the screen", () => {
  test.beforeEach(async ({ page }) => {
    await signIn(page, ADMIN);
  });
  for (const route of ROUTES) {
    test(`${route} passes axe, has no horizontal scroll and 44px targets`, async ({ page }) => {
      await page.goto(route);
      await expect(page.getByTestId("analytics-toolbar")).toBeVisible();
      await expect(page.getByText(/^\d+ of \d+ trades/)).toBeVisible();
      await page.waitForLoadState("networkidle");
      await expectNoHorizontalScroll(page);
      await expectTapTargets(page);
      await expectNoAxeViolations(page);
    });
  }
});

test.describe("analytics behaviour", () => {
  test.beforeEach(async ({ page }) => {
    await signIn(page, ADMIN);
  });

  test("backtest view: KPIs, charts with summaries and data tables, Monte Carlo", async ({ page }) => {
    await page.goto("/journal/strategies/3?tab=analytics");
    await expect(page.getByText("160 of 160 trades")).toBeVisible();
    // $ is the headline (amends 01): Net P&L leads, R sits underneath, the equity curve opens in $.
    await expect(page.getByText("Net P&L", { exact: true }).first()).toBeVisible();
    const equity = page.getByRole("img", { name: /Equity curve in \$\. 160 trades, finishing at/ });
    await expect(equity).toBeAttached();
    // Charts start when they scroll into view, so the draw-in plays on first sight.
    await equity.scrollIntoViewIfNeeded();
    await expect(equity.locator("canvas").first()).toBeVisible();
    // Every chart has a text summary and a data table.
    const card = page.getByRole("region", { name: "Equity curve" });
    await card.getByRole("button", { name: "View data table" }).click();
    await expect(card.getByRole("table")).toBeVisible();
    await expect(card.getByRole("row")).toHaveCount(161);
    // The formula is one tap away.
    await page.getByRole("button", { name: "How win rate is worked out" }).first().click();
    await expect(page.getByText("Breakevens are left out, as FX Replay does.").first()).toBeVisible();
    // Monte Carlo runs in a worker and answers the drawdown question.
    const mc = page.getByTestId("monte-carlo");
    await mc.scrollIntoViewIfNeeded();
    await expect(mc.locator("#mc-prob")).toContainText("of paths", { timeout: 15_000 });
    await expect(page.getByTestId("pnl-calendar")).toBeVisible();
  });

  test("a filter lands in the URL, narrows every number, and survives a reload", async ({ page }) => {
    await page.goto("/journal/strategies/3?tab=analytics");
    await expect(page.getByText("160 of 160 trades")).toBeVisible();
    await openFilters(page);
    await page.getByRole("button", { name: "Mon", exact: true }).click();
    await page.getByRole("button", { name: "Short", exact: true }).click();
    await closeFilters(page);
    await expect(page).toHaveURL(/weekdays=0/);
    await expect(page).toHaveURL(/directions=sell/);
    const summary = page.getByText(/^\d+ of 160 trades · Backtest · Mon · shorts/);
    await expect(summary).toBeVisible();
    const text = await summary.textContent();
    await page.reload();
    await expect(page.getByText(text ?? "")).toBeVisible();
    await openFilters(page);
    await expect(page.getByRole("button", { name: "Mon", exact: true })).toHaveAttribute("aria-pressed", "true");
    await page.getByRole("button", { name: "Clear all" }).click();
    await closeFilters(page);
    await expect(page.getByText("160 of 160 trades")).toBeVisible();
    await expect(page).not.toHaveURL(/weekdays/);
  });

  test("the source switch keeps its place in the URL", async ({ page }) => {
    await page.goto("/journal/strategies/3?tab=analytics");
    const source = page.getByRole("radiogroup", { name: "Data source" });
    await source.getByRole("radio", { name: "Ideal", exact: true }).click();
    await expect(page).toHaveURL(/src=ideal/);
    await expect(page.getByRole("region", { name: "Entry times" })).toBeVisible();
    await expect(page.getByRole("region", { name: "Strategy profile" })).toBeVisible();
    await source.getByRole("radio", { name: "Compare" }).click();
    await expect(page).toHaveURL(/src=compare/);
    await expect(page.getByText("Winners capture")).toBeVisible();
    // A table on wider screens; one card per row on the phone.
    await expect(page.getByTestId(isPhone(page) ? "compare-cards" : "compare-table")).toBeVisible();
  });

  test("no trades match: a clear empty state with a way back", async ({ page }) => {
    await page.goto("/journal/strategies/3?tab=analytics&instruments=EURUSD");
    await expect(page.getByText("No trades match these filters")).toBeVisible();
    await page.getByRole("button", { name: "Clear filters" }).click();
    await expect(page.getByText("160 of 160 trades")).toBeVisible();
  });

  test("the imported strategy reconciles with FX Replay", async ({ page }) => {
    await page.goto("/journal/strategies/1?tab=analytics");
    await expect(page.getByTestId("reconcile")).toContainText("Reconciled with FX Replay");
  });

  test("split by owner overlays up to three owners in their colours", async ({ page }) => {
    await page.goto("/journal/analytics?split=1");
    await expect(page.getByRole("heading", { level: 1, name: "Analytics" })).toBeVisible();
    const owners = page.getByTestId("owner-overlay");
    await expect(owners).toBeVisible();
    for (const name of ["Jamie", "Sam", "Alex"]) await expect(owners.getByText(name, { exact: true })).toBeVisible();
  });

  test("more than three owners become small multiples", async ({ page }) => {
    await page.goto("/dev/components");
    const multiples = page.getByTestId("owner-multiples");
    await multiples.scrollIntoViewIfNeeded();
    await expect(multiples.getByRole("img")).toHaveCount(4);
  });

  test("export: the zip and CSV download with the current filters", async ({ page, context }) => {
    await page.goto("/journal/strategies/3?tab=analytics&weekdays=0&export=1");
    const dialog = page.getByRole("dialog", { name: "Export" });
    await expect(dialog).toBeVisible();
    const zipHref = await dialog.getByRole("link", { name: /Download zip for AI/ }).getAttribute("href");
    expect(decodeURIComponent(zipHref ?? "")).toContain('"weekdays":[0]');
    const zip = await context.request.get(zipHref ?? "");
    expect(zip.status()).toBe(200);
    expect(zip.headers()["content-type"]).toBe("application/zip");
    expect((await zip.body()).subarray(0, 2).toString()).toBe("PK");
    const csvHref = await dialog.getByRole("link", { name: /Download CSV/ }).getAttribute("href");
    const csv = await context.request.get(csvHref ?? "");
    expect((await csv.text()).split("\n")[0]).toContain("opened_uk");
  });

  test("Copy for AI puts the dossier on the clipboard and the icon turns into a tick", async ({ page, context, browserName }) => {
    test.skip(browserName !== "chromium", "clipboard permissions are Chromium-only here");
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    await page.goto("/journal/strategies/3?tab=analytics&export=1");
    const dialog = page.getByRole("dialog", { name: "Export" });
    await dialog.getByRole("button", { name: "Copy for AI" }).click();
    await expect(dialog.getByRole("button", { name: "Copied" })).toBeVisible();
    const text = await page.evaluate(() => navigator.clipboard.readText());
    expect(text.startsWith("# Strategy dossier")).toBe(true);
  });

  test("strategy cards carry the real headline stats", async ({ page }) => {
    await page.goto("/journal");
    const card = page.getByRole("link", { name: /NAS100 London breaker/ });
    await expect(card.getByText("Profit factor")).toBeVisible();
    await expect(card.getByText("Max DD")).toBeVisible();
  });

  test("the session recap shows how the session compares", async ({ page }) => {
    await page.goto("/journal/strategies/1");
    await page.getByRole("button", { name: "Recap" }).first().click();
    await expect(page.getByTestId("recap-insights")).toBeVisible();
  });
});

test("a member reads everyone's analytics", async ({ page }) => {
  await signIn(page, MEMBER);
  await page.goto("/journal/strategies/3?tab=analytics");
  await expect(page.getByText("160 of 160 trades")).toBeVisible();
  await expect(page.getByText(/Read-only/)).toBeVisible();
});
