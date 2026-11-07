import { type BrowserContext, expect, type Page } from "@playwright/test";

/** Seeded by `python -m app.cli seed-dev` before the smoke backend starts (see playwright.config.ts). */
export const ADMIN = { email: "jamie@example.test", password: "password-dev-1", name: "Jamie" };
export const MEMBER = { email: "sam@example.test", password: "password-dev-1", name: "Sam" };
export const MEMBER_2 = { email: "alex@example.test", password: "password-dev-1", name: "Alex" };

export async function signIn(page: Page, user: { email: string; password: string }) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(user.email);
  await page.getByLabel("Password", { exact: true }).fill(user.password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL((u) => !u.pathname.startsWith("/login"));
  // The shell is mounted (and its keyboard shortcuts attached) once the account menu is on screen; the URL
  // changes a render earlier, which is too soon for a Cmd+K or a click.
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
}

/** Calls the API with the browser context's cookies and the CSRF double-submit header. */
export async function api(context: BrowserContext, method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE", path: string, data?: unknown) {
  let cookies = await context.cookies();
  if (!cookies.some((c) => c.name === "tp_csrf")) {
    await context.request.get("/api/auth/csrf");
    cookies = await context.cookies();
  }
  const csrf = cookies.find((c) => c.name === "tp_csrf")?.value ?? "";
  return context.request.fetch(path, { method, data, headers: { "X-CSRF-Token": csrf } });
}

/** Admin creates an invite; returns the token. */
export async function createInvite(adminContext: BrowserContext, role: "admin" | "member" = "member"): Promise<string> {
  const res = await api(adminContext, "POST", "/api/admin/invites", { role });
  expect(res.status()).toBe(201);
  const body = (await res.json()) as { url: string };
  return body.url.split("/invite/")[1];
}
