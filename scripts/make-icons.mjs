// Generate the favicon set, apple-touch-icon and site.webmanifest from frontend/public/brand/t-tile.png.
//   cd frontend && node ../scripts/make-icons.mjs
// Colours come from the @theme block in frontend/src/index.css so the manifest never drifts from the tokens.
import { readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join, resolve } from "node:path";

const require = createRequire(join(process.cwd(), "package.json"));
const sharp = require("sharp");
const pngToIcoModule = require("png-to-ico");
const pngToIco = pngToIcoModule.default ?? pngToIcoModule;

const PUBLIC = resolve("public");
const SRC = join(PUBLIC, "brand", "t-tile.png");
const css = readFileSync(resolve("src/index.css"), "utf8");
const token = (name) => {
  const m = css.match(new RegExp(`${name}:\\s*(#[0-9a-fA-F]{6})`));
  if (!m) throw new Error(`token ${name} not found in index.css`);
  return m[1].toUpperCase();
};
const bg = token("--color-bg");

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

const manifest = {
  name: "Trading Portal",
  short_name: "Portal",
  description: "Hub, Replay Journal and News Room for Jamie and the mates.",
  start_url: "/",
  scope: "/",
  display: "standalone",
  orientation: "any",
  background_color: bg,
  theme_color: bg,
  icons: [
    { src: "/favicon-192.png", sizes: "192x192", type: "image/png" },
    { src: "/favicon-512.png", sizes: "512x512", type: "image/png" },
    { src: "/favicon-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
  ],
};
writeFileSync(join(PUBLIC, "site.webmanifest"), JSON.stringify(manifest, null, 2) + "\n");
console.log(`icons + site.webmanifest written to ${PUBLIC} (theme ${bg})`);
