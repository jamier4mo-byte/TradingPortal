import { expect, test } from "@playwright/test";

import { expectNoAxeViolations, expectNoHorizontalScroll, expectTapTargets } from "./helpers/a11y.ts";
import { ADMIN, signIn } from "./helpers/auth.ts";

test("API is healthy", async ({ request }) => {
  const body = await (await request.get("/api/health")).json();
  expect(body.db_ok).toBe(true);
});

test("signed-out visitors are sent to the login screen", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("img", { name: "Trading Portal" }).first()).toBeVisible();
  await expectNoAxeViolations(page);
  await expectNoHorizontalScroll(page);
});

test("Hub greets the signed-in user and shows both launch islands", async ({ page }) => {
  await signIn(page, ADMIN);
  await expect(page.getByRole("heading", { level: 1, name: /(Good (morning|afternoon|evening|night)|Welcome back), Jamie/ })).toBeVisible();
  await expect(page.getByRole("link", { name: "Open Replay Journal" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Open News Room" })).toBeVisible();
  await expectNoHorizontalScroll(page);
  await expectTapTargets(page);
  await expectNoAxeViolations(page);
});
