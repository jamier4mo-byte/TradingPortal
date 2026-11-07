import { expect, type Page, test } from "@playwright/test";

import { expectNoAxeViolations, expectNoHorizontalScroll, expectTapTargets } from "./helpers/a11y.ts";
import { ADMIN, api, MEMBER_2, signIn } from "./helpers/auth.ts";

/** Motion pass (Foundations → Motion, loading and engagement; review kit F18). Playwright runs with
 * reducedMotion: "reduce", but the seeded users are on Full, and the in-app Full setting overrides the OS
 * preference on purpose (tokens skill). So in these tests motionLevel() is "full" for the seeded users:
 * the portal intro plays after a sign-in, cards stagger in, and View Transitions run on route changes.
 * Alex (MEMBER_2) is the user whose setting is changed; it is put back to Full after each test. */

declare global {
  interface Window {
    __vtCalls?: number;
  }
}

async function afterIntro(page: Page) {
  // The intro leaves on its own after about 1.25 s (and never blocks input beyond 1 s).
  await expect(page.getByTestId("portal-intro")).toHaveCount(0, { timeout: 8_000 });
}

/** The shell's own links: the sidebar on tablet and up, the tab bar on the phone. */
async function navTo(page: Page, name: RegExp) {
  await page.getByRole("link", { name }).first().click();
}

async function setMotion(page: Page, pref: "full" | "reduced" | "off") {
  const res = await api(page.context(), "PATCH", "/api/me", { motion_pref: pref });
  expect(res.ok()).toBeTruthy();
}

test.describe("motion setting", () => {
  test.afterEach(async ({ page }) => {
    await setMotion(page, "full");
  });

  test("the Settings pill switches data-motion on <html> and it survives a reload", async ({ page }) => {
    await signIn(page, MEMBER_2);
    await afterIntro(page);
    await page.goto("/settings");
    await page.getByRole("radio", { name: "Off" }).click();
    await expect(page.locator("html")).toHaveAttribute("data-motion", "off");
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("data-motion", "off");
    await page.getByRole("radio", { name: "Reduced" }).click();
    await expect(page.locator("html")).toHaveAttribute("data-motion", "reduced");
    await page.getByRole("radio", { name: "Full" }).click();
    await expect(page.locator("html")).toHaveAttribute("data-motion", "full");
  });

  test("Off: a route change never calls startViewTransition and toasts carry no animation classes", async ({ page }) => {
    await page.addInitScript(() => {
      window.__vtCalls = 0;
      const doc = document as Document & { startViewTransition?: (cb: () => void) => unknown };
      const original = doc.startViewTransition?.bind(document);
      if (original) {
        doc.startViewTransition = (cb: () => void) => {
          window.__vtCalls = (window.__vtCalls ?? 0) + 1;
          return original(cb);
        };
      }
    });
    await signIn(page, MEMBER_2);
    await afterIntro(page);
    await setMotion(page, "off");
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("data-motion", "off");
    // Client-side navigation through the shell (sidebar on desktop, tab bar on the phone).
    await navTo(page, /^(Replay )?Journal$/);
    await expect(page).toHaveURL(/\/journal$/);
    await navTo(page, /^News( Room)?$/);
    await expect(page).toHaveURL(/\/news$/);
    expect(await page.evaluate(() => window.__vtCalls)).toBe(0);
    // Cards render at once: no stagger ran.
    await expect(page.locator("[data-stagger]").first()).not.toHaveAttribute("data-stagger", "entering");

    await page.goto("/dev/components");
    await page.getByRole("button", { name: "Positive" }).click();
    const toast = page.getByRole("status").filter({ hasText: "8 trades imported" });
    await expect(toast).toBeVisible();
    await expect(toast).not.toHaveClass(/anim-/);
  });

  test("Reduced: no portal intro after a sign-in", async ({ page }) => {
    // Set Reduced in a separate context first (the setting lives on the user), then sign in fresh.
    await signIn(page, MEMBER_2);
    await afterIntro(page);
    await setMotion(page, "reduced");
    await api(page.context(), "POST", "/api/auth/logout");
    await signIn(page, MEMBER_2);
    await expect(page.locator("html")).toHaveAttribute("data-motion", "reduced");
    await page.waitForTimeout(700);
    await expect(page.getByTestId("portal-intro")).toHaveCount(0);
  });
});

test("portal intro plays once after a sign-in under Full, and not again the same day", async ({ page }) => {
  await signIn(page, ADMIN);
  const intro = page.getByRole("status").filter({ hasText: "Opening the portal" });
  await expect(intro).toBeVisible();
  await expect(page.getByTestId("portal-intro")).toHaveCount(0, { timeout: 8_000 });
  // The Hub was underneath all along.
  await expect(page.getByRole("link", { name: "Open Replay Journal" })).toBeVisible();

  await api(page.context(), "POST", "/api/auth/logout");
  await signIn(page, ADMIN);
  await page.waitForTimeout(700);
  await expect(page.getByTestId("portal-intro")).toHaveCount(0);
});

test("first load staggers the strategy cards in, a revisit renders at once", async ({ page }) => {
  await signIn(page, ADMIN);
  await afterIntro(page);
  await page.goto("/journal");
  const grid = page.getByRole("list", { name: "Strategies" });
  await expect(grid).toHaveAttribute("data-stagger", "done");
  const cards = grid.getByRole("listitem");
  const n = await cards.count();
  expect(n).toBeGreaterThan(0);
  for (let i = 0; i < n; i++) {
    await expect(cards.nth(i)).toHaveCSS("opacity", "1");
  }
  // Revisit in the same session: no entrance.
  await navTo(page, /^Hub$/);
  await expect(page).toHaveURL(/\/$/);
  await navTo(page, /^(Replay )?Journal$/);
  await expect(page.getByRole("list", { name: "Strategies" })).toHaveAttribute("data-stagger", "skipped");
});

test("a strategy card and the strategy page heading share a view-transition-name", async ({ page }) => {
  await signIn(page, ADMIN);
  await afterIntro(page);
  await page.goto("/journal");
  const card = page.getByRole("list", { name: "Strategies" }).getByRole("link").first();
  const cardName = await card.locator("h2").evaluate((el) => (el as HTMLElement).style.viewTransitionName);
  const title = (await card.locator("h2").textContent())?.trim() ?? "";
  expect(cardName).toMatch(/^strategy-\d+$/);
  await card.click();
  await expect(page).toHaveURL(/\/journal\/strategies\/\d+$/);
  const heading = page.getByRole("main").getByRole("heading", { level: 1, name: title });
  await expect(heading).toBeVisible();
  expect(await heading.evaluate((el) => (el as HTMLElement).style.viewTransitionName)).toBe(cardName);
});

test("long trade lists show 40 rows, load more as you scroll and offer Show all", async ({ page }) => {
  await signIn(page, ADMIN);
  await afterIntro(page);
  await page.goto("/journal/strategies/3?tab=backtest");
  const footer = page.getByTestId("trade-list-footer");
  await expect(footer).toContainText(/Showing 40 of \d+/);
  const total = Number((await footer.textContent())?.match(/of (\d+)/)?.[1]);
  expect(total).toBeGreaterThan(40);
  await footer.scrollIntoViewIfNeeded();
  await expect(footer).toContainText(/Showing (80|1\d\d) of/);
  await footer.getByRole("button", { name: "Show all" }).click();
  await expect(footer).toContainText(`Showing ${total} of ${total}`);
  await expect(footer.getByRole("button", { name: "Show all" })).toHaveCount(0);
  await expect(page.getByRole("list", { name: "Trades" }).or(page.getByRole("table")).first()).toBeVisible();
});

test("strategy page and trade detail: axe, no horizontal scroll, 44px targets", async ({ page }) => {
  await signIn(page, ADMIN);
  await afterIntro(page);
  for (const path of ["/journal/strategies/3", "/journal/strategies/1/trades/1"]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await page.waitForLoadState("networkidle");
    await expectNoHorizontalScroll(page);
    await expectTapTargets(page);
    await expectNoAxeViolations(page);
  }
});
