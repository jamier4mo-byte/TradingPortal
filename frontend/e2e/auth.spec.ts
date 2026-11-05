import { expect, test } from "@playwright/test";

import { ADMIN, api, createInvite, MEMBER, signIn } from "./helpers/auth.ts";

test("wrong password shows a plain error and stays on the page", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill(ADMIN.email);
  await page.getByLabel("Password", { exact: true }).fill("not-the-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("alert")).toHaveText("Wrong email or password.");
  await expect(page).toHaveURL(/\/login$/);
});

test("admin signs in, a member joins through an invite link in a second browser context", async ({ page, browser }) => {
  await signIn(page, ADMIN);

  // Make the invite through the UI and read the link back.
  await page.goto("/admin/users");
  await page.getByRole("button", { name: /Invite/ }).click();
  await page.getByRole("button", { name: "Create invite link" }).click();
  const url = await page.getByTestId("invite-url").textContent();
  expect(url).toMatch(/\/invite\/[A-Za-z0-9_-]{20,}$/);
  const token = url!.split("/invite/")[1];

  const other = await browser.newContext();
  const member = await other.newPage();
  await member.goto(`/invite/${token}`);
  await expect(member.getByRole("heading", { name: "Create your account" })).toBeVisible();
  const email = `newbie-${Date.now()}@example.test`;
  await member.getByLabel("Email").fill(email);
  await member.getByLabel("Display name").fill("Newbie");
  await member.getByLabel("Password", { exact: true }).fill("a-long-password-1");
  await member.getByRole("button", { name: "Create account" }).click();
  await expect(member.getByRole("heading", { level: 1, name: /Newbie/ })).toBeVisible();

  // The link is single-use.
  const again = await other.newPage();
  await again.goto(`/invite/${token}`);
  await expect(again.getByRole("heading", { name: "This invite won't work" })).toBeVisible();

  // Members can't reach admin screens or admin API calls (403), and see the read-only tag list.
  await member.goto("/admin/users");
  await expect(member).toHaveURL(/\/$/);
  const forbidden = await api(other, "POST", "/api/admin/invites", { role: "member" });
  expect(forbidden.status()).toBe(403);
  const me = await (await api(other, "GET", "/api/auth/me")).json();
  const promote = await api(other, "PATCH", `/api/admin/users/${me.id}/role`, { role: "admin" });
  expect(promote.status()).toBe(403);
  await member.goto("/tags");
  await expect(member.getByRole("status").filter({ hasText: "Read-only" })).toBeVisible();
  await expect(member.getByRole("button", { name: /Propose/ })).toBeVisible();

  // Admin deactivates the member: they're signed out and can't sign in again.
  await page.goto("/admin/users");
  const row = page.getByRole("listitem").filter({ hasText: email });
  await row.getByRole("button", { name: "Deactivate" }).click();
  await page.getByRole("button", { name: "Deactivate", exact: true }).last().click();
  await expect(row).toContainText("Newbie (deactivated)");
  await member.reload();
  await expect(member).toHaveURL(/\/login/);
  await member.getByLabel("Email").fill(email);
  await member.getByLabel("Password", { exact: true }).fill("a-long-password-1");
  await member.getByRole("button", { name: "Sign in" }).click();
  await expect(member.getByRole("alert")).toHaveText("This account is deactivated.");
  await other.close();
});

test("five wrong passwords lock the account for 15 minutes", async ({ page, browser }) => {
  // A throw-away account so the lock never touches the seeded users.
  const admin = await browser.newContext();
  const adminPage = await admin.newPage();
  await signIn(adminPage, ADMIN);
  const token = await createInvite(admin);
  await admin.close();
  const email = `lockme-${Date.now()}@example.test`;
  const fresh = await browser.newContext();
  const res = await fresh.request.post("/api/auth/invite/accept", {
    data: { token, email, display_name: "Lock Me", password: "a-long-password-1" },
    headers: { "X-CSRF-Token": await csrfFor(fresh) },
  });
  expect(res.status()).toBe(200);
  await fresh.close();

  await page.goto("/login");
  for (let i = 0; i < 5; i++) {
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password", { exact: true }).fill("wrong-password-1");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByRole("alert")).toHaveText("Wrong email or password.");
  }
  await page.getByLabel("Password", { exact: true }).fill("a-long-password-1");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Locked for now" })).toBeVisible();
  await expect(page.getByText(/Try again in \d+ min/)).toBeVisible();
});

test("member sees only their own settings and can sign out from the menu", async ({ page }) => {
  await signIn(page, MEMBER);
  await page.goto("/settings");
  await expect(page.getByText(MEMBER.email)).toBeVisible();
  await expect(page.getByRole("heading", { name: "API keys" })).toBeVisible();
  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login/);
  await page.goto("/settings");
  await expect(page).toHaveURL(/\/login/);
});

async function csrfFor(context: import("@playwright/test").BrowserContext): Promise<string> {
  await context.request.get("/api/auth/csrf");
  return (await context.cookies()).find((c) => c.name === "tp_csrf")?.value ?? "";
}
