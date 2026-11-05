# Phase 1 report: Foundations

Branch `build/01-foundations`, 5 Nov 2026. Gate 1 passed; merged into local `main` (not pushed).

## What was built

**Backend** (`backend/app/`)
- `core/`: pydantic-settings (`TRADING_PORTAL_*`, reads `.env`), Argon2id passwords, opaque tokens stored as SHA-256, HKDF-derived Fernet vault key, double-submit CSRF middleware, in-memory per-IP rate limiter, dependencies (`current_user`, `require_admin`, `require_owner_or_admin`, `apply_scope` for `scope=mine|everyone|others`).
- `models/`: `User`, `Session`, `Invite`, `PasswordReset`, `Passkey`, `AuditLog`, `UserApiKey`, `Tag`; mixins for timestamps, soft delete and owner (`OwnedRecordMixin` = `owner_id` + `created_at` + `updated_at` + `deleted_at`). A `UTCDateTime` type keeps every datetime timezone-aware on SQLite.
- `services/`: sign-in with lockout (5 failures → 15 min), 30-day sliding sessions, invites (7 days, one use, claimed atomically), admin reset links (1 hour, one use), change password (signs out other devices), roles and deactivate/reactivate (never delete; label "(deactivated)"), WebAuthn passkeys via py_webauthn (discoverable sign-in, in-memory 60 s challenges), key vault (set/delete/test; plaintext never returned or logged), tag vocabulary (`resolve_tag` is case- and punctuation-insensitive, admin create/edit/merge/delete, member proposals), audit log.
- `api/`: `/api/auth/*`, `/api/me/*`, `/api/users`, `/api/admin/*`, `/api/tags/*`, `/api/health`, `/api/docs` (dev only). Unknown `/api/*` → 404 JSON, never the SPA.
- Migrations `0002_foundations` (schema) and `0003_seed_tags` (38 ICT/SMC tags with synonyms).
- CLI: `make create-admin` (interactive), `make seed-dev` (`/tmp/tp-dev`: jamie/sam/alex), `make dev-secrets`.
- 136 pytest tests: role × action matrix (15 endpoints × 3 roles), lockout, rate limit, CSRF, sliding window, expired session, deactivation, invites (reuse, expiry, email pin), resets, passkey register + sign-in with a simulated authenticator (replay and wrong-origin rejected), vault round trip, tag resolution and merge, settings rules, audit rows.

**Front end** (`frontend/src/`)
- Data layer: TanStack Query, typed `lib/api.ts` (CSRF header, 401 → login), `AuthProvider`, `RequireAuth`, `RequireAdmin`; `data-motion` on `<html>` from the user's setting.
- Auth screens: login (password or passkey), locked-out state, accept invite, reset password, all on one `AuthFrame` with the logo over a brand hairline and the UK clock as the only atmosphere.
- Shell: sidebar collapsible to icons (laptop+, remembered), icon rail (tablet), bottom tabs Hub · Journal · News · Calendar · More plus a floating "+" (phone); top bar with Cmd+K palette, UK clock (`.num`), session status, notifications placeholder, avatar menu; safe-area insets.
- Shared components (`components/ui/`): Skeleton, EmptyState (inline-SVG line illustrations), ErrorState, ReadOnlyBanner, OfflineBanner, Toast with undo, ConfirmDialog, Drawer (right / bottom sheet), PillToggle (sliding spring indicator), ViewScopeToggle (`?scope=` in the URL), OwnerChip, Chip, StatTile, RingGauge, Field/TextInput. All on `/dev/components`.
- Pages: Hub (greets the signed-in user), Tags (member: read-only banner + propose), Admin Users (invite link with copy, role, deactivate/reactivate, reset link), Admin Tags (approve, edit, merge, delete), Settings (profile, password, passkeys, Twelve Data key, Motion Full/Reduced/Off, breakeven threshold default 2), More (phone).
- Motion: `motion` is the only animation library; View Transitions route change with a `motion` cross-fade fallback (8–12px rise, fade-only in Reduced, none in Off); presets in `lib/motion.ts`.
- Tokens: 8 owner colours and `--color-border-input` added to `@theme` and the tokens skill; `.btn`/`.input`/`.card`/`.skeleton` moved into `@layer components`.
- PWA: `scripts/make-icons.mjs` → `favicon.ico`, 16/32/192/512 PNGs, `apple-touch-icon-180.png`, `site.webmanifest` (standalone, theme from the bg token); head tags incl. og:image, theme-color, viewport-fit=cover.
- Budget: `scripts/check-bundle.mjs` in `make lint` and CI; Hub initial JS **180.6 KB gzip** (budget 200). Every tool page and the auth screens are lazy; ECharts isn't on the Hub.
- e2e (`frontend/e2e`): sign-in helper, auth flows, roles, lockout, admin tags/keys/motion, every route (axe WCAG 2.2 AA, no horizontal scroll, 44px targets) at 1440 and 375, device navigation, Cmd+K, gallery. `scripts/capture.mjs` signs in and covers login, tags, settings, more, admin, admin-tags, components.

## Gate 1 checklist

| Check | Result | How verified |
|---|---|---|
| Admin signs in; member accepts an invite in a second browser context | Pass | `e2e/auth.spec.ts` "admin signs in, a member joins…" (desktop + phone) |
| Member gets 403 editing the admin's records; sees the read-only banner | Pass | Same spec: `POST /api/admin/invites` and `PATCH …/role` → 403; `/tags` shows "Read-only". Backend: `test_role_matrix` (45 cases), `test_require_owner_or_admin` |
| Deactivation signs the member out and blocks sign-in; lockout after 5 failures | Pass | Same spec + "five wrong passwords lock the account"; backend `test_deactivated_user_is_signed_out…`, `test_lockout_after_five_failures…` |
| `make lint`, `make test`, `make smoke` green; axe on every route | Pass | lint clean (ruff, oxlint, tsc, bundle); 136 pytest; 46 Playwright incl. axe on 10 routes × 2 viewports + login |
| `/check-devices` at 360/375/430/768/1440/1920; tabs on phone, rail on tablet, sidebar on desktop | Pass | `docs/check-devices/2026-11-05/` (66 screenshots, not committed); `e2e/routes.spec.ts` "navigation matches the device" |
| design-reviewer: no blockers or majors | Pass | First pass: 1 blocker + 5 majors, all fixed (reduced-motion rule, CSS layering, safe-area header, 44px pill, logo ≥ 240px / sidebar `w-72`, input border 3:1). Second pass: see Known issues for what was left |
| Bundle budget | Pass | 180.6 KB gzip of 200 KB |

## Assumptions
1. Defaults from the prompt were used as given: dark ink on accent buttons; proposed win/loss/impact hexes kept; email + password with optional passkeys; invite-only; admin/member; Mine · Everyone · Others defaulting to Everyone; 30-day sliding sessions; double-submit CSRF; 5-failure/15-minute lockout plus a per-IP limit (10/min, `TRADING_PORTAL_LOGIN_RATE_PER_MINUTE`).
2. **Locked accounts answer 423** so the UI can show the locked-out screen. That reveals the account exists (the security review flagged it). Accepted on purpose for a four-person app behind a per-IP limit.
3. In development with no `TRADING_PORTAL_SECRET_KEY`, a dev-only key is written to `<data dir>/.dev-secret-key` so sessions and the vault survive restarts; `make dev-secrets` writes a proper one into `.env`. Production refuses to start without one.
4. "Members propose tags" = a tag row with `status=proposed` that the admin approves, edits or removes. Proposed tags are visible to everyone, labelled "proposed".
5. Passkey challenges live in process memory (60 s). Fine for one Fly machine; move to a table if there's ever more than one.
6. WebAuthn RP id defaults to `localhost` and origins to the Vite dev URL. Production needs `TRADING_PORTAL_RP_ID` and `TRADING_PORTAL_ORIGINS` set to the real host.
7. The key vault "test" is a stub: a key passes if it decrypts and is ≥ 8 characters. Prompt 4 replaces it with a real Twelve Data call.
8. Owner colours (teal, periwinkle, pink, sand, lilac, sky, chartreuse, mauve) are proposed; each user gets a fixed `colour_index` (0–7, cycling) at creation.
9. The sidebar widened from 240px to 288px so the full logo meets the 240px minimum from the Foundations doc.
10. `make lint` now builds the front end first (the bundle check needs `dist/`).

## Open questions for Jamie
1. Keep dark ink on blue buttons, or darken the button so white text passes AA?
2. Confirm the proposed win `#2FD27F`, loss `#FF5A66`, breakeven `#8F99AD`, impact orange `#FF9F43` / yellow `#F5D547`?
3. Confirm the 8 owner colours, or name hues you'd rather see?
4. Should a locked account say "locked" (current) or just "wrong email or password"?
5. Should the in-app Motion "Full" override the device's reduce-motion setting (current), or should the device setting always win?
6. Phone top bar carries search, bell and avatar; the doc says "title and one action". Keep search only, or keep all three?
7. Breakeven threshold is ±2 in $; is that dollars or pips/points for your instruments?
8. Should members see other members' email addresses (`/api/users` currently hides them; admin list shows them)?

## Known issues
- Design-reviewer minors left for later: enter-only dialog animations (no leave animation; desktop drawer rises rather than slides), chip remove hit-areas overlap with `gap-2`, `og:image` is the transparent logo (needs a dark social card), `text-[10px]` initials in avatars, phone top bar has more than one action (Q6).
- `index.js` is 516 KB raw / 163 KB gzip: `motion`, Radix and React Router make up most of it. Under budget but worth trimming in Prompt 5 (e.g. lazy-load `motion` for the launch sequences).
- Context7 MCP shows "connected" but rejects calls ("Invalid API key"); library APIs were read from the installed packages instead. Playwright, chrome-devtools and flyctl MCP servers are still pending approval in this session.
- Pyright (the editor LSP) can't see `backend/.venv`, so it reports missing imports; ruff and pytest are the source of truth.
- `make smoke` leaves the seeded smoke DB in the OS temp dir (as before).

## Production secrets needed so far
| Secret | Used for |
|---|---|
| `TRADING_PORTAL_SECRET_KEY` | Derives the Fernet key for the API-key vault; required in production |
| `TRADING_PORTAL_ENV=production` | Secure cookies, no `/api/docs`, no dev-key fallback |
| `TRADING_PORTAL_RP_ID`, `TRADING_PORTAL_ORIGINS` | WebAuthn passkeys on the real host (config, not secret) |
| `FLY_API_TOKEN` (GitHub Actions) | Deploys; still unset by design |

## Jamie's check (10 min)
1. `make dev-secrets` then `make dev`, open http://localhost:5173 — you land on the sign-in screen.
2. In another terminal: `make create-admin` (your email, a 10+ character password). Sign in. The Hub greets you by name; the sidebar shows Tags, Settings and Admin.
3. Admin → Users → **Invite someone** → **Create invite link** → **Copy link**. Open a private window, paste the link, create "Sam". Sam lands on the Hub with no Admin entry; `/admin/users` bounces to the Hub.
4. As Sam: Tags shows the read-only banner and **Propose a tag**. Propose "Rejection block" with synonym "RB".
5. As you: Admin → Tags → **Approve** it. Try **Merge** on any tag; **Filter** by "fvg" and "f.v.g" — both find FVG.
6. Settings: set Motion to Reduced, change the breakeven threshold, paste any 8+ character string as a Twelve Data key → only the last 4 appear; **Check key** → "Key looks good"; remove it. Add a passkey (Touch ID on the Mac) and sign in with it from the login screen.
7. Admin → Users → **Deactivate** Sam: the private window is signed out on its next click and Sam can't sign in again. Reactivate.
8. Sign out, then type a wrong password 5 times → the locked-out screen.
9. Resize the window: bottom tabs under 600px, icon rail to 1023px, sidebar from 1024px (collapse it with the « at the bottom). Press ⌘K and type "sett".
10. `make lint` prints the Hub bundle size; `make test` and `make smoke` are green.
