import { expect, type Page, test } from "@playwright/test";

import { expectNoAxeViolations, expectNoHorizontalScroll, expectTapTargets } from "./helpers/a11y.ts";
import { ADMIN, api, signIn } from "./helpers/auth.ts";

/** seed-dev adds synthetic news for the current week around "now" (high-impact events later today),
 * past releases of US CPI and NFP with stored price reactions, and the fake price provider. The smoke
 * backend runs with TRADING_PORTAL_FEEDS=off and PRICE_PROVIDER=fake: nothing here reaches a real feed. */

const isPhone = (page: Page) => (page.viewportSize()?.width ?? 1440) < 600;

const SCREENS = ["/news", "/news?view=week", "/news/week", "/settings/alerts", "/markets", "/markets/EURUSD", "/markets/GER40"];

async function settle(page: Page) {
  await page.waitForLoadState("networkidle");
  await expect(page.locator(".skeleton")).toHaveCount(0);
}

test.describe("News Room screens are accessible and fit the screen", () => {
  test.beforeEach(async ({ page }) => {
    await signIn(page, ADMIN);
  });
  for (const route of SCREENS) {
    test(`${route} passes axe, has no horizontal scroll and 44px targets`, async ({ page }) => {
      await page.goto(route);
      await settle(page);
      await expectNoHorizontalScroll(page);
      await expectTapTargets(page);
      await expectNoAxeViolations(page);
    });
  }

  test("event detail passes axe and fits the screen", async ({ page, context }) => {
    const res = await api(context, "GET", "/api/news/events?from=2000-01-01&to=2100-01-01&impacts=high");
    const body = (await res.json()) as { events: { id: number; name: string; released: boolean }[] };
    const released = body.events.find((e) => e.released) ?? body.events[0];
    await page.goto(`/news/events/${released.id}`);
    await settle(page);
    await expect(page.getByRole("heading", { level: 1, name: released.name })).toBeVisible();
    await expectNoHorizontalScroll(page);
    await expectTapTargets(page);
    await expectNoAxeViolations(page);
  });
});

test.describe("News Room behaviour", () => {
  test.beforeEach(async ({ page }) => {
    await signIn(page, ADMIN);
  });

  test("today's events in UK time, the countdown, and a filter that narrows the list", async ({ page }) => {
    await page.goto("/news?view=day");
    await expect(page.getByRole("img", { name: "News Room" })).toBeVisible();
    const next = page.getByRole("region", { name: "Next high-impact event" });
    await expect(next.getByRole("timer")).toBeVisible();
    await expect(next.getByText(/UK$/)).toBeVisible();
    await expect(page.getByRole("region", { name: "Today" }).getByRole("link").first()).toBeVisible();

    if (isPhone(page)) {
      await page.getByRole("button", { name: /^Filters/ }).click();
      await page.getByRole("dialog").getByRole("button", { name: "High", exact: true }).click();
      await page.getByRole("button", { name: "Show events" }).click();
    } else {
      await page.getByRole("region", { name: "Filters" }).getByRole("button", { name: "High", exact: true }).click();
    }
    await expect(page).toHaveURL(/impact=high/);
    const today = page.getByRole("region", { name: "Today" });
    await expect(today.getByText("Med", { exact: true })).toHaveCount(0);
    await expect(today.getByText("Low", { exact: true })).toHaveCount(0);
  });

  test("the trading-day timeline shows sessions and a now line", async ({ page }) => {
    await page.goto("/news?view=day");
    const timeline = page.getByRole("region", { name: "Trading day" });
    for (const s of ["Asia", "London", "New York"]) await expect(timeline.getByText(s, { exact: true }).first()).toBeVisible();
    await expect(timeline.getByText(/News window ±\d+ min/)).toBeVisible();
  });

  test("an event opens its detail with history, reactions and a summary", async ({ page, context }) => {
    const res = await api(context, "GET", "/api/news/events?from=2000-01-01&to=2100-01-01&impacts=high");
    const events = ((await res.json()) as { events: { id: number; name: string }[] }).events;
    // The seeded CPI history has stored reactions.
    const cpi = events.find((e) => /CPI/.test(e.name)) ?? events[0];
    await page.goto(`/news/events/${cpi.id}`);
    await expect(page.getByRole("region", { name: "What it is" })).toBeVisible();
    await expect(page.getByRole("region", { name: "Release history" })).toBeVisible();
    await expect(page.getByRole("region", { name: "Price reaction" })).toBeVisible();
    await page.getByRole("button", { name: "News Room" }).click();
    await expect(page).toHaveURL(/\/news/);
  });

  test("week ahead lists high-impact events by day", async ({ page }) => {
    await page.goto("/news/week");
    await expect(page.getByRole("region", { name: "Week ahead" })).toBeVisible();
    await expect(page.getByText(/high-impact (event|events) from/)).toBeVisible();
  });

  test("alerts settings: permission is only asked from a button, and the server explains missing VAPID", async ({ page }) => {
    await page.goto("/settings/alerts");
    await expect(page.getByRole("heading", { name: "News alerts" })).toBeVisible();
    // The smoke backend has no VAPID keys, so the page says so instead of offering a broken button.
    await expect(page.getByText(/Push isn.t set up on the server yet/)).toBeVisible();
    // Preferences save as they change.
    const prefs = page.getByRole("region", { name: "What to alert" });
    await prefs.getByRole("switch", { name: /News alerts/ }).click();
    await expect(prefs.getByRole("switch", { name: /News alerts/ })).toHaveAttribute("aria-checked", "true");
    await page.reload();
    await expect(page.getByRole("region", { name: "What to alert" }).getByRole("switch", { name: /News alerts/ })).toHaveAttribute("aria-checked", "true");
  });
});

test.describe("prices", () => {
  test.beforeEach(async ({ page }) => {
    await signIn(page, ADMIN);
  });

  test("the browser never calls Twelve Data (or the news feeds) directly", async ({ page }) => {
    const outside: string[] = [];
    page.on("request", (req) => {
      const host = new URL(req.url()).host;
      if (/twelvedata\.com|jblanked\.com|faireconomy\.media|forexfactory\.com/.test(host)) outside.push(req.url());
    });
    await page.goto("/markets");
    await settle(page);
    const search = page.getByRole("combobox", { name: "Search instruments" });
    await search.fill("eur");
    await expect(page.getByRole("listbox", { name: "Matching instruments" })).toBeVisible();
    await page.keyboard.press("Escape");
    await page.goto("/markets/EURUSD");
    await settle(page);
    await page.goto("/news");
    await settle(page);
    await page.goto("/settings");
    await settle(page);
    expect(outside).toEqual([]);
  });

  test("pin an instrument, see a delayed ticker, open the instrument view, unpin", async ({ page, context }) => {
    // Start clean for this user.
    const pins = ((await (await api(context, "GET", "/api/prices/pins")).json()) as { pins: { symbol: string }[] }).pins;
    for (const p of pins) await api(context, "DELETE", `/api/prices/pins?symbol=${encodeURIComponent(p.symbol)}`);

    await page.goto("/markets");
    await expect(page.getByText("Nothing pinned yet")).toBeVisible();
    await page.getByRole("button", { name: "EURUSD", exact: true }).click();
    const list = page.getByRole("list", { name: "Pinned instruments" });
    await expect(list.getByText("EUR/USD").first()).toBeVisible();
    await expect(list.getByText(/Delayed · updated \d\d:\d\d/).first()).toBeAttached();
    await list.getByRole("link", { name: /EUR\/USD/ }).first().click();
    await expect(page.getByRole("heading", { level: 1, name: "EUR/USD" })).toBeVisible();
    await expect(page.getByText(/Delayed · updated \d\d:\d\d/)).toBeVisible();
    await page.getByRole("button", { name: "Unpin" }).click();
    await expect(page.getByRole("button", { name: "Pin" })).toBeVisible();
  });

  test("an instrument the plan doesn't cover never shows a made-up price", async ({ page }) => {
    await page.goto("/markets/GER40");
    await expect(page.getByText("Not available on your Twelve Data plan")).toBeVisible();
  });
});
