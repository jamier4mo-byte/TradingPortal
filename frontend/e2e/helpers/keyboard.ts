import { expect, type Page } from "@playwright/test";

/** What the focused element looks like right now, read in the page. */
async function focusInfo(page: Page) {
  return page.evaluate(() => {
    const el = document.activeElement as HTMLElement | null;
    if (!el || el === document.body) return { tag: "body", visible: false, ring: false, focusVisible: false, text: "", href: "", role: "", label: "" };
    const r = el.getBoundingClientRect();
    const visible = r.width > 0 && r.height > 0;
    const focusVisible = el.matches(":focus-visible");
    const ringOn = (node: Element) => {
      const cs = getComputedStyle(node);
      return cs.outlineStyle !== "none" && parseFloat(cs.outlineWidth) > 0;
    };
    // The ring must be on the element itself, or on a wrapper that styles :focus-within (a combobox
    // whose inner input sits in a bordered field), or the element is a Radix menu item that highlights.
    let ring = ringOn(el);
    if (!ring) {
      let node: Element | null = el.parentElement;
      for (let i = 0; i < 3 && node && !ring; i++, node = node.parentElement) if (node.matches(":focus-within") && ringOn(node)) ring = true;
    }
    if (!ring && el.hasAttribute("data-highlighted")) ring = true;
    return {
      tag: el.tagName.toLowerCase(),
      visible,
      ring,
      focusVisible,
      text: (el.textContent ?? "").trim().slice(0, 80),
      href: el.getAttribute("href") ?? "",
      role: el.getAttribute("role") ?? "",
      label: el.getAttribute("aria-label") ?? (el as HTMLInputElement).labels?.[0]?.textContent?.trim() ?? "",
    };
  });
}

export type Focus = Awaited<ReturnType<typeof focusInfo>>;

/** After a keyboard move the focused element must be on screen and, when :focus-visible matches, show a ring. */
export async function expectFocusVisible(page: Page) {
  const f = await focusInfo(page);
  expect(f.tag, "something has focus").not.toBe("body");
  expect(f.visible, `${f.tag} "${f.text || f.label}" has a size`).toBe(true);
  if (f.focusVisible) expect(f.ring, `${f.tag} "${f.text || f.label}" shows a focus ring`).toBe(true);
  return f;
}

/** Presses Tab until `match` is true for the focused element, checking the ring at every step. Past the
 * last element focus goes to the browser's own UI (activeElement is body) and the next Tab comes back in at
 * the top; one such wrap is allowed, so a target above the start is still reached. */
export async function tabUntil(page: Page, match: (f: Focus) => boolean, max = 60): Promise<Focus> {
  const seen: string[] = [];
  let wrapped = false;
  for (let i = 0; i < max; i++) {
    await page.keyboard.press("Tab");
    const f = await focusInfo(page);
    if (f.tag === "body") {
      if (wrapped) throw new Error(`Focus left the page twice without reaching the target. Path:\n  ${seen.join("\n  ")}`);
      wrapped = true;
      seen.push("(browser UI)");
      continue;
    }
    await expectFocusVisible(page);
    seen.push(`${f.tag}${f.role ? `[${f.role}]` : ""} ${f.href || f.label || f.text}`);
    if (match(f)) return f;
  }
  throw new Error(`Tabbed ${max} times without reaching the target. Path:\n  ${seen.join("\n  ")}`);
}
