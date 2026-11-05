# Build progress

One checklist per masterprompt. Each item is ticked when it lands and is committed on the
prompt's branch. If a prompt stops part-way, the next run continues from the first unticked item.

## Prompt 1 — Foundations (branch `build/01-foundations`)

### 0. Preflight
- [x] Clean `main`; only `docs/build/masterprompts/` and `.claude/settings.local.json` untracked
- [x] Branch `build/01-foundations`; `.claude/settings.local.json` git-ignored; masterprompts committed
- [x] Baseline: `make setup` OK · `make test` 2 passed · `make lint` clean · `make smoke` (see report)
- [x] MCP: context7 and github connected; playwright, chrome-devtools, flyctl pending approval
- [x] `docs/build/PROGRESS.md` created

### 1. Backend structure
- [ ] `app/models`, `app/schemas`, `app/api`, `app/services`, `app/core` laid out
- [ ] pydantic-settings; `TRADING_PORTAL_SECRET_KEY`; `make dev-secrets`; production refuses to start without it
- [ ] Mixins: timestamps, soft delete, owner
- [ ] `audit_log` table
- [ ] Test fixtures: temp data dir, migrations, factories

### 2. Users, sign-in and roles
- [ ] Tables: users, sessions, invites, password_resets, passkeys (migration)
- [ ] Endpoints: login, logout, me, accept invite, forgot/reset, change password
- [ ] Passkey register and login
- [ ] Admin: invites, list users, change role, deactivate/reactivate
- [ ] `make create-admin`
- [ ] `require_admin`, `require_owner_or_admin`, scope filter
- [ ] Tests: role × action matrix, lockout, invites, deactivated, CSRF, sliding session

### 3. Per-user key vault
- [ ] `user_api_keys` table, Fernet, set/delete/test endpoints, tests

### 4. Shared tag vocabulary
- [ ] `tags` table, admin CRUD + merge, member proposals, `resolve_tag`, seed migration, tests

### 5. Front-end foundation
- [ ] TanStack Query + typed `api` client (CSRF, 401 → login); protected routes; role-aware UI
- [ ] Auth screens: login (password/passkey), accept invite, reset, locked-out
- [ ] App shell per device: sidebar / rail / bottom tabs, top bar (Cmd+K, clock, session, bell, avatar), safe areas
- [ ] Shared components + `/dev/components` gallery
- [ ] 8 owner colour tokens in `@theme` + tokens skill table
- [ ] Admin pages: Users, Tags
- [ ] Settings: profile, password, passkeys, API keys, motion, breakeven threshold
- [ ] Motion foundation: `motion`, route transitions, presets
- [ ] PWA basics: icons script, manifest, head tags
- [ ] Bundle budget `scripts/check-bundle.mjs` in `make lint` and CI; lazy routes

### 6. Dev experience
- [ ] `make seed-dev`
- [ ] e2e: sign-in helper, auth flows, new routes in `capture.mjs`
- [ ] `CLAUDE.md` → Commands updated

### 7. Gate 1
- [ ] Admin signs in; member accepts invite in a second context
- [ ] Member gets 403 on admin's records; read-only banner shown
- [ ] Deactivation signs out and blocks sign-in; lockout after 5 failures
- [ ] `make lint`, `make test`, `make smoke` green; axe on every route
- [ ] `/check-devices` clean at 360/375/430/768/1440/1920; nav per device
- [ ] design-reviewer: no blockers or majors
- [ ] Bundle budget passes
- [ ] `docs/build/PHASE-1-REPORT.md` written; merged to local `main`
