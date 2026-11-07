# Security review and hardening (Prompt 5, step 6)

Branch `build/05-hub-calendar-launch`, 7 Nov 2026. Scope: the FastAPI backend (`backend/app`), the way it serves
the built SPA, the deploy files (`fly.toml`, `Dockerfile`, `backend/entrypoint.sh`, `.github/workflows/deploy.yml`)
and the dependencies. The front end was read only as far as the headers needed (`frontend/dist/index.html`,
`lib/api.ts`, the Monte Carlo worker, `public/sw.js`); nothing under `frontend/src` or `sw.js` was changed.

Severity: **high** = exploitable by an outsider or a member to read/alter others' data or take the machine down;
**medium** = a real weakening of a control, or a leak of secret material in an export/log; **low** = defence in
depth or hygiene; **info** = checked and fine, recorded so it isn't re-reviewed from scratch.

## 1. Findings

| # | Area | Finding | Severity | Status | Where |
|---|------|---------|----------|--------|-------|
| 1 | Headers | No `Content-Security-Policy`, `X-Frame-Options`, `Referrer-Policy`, `X-Content-Type-Options`, `Permissions-Policy`, `COOP` or HSTS on any response | medium | **fixed** | `core/headers.py` `SecurityHeadersMiddleware`, wired in `main.py`; `tests/test_security_headers.py`; `frontend/e2e/csp.spec.ts` |
| 2 | Headers | `/api/auth/*`, `/api/me/*`, `/api/admin/*` answers were cacheable by default; `/sw.js` had no `no-cache`; `/assets/*` had no long-lived cache | low | **fixed** | same middleware (`cache_control_for`); a handler's own `Cache-Control` always wins |
| 3 | Attack surface | `/openapi.json` and `/redoc` were still served in production (only `/api/docs` was switched off) | low | **fixed** | `main.py`: `openapi_url` → `/api/openapi.json` in dev, `None` in production; `redoc_url=None` always; test |
| 4 | DoS | No request-body cap: any JSON route accepted an unbounded body; upload routes read the whole body before checking the 12 MB image / 20 MB CSV limits | medium | **fixed** | `core/headers.py` `BodyLimitMiddleware`: 2 MB default, 14 MB screenshots, 6 MB CSV imports; `Content-Length` checked first, chunked bodies counted and cut off with a 413; tests |
| 5 | Export | "Export everything" zip carried the live `sessions` (hashed tokens), `invites` and `password_resets` rows | medium | **fixed** | `services/export_all.py`: the snapshot copy has those three tables emptied and is `VACUUM`ed before zipping; `manifest.json.omitted_tables`; README says so; test greps every zip member for a vault plaintext and checks the live DB is untouched |
| 6 | Export | `user_api_keys.ciphertext` (Fernet, HKDF key from `TRADING_PORTAL_SECRET_KEY`) and `users.password_hash` (Argon2id) stay in the export | info | **accepted** | A restore needs both; neither is readable without the secret key / the password. The test proves the plaintext key never appears |
| 7 | Rate limits | Expensive endpoints (`/api/analytics/export/{ai,csv}`, `/api/admin/export`, `/api/strategies/{id}/imports/preview`) had no per-user limit | low | **fixed** | `core/deps.py` `heavy_limiter` (10/min per user id) via `HeavyUser` / `heavy_endpoint`; `tests/test_ratelimits.py` |
| 8 | Rate limits | Per-IP limiter on login, invite peek/accept, reset, passkey begin/finish | info | **present** | `api/auth.py` `_limit` on every unauthenticated route (one shared 10/min limiter); now tested route by route |
| 9 | Uploads | CSV import had a 20 MB byte cap but no row cap | low | **fixed** | `services/fxreplay.py`: 5 MB and 50 000 rows; `api/journal.py` `_read_csv` reads at most 5 MB + 1 and answers 413 |
| 10 | Auth | Admin invite / reset links were built from the request's `Origin` header, else `Host` (Host-header injection → a link pointing at another site) | low | **fixed** | `api/admin.py` `_origin`: `Origin` is honoured only if it is one of `TRADING_PORTAL_ORIGINS`; otherwise the first configured origin; `Host` only as a last resort; test |
| 11 | Auth | Reset link claim wasn't atomic (two concurrent uses could both pass the `used_at` check) | low | **fixed** | `services/users.py` `use_reset`: single `UPDATE … WHERE used_at IS NULL AND expires_at > now` claim, like invites |
| 12 | Auth | 422 validation errors echo the submitted `input`, including a mistyped password on `/api/auth/login` or `/api/me/password` | low | **fixed** | `main.py` validation handler drops `input` under `/api/auth/` and `/api/me`; test |
| 13 | Auth | A junk `rawId` in a passkey sign-in response raised in `base64url_to_bytes` → 500 | low | **fixed** | `services/passkeys.py` → `PasskeyError` 400 |
| 14 | Auth | Session tokens random (32 bytes) and stored as SHA-256; cookie `HttpOnly`, `SameSite=Lax`, `Secure` in production; sliding 30-day expiry (slide ≤ once a day); logout deletes the server row; password change and deactivation revoke every session | info | **present** | `services/users.py`, `core/deps.py`; existing tests |
| 15 | Auth | Timing: `authenticate` verifies against a dummy Argon2 hash when the email is unknown | info | **present** | `core/security.py` `_DUMMY_HASH` |
| 16 | Auth | Locked accounts answer 423 (reveals the account exists) | info | **accepted** | Phase 1 assumption 2; softened by the per-IP limiter |
| 17 | CSRF | Double-submit on every unsafe `/api` call: readable `tp_csrf` cookie must equal `X-CSRF-Token`, compared in constant time; the API only accepts JSON or multipart with that header, and the session cookie is `SameSite=Lax`, so a cross-site form post or `fetch` can't carry the header | info | **sound** | `core/csrf.py`; `fly.dev` is on the Public Suffix List so sibling apps can't plant cookies |
| 18 | Invites/resets | Tokens: 32 random bytes, stored hashed, looked up by hash (no plaintext compared or logged), single use (atomic claim), 7 days / 1 hour | info | **present** | `services/users.py` |
| 19 | Passwords | Argon2id (library defaults), minimum 10 characters, no leading/trailing spaces, can't reuse the current one | info | **present** | `core/security.py` |
| 20 | Passkeys | Challenges in memory for 60 s, one process (fine on one machine); registration bound to the signed-in user; origin and RP id from settings | info | **present** | `services/passkeys.py` |
| 21 | Roles | Every `/api` route classified public / member / admin and checked for every role automatically | info | **added** | `tests/test_route_roles.py` (section 2) |
| 22 | Uploads | Magic-byte sniff (PNG/JPEG/WebP/GIF only; SVG refused), 12 MB cap, dimension and pixel cap before decoding, thumbnail re-encoded to WebP; storage key is `{strategy}/{trade}/{slot}-{random}.{ext}`: the client filename is only stored as metadata, never used in a path; `check_key` + `_resolve` keep keys under the root; served with the sniffed `content_type` and now `nosniff`; `/api/screenshots/{id}/full|thumb` need a session and 404 on soft-deleted rows | info | **present** | `services/screenshots.py`, `services/storage.py`, `api/journal.py`; existing tests |
| 23 | Zip | Zip-slip: export entry names are `screenshots/<storage key>` where every key passed `check_key` on write; the AI export's image names are generated | info | **present** | `services/export_all.py`, `services/analytics/export.py` |
| 24 | Vault | HKDF-SHA256 → Fernet; `set_key` stores ciphertext + `last4`; `reveal_for_server_use` is the only decrypt path and is used for outbound headers only; `ApiKeyOut` has no plaintext field; audit rows carry the provider name only; `TwelveDataProvider.__repr__` and `_scrub` hide the key; the key travels in `Authorization`, never the URL | info | **present** | `services/keys.py`, `core/security.py`, `services/prices/provider.py` |
| 25 | SSRF | Feed URLs are fixed settings (`ff_calendar_url`, JBlanked `BASE_URL` + `jblanked_source` literal); user input reaches only query parameters (`symbol`, `q`); `httpx.Client` is built with `follow_redirects=False` (httpx default), 15 s timeout, generic `User-Agent`; push endpoints are allow-listed to the Google/Mozilla/Apple/Microsoft push hosts (https, port 443, no userinfo) at registration (`SubscriptionIn` validator) and again at send | info | **present** | `services/http.py`, `services/news/*.py`, `services/prices/provider.py`, `services/push.py`, `schemas/alerts.py` |
| 26 | Errors | Unhandled exceptions return Starlette's plain `Internal Server Error` (no traceback: `debug` is off); `/api/{path}` 404 is JSON and never falls through to the SPA | info | **present** | `main.py`; tests |
| 27 | SPA | `spa()` resolves the candidate and requires `FRONTEND_DIST` among its parents, so `..`, `%2e%2e`, `//etc/passwd` and `%2f` all fall back to `index.html` | info | **present** | tested in `test_security_headers.py` |
| 28 | Scheduler | Jobs run only from the lifespan task behind a DB lease; no route triggers them | info | **present** | `services/scheduler.py` |
| 29 | Audit log | `auth.login/logout/locked`, `invite.created/accepted`, `reset.created/used`, `user.password_changed/role_changed/active/deactivated`, `passkey.registered/deleted`, `api_key.set/deleted` (no key material), `export.everything`, tag/strategy/trade/task changes, `news.instrument_map` | info | **present** | `services/audit.py` and callers |
| 30 | Proxy trust | `_client_ip` trusts `Fly-Client-IP` then the first `X-Forwarded-For` hop. Behind Fly's proxy both are set by Fly. Off Fly (local, or if the app is ever exposed directly) a client can spoof them and dodge the per-IP limiter; the per-account lockout still applies | low | **open (documented)** | `api/auth.py` |
| 31 | CORS | No CORS middleware; the API is same-origin only. `TRADING_PORTAL_ORIGINS` is used by WebAuthn and (now) by the invite-link builder only | info | **confirmed** | grep: no `CORSMiddleware` |
| 32 | Dependencies | `npm audit --omit=dev`: 0 vulnerabilities; `pip-audit` on the venv's installed packages: none known | info | **clean** | section 4; `make audit`; non-blocking CI step |
| 33 | Push | `upsert_subscription` moves an endpoint re-registered by another user to the new user and wipes the old delivery history | info | **accepted** | A browser profile changing hands; the endpoint is allow-listed and the subscription keys are never returned |
| 34 | Push | `push_subscriptions.p256dh/auth` are in the export (they let the holder send notifications to that device until it re-subscribes) | low | **accepted** | Needed for a restore to keep alerts working; the zip is admin-only, rate-limited and audited |

No finding was rated high. Every medium is fixed.

## 2. Route × role table

`backend/tests/test_route_roles.py` discovers every `/api` route by walking the app's routers (that includes the
`include_in_schema=False` routes `/api/admin/export` and `/api/screenshots/{id}/full|thumb`, which an
`app.openapi()`-only scan would miss; the test also asserts the OpenAPI paths are a subset of what it found).
Each route × method is called as anonymous, member and admin with an empty body (or a tiny CSV for the
multipart routes) and path parameters set to `1`, and checked against the checked-in `ROUTE_ROLES` table:

| Class | Rule | Count |
|-------|------|-------|
| `public` | anonymous is not refused with 401/403 | 9 (`/api/health`, `/api/auth/csrf`, `login`, `logout`, `invite/{token}`, `invite/accept`, `reset`, `passkey/login/begin`, `passkey/login/finish`) |
| `member` | anonymous → 401; member and admin get past auth (owner checks happen inside the handler and are covered by the journal/calendar/alert tests) | 89 |
| `admin` | anonymous → 401; member → 403; admin gets past auth | 12 (`/api/admin/*` ×6, `POST/PATCH /api/instruments`, `PUT /api/news/instrument-map`, `PATCH/DELETE /api/tags/{id}`, `POST /api/tags/{id}/merge`) |

A route that appears without a row fails `test_every_route_is_classified` with a message naming it; a row
whose route disappeared fails too. No route failed its gate. `tests/test_permissions.py` (the hand-written
matrix with real bodies) is unchanged and still passes.

## 3. Headers

Every response carries:

```
Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline';
  img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; worker-src 'self' blob:;
  manifest-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'
  [; upgrade-insecure-requests   — production only]
Strict-Transport-Security: max-age=63072000; includeSubDomains   — production only
Referrer-Policy: strict-origin-when-cross-origin
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=(), usb=()
Cross-Origin-Opener-Policy: same-origin
```

Cache-Control defaults (only when the handler set none): `no-store` under `/api/auth/`, `/api/me`, `/api/admin/`;
`public, max-age=31536000, immutable` under `/assets/` (hashed filenames); `no-cache` for `/sw.js` and
`/index.html` (the SPA fallback already sends `no-cache`; screenshots keep their own `private, immutable`).

Trade-offs and checks:
- `script-src 'self'` with no `'unsafe-inline'` or `'unsafe-eval'`: confirmed against the built
  `frontend/dist/index.html` (Vite 8): one `<script type="module" src="/assets/…">`, `modulepreload` links, one
  stylesheet, no inline script and no inline modulepreload polyfill. ECharts renders to canvas (no eval).
- `style-src 'unsafe-inline'`: React, `motion` and FullCalendar set `style=` attributes (27 `style={…}` uses in
  `frontend/src` plus library-generated ones). Styles can't execute script; accepted. Nonces would need a
  server-rendered index, which this static SPA doesn't have.
- `worker-src 'self' blob:`: the Monte Carlo worker is a same-origin module (`new Worker(new URL(…))`) and the
  service worker is `/sw.js`; `blob:` is kept for Vite's worker fallback.
- `img-src data: blob:`: screenshot previews before upload and chart exports.
- `font-src data:`: the first e2e run with `font-src 'self'` logged 24 "Refused to load the font" violations:
  FullCalendar ships its icon font (`fcicons`, IcoMoon) as a `data:application/x-font-ttf` URI and Vite inlines
  the small font subsets under its asset-inline limit as `data:font/woff2`. Fonts can't execute, so `data:` is
  allowed for fonts only (not for scripts or styles).
- HSTS and `upgrade-insecure-requests` are production-only because Fly terminates TLS (`force_https = true`)
  and the dev server is plain http.
- The middleware is pure ASGI (no body buffering) and is outermost, so a 401, a CSRF 403 or a 413 carries the
  headers too. `frontend/e2e/csp.spec.ts` signs in and visits `/`, the analytics tab (canvases + worker), `/news`,
  `/calendar` and `/settings`, failing on any `Refused to …` console message.

## 4. Dependency audit (7 Nov 2026)

`cd frontend && npm audit --omit=dev` → **found 0 vulnerabilities**.
`pip freeze` of `backend/.venv` through `pip-audit` → **No known vulnerabilities found**.

Backend: fastapi 0.162.0 · starlette 1.10.0 · uvicorn 0.54.0 · SQLAlchemy 2.1.8 · alembic 1.20.1 ·
pydantic 2.14.3 · pydantic-settings 2.16.2 · argon2-cffi 25.1.0 · cryptography 50.0.2 · webauthn 3.0.1 ·
python-multipart 0.0.33 · pillow 13.0.0 · httpx 0.28.1 · pywebpush 2.5.0 · requests 2.34.2 · urllib3 2.8.0 ·
boto3 1.43.126 · python-dateutil 2.9.0.post0 · (dev) moto 5.2.5.
Front end: react 19.3 · react-router-dom 7.18 · @tanstack/react-query 5.106 · echarts 6.1 · motion 14.9 ·
@fullcalendar 6.1.22 · radix-ui dialog/dropdown/switch/toast/tooltip · @simplewebauthn/browser 14 · lucide-react 1.61.

`make audit` runs both (pip-audit through `pipx run`, so it never joins the venv). `.github/workflows/deploy.yml`
has the same two commands as a `continue-on-error` step after the front-end build: advisory, never blocking.

## 5. Other things checked

- `fly.toml`: `force_https`, `TRADING_PORTAL_ENV=production` (secure cookies, no docs/schema, secret key required
  and ≥ 32 chars), RP id and origins pinned to the host; health check runs `select 1`.
- `Dockerfile`: pinned Litestream release, `pip install --no-deps -e` of the app, no secrets baked in.
- `entrypoint.sh`: never overwrites an existing database on the volume; migrations before serving.
- `.env` is git-ignored and was not read; tests set every secret-bearing variable blank (`conftest.py`).
- Network under tests: `services/http.py` refuses every real request; push uses `FakePushSender`; S3 via moto.
- `calendar.py` untouched (already refuses sub-daily rules, caps occurrences and the 62-day window).

## 6. Assumptions

1. Two per-process in-memory limiters (per-IP for sign-in, per-user for heavy endpoints) are enough on one
   Fly machine; a second machine would need them in the database like `leases`.
2. 10 heavy calls a minute per user is plenty for people; a stuck client loop is what it's for.
3. Rows removed from the export snapshot (`sessions`, `password_resets`, `invites`) are ephemeral by nature; an
   admin re-issues any open invite after a restore. Everything else stays so a restore is complete.
4. The 423 lockout disclosure and the Origin/Host fallback in `_origin` when no origins are configured are kept
   as documented.

## 7. For the main session (front end)

Nothing is required. The CSP as shipped does not block the current build (e2e `csp.spec.ts`). Two things to
keep in mind for future front-end work:
- Never add an inline `<script>` or an `onclick=` attribute to `index.html` or a component: `script-src 'self'`
  will block it. Third-party scripts or fonts from a CDN would also need their origin added to the policy
  (`core/headers.py` `CSP_DIRECTIVES`); the self-hosted `@fontsource` fonts are fine.
- If the PWA agent's `sw.js` caches cross-origin responses or uses `importScripts()` from another origin, add
  that origin to `worker-src`/`connect-src`; same-origin caching needs nothing.

## 8. Test results

- `cd backend && .venv/bin/pytest -q` → **726 passed** (3 min 22 s). New files: `tests/test_security_headers.py`
  (18), `tests/test_route_roles.py` (3 + one case per route × method = 113), `tests/test_ratelimits.py` (10);
  new cases in `tests/test_export_all.py` and `tests/test_auth.py`.
- `ruff check . && ruff format --check .` → clean.
- `cd frontend && SMOKE_PORT=… npx playwright test e2e/csp.spec.ts e2e/smoke.spec.ts e2e/routes.spec.ts
  e2e/analytics.spec.ts` against a backend with the headers on: `csp.spec.ts` passes on desktop and phone
  (the first run caught the `font-src` gap above, which is why `data:` is allowed for fonts). Final run:
  **66 passed, 4 failed**, and the four are not header-related: `smoke.spec.ts` "Hub greets…" fails axe
  colour-contrast on the Hub's calendar card (`text-muted` labels) and `routes.spec.ts` "Cmd+K palette" never
  sees the palette open. Both files (`Hub.tsx`, `index.css`, `CommandPalette.tsx`) had uncommitted edits from
  the motion/PWA agents during this run, and a one-off check pressing Cmd+K under the CSP logged no
  "Refused to…" message, so they are that work in flight, not the policy. Not touched here.
