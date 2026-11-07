import { type Browser, type BrowserContext, expect, type Page, test } from "@playwright/test";

import { expectNoAxeViolations, expectNoHorizontalScroll, expectTapTargets } from "./helpers/a11y.ts";
import { ADMIN, api, MEMBER, signIn } from "./helpers/auth.ts";

/** seed-dev adds ~10 tasks over this week and next for Jamie, Sam and Alex (one weekly series with a
 * moved and a completed occurrence). Tests create their own tasks for today and delete them afterwards. */

const isPhone = (page: Page) => (page.viewportSize()?.width ?? 1440) < 600;
const SCREENS = ["/calendar", "/calendar?view=day", "/calendar?view=month"];

/** Today's UK calendar date. */
function todayUK(): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/London", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
}

/** The UTC instant of a UK wall-clock time today (the browser and the runner may not be in the UK). */
function todayAtUK(hour: number): string {
  const day = todayUK();
  const guess = Date.UTC(+day.slice(0, 4), +day.slice(5, 7) - 1, +day.slice(8, 10), hour);
  const wall = new Intl.DateTimeFormat("en-GB", { timeZone: "Europe/London", hour: "2-digit", hourCycle: "h23" }).format(new Date(guess));
  const offsetHours = +wall - hour; // 0 in winter, 1 in summer
  return new Date(guess - offsetHours * 3600_000).toISOString();
}

async function createTask(context: BrowserContext, title: string, hour: number) {
  const res = await api(context, "POST", "/api/calendar/tasks", {
    title,
    category: "review",
    start_at: todayAtUK(hour),
    end_at: todayAtUK(hour + 1),
  });
  expect(res.status()).toBe(201);
  return (await res.json()) as { id: number };
}

async function deleteTask(context: BrowserContext, id: number) {
  await api(context, "DELETE", `/api/calendar/tasks/${id}`);
}

async function settle(page: Page) {
  await page.waitForLoadState("networkidle");
  await expect(page.locator(".skeleton")).toHaveCount(0);
}

async function asAdmin(browser: Browser) {
  const context = await browser.newContext();
  const page = await context.newPage();
  await signIn(page, ADMIN);
  return context;
}

test.describe("Calendar screens are accessible and fit the screen", () => {
  test.beforeEach(async ({ page }) => {
    await signIn(page, ADMIN);
  });
  for (const route of SCREENS) {
    test(`${route} passes axe, has no horizontal scroll and 44px targets`, async ({ page }) => {
      await page.goto(route);
      await settle(page);
      await expect(page.getByRole("main").getByRole("heading", { level: 1, name: "Calendar" })).toBeVisible();
      await expectNoHorizontalScroll(page);
      await expectTapTargets(page);
      await expectNoAxeViolations(page);
    });
  }
});

test.describe("Calendar behaviour", () => {
  test.beforeEach(async ({ page }) => {
    await signIn(page, ADMIN);
  });

  test("a task created through the drawer appears on the calendar", async ({ page, context }) => {
    const title = `Drawer task ${Date.now()}`;
    await page.goto("/calendar?view=day");
    await settle(page);
    await page.getByRole("button", { name: "New task" }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog.getByRole("heading", { name: "New task" })).toBeVisible();
    await dialog.getByLabel("Title").fill(title);
    await dialog.getByLabel("Start").fill("15:00");
    await dialog.getByLabel("End").fill("16:00");
    await dialog.getByLabel("Category").selectOption("admin");
    await dialog.getByRole("button", { name: "Add task" }).click();
    await expect(page.getByText("Task added", { exact: true })).toBeVisible();
    await expect(page.getByRole("region", { name: "Team calendar" }).getByText(title).first()).toBeVisible();
    // Tidy up through the API so the other viewport's run starts clean.
    const list = (await (await api(context, "GET", "/api/calendar/tasks?scope=mine")).json()) as { id: number; title: string }[];
    for (const t of list.filter((t) => t.title === title)) await deleteTask(context, t.id);
  });

  test("mark done shows an undo toast, and undo puts it back", async ({ page, context }) => {
    const title = `Done test ${Date.now()}`;
    const task = await createTask(context, title, 11);
    try {
      await page.goto("/calendar?view=day");
      await settle(page);
      const region = page.getByRole("region", { name: "Team calendar" });
      if (isPhone(page)) {
        await region.getByRole("button", { name: `Mark ${title} done` }).click();
      } else {
        await region.getByText(title).first().click();
        await page.getByRole("dialog").getByRole("button", { name: "Mark done" }).click();
      }
      await expect(page.getByText("Marked done", { exact: true })).toBeVisible();
      await expect.poll(async () => ((await (await api(context, "GET", `/api/calendar/occurrences?from=${todayUK()}&to=${todayUK()}`)).json()) as { occurrences: { task_id: number; done: boolean }[] }).occurrences.find((o) => o.task_id === task.id)?.done).toBe(true);
      await page.getByRole("button", { name: "Undo" }).click();
      await expect.poll(async () => ((await (await api(context, "GET", `/api/calendar/occurrences?from=${todayUK()}&to=${todayUK()}`)).json()) as { occurrences: { task_id: number; done: boolean }[] }).occurrences.find((o) => o.task_id === task.id)?.done).toBe(false);
      if (isPhone(page)) await expect(region.getByRole("button", { name: `Mark ${title} done` })).toHaveAttribute("aria-pressed", "false");
    } finally {
      await deleteTask(context, task.id);
    }
  });

  test("an owner chip hides that owner's tasks and remembers it", async ({ page, context }) => {
    const title = `Chip test ${Date.now()}`;
    const task = await createTask(context, title, 13);
    try {
      await page.goto("/calendar?view=day");
      await settle(page);
      const region = page.getByRole("region", { name: "Team calendar" });
      await expect(region.getByText(title).first()).toBeVisible();
      const chip = page.getByRole("group", { name: "Owners" }).getByRole("button", { name: /Jamie$/ });
      await expect(chip).toHaveAttribute("aria-pressed", "true");
      await chip.click();
      await expect(chip).toHaveAttribute("aria-pressed", "false");
      await expect(region.getByText(title)).toHaveCount(0);
      await page.reload();
      await settle(page);
      await expect(page.getByRole("group", { name: "Owners" }).getByRole("button", { name: /Jamie$/ })).toHaveAttribute("aria-pressed", "false");
      await page.getByRole("group", { name: "Owners" }).getByRole("button", { name: /Jamie$/ }).click();
      await expect(region.getByText(title).first()).toBeVisible();
    } finally {
      await deleteTask(context, task.id);
    }
  });

  test("the phone shows a day / 3-day agenda instead of the grid", async ({ page }) => {
    test.skip(!isPhone(page), "phone layout only");
    await page.goto("/calendar");
    await settle(page);
    await expect(page.locator(".fc")).toHaveCount(0);
    const views = page.getByRole("radiogroup", { name: "Calendar view" });
    await expect(views.getByRole("radio", { name: "3 days" })).toHaveAttribute("aria-checked", "true");
    await expect(page.getByRole("region", { name: "Team calendar" }).getByRole("heading", { name: /^Today/ })).toBeVisible();
    await views.getByRole("radio", { name: "Day", exact: true }).click();
    await expect(page).toHaveURL(/view=day/);
  });

  test("desktop shows the week grid with UK time labels and a Monday start", async ({ page }) => {
    test.skip(isPhone(page), "desktop layout only");
    await page.goto("/calendar");
    await settle(page);
    await expect(page.locator(".fc-timeGridWeek-view")).toBeVisible();
    await expect(page.locator(".fc-col-header-cell").first()).toContainText(/^Mon/);
    await expect(page.getByText("UK time")).toBeVisible();
  });
});

test.describe("Calendar permissions", () => {
  test("a member sees the admin's task but can't edit it", async ({ page, browser }) => {
    const admin = await asAdmin(browser);
    const title = `Jamie's task ${Date.now()}`;
    // 14:00: the seed puts Alex's "Tag last week's trades" at 10:00 today, and an overlapping event would sit on top of this one.
    const task = await createTask(admin, title, 14);
    try {
      await signIn(page, MEMBER);
      await page.goto("/calendar?view=day");
      await settle(page);
      await expect(page.getByText("other people’s are view-only")).toBeVisible();
      const region = page.getByRole("region", { name: "Team calendar" });
      await region.getByText(title).first().click();
      const dialog = page.getByRole("dialog");
      await expect(dialog.getByRole("heading", { name: "Task", exact: true })).toBeVisible();
      await expect(dialog.getByText(/Viewing Jamie.s task/)).toBeVisible();
      await expect(dialog.getByLabel("Title")).toHaveAttribute("readonly", "");
      await expect(dialog.getByRole("button", { name: "Save" })).toHaveCount(0);
      await expect(dialog.getByRole("button", { name: "Delete" })).toHaveCount(0);
      if (isPhone(page)) {
        await dialog.getByRole("button", { name: "Close" }).click();
        await expect(region.getByRole("button", { name: `Mark ${title} done` })).toBeDisabled();
      }
    } finally {
      await deleteTask(admin, task.id);
      await admin.close();
    }
  });
});
