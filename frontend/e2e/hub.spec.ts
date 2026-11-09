import { expect, type Page, test } from "@playwright/test";

import { expectNoAxeViolations, expectNoHorizontalScroll, expectTapTargets } from "./helpers/a11y.ts";
import { ADMIN, signIn } from "./helpers/auth.ts";

/** The Hub (Foundations §1): hero, today's news, launch islands, live market data and the
 * engagement cards. seed-dev gives Jamie strategies, sessions and a synthetic news week; the smoke backend
 * runs with the feeds off and the fake price provider. Playwright runs with reducedMotion: "reduce", so
 * motionLevel() is "reduced": the launch overlay is a plain fade but still holds for its minimum. */

async function settle(page: Page) {
  await page.waitForLoadState("networkidle");
}

test.beforeEach(async ({ page }) => {
  await signIn(page, ADMIN);
  await settle(page);
});

test("hero greets Jamie with an ordinal date, a live clock and a session line", async ({ page }) => {
  const hero = page.getByRole("region", { name: "Greeting" });
  await expect(hero.getByRole("heading", { level: 1 })).toContainText("Jamie");
  await expect(hero.getByText(/Today is \w+ \d+(st|nd|rd|th) \w+/)).toBeVisible();
  await expect(hero.getByText(/UK \d\d:\d\d:\d\d/)).toBeVisible();
  await expect(hero.getByText(/session|Markets closed/)).toBeVisible();
  await expect(hero).toHaveAttribute("data-daypart", /dawn|day|dusk|night/);
  await expect(hero).toHaveAttribute("data-session", /asia|london|newyork|closed/);
});

test("both islands show a live stat and the news card has a headline or the quiet-day message", async ({ page }) => {
  const journal = page.getByRole("link", { name: "Open Replay Journal" });
  const news = page.getByRole("link", { name: "Open News Room" });
  await expect(journal).toContainText(/Last session: \d+ trades|strateg|Create your first strategy/);
  await expect(news).toContainText(/Next event: |No high-impact news ahead/);
  const card = page.getByRole("region", { name: "Today's news" });
  await expect(card.getByRole("heading", { name: "Today's news" })).toBeVisible();
  await expect(card.getByRole("link", { name: "Open the News Room" })).toBeVisible();
  await expect(card.getByText(/high-impact|No high-impact news today\./).first()).toBeVisible();
});

test("the checklist lists five items and the streak card appears after scrolling", async ({ page }) => {
  const checklist = page.getByRole("region", { name: "Getting set up" });
  await checklist.scrollIntoViewIfNeeded();
  await expect(checklist.getByRole("listitem")).toHaveCount(5);
  await expect(checklist.getByText("Add your Twelve Data key")).toBeVisible();
  await expect(checklist.getByText("Install to the home screen")).toBeVisible();
  const streak = page.getByRole("region", { name: "Showing up" });
  await streak.scrollIntoViewIfNeeded();
  await expect(streak).toBeVisible();
  await expect(streak.getByText(/-day streak · best \d+|Log a session or review a trade to start a streak/)).toBeVisible();
  const bests = page.getByRole("region", { name: "Personal bests" });
  await bests.scrollIntoViewIfNeeded();
  await expect(bests).toBeVisible();
});

test("the live market card is on the page and the retired team calendar is gone", async ({ page }) => {
  await expect(page.getByRole("region", { name: "Team calendar" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Open calendar" })).toHaveCount(0);
  const market = page.getByRole("region", { name: "Live market data" });
  await market.scrollIntoViewIfNeeded();
  await expect(market).toBeVisible();
  await expect(page.getByRole("link", { name: "Open Markets" })).toBeVisible();
});

test("clicking the Replay Journal island plays the launch loader and lands on /journal", async ({ page }) => {
  await page.getByRole("link", { name: "Open Replay Journal" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Opening Replay Journal" })).toBeVisible();
  await page.waitForURL(/\/journal$/);
  await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
});

test("a modifier click on an island is a plain link (no loader)", async ({ page, context }) => {
  const [popup] = await Promise.all([context.waitForEvent("page"), page.getByRole("link", { name: "Open News Room" }).click({ modifiers: ["ControlOrMeta"] })]);
  await popup.waitForLoadState();
  expect(new URL(popup.url()).pathname).toBe("/news");
  await expect(page).toHaveURL(/\/$/);
  await popup.close();
});

test("the Hub passes axe, has no horizontal scroll and 44px targets", async ({ page }) => {
  await page.mouse.wheel(0, 4000);
  await settle(page);
  await expect(page.locator(".skeleton")).toHaveCount(0);
  await expectNoHorizontalScroll(page);
  await expectTapTargets(page);
  await expectNoAxeViolations(page);
});
