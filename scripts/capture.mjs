// Screenshots of the given screens at the device widths from the Foundations doc.
//
//   cd frontend && BASE=http://127.0.0.1:8768 OUT=../docs/check-devices/2026-11-05 \
//     SCREENS=hub,journal SIZES=360x780,375x812,430x932,768x1024,1440x900,1920x1080 node ../scripts/capture.mjs
//
// Never point BASE at an app using your real data folder.
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join, resolve } from "node:path";

const { chromium } = createRequire(join(process.cwd(), "package.json"))("@playwright/test");

const BASE = process.env.BASE ?? "http://127.0.0.1:8768";
const OUT = resolve(process.env.OUT ?? "../docs/check-devices/latest");
const ROUTES = { hub: "/", journal: "/journal", news: "/news", calendar: "/calendar" };
const SCREENS = (process.env.SCREENS ?? Object.keys(ROUTES).join(",")).split(",");
const SIZES = (process.env.SIZES ?? "360x780,375x812,430x932,768x1024,1440x900,1920x1080").split(",").map((s) => {
  const [w, h] = s.split("x").map(Number);
  return { w, h };
});

mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch();
for (const { w, h } of SIZES) {
  const context = await browser.newContext({
    viewport: { width: w, height: h },
    reducedMotion: "reduce",
    isMobile: w < 600,
    hasTouch: w < 1024,
  });
  const page = await context.newPage();
  for (const name of SCREENS) {
    const path = ROUTES[name] ?? name;
    await page.goto(`${BASE}${path}`, { waitUntil: "networkidle" });
    await page.evaluate(() => document.fonts.ready);
    const file = join(OUT, `${name}-${w}.png`);
    await page.screenshot({ path: file, fullPage: true });
    console.log(file);
  }
  await context.close();
}
await browser.close();
