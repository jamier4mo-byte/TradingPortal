import { expect, test } from "@playwright/test";

import { expectNoAxeViolations, expectNoHorizontalScroll, expectTapTargets } from "./helpers/a11y.ts";
import { ADMIN, signIn } from "./helpers/auth.ts";

const ROUTES = ["/", "/journal", "/news", "/calendar", "/tags", "/settings", "/more", "/admin/users", "/admin/tags", "/dev/components"];

test.describe("every route is accessible and fits the screen", () => {
  test.beforeEach(async ({ page }) => {
    await signIn(page, ADMIN);
  });
  for (const route of ROUTES) {
    test(`${route} passes axe, has no horizontal scroll and 44px targets`, async ({ page }) => {
      await page.goto(route);
      await page.waitForLoadState("networkidle");
      await expect(page.locator("main")).toBeVisible();
      await expectNoHorizontalScroll(page);
      await expectTapTargets(page);
      await expectNoAxeViolations(page);
    });
  }
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
  await expect(page.getByText("Task marked done")).toBeVisible();
  await page.getByRole("button", { name: "Undo", exact: true }).click();
  await expect(page.getByText("Undone")).toBeVisible();
  await page.getByRole("radio", { name: "Others" }).click();
  await expect(page).toHaveURL(/scope=others/);
});
