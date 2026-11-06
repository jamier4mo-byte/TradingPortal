/** Typed API client. Cookies carry the session; the CSRF cookie is echoed in a header on every write.
 * A 401 anywhere means the session ended: we tell the auth layer, which sends the user to /login. */

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

const CSRF_COOKIE = "tp_csrf";
const CSRF_HEADER = "X-CSRF-Token";

export const unauthorised = new EventTarget();

function readCookie(name: string): string | null {
  const match = document.cookie.split("; ").find((c) => c.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.slice(name.length + 1)) : null;
}

async function ensureCsrf(): Promise<string> {
  let token = readCookie(CSRF_COOKIE);
  if (!token) {
    await fetch("/api/auth/csrf", { credentials: "same-origin" });
    token = readCookie(CSRF_COOKIE);
  }
  return token ?? "";
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET") headers[CSRF_HEADER] = await ensureCsrf();
  const res = await fetch(path, {
    method,
    headers,
    credentials: "same-origin",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (res.status === 401) unauthorised.dispatchEvent(new Event("unauthorised"));
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail ?? data);
    } catch {
      /* no JSON body */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

async function upload<T>(path: string, form: FormData): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json", [CSRF_HEADER]: await ensureCsrf() };
  const res = await fetch(path, { method: "POST", headers, credentials: "same-origin", body: form });
  if (res.status === 401) unauthorised.dispatchEvent(new Event("unauthorised"));
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail ?? data);
    } catch {
      /* no JSON body */
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  upload,
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body ?? {}),
  put: <T>(path: string, body?: unknown) => request<T>("PUT", path, body ?? {}),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, body ?? {}),
  delete: <T>(path: string) => request<T>("DELETE", path),
};

// ---- types mirrored from backend/app/schemas ----
export type Role = "admin" | "member";
export type MotionPref = "full" | "reduced" | "off";

export interface User {
  id: number;
  email: string;
  display_name: string;
  label: string;
  role: Role;
  status: "active" | "deactivated";
  colour_index: number;
  motion_pref: MotionPref;
  breakeven_threshold: number;
  last_seen_at: string | null;
  created_at: string;
}

export interface PublicUser {
  id: number;
  display_name: string;
  label: string;
  status: "active" | "deactivated";
  colour_index: number;
}

export interface Invite {
  id: number;
  role: Role;
  email: string | null;
  expires_at: string;
  url: string;
}

export interface ResetLink {
  user_id: number;
  expires_at: string;
  url: string;
}

export interface Passkey {
  id: number;
  name: string;
  backed_up: boolean;
  created_at: string;
  last_used_at: string | null;
}

export interface ApiKey {
  provider: string;
  last4: string;
  created_at: string;
  updated_at: string;
  last_tested_at: string | null;
  last_test_ok: boolean | null;
}

export type TagCategory = "pd_array" | "entry_model" | "liquidity" | "structure" | "killzone" | "confluence" | "other";

export interface Tag {
  id: number;
  name: string;
  slug: string;
  category: TagCategory;
  synonyms: string[];
  status: "approved" | "proposed";
  created_by_id: number | null;
  created_at: string;
  updated_at: string;
}

export const TAG_CATEGORY_LABELS: Record<TagCategory, string> = {
  pd_array: "PD arrays",
  entry_model: "Entry models",
  liquidity: "Liquidity",
  structure: "Structure",
  killzone: "Killzones",
  confluence: "Confluences",
  other: "Other",
};
