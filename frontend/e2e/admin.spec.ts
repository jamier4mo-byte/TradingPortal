import { expect, test } from "@playwright/test";

import { ADMIN, signIn } from "./helpers/auth.ts";

test("admin approves a proposed tag and merges one into another", async ({ page }) => {
  await signIn(page, ADMIN);
  await page.goto("/admin/tags");
  const proposed = page.getByRole("heading", { name: "Proposed by members" });
  if (await proposed.isVisible()) {
    await page.getByRole("button", { name: "Approve" }).first().click();
    await expect(page.getByText(/approved$/)).toBeVisible();
    await page.getByRole("button", { name: "Dismiss" }).click();
    await expect(page.getByText(/approved$/)).toHaveCount(0);
  }
  const stamp = Date.now();
  const name = `Merge me ${stamp}`;
  await page.getByRole("button", { name: /^New( tag)?$/ }).click();
  await page.getByLabel("Name").fill(name);
  await page.getByLabel("Synonyms").fill(`mm${stamp}, m.m.${stamp}`);
  await page.getByRole("button", { name: "Create tag" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByText(name, { exact: true })).toBeVisible();
  await page.getByRole("button", { name: `Merge ${name} into another tag`, exact: true }).click();
  await page.getByLabel("Into", { exact: true }).selectOption({ label: "FVG · PD arrays" });
  await page.getByRole("button", { name: "Merge", exact: true }).click();
  await expect(page.getByText("Merged into “FVG”")).toBeVisible();
  await expect(page.getByText(name, { exact: true })).toHaveCount(0);
});

test("admin saves and removes a Twelve Data key, seeing only the last 4", async ({ page }) => {
  await signIn(page, ADMIN);
  await page.goto("/settings");
  await page.getByLabel(/Twelve Data key|Replace key/).fill("fake-twelve-data-key-ABCD");
  await page.getByRole("button", { name: "Save key" }).click();
  await expect(page.getByText("····ABCD")).toBeVisible();
  await expect(page.getByText("fake-twelve-data-key-ABCD")).toHaveCount(0);
  await page.getByRole("button", { name: "Check key" }).click();
  await expect(page.getByText("Key looks good")).toBeVisible();
  await page.getByRole("button", { name: "Remove", exact: true }).click();
  await page.getByRole("button", { name: "Remove key" }).click();
  await expect(page.getByText("No Twelve Data key yet")).toBeVisible();
});

test("motion setting is stored and applied to the document", async ({ page }) => {
  await signIn(page, ADMIN);
  await page.goto("/settings");
  await page.getByRole("radio", { name: "Reduced" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-motion", "reduced");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-motion", "reduced");
  await page.getByRole("radio", { name: "Full" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-motion", "full");
});
