> **Historical.** This prompt was written for the old Replay Journal repo. In this fresh repo the same tooling is already committed (`.mcp.json`, `.claude/`), and `scripts/claude-setup.sh` does the Mac-only installs. See `docs/claude-setup/SETUP-REPORT.md`.

# Masterprompt: install the Trading Portal's Claude skills and tools

How to use: open Terminal, `cd ~/Desktop/"Trading Portal"`, run `claude`, and paste everything below the line.
Source: "Trading Portal Foundations: Review & Build Kit" → Claude skills and tools (checked 5 Nov 2026).

---

You are setting up Claude Code tooling for the Trading Portal repo in the current folder (git repo `jamier4mo-byte/Replay-Journal`). Stack: FastAPI + SQLAlchemy/Alembic + SQLite backend in `backend/` (venv at `backend/.venv`), React 19 + Vite 8 + Tailwind 4 + Radix + ECharts front end in `frontend/` (Playwright tests in `frontend/e2e`). Deploys to Fly.io from GitHub Actions on push to `main`.

Install and verify the tools below, in order. Work autonomously, but follow these rules:

RULES
- Create a branch `chore/claude-tooling` before changing any file. Do not push, deploy, or merge.
- Never write a token or API key into any file in the repo, and never echo one to the terminal. Servers that need a secret go in **user** scope (`--scope user`); servers with no secret go in **project** scope (`.mcp.json`, committed).
- Never touch `~/ReplayJournal/data` (Jamie's real journal). Any run of the app uses `REPLAY_JOURNAL_DATA_DIR=/tmp/rj-setup`.
- Keep existing files: merge into `.claude/settings.json`, `.claude/launch.json`, `.claude/skills/` and `.mcp.json` rather than overwriting.
- If a command fails, try once more with the fix the error suggests, then mark that item FAILED in the report and move on.
- Where a step needs Jamie (a key, a browser sign-in, a slash command only he can type), batch these into ONE question at the end of the preflight, not one by one.

STEP 0 — PREFLIGHT (report versions, install nothing yet)
- `claude --version`, `node --version` (need ≥ 22.13 for Context7), `npm --version`, `python3 --version`, `git --version`.
- `fly version` and `fly auth whoami` (flyctl). If missing: `brew install flyctl`.
- Check whether `claude plugin --help` exists. If it does, use `claude plugin marketplace add …` / `claude plugin install …` for the plugin steps below. If it doesn't, collect the `/plugin …` lines into the final report for Jamie to paste.
- `claude mcp list` to see what is already installed; skip anything already present.
- Then ask Jamie, in one message, to create: (a) a Context7 API key (free at https://context7.com/dashboard), (b) a fine-grained GitHub token limited to `jamier4mo-byte/Replay-Journal` with Contents, Issues, Pull requests and Actions read/write (https://github.com/settings/personal-access-tokens/new). Keys must never be pasted into this chat: for Steps 3 and 5, give Jamie the exact `claude mcp add …` command with `YOUR_KEY` as a placeholder, for him to run in a separate Terminal tab with his key. Continue with steps that need no secret while waiting.

STEP 1 — Playwright MCP (Microsoft) · project scope · https://github.com/microsoft/playwright-mcp
`claude mcp add --scope project playwright -- npx @playwright/mcp@latest`

STEP 2 — frontend-design skill (Anthropic) · https://github.com/anthropics/skills
The repo already has `.claude/skills/frontend-design/`. Compare it with the official one; if the official one is newer, install the plugin (`frontend-design@claude-plugins-official`) and keep the repo copy only if it holds Trading Portal-specific changes.

STEP 3 — Context7 MCP (Upstash) · user scope · https://github.com/upstash/context7
`claude mcp add --scope user --transport http context7 https://mcp.context7.com/mcp --header "Authorization: Bearer YOUR_KEY"  # Jamie runs this himself`
(Or the plugin `context7@claude-plugins-official`.) Free plan: 1,000 calls/month.

STEP 4 — flyctl MCP (Fly.io) · https://fly.io/docs/flyctl/mcp-server/
`fly mcp server --claude --server flyctl` — experimental; keep the default 127.0.0.1 bind and never pass `--access-token` on the command line.

STEP 5 — GitHub MCP server (GitHub) · user scope · https://github.com/github/github-mcp-server
`claude mcp add --scope user --transport http github https://api.githubcopilot.com/mcp --header "Authorization: Bearer YOUR_KEY"  # Jamie runs this himself`
Do NOT use the archived `@modelcontextprotocol/server-github` package.

STEP 6 — Official plugins (Anthropic) · https://code.claude.com/docs/en/discover-plugins
- `security-guidance@claude-plugins-official`
- `code-review@claude-plugins-official`
- `typescript-lsp@claude-plugins-official` — first `npm i -g typescript-language-server typescript`
- `pyright-lsp@claude-plugins-official` — first `npm i -g pyright`

STEP 7 — Anthropic example skills (webapp-testing, skill-creator) · https://github.com/anthropics/skills
Marketplace `anthropics/skills`, then plugin `example-skills@anthropic-agent-skills`.

STEP 8 — Chrome DevTools MCP (Google) · OPTIONAL · project scope · https://github.com/ChromeDevTools/chrome-devtools-mcp
`claude mcp add --scope project chrome-devtools -- npx chrome-devtools-mcp@latest --no-usage-statistics --no-performance-crux`

STEP 9 — Project hooks, subagent and skill (no downloads)
- `.claude/hooks/lint-changed.sh`: reads the hook JSON on stdin with `python3`, takes `tool_input.file_path`; runs `backend/.venv/bin/ruff check --fix <file>` for `.py` under `backend/`, `npx oxlint <file>` (from `frontend/`) for `.ts/.tsx`. Always exits 0 and prints problems, so it never blocks an edit. `chmod +x`.
- `.claude/settings.json`: a `PostToolUse` hook with matcher `Edit|Write|MultiEdit` that runs that script. Do NOT add a Stop hook that runs the full Playwright suite (too slow); instead add a slash command `.claude/commands/check-devices.md` that runs the Playwright suite and screenshots the changed screens at 360, 375, 430, 768, 1440 and 1920px wide.
- `.claude/agents/design-reviewer.md`: a read-only subagent that reviews UI diffs against the design rules in `docs/` and the Foundations doc's "Look and feel" and "What to avoid" (dark-first, #2F7BFF accent, blue→violet gradient for brand marks only, 1px borders, tabular figures, reserved win/loss/news colours, no glass/neon on working screens, WCAG 2.2 AA, 44px tap targets). It returns findings, never edits.
- `.claude/skills/trading-portal-tokens/SKILL.md`: a project skill holding the colour, type, spacing, radius and motion tokens (150/250/400–600ms, ease-out in, ease-in out). Pull the values from the existing front-end Tailwind/CSS tokens first; where the Foundations doc differs, list both and flag it — don't pick.

NOT NOW (list in the report only)
- Sentry + Sentry MCP — later, once the app has mates using it.
- shadcn MCP — only if `frontend/components.json` exists; check and report.
- dataviz skill — already in Jamie's account; nothing to install.

STEP 10 — VERIFY
- `claude mcp list` — every server above shows connected (note which need a restart).
- Start the app against `REPLAY_JOURNAL_DATA_DIR=/tmp/rj-setup` (see `Makefile`/`RUNBOOK.md`), then use the Playwright MCP to open the home page at 375px and 1440px and save the screenshots to `docs/claude-setup/`.
- Use Context7 to fetch one ECharts doc page (proves the key works).
- `fly status` via the flyctl MCP (read only).
- Make one deliberate lint error in a scratch copy of a file to prove the hook fires, then revert it.
- Commit on the branch: `chore: Claude Code tooling (MCP servers, hooks, design-reviewer, tokens skill)`.

STEP 11 — REPORT
Write `docs/claude-setup/SETUP-REPORT.md` with a table: tool · scope · status (OK / FAILED / NEEDS JAMIE / SKIPPED) · how to verify · notes. Then list any `/plugin …` lines Jamie must paste himself and anything that needs a restart of Claude Code. End with a three-line summary in chat.
