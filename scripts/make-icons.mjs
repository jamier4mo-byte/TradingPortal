// Generate the favicon set, apple-touch-icon, iOS launch screens and site.webmanifest from
// frontend/public/brand/t-tile.png, and write the matching <link rel="apple-touch-startup-image"> tags into
// frontend/index.html between the <!-- startup-images --> markers (idempotent: re-running replaces them).
//   cd frontend && node ../scripts/make-icons.mjs
// Colours come from the @theme block in frontend/src/index.css so nothing here drifts from the tokens.
import { readFileSync, statSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join, resolve } from "node:path";

const require = createRequire(join(process.cwd(), "package.json"));
const sharp = require("sharp");
const pngToIcoModule = require("png-to-ico");
const pngToIco = pngToIcoModule.default ?? pngToIcoModule;

const PUBLIC = resolve("public");
const SRC = join(PUBLIC, "brand", "t-tile.png");
const INDEX = resolve("index.html");
const css = readFileSync(resolve("src/index.css"), "utf8");
const token = (name) => {
  const m = css.match(new RegExp(`${name}:\\s*(#[0-9a-fA-F]{6})`));
  if (!m) throw new Error(`token ${name} not found in index.css`);
  return m[1].toUpperCase();
};
const bg = token("--color-bg");

// ---- icons ----
const sizes = [16, 32, 192, 512];
for (const size of sizes) {
  // The 16px and 32px marks are tiny; sharp's Lanczos keeps them crisp, and the sparkle is lost at that size anyway.
  await sharp(SRC).resize(size, size, { fit: "contain", background: { r: 0, g: 0, b: 0, alpha: 0 } }).png().toFile(join(PUBLIC, `favicon-${size}.png`));
}
await sharp(SRC)
  .resize(180, 180, { fit: "contain", background: bg })
  .flatten({ background: bg })
  .png()
  .toFile(join(PUBLIC, "apple-touch-icon-180.png"));
writeFileSync(join(PUBLIC, "favicon.ico"), await pngToIco([join(PUBLIC, "favicon-16.png"), join(PUBLIC, "favicon-32.png")]));

// ---- launch screens (apple-touch-startup-image) ----
// The intro's first frame: the page background with the T tile centred, nothing else. iOS picks the image
// whose media query matches the device, so each common iPhone/iPad portrait size gets its own PNG.
// [name, CSS width, CSS height, device pixel ratio]
const STARTUP = [
  ["iphone-se", 375, 667, 2], // iPhone SE (2nd/3rd gen), 8
  ["iphone-8-plus", 414, 736, 3], // iPhone 8 Plus
  ["iphone-x", 375, 812, 3], // iPhone X, XS, 11 Pro, 12 mini, 13 mini
  ["iphone-xr", 414, 896, 2], // iPhone XR, 11
  ["iphone-xs-max", 414, 896, 3], // iPhone XS Max, 11 Pro Max
  ["iphone-12", 390, 844, 3], // iPhone 12, 12 Pro, 13, 13 Pro, 14
  ["iphone-12-pro-max", 428, 926, 3], // iPhone 12 Pro Max, 13 Pro Max, 14 Plus
  ["iphone-14-pro", 393, 852, 3], // iPhone 14 Pro, 15, 15 Pro, 16
  ["iphone-14-pro-max", 430, 932, 3], // iPhone 14 Pro Max, 15 Plus, 15 Pro Max, 16 Plus
  ["iphone-16-pro", 402, 874, 3], // iPhone 16 Pro, 17, 17 Pro
  ["iphone-16-pro-max", 440, 956, 3], // iPhone 16 Pro Max, 17 Pro Max
  ["ipad-mini", 744, 1133, 2], // iPad mini (6th gen+)
  ["ipad-10", 810, 1080, 2], // iPad 10.2" (7th–9th gen)
  ["ipad-10-9", 820, 1180, 2], // iPad 10.9" (10th gen), iPad Air 11"
  ["ipad-pro-11", 834, 1194, 2], // iPad Pro 11", iPad Air 10.9" (4th/5th gen)
  ["ipad-pro-11-m4", 834, 1210, 2], // iPad Pro 11" (M4)
  ["ipad-pro-12-9", 1024, 1366, 2], // iPad Pro 12.9"
  ["ipad-pro-13", 1032, 1376, 2], // iPad Pro 13" (M4), iPad Air 13"
];
const tile = sharp(SRC);
const tileMeta = await tile.metadata();
const links = [];
let largest = 0;
for (const [name, w, h, dpr] of STARTUP) {
  const W = w * dpr;
  const H = h * dpr;
  const edge = Math.round(Math.min(W, H) * 0.24); // the tile is a quarter of the short edge, like the intro
  const mark = await sharp(SRC)
    .resize(edge, Math.round((edge * tileMeta.height) / tileMeta.width), { fit: "contain", background: { r: 0, g: 0, b: 0, alpha: 0 } })
    .png()
    .toBuffer();
  const file = `startup-${name}.png`;
  await sharp({ create: { width: W, height: H, channels: 3, background: bg } })
    .composite([{ input: mark, gravity: "centre" }])
    .png({ compressionLevel: 9, palette: true, quality: 90, effort: 10 })
    .toFile(join(PUBLIC, file));
  largest = Math.max(largest, statSync(join(PUBLIC, file)).size);
  links.push(
    `    <link rel="apple-touch-startup-image" media="screen and (device-width: ${w}px) and (device-height: ${h}px) and (-webkit-device-pixel-ratio: ${dpr}) and (orientation: portrait)" href="/${file}" />`,
  );
}

const html = readFileSync(INDEX, "utf8");
const START = "<!-- startup-images -->";
const END = "<!-- /startup-images -->";
const a = html.indexOf(START);
const b = html.indexOf(END);
if (a === -1 || b === -1 || b < a) throw new Error(`index.html needs ${START} … ${END} markers in <head>`);
const next = `${html.slice(0, a + START.length)}\n${links.join("\n")}\n    ${html.slice(b)}`;
if (next !== html) writeFileSync(INDEX, next);

// ---- manifest ----
const manifest = {
  id: "/",
  name: "Trading Portal",
  short_name: "Portal",
  description: "Hub, Replay Journal and News Room for Jamie and the mates.",
  start_url: "/",
  scope: "/",
  display: "standalone",
  orientation: "any",
  background_color: bg,
  theme_color: bg,
  categories: ["finance", "productivity"],
  icons: [
    { src: "/favicon-192.png", sizes: "192x192", type: "image/png" },
    { src: "/favicon-512.png", sizes: "512x512", type: "image/png" },
    { src: "/favicon-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
  ],
};
writeFileSync(join(PUBLIC, "site.webmanifest"), JSON.stringify(manifest, null, 2) + "\n");
console.log(`icons, ${STARTUP.length} launch screens (largest ${(largest / 1024).toFixed(1)} KB) and site.webmanifest written to ${PUBLIC} (theme ${bg}); index.html startup links updated`);
