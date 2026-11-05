# Build progress

One checklist per masterprompt. Each item is ticked when it lands and is committed on the
prompt's branch. If a prompt stops part-way, the next run continues from the first unticked item.

## Prompt 1 — Foundations (branch `build/01-foundations`)

### 0. Preflight
- [x] Clean `main`; only `docs/build/masterprompts/` and `.claude/settings.local.json` untracked
- [x] Branch `build/01-foundations`; `.claude/settings.local.json` git-ignored; masterprompts committed
- [x] Baseline: `make setup` OK · `make test` 2 passed · `make lint` clean · `make smoke` 10/10
- [x] MCP: context7 and github connected; playwright, chrome-devtools, flyctl pending approval
- [x] `docs/build/PROGRESS.md` created

### 1. Backend structure
- [x] `app/models`, `app/schemas`, `app/api`, `app/services`, `app/core` laid out
- [x] pydantic-settings; `TRADING_PORTAL_SECRET_KEY`; `make dev-secrets`; production refuses to start without it
- [x] Mixins: timestamps, soft delete, owner
- [x] `audit_log` table
- [x] Test fixtures: temp data dir, migrations, factories

### 2. Users, sign-in and roles
- [x] Tables: users, sessions, invites, password_resets, passkeys (migration)
- [x] Endpoints: login, logout, me, accept invite, forgot/reset, change password
- [x] Passkey register and login
- [x] Admin: invites, list users, change role, deactivate/reactivate
- [x] `make create-admin`
- [x] `require_admin`, `require_owner_or_admin`, scope filter
- [x] Tests: role × action matrix, lockout, invites, deactivated, CSRF, sliding session

### 3. Per-user key vault
- [x] `user_api_keys` table, Fernet, set/delete/test endpoints, tests

### 4. Shared tag vocabulary
- [x] `tags` table, admin CRUD + merge, member proposals, `resolve_tag`, seed migration, tests

### 5. Front-end foundation
- [x] TanStack Query + typed `api` client (CSRF, 401 → login); protected routes; role-aware UI
- [x] Auth screens: login (password/passkey), accept invite, reset, locked-out
- [x] App shell per device: sidebar / rail / bottom tabs, top bar (Cmd+K, clock, session, bell, avatar), safe areas
- [x] Shared components + `/dev/components` gallery
- [x] 8 owner colour tokens in `@theme` + tokens skill table
- [x] Admin pages: Users, Tags
- [x] Settings: profile, password, passkeys, API keys, motion, breakeven threshold
- [x] Motion foundation: `motion`, route transitions, presets
- [x] PWA basics: icons script, manifest, head tags
- [x] Bundle budget `scripts/check-bundle.mjs` in `make lint` and CI; lazy routes

### 6. Dev experience
- [x] `make seed-dev`
- [x] e2e: sign-in helper, auth flows, new routes in `capture.mjs`
- [x] `CLAUDE.md` → Commands updated

### 7. Gate 1
- [x] Admin signs in; member accepts invite in a second context
- [x] Member gets 403 on admin's records; read-only banner shown
- [x] Deactivation signs out and blocks sign-in; lockout after 5 failures
- [x] `make lint`, `make test`, `make smoke` green; axe on every route
- [x] `/check-devices` clean at 360/375/430/768/1440/1920; nav per device
- [x] design-reviewer: no blockers or majors
- [x] Bundle budget passes
- [x] `docs/build/PHASE-1-REPORT.md` written; merged to local `main`
