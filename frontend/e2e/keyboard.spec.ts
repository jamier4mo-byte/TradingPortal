import { expect, test } from "@playwright/test";

import { settle } from "./helpers/a11y.ts";
import { ADMIN } from "./helpers/auth.ts";
import { expectFocusVisible, tabUntil } from "./helpers/keyboard.ts";

/**
 * Keyboard-only walkthrough (Accessibility: WCAG 2.1.1, 2.4.3, 2.4.7, 2.4.11). Every Tab lands on an element
 * that is on screen and, when :focus-visible matches, has a visible ring (helpers/keyboard.ts). Desktop only:
 * the phone project has no hardware keyboard.
 */
test.skip(({ isMobile }) => !!isMobile, "keyboard walkthrough runs on the desktop project");

/** A keyboard user waits for the screen to finish loading: the account menu's lazy chunk has replaced the
 * disabled avatar and no skeleton is left (while loading, main has nothing to focus and Tab leaves the page). */
async function ready(page: import("@playwright/test").Page) {
  await expect(page.getByRole("button", { name: "Account menu" })).toBeEnabled();
  await settle(page);
}

test("sign in, open the journal, a strategy, the Backtest tab and the import drawer with the keyboard", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible(); // the sign-in screen is lazy-loaded
  await tabUntil(page, (f) => f.tag === "input" && f.label === "Email");
  await page.keyboard.type(ADMIN.email);
  await page.keyboard.press("Tab");
  await expectFocusVisible(page);
  await page.keyboard.type(ADMIN.password);
  await page.keyboard.press("Enter");
  await page.waitForURL((u) => !u.pathname.startsWith("/login"));
  await ready(page);

  // Shell → Replay Journal
  await tabUntil(page, (f) => f.tag === "a" && f.href === "/journal");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/journal$/);
  await ready(page);

  // First strategy card
  const card = await tabUntil(page, (f) => f.tag === "a" && /^\/journal\/strategies\/\d+$/.test(f.href));
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(new RegExp(`${card.href}$`));
  await expect(page.getByRole("radiogroup", { name: "Strategy tab" })).toBeVisible();
  await ready(page);

  // Backtest tab (a radiogroup of buttons: Tab reaches each, Enter activates)
  await tabUntil(page, (f) => f.role === "radio" && f.text === "Backtest");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("radio", { name: "Backtest" })).toHaveAttribute("aria-checked", "true");
  await expect(page).toHaveURL(/tab=backtest/);

  // Import drawer: Enter opens, Esc closes and focus goes back to the trigger. On a locked strategy the
  // Backtest tab has no Import button of its own, so the header's "Import CSV" is reached by wrapping round.
  const trigger = await tabUntil(page, (f) => f.tag === "button" && /^Import( CSV)?(Import)?$/.test(f.text));
  await page.keyboard.press("Enter");
  const drawer = page.getByRole("dialog", { name: "Import from FX Replay" });
  await expect(drawer).toBeVisible();
  const inDrawer = await expectFocusVisible(page);
  expect(inDrawer.label || inDrawer.text, "focus moved into the drawer").toBeTruthy();
  // Let the panel finish sliding in (a person sees it land before reaching for Esc).
  await expect.poll(() => drawer.evaluate((el) => getComputedStyle(el).transform)).toMatch(/^(none|matrix\(1, 0, 0, 1, 0, 0\))$/);
  await page.keyboard.press("Escape");
  await expect(drawer).toBeHidden();
  await expect.poll(() => page.evaluate(() => document.activeElement?.tagName)).toBe("BUTTON");
  const back = await expectFocusVisible(page);
  expect(back.tag).toBe("button");
  expect(back.text).toBe(trigger.text);
});

test("add a calendar task, jump with Cmd+K and open a news event with the keyboard", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible(); // the sign-in screen is lazy-loaded
  await tabUntil(page, (f) => f.tag === "input" && f.label === "Email");
  await page.keyboard.type(ADMIN.email);
  await page.keyboard.press("Tab");
  await page.keyboard.type(ADMIN.password);
  await page.keyboard.press("Enter");
  await page.waitForURL((u) => !u.pathname.startsWith("/login"));
  await ready(page);

  // Calendar: New task → title → Add task
  await page.goto("/calendar");
  await expect(page.getByRole("heading", { level: 1, name: "Calendar" })).toBeVisible();
  await ready(page);
  await tabUntil(page, (f) => f.tag === "button" && f.text.endsWith("New task"));
  await page.keyboard.press("Enter");
  const dialog = page.getByRole("dialog", { name: "New task" });
  await expect(dialog).toBeVisible();
  const title = `Keyboard task ${Date.now()}`;
  const focused = await expectFocusVisible(page);
  expect(focused.label).toBe("Title");
  await page.keyboard.type(title);
  await tabUntil(page, (f) => f.tag === "button" && f.text === "Add task", 20);
  await page.keyboard.press("Enter");
  await expect(dialog).toBeHidden();
  await expect(page.getByText(title).first()).toBeVisible();
  // Focus goes back to the button that opened the drawer
  await expect.poll(() => page.evaluate(() => document.activeElement?.textContent?.trim())).toMatch(/New task$/);

  // Cmd+K: arrows + Enter
  await page.keyboard.press("ControlOrMeta+k");
  const palette = page.getByRole("textbox", { name: "Jump to a screen" });
  await expect(palette).toBeFocused();
  await expectFocusVisible(page);
  await page.keyboard.type("ne");
  const options = page.getByRole("option");
  await expect(options.first()).toBeVisible();
  await page.keyboard.press("ArrowDown");
  const picked = await page.locator('[role="option"][aria-selected="true"]').textContent();
  expect(picked?.trim()).toBeTruthy();
  await page.keyboard.press("Enter");
  await expect(page).not.toHaveURL(/\/calendar$/);
  // The screen's h1 (some are a logo image, so match the accessible name, not the text)
  await expect(page.getByRole("heading", { level: 1, name: picked!.trim() }).first()).toBeAttached();

  // News Room: Tab to an event, Enter into it, back again
  await page.goto("/news");
  await expect(page.getByRole("heading", { level: 1, name: "News Room" })).toBeVisible();
  await ready(page);
  const event = await tabUntil(page, (f) => f.tag === "a" && /^\/news\/events\/\d+$/.test(f.href), 80);
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(new RegExp(`${event.href}$`));
  await expect(page.getByRole("main").getByRole("heading", { level: 1 })).toBeVisible();
  // Alt+ArrowLeft is the browser's own back shortcut; headless Chromium may ignore it, so the in-page back
  // link is the fallback.
  await page.keyboard.press("Alt+ArrowLeft");
  const wentBack = await page
    .waitForURL(/\/news$/, { timeout: 2_000 })
    .then(() => true)
    .catch(() => false);
  if (!wentBack) {
    await tabUntil(page, (f) => f.tag === "a" && f.href === "/news");
    await page.keyboard.press("Enter");
  }
  await expect(page).toHaveURL(/\/news$/);
});
