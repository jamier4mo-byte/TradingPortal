import { readFileSync } from "node:fs";
import { join } from "node:path";

import { type BrowserContext, expect, type Page, test } from "@playwright/test";

import { expectNoAxeViolations, expectNoHorizontalScroll, expectTapTargets } from "./helpers/a11y.ts";
import { ADMIN, api, MEMBER, signIn } from "./helpers/auth.ts";

const FIXTURE = join(import.meta.dirname, "..", "..", "backend", "tests", "fixtures", "fxreplay-sample.csv");
const CSV = readFileSync(FIXTURE);
// A real 4×4 PNG so the browser pipeline can decode it.
const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAQAAAAECAIAAAAmkwkpAAAAFklEQVQIW2P8z8DwnwEJMDIwMDBQQQAA//8DAPzfA/9S4qJ1AAAAAElFTkSuQmCC",
  "base64",
);

/** Seeded by seed-dev: strategy 1 (Jamie, ideal session 1 + backtest session 2), strategy 2 (Sam). */
const ROUTES = ["/journal", "/journal/strategies/1", "/journal/strategies/1?tab=backtest", "/journal/strategies/1?tab=analytics", "/journal/strategies/1/trades/1", "/journal/sessions/1/match", "/journal/sessions/1/annotate", "/journal/trash"];

async function newStrategy(context: BrowserContext, name: string): Promise<number> {
  const res = await api(context, "POST", "/api/strategies", { name, instruments: ["NAS100"], timeframes: ["5m"], entry_models: ["FVG"] });
  expect(res.status()).toBe(201);
  return ((await res.json()) as { id: number }).id;
}

async function importCsv(context: BrowserContext, strategyId: number, destination: "ideal" | "backtest") {
  const res = await context.request.post(`/api/strategies/${strategyId}/imports`, {
    multipart: { file: { name: "export.csv", mimeType: "text/csv", buffer: CSV }, destination },
    headers: { "X-CSRF-Token": (await context.cookies()).find((c) => c.name === "tp_csrf")?.value ?? "" },
  });
  expect(res.status()).toBe(201);
  return (await res.json()) as { session: { id: number }; trades: { id: number }[] };
}

/** Puts an image on a synthetic clipboard and fires paste, as ⌘V would. */
async function pasteImage(page: Page, name = "pasted.png") {
  await page.evaluate(
    ({ b64, name }) => {
      const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
      const dt = new DataTransfer();
      dt.items.add(new File([bytes], name, { type: "image/png" }));
      const target = document.activeElement ?? document.body;
      target.dispatchEvent(new ClipboardEvent("paste", { clipboardData: dt, bubbles: true, cancelable: true }));
    },
    { b64: PNG.toString("base64"), name },
  );
}

test.describe("journal screens are accessible and fit the screen", () => {
  test.beforeEach(async ({ page }) => {
    await signIn(page, ADMIN);
  });
  for (const route of ROUTES) {
    test(`${route} passes axe, has no horizontal scroll and 44px targets`, async ({ page }) => {
      await page.goto(route);
      await page.waitForLoadState("networkidle");
      await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
      await expectNoHorizontalScroll(page);
      await expectTapTargets(page);
      await expectNoAxeViolations(page);
    });
  }
});

test("strategy grid shows everyone's cards, the scope filter and the stage", async ({ page }) => {
  await signIn(page, ADMIN);
  await page.goto("/journal");
  await expect(page.getByRole("link", { name: /NAS100 silver bullet/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /EURUSD London reversal/ })).toBeVisible();
  await page.getByRole("radio", { name: "Mine" }).click();
  await expect(page.getByRole("link", { name: /EURUSD London reversal/ })).toBeHidden();
  await expect(page.getByRole("link", { name: /NAS100 silver bullet, Backtesting/ })).toBeVisible();
});

test("import flow: upload → preview → confirm, winners only, undo and restore, duplicates on a re-import", async ({ page, context }) => {
  await signIn(page, ADMIN);
  await page.goto("/journal");
  await page.getByRole("button", { name: /New strategy|^New$/ }).first().click();
  await page.getByLabel("Name").fill("Import e2e");
  await page.getByRole("button", { name: "Create strategy" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Import e2e" })).toBeVisible();

  await page.getByRole("button", { name: /Import/ }).first().click();
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: /Choose the CSV/ }).click();
  await (await chooser).setFiles({ name: "export.csv", mimeType: "text/csv", buffer: CSV });
  await expect(page.getByText("10 of 12")).toBeVisible();
  await expect(page.getByRole("radio", { name: /Ideal · 6 winners/ })).toBeChecked();
  await expect(page.getByText("2 rows can't be read")).toBeVisible();
  await page.getByRole("button", { name: "Import 6 trades" }).click();
  await expect(page.getByText("6 trades imported").first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Annotate trades" })).toBeVisible();
  await page.getByRole("button", { name: "Later" }).click();
  await expect(page.getByText("6 trades · 0/18 screenshots")).toBeVisible();

  // Undo from the toast, then undo the undo
  await page.getByRole("button", { name: "Undo", exact: true }).click();
  await expect(page.getByText("Import undone", { exact: true })).toBeVisible();
  await expect(page.getByText("No ideal trades yet")).toBeVisible();
  await page.getByRole("button", { name: "Undo", exact: true }).click();
  await expect(page.getByText("Import restored", { exact: true })).toBeVisible();
  await expect(page.getByText("6 trades · 0/18 screenshots")).toBeVisible();

  // Backtest is its own ledger and takes every row; importing the same file again is all duplicates
  const id = Number(page.url().match(/strategies\/(\d+)/)?.[1]);
  const second = await importCsv(context, id, "backtest");
  expect(second.trades).toHaveLength(10);
  await page.reload();
  await page.getByRole("button", { name: /Import/ }).first().click();
  const chooser2 = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: /Choose the CSV/ }).click();
  await (await chooser2).setFiles({ name: "export.csv", mimeType: "text/csv", buffer: CSV });
  await expect(page.getByText(/6 trades are already in this strategy's ideal catalogue/)).toBeVisible();
  await page.getByRole("radio", { name: /Backtest · 0 trades/ }).click();
  await expect(page.getByText(/10 trades are already in this strategy's backtest/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Import 0 trades" })).toBeDisabled();
});

test("bulk matcher pairs 24 dropped files by name and saves them all", async ({ page, context }) => {
  await signIn(page, ADMIN);
  const id = await newStrategy(context, "Matcher e2e");
  const { session } = await importCsv(context, id, "backtest");
  await page.goto(`/journal/sessions/${session.id}/match`);
  await expect(page.getByRole("heading", { level: 1, name: "Match screenshots" })).toBeVisible();
  const files = [];
  for (let i = 1; i <= 8; i++) {
    files.push({ name: `T0${i}_htf.png`, mimeType: "image/png", buffer: PNG });
    files.push({ name: `T0${i}_entry.png`, mimeType: "image/png", buffer: PNG });
    files.push({ name: `t${i}-outcome.png`, mimeType: "image/png", buffer: PNG });
  }
  await page.getByLabel("Screenshots", { exact: true }).setInputFiles(files);
  await expect(page.getByText("24 of 24 matched automatically")).toBeVisible();
  await expect(page.getByRole("button", { name: /Entry for trade 3: T03_entry.png, Sure/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /HTF for trade 3: T03_htf.png, Sure/ })).toBeVisible();
  // Fix one by tapping: pick up trade 1's entry and drop it on trade 10's outcome, then put it back
  await page.getByRole("button", { name: /Entry for trade 1: T01_entry.png/ }).click();
  await page.getByRole("button", { name: /Outcome for trade 10: empty/ }).click();
  await expect(page.getByRole("button", { name: /Outcome for trade 10: T01_entry.png/ })).toBeVisible();
  await page.getByRole("button", { name: /Outcome for trade 10: T01_entry.png/ }).click();
  await page.getByRole("button", { name: /Entry for trade 1: empty/ }).click();
  await page.getByRole("button", { name: /Save all \(24\)/ }).click();
  await expect(page).toHaveURL(new RegExp(`/journal/sessions/${session.id}/annotate`), { timeout: 30_000 });
  const res = await api(context, "GET", `/api/journal/sessions/${session.id}`);
  const body = (await res.json()) as { progress: { screenshots: number } };
  expect(body.progress.screenshots).toBe(24);
});

test("annotate mode completes 8 trades with the keyboard only", async ({ page, context }) => {
  test.setTimeout(90_000);
  await signIn(page, ADMIN);
  const id = await newStrategy(context, "Annotate e2e");
  const { session } = await importCsv(context, id, "backtest");
  await page.goto(`/journal/sessions/${session.id}/annotate`);
  await expect(page.getByRole("dialog", { name: "Trade 1/10" })).toBeVisible();
  for (let i = 1; i <= 8; i++) {
    await expect(page.getByRole("heading", { level: 1, name: `Trade ${i}/10` })).toBeVisible();
    await expect(page.getByRole("button", { name: /^Add HTF screenshot/ })).toBeVisible(); // stepper mounted, paste listener live
    await pasteImage(page, `htf-${i}.png`);
    await expect(page.getByRole("button", { name: /^HTF screenshot/ })).toBeVisible();
    await pasteImage(page, `entry-${i}.png`);
    await expect(page.getByRole("button", { name: /^Entry screenshot/ })).toBeVisible();
    await pasteImage(page, `outcome-${i}.png`);
    await expect(page.getByRole("button", { name: /^Outcome screenshot/ })).toBeVisible();
    await expect(page.getByLabel("HTF bias", { exact: true })).toBeFocused();
    await page.keyboard.type(`Bullish ${i}`);
    for (let f = 0; f < 5; f++) await page.keyboard.press("Enter"); // to the last template field
    await page.keyboard.press("ControlOrMeta+Shift+Enter"); // mark completed and move on
  }
  await expect(page.getByRole("heading", { level: 1, name: "Trade 9/10" })).toBeVisible();
  await page.keyboard.press("k");
  await expect(page.getByRole("heading", { level: 1, name: "Trade 8/10" })).toBeVisible();
  await page.keyboard.press("j");
  await expect(page.getByRole("heading", { level: 1, name: "Trade 9/10" })).toBeVisible();
  await expect(page.getByText("8/10 completed")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page).toHaveURL(new RegExp(`/journal/strategies/${id}$`));
  await expect(page.getByText("10 trades · 24/30 screenshots · 8/10 reasons · 8/10 completed")).toBeVisible();
  const res = await api(context, "GET", `/api/journal/sessions/${session.id}/trades`);
  const trades = (await res.json()) as { reasoning: Record<string, string>; annotated_at: string | null; screenshots: { slot: string }[] }[];
  expect(trades.filter((t) => t.reasoning.htf_bias?.startsWith("Bullish"))).toHaveLength(8);
  expect(trades.filter((t) => t.annotated_at)).toHaveLength(8);
  expect(trades.filter((t) => ["htf", "entry", "outcome"].every((slot) => t.screenshots.some((s) => s.slot === slot)))).toHaveLength(8);
});

test("quick log remembers values and opens from the phone's + button", async ({ page }, testInfo) => {
  await signIn(page, ADMIN);
  if (testInfo.project.name === "phone") {
    await page.getByRole("button", { name: "Quick log a trade" }).click();
    await expect(page.getByRole("dialog", { name: "Log a trade" })).toBeVisible();
    await page.getByRole("link", { name: "NAS100 silver bullet" }).click();
  } else {
    await page.goto("/journal/strategies/1?quicklog=1");
  }
  await expect(page.getByRole("dialog", { name: "Log an ideal trade" })).toBeVisible();
  await page.getByLabel("Entry", { exact: true }).fill("21000");
  await page.getByLabel("Stop").fill("20960");
  await page.getByLabel("Target").fill("21120");
  await page.getByLabel("Exit price").fill("21100");
  await page.getByLabel("P&L ($)").fill("250");
  await page.getByRole("button", { name: "Log trade" }).click();
  await expect(page.getByRole("dialog", { name: "Screenshots" })).toBeVisible();
  await page.getByRole("button", { name: "Done" }).click();
  await expect(page.getByText("Trade logged", { exact: true })).toBeVisible();
});

test("a member sees the admin's strategy read-only and gets 403 on writes", async ({ page, context }) => {
  await signIn(page, MEMBER);
  await page.goto("/journal/strategies/1");
  await expect(page.getByRole("status").filter({ hasText: "Read-only" })).toBeVisible();
  await expect(page.getByRole("button", { name: /Log trade|^Log$/ })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Finish annotating" })).toHaveCount(0);
  expect((await api(context, "PATCH", "/api/strategies/1", { name: "Taken" })).status()).toBe(403);
  expect((await api(context, "PATCH", "/api/trades/1", { notes: "mine" })).status()).toBe(403);
  expect((await api(context, "DELETE", "/api/journal/sessions/1")).status()).toBe(403);
  await page.goto("/journal/strategies/1/trades/1");
  await expect(page.getByRole("status").filter({ hasText: "Read-only" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Delete trade" })).toHaveCount(0);
});

test("trade detail shows the gallery and the trash restores a deleted trade", async ({ page, context }) => {
  await signIn(page, ADMIN);
  const id = await newStrategy(context, "Trash e2e");
  const { trades } = await importCsv(context, id, "ideal");
  await page.goto(`/journal/strategies/${id}/trades/${trades[0].id}`);
  await expect(page.getByText("No screenshots yet")).toBeVisible();
  await page.getByRole("button", { name: "Delete trade" }).click();
  await page.getByRole("button", { name: "Move to Trash" }).click();
  await expect(page).toHaveURL(new RegExp(`/journal/strategies/${id}`));
  await page.goto("/journal/trash");
  await expect(page.getByRole("heading", { name: "Trades" })).toBeVisible();
  await page.getByRole("region", { name: "Trades" }).getByRole("button", { name: "Restore" }).first().click();
  await expect(page.getByText("Restored", { exact: true })).toBeVisible();
  const res = await api(context, "GET", `/api/trades/${trades[0].id}`);
  expect(res.status()).toBe(200);
});
