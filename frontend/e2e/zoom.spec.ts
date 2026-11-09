import { expect, test } from "@playwright/test";

import { expectNoHorizontalScroll } from "./helpers/a11y.ts";
import { ADMIN, signIn } from "./helpers/auth.ts";

/**
 * 200% text zoom (WCAG 1.4.4 and 1.4.10). Tailwind sizes are in px, so a root font-size change is not
 * enough. CSS `zoom: 2` on <html> was tried first and is not faithful in Chromium: media queries still see
 * the unzoomed viewport, so a 720px window laid the shell out as a tablet inside 360px of room. Browser zoom
 * at 200% halves the CSS viewport and doubles the device pixel ratio, so that is what this emulates: a
 * 360×450 CSS-pixel viewport at DPR 2 with a desktop user agent (the phone project is a different device).
 * Nothing may scroll sideways, and the heading and the top bar must stay on screen.
 */
test.skip(({ isMobile }) => !!isMobile, "zoom emulation runs on the desktop project");
test.use({ viewport: { width: 360, height: 450 }, deviceScaleFactor: 2 });

const ROUTES = ["/", "/journal/strategies/3?tab=analytics", "/news", "/news?view=week"];

test.beforeEach(async ({ page }) => {
  await signIn(page, ADMIN);
});

for (const route of ROUTES) {
  test(`${route} holds up at 200% zoom`, async ({ page }) => {
    await page.goto(route);
    await page.waitForLoadState("networkidle");
    await expect(page.locator('[data-stagger="entering"]')).toHaveCount(0);
    await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
    await expectNoHorizontalScroll(page);
    const m = await page.evaluate(() => {
      const doc = document.documentElement;
      const header = document.querySelector("header");
      // Wide tables and the trading-day timeline scroll inside their own container on purpose (a horizontal
      // scroller inside a card, not the page); only elements that no ancestor clips or scrolls count.
      const scrolls = (el: HTMLElement) => {
        for (let n = el.parentElement; n && n !== document.body; n = n.parentElement) {
          const o = getComputedStyle(n).overflowX;
          if (o === "auto" || o === "scroll" || o === "hidden") return true;
        }
        return false;
      };
      const wide = [...document.querySelectorAll<HTMLElement>("body *")]
        .filter((el) => el.getBoundingClientRect().right > doc.clientWidth + 1 && getComputedStyle(el).position !== "fixed" && !scrolls(el))
        .slice(0, 6)
        .map((el) => `${el.tagName.toLowerCase()}.${String(el.className).split(" ").slice(0, 3).join(".")} right=${Math.round(el.getBoundingClientRect().right)}`);
      return { headerOverflow: header ? header.scrollWidth - header.clientWidth : 0, wide };
    });
    expect(m.headerOverflow, "top bar overflow").toBeLessThanOrEqual(0);
    expect(m.wide, "elements past the right edge").toEqual([]);
  });
}
