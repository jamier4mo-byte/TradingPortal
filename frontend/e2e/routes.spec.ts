import { expect, type Page, test } from "@playwright/test";

import { expectScreenAccessible, settle } from "./helpers/a11y.ts";
import { ADMIN, api, createInvite, MEMBER, signIn } from "./helpers/auth.ts";

/**
 * Every real screen, both widths: axe (WCAG 2.2 AA), no horizontal scroll and 44px targets, once the
 * screen has settled (no skeleton left, first-load stagger finished). Routes with ids lean on seed-dev:
 * strategy 1 has imported trades (and session 1), strategy 3 has 160 backtest trades, the calendar and a
 * synthetic news week are seeded, prices come from the fake provider.
 */
const SIGNED_IN_ROUTES = [
  "/",
  "/journal",
  "/journal/trash",
  "/journal/analytics",
  "/journal/strategies/1",
  "/journal/strategies/1?tab=backtest",
  "/journal/strategies/3?tab=analytics",
  "/journal/strategies/3?tab=analytics&src=ideal",
  "/journal/strategies/3?tab=analytics&src=compare",
  "/journal/strategies/1/trades/1",
  "/journal/sessions/1/annotate",
  "/journal/sessions/1/match",
  "/news",
  "/news?view=week",
  "/news/week",
  "/news/events/:id",
  "/markets",
  "/markets/EURUSD",
  "/markets/GER40",
  "/settings/alerts",
  "/calendar",
  "/calendar?view=day",
  "/calendar?view=month",
  "/tags",
  "/settings",
  "/more",
  "/admin/users",
  "/admin/tags",
  "/dev/components",
  "/nope",
];

function day(offset: number) {
  const d = new Date();
  d.setDate(d.getDate() + offset);
  return d.toISOString().slice(0, 10);
}

async function resolve(page: Page, route: string) {
  if (route !== "/news/events/:id") return route;
  const res = await api(page.context(), "GET", `/api/news/events?from=${day(-6)}&to=${day(6)}`);
  expect(res.ok()).toBe(true);
  const { events } = (await res.json()) as { events: { id: number }[] };
  expect(events.length).toBeGreaterThan(0);
  return `/news/events/${events[0].id}`;
}

test.describe("every route is accessible and fits the screen", () => {
  test.beforeEach(async ({ page }) => {
    await signIn(page, ADMIN);
  });
  for (const route of SIGNED_IN_ROUTES) {
    test(`${route} passes axe, has no horizontal scroll and 44px targets`, async ({ page }) => {
      await page.goto(await resolve(page, route));
      await expect(page.locator("main")).toBeVisible();
      // The component gallery shows the Skeleton component on purpose.
      await settle(page, { allowSkeleton: route === "/dev/components" });
      await expectScreenAccessible(page);
    });
  }
});

test.describe("signed-out screens", () => {
  test("/login", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
    await settle(page);
    await expectScreenAccessible(page);
  });

  test("/invite/:token and /reset/:token", async ({ page, context }) => {
    await signIn(page, ADMIN);
    const invite = await createInvite(context);
    const users = await api(context, "GET", "/api/admin/users");
    expect(users.ok()).toBe(true);
    const sam = ((await users.json()) as { id: number; email: string }[]).find((u) => u.email === MEMBER.email);
    expect(sam).toBeTruthy();
    const resetRes = await api(context, "POST", `/api/admin/users/${sam!.id}/reset-link`);
    expect(resetRes.status()).toBe(201);
    const reset = ((await resetRes.json()) as { url: string }).url.split("/reset/")[1];
    await context.clearCookies();

    await page.goto(`/invite/${invite}`);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await settle(page);
    await expectScreenAccessible(page);

    await page.goto(`/reset/${reset}`);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await settle(page);
    await expectScreenAccessible(page);
  });
});

test("navigation matches the device", async ({ page }, testInfo) => {
  await signIn(page, ADMIN);
  const bottomTabs = page.getByRole("navigation", { name: "Tools" }).filter({ has: page.getByRole("link", { name: "More" }) });
  const sidebar = page.getByRole("complementary", { name: "Tools" });
  if (testInfo.project.name === "phone") {
    await expect(bottomTabs).toBeVisible();
    await expect(sidebar).toBeHidden();
    await expect(page.getByRole("button", { name: /Quick log/ })).toBeVisible();
  } else {
    await expect(sidebar).toBeVisible();
    await expect(bottomTabs).toBeHidden();
    await expect(page.getByText("UK", { exact: false }).first()).toBeVisible();
    // Sidebar collapses to icons and remembers it
    await page.getByRole("button", { name: "Collapse sidebar to icons" }).click();
    await expect(page.getByRole("button", { name: "Expand sidebar" })).toBeVisible();
    await page.reload();
    await expect(page.getByRole("button", { name: "Expand sidebar" })).toBeVisible();
    await page.getByRole("button", { name: "Expand sidebar" }).click();
  }
});

test("Cmd+K palette jumps to a screen", async ({ page }) => {
  await signIn(page, ADMIN);
  await page.keyboard.press("ControlOrMeta+k");
  await page.getByRole("textbox", { name: "Jump to a screen" }).fill("sett");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/settings$/);
});

test("components gallery shows every state", async ({ page }) => {
  await signIn(page, ADMIN);
  await page.goto("/dev/components");
  for (const name of ["Skeleton", "Banners", "Empty states", "Error state", "Toast", "Dialogs", "Toggles", "Chips and owners", "Stat tiles and gauges"]) {
    await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
  }
  await page.getByRole("button", { name: "With undo" }).click();
  await expect(page.getByText("Task marked done", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Undo", exact: true }).click();
  await expect(page.getByText("Undone", { exact: true })).toBeVisible();
  await page.getByRole("radio", { name: "Others" }).click();
  await expect(page).toHaveURL(/scope=others/);
});
