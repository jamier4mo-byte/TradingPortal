// Performance budget (F18): the Hub route's initial JavaScript must be under 200KB gzipped.
//   cd frontend && npm run build && node ../scripts/check-bundle.mjs
// Reads dist/.vite/manifest.json and sums the entry chunk plus every chunk it imports statically.
// Lazy (dynamic) imports — ECharts, the tool pages — are not counted, because they don't load with the Hub.
import { readFileSync, statSync } from "node:fs";
import { join, resolve } from "node:path";
import { gzipSync } from "node:zlib";

const BUDGET_KB = Number(process.env.BUNDLE_BUDGET_KB ?? 200);
const DIST = resolve(process.env.DIST ?? "dist");
const manifest = JSON.parse(readFileSync(join(DIST, ".vite", "manifest.json"), "utf8"));

const entry = Object.values(manifest).find((m) => m.isEntry);
if (!entry) throw new Error("no entry chunk in the Vite manifest");

const seen = new Set();
const walk = (key) => {
  const chunk = manifest[key] ?? Object.values(manifest).find((m) => m.file === key);
  if (!chunk || seen.has(chunk.file)) return;
  seen.add(chunk.file);
  for (const imp of chunk.imports ?? []) walk(imp);
};
walk(Object.keys(manifest).find((k) => manifest[k] === entry));

// ECharts must never load with the Hub: it lives behind Chart.tsx's dynamic import (F18).
const echartsKey = Object.keys(manifest).find((k) => k.endsWith("components/charts/echarts.ts"));
const echartsFile = echartsKey ? manifest[echartsKey].file : null;
if (echartsFile && seen.has(echartsFile)) {
  console.error(`ECharts (${echartsFile}) is in the Hub's initial JS. Import charts only through components/charts/Chart.tsx.`);
  process.exit(1);
}
for (const file of seen) {
  if (readFileSync(join(DIST, file), "utf8").includes("echarts/lib")) {
    console.error(`${file} carries ECharts code into the Hub's initial JS.`);
    process.exit(1);
  }
}

let total = 0;
const rows = [];
for (const file of seen) {
  const gz = gzipSync(readFileSync(join(DIST, file))).length;
  total += gz;
  rows.push([file, statSync(join(DIST, file)).size, gz]);
}
rows.sort((a, b) => b[2] - a[2]);
for (const [file, raw, gz] of rows) console.log(`${(gz / 1024).toFixed(1).padStart(7)} KB gz  ${(raw / 1024).toFixed(1).padStart(7)} KB  ${file}`);
const kb = total / 1024;
console.log(`\nHub initial JS: ${kb.toFixed(1)} KB gzip (budget ${BUDGET_KB} KB)`);
console.log(echartsFile ? `ECharts: lazy chunk ${echartsFile}, not in the Hub ✓` : "ECharts: not bundled yet");
if (kb > BUDGET_KB) {
  console.error(`Over budget by ${(kb - BUDGET_KB).toFixed(1)} KB. Lazy-load the heavy import or split the chunk.`);
  process.exit(1);
}
