# Prompt 1 of 5: Foundations (sign-in, roles, shell, states)

Paste everything below the line into a fresh `claude` session in `~/Desktop/Trading Portal`.

---

You are building the Trading Portal, Jamie's multi-tool trading web app (Hub, Replay Journal, News Room), in this repo. This is **Prompt 1 of 5: Foundations**. Work fully autonomously from start to finish.

## Operating rules (apply all the way through)

- **Don't stop to ask.** If something is undecided, use the Defaults below or the most conservative reasonable choice. Record it under "Assumptions" in the phase report and carry on. Stop early only if continuing would break one of these rules.
- **Read first, in full:**
  - `CLAUDE.md`
  - `docs/planning/trading-portal-foundations.md`
  - `docs/planning/trading-portal-review-and-build-kit.md`
  - `.claude/skills/trading-portal-tokens/SKILL.md`
  - `docs/claude-setup/SETUP-REPORT.md`
  - `docs/build/PROGRESS.md` and any `docs/build/PHASE-*-REPORT.md`, if they exist

  The Review & Build Kit's **Decisions** and **Doc fixes (F1–F19)** override the Foundations doc where they differ.
- **Resume-safe.** Keep `docs/build/PROGRESS.md` as a checklist of this prompt's steps, with a section headed `## Prompt 1`. Tick each step when it lands and commit. If the file shows this prompt partly done, continue from the first unticked item; never redo finished work.
- **Plan, then execute.** Turn the steps below into a task list. Use the Explore and Plan subagents, in parallel, to read the old app and design big pieces, so the main context stays lean. Use Context7 for current library APIs (FastAPI, SQLAlchemy 2, Alembic, React Router 7, Radix, Tailwind 4, Motion, py_webauthn, SimpleWebAuthn) instead of relying on memory.
- **Git.**
  - Start from a clean local `main` and create `build/01-foundations`. If that branch already exists, resume on it.
  - Make small commits with clear messages.
  - **Never** push, deploy, create Fly resources or set Fly secrets.
  - At the end, if the gate passes, run `git switch main && git merge --no-ff build/01-foundations`, locally only. If it fails, leave the branch unmerged and explain why.
- **Data.**
  - Never read or write `~/ReplayJournal/data`.
  - Dev and test data live under `/tmp/tp-*`; never in the repo.
  - `~/Desktop/Replay Journal` is the old app, for **reference only**: read it, never edit it, never copy it wholesale. Rebuild everything in this repo's style.
- **Secrets.**
  - Never in the repo, and never echoed.
  - Local dev reads `.env` (git-ignored); generate any dev-only secret into it with a script.
  - List every production secret the app needs in the phase report.
  - Tests mock every network call.
- **Database.**
  - Schema changes only through Alembic migrations in `backend/migrations/versions/`.
  - Every owned record has `owner_id`, `created_at`, `updated_at` and `deleted_at` (soft delete).
- **Permissions are server-side.** On every write: members change only their own records; the admin changes anything; deactivated users can do nothing. Each rule has a test.
- **Design.**
  - Use the tokens skill before any style, and never put a hex value outside `@theme`.
  - Use the one Card pattern, `.num` on every number and the reserved colours, with 44px targets and WCAG 2.2 AA.
  - Every screen has five states: loading skeleton, empty, error, read-only and offline. Each is designed for phone, tablet and desktop.
  - Follow the frontend-design skill so screens don't look templated.
- **Quality bar for every step.**
  - `make lint` and `make test` pass.
  - New backend logic has pytest tests.
  - New screens have Playwright e2e tests at 375px and 1440px, including axe.
  - After UI work, run `/check-devices` (or follow `.claude/commands/check-devices.md` by hand) and ask the `design-reviewer` subagent for a review. Fix every blocker and major.
- **Don't loop.** If the same failure survives two genuine fixes, log it under "Known issues" and move on.

## Defaults (settled unless Jamie said otherwise in an earlier report)

- Button text on accent stays dark ink (`--color-on-accent`). The proposed win, loss and impact hexes stay.
- Login is email + password (Argon2id), with optional passkeys. There is no public sign-up; accounts come only from admin invite links.
- Roles are `admin` and `member`. Jamie is the first admin.
- The view toggle is **Mine · Everyone · Others** (F12), defaulting to Everyone. Everything is visible to everyone; strategies can't be duplicated.
- Sessions are server-side, in an httpOnly cookie, SameSite=Lax, Secure in production, and last 30 days (sliding).
- CSRF uses a double-submit token on every unsafe method.
- Lockout: after 5 failed logins, the account is locked for 15 minutes. Logins are also rate-limited per IP.

## Steps

**0. Preflight**
- Check that `git status` is clean. If `docs/build/masterprompts/` is untracked, commit it first, on the new branch.
- Run `make setup`, `make test`, `make lint` and `make smoke`, and record the baseline.
- Note which MCP servers are connected (`claude mcp list`). If Context7 isn't there, carry on and note it.
- Create `docs/build/PROGRESS.md`.

**1. Backend structure**
- Lay out `app/models/`, `app/schemas/` (Pydantic v2), `app/api/` (one router per area under `/api`), `app/services/` and `app/core/` (settings, security, deps).
- Move settings to pydantic-settings, reading the environment plus `.env`. Add `TRADING_PORTAL_SECRET_KEY`:
  - `make dev-secrets` writes a random one into `.env` if it's missing.
  - Production refuses to start without it.
- Write shared model mixins (timestamps, soft delete, owner).
- Add an `audit_log` table (actor, action, target, metadata, at).
- Test fixtures: a temporary data directory per test session, migrations applied, and factory helpers for users and records.

**2. Users, sign-in and roles** (F6, F11, 4.1)
- **Tables:**
  - `users`: email, display name, role, status active/deactivated, password hash, owner-colour index, failed logins, locked-until, last seen
  - `sessions`: hashed token, expiry, user agent
  - `invites`: hashed token, role, 7-day expiry, used-at, created-by
  - `password_resets`: one-time, 1 hour
  - `passkeys`: WebAuthn credentials, via py_webauthn
- **Endpoints:**
  - login, logout, me
  - accept invite: set name and password
  - forgot/reset by admin-issued link (no email sending yet: the admin copies the link)
  - change password
  - passkey register and login
  - admin only: create an invite link; list users; change a role; deactivate and reactivate (F6: never delete; a deactivated user's work stays visible, labelled "(deactivated)")
- **Bootstrap:** a `make create-admin` CLI that asks for email and password interactively (also usable through `fly ssh console` later).
- **Shared helpers:** `require_admin`, `require_owner_or_admin(record, user)`, and a scope filter `scope=mine|everyone|others` for list endpoints.
- **Tests:** a full role × action matrix, lockout, expired and reused invites, deactivated-user rejection, CSRF rejection and the session sliding window.

**3. Per-user key vault** (F1, F13; used in Prompt 4)
- `user_api_keys` table: provider, Fernet ciphertext derived from the secret key, last 4 characters, created and last-tested.
- Endpoints to set, delete and test a key. Test is a stub until Prompt 4.
- A plaintext key never leaves the server and is never logged.

**4. Shared tag vocabulary** (U5)
- `tags` table: name, slug, category (`pd_array`, `entry_model`, `liquidity`, `structure`, `killzone`, `confluence`, `other`), synonyms list and created-by.
- Admin can create, edit and merge tags; members can propose new tags.
- A `resolve_tag(text)` service matches names and synonyms case- and punctuation-insensitively (`FVG` = `fair value gap` = `f.v.g`).
- Seed an ICT/SMC starter list in a data migration. Include at least: FVG, IFVG, order block, breaker, mitigation block, BOS, MSS/CHoCH, liquidity sweep, BSL, SSL, equal highs/lows, OTE, premium/discount, PD array, SMT divergence, NWOG/NDOG, Asia/London/NY AM/NY PM killzones, Silver Bullet, Judas swing, HTF bias.

**5. Front-end foundation**
- **Data layer:** add TanStack Query and a typed `api` client that handles CSRF and 401 → login redirect. Add protected routes and role-aware UI.
- **Auth screens:** login (password or passkey), accept invite, reset password and locked-out message. These are designed screens with the Trading Portal logo, not default forms.
- **App shell, per device** (Devices → Navigation by device):
  - Desktop and laptop: a sidebar collapsible to icons, with status dots.
  - Tablet: an icon rail.
  - Phone: a bottom tab bar (Hub, Journal, News, Calendar, More), a top bar with the page title and one action, a floating "+", and filters in bottom sheets.
  - Top bar: Cmd+K palette, UK clock (`.num`), session status (Asia/London/NY open or closed, weekend), notifications placeholder and avatar menu.
  - Respect safe-area insets.
- **Shared components:**
  - Skeleton (shimmer)
  - EmptyState (inline-SVG line illustration plus one next step)
  - ErrorState with retry
  - ReadOnlyBanner ("Viewing Sam's strategy · read-only")
  - OfflineBanner
  - Toast with undo
  - ConfirmDialog
  - Drawer (right side on desktop, bottom sheet on phone)
  - PillToggle with a sliding indicator
  - ViewScopeToggle (Mine · Everyone · Others, kept in the URL)
  - OwnerChip
  - Chip with dot
  - StatTile
  - RingGauge

  Add them all to a hidden `/dev/components` gallery page. The e2e tests and the design-reviewer can use it.
- **Owner colours:** define 8 owner tokens in `@theme`, and update the tokens skill table in the same commit. They must be distinct from each other and from the reserved win, loss and impact hues, and pass 3:1 on `surface-1`.
- **Admin pages:** Users (invite link with copy button, role, deactivate/reactivate, reset link) and Tags (list, synonyms, merge).
- **Settings page:**
  - Profile, password, passkeys
  - API keys section (Twelve Data, placeholder state until Prompt 4)
  - Motion setting **Full / Reduced / Off**, stored per user and applied as a `data-motion` attribute that every animation respects alongside `prefers-reduced-motion`
  - Breakeven threshold, default 2 (F16)
- **Motion foundation** (F18):
  - Add `motion`, the only animation library.
  - A route-change wrapper using the View Transitions API with a fallback cross-fade: content fades with an 8–12px rise while the shell stays still.
  - Motion presets built from the tokens.
- **PWA basics** (F17):
  - From `frontend/public/brand/t-tile.png`, generate `favicon.ico` plus 16, 32, 192 and 512px PNGs and a 180px `apple-touch-icon`, with a small script committed in `scripts/`.
  - `site.webmanifest`: `display: standalone`, theme and background set to the bg token's value, written by the script.
  - The head tags from the Foundations doc, plus og:image from `tradingportal-logo.png`, `theme-color` and `viewport-fit=cover`.
  - The service worker comes in Prompt 4.
- **Performance budget** (F18): add `scripts/check-bundle.mjs` and wire it into `make lint` and CI. It fails if the Hub route's initial JS is over 200KB gzip. ECharts and every tool page are lazy-loaded.

**6. Dev experience**
- `make seed-dev` fills `/tmp/tp-dev` with an admin, two members and a few sample records.
- Update the e2e suite so it signs in through a helper and covers the auth flows. Add `/admin`, `/settings` and `/dev/components` to `scripts/capture.mjs` `ROUTES`.
- Update `CLAUDE.md` → Commands.

**7. Gate 1 checks** (all must pass)
- Admin signs in. A member signs up through an invite link in a second browser context.
- The member gets 403 from the API when trying to edit or delete the admin's records, and sees the read-only banner in the UI.
- Deactivating the member signs them out and blocks sign-in. Lockout triggers after 5 failures.
- `make lint`, `make test` and `make smoke` are green, and axe passes on every route.
- `/check-devices` shows no problems at 360, 375, 430, 768, 1440 and 1920px. Bottom tabs appear on the phone, the rail on the tablet and the sidebar on desktop.
- The design-reviewer has no blockers or majors left.
- The bundle budget passes.

## Finish

Write `docs/build/PHASE-1-REPORT.md` with:
- What was built
- The Gate 1 checklist with pass/fail and how each was verified
- Assumptions
- Open questions for Jamie, numbered and answerable in one line each
- Known issues
- Production secrets needed so far
- **"Jamie's check (10 min)"**: exact commands and clicks to see it working, starting with `make dev` and `make create-admin`

Tick everything in `PROGRESS.md`, commit, merge locally if the gate passed, and print a short summary.
