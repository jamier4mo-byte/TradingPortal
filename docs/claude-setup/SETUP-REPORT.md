# Claude Code tooling: setup report

Fresh Trading Portal repo, first commit on `main`, 5 Nov 2026. Remote `origin` = https://github.com/jamier4mo-byte/TradingPortal.git, **not pushed**.

**How it was built.** The tooling and skeleton were built and tested in a cloud sandbox, then copied into `~/Desktop/Trading Portal`. That sandbox can't run your Mac's `claude`, `fly` or `brew`. Everything Mac-side is therefore in **`scripts/claude-setup.sh`**: it needs no keys and logs to `docs/claude-setup/setup-run.log`, which is git-ignored. Plugins and user-scope servers are per Mac, not per repo, so they need installing once whichever repo you use.

## Status

| Tool | Scope | Status | How to verify | Notes |
|---|---|---|---|---|
| Playwright MCP (Microsoft) | project (`.mcp.json`) | OK | `claude mcp list` shows `playwright`; approve it on first use | Drove `@playwright/mcp@latest` to screenshot the Hub: `home-375.png`, `home-1440.png` here. |
| Chrome DevTools MCP (Google) | project (`.mcp.json`) | OK (config) | `claude mcp list` shows `chrome-devtools` | Optional; flags `--no-usage-statistics --no-performance-crux`. Needs Chrome. |
| flyctl MCP (Fly.io) | project (`.mcp.json`, `fly mcp server`, stdio) | NEEDS JAMIE | `fly auth login`, then in Claude Code: "use flyctl to list my apps" | Experimental. Uses your `fly auth` sign-in, with no token on the command line and no port binding. The Fly app isn't created yet (see `fly.toml`). |
| Context7 MCP (Upstash) | user | NEEDS JAMIE | `claude mcp list` → `context7: connected`, then "use context7 to fetch the ECharts series-line docs" | Needs your key (command below). The sandbox can't reach mcp.context7.com, so the ECharts test is yours. |
| GitHub MCP server (GitHub) | user | NEEDS JAMIE | `claude mcp list` → `github: connected`, then "show the TradingPortal repo's branches" | Fine-grained token for **`jamier4mo-byte/TradingPortal`**, not Replay-Journal. Not the archived `@modelcontextprotocol/server-github`. |
| frontend-design skill (Anthropic) | project (`.claude/skills/frontend-design/`) | OK | `/skills` | Byte-identical to upstream `main` on 5 Nov 2026, so no plugin is needed. |
| security-guidance, code-review, typescript-lsp, pyright-lsp | user plugins | NEEDS JAMIE | `claude plugin list` | `scripts/claude-setup.sh` installs them, or paste the `/plugin` lines below. The LSPs need `npm i -g typescript-language-server typescript pyright`, which the script runs. |
| example-skills (webapp-testing, skill-creator, …) | user plugin (`anthropics/skills` → `anthropic-agent-skills`) | NEEDS JAMIE | `/skills` lists `webapp-testing` | Also brings a second copy of frontend-design. |
| Lint hook (`.claude/hooks/lint-changed.sh`, `PostToolUse` in `.claude/settings.json`) | project | OK | Edit a `.py` or `.tsx` file in Claude Code | Proven here with real ruff and oxlint. A deliberate F821 and a `debugger` statement were reported back to Claude; clean files printed nothing; it always exits 0; the scratch files were removed. |
| `/check-devices` | project | OK | Run `/check-devices` | `make smoke`, then `scripts/capture.mjs` at 360, 375, 430, 768, 1440 and 1920px on a `/tmp` data folder. There's no Stop hook, by design. |
| `design-reviewer` subagent | project | OK | `/agents` | Read-only. Checks Foundations "Look and feel" and "What to avoid", the tokens skill, AA contrast and 44px targets. |
| `trading-portal-tokens` skill | project | OK | `/skills` | Built from the Foundations doc. Values the doc didn't give (win/loss/impact hexes) are marked **proposed**. One open question: button text colour on blue (see below). |
| Smoke suite (`frontend/e2e`) | repo | OK | `make smoke` | 10/10 pass at 1440px and 375px: health, Hub render, no horizontal scroll, 44px targets, axe WCAG 2.2 AA. It caught two 42px/36px phone buttons, which are now fixed. |
| Backend | repo | OK | `make test`, `make lint` | 2 pytest tests pass; ruff is clean; Alembic baseline `0001` applies. |

## Not now
- **Sentry + Sentry MCP:** later, once mates are using it.
- **shadcn MCP:** the repo has no `frontend/components.json`. If you want shadcn components, run `npx shadcn@latest init` first, then add the MCP.
- **dataviz skill:** already in your Claude account.

## Decisions for you
1. **Button text on `#2F7BFF`.** White text there is 3.9:1, which fails WCAG AA, so the skeleton uses dark ink (`#0B0F1A`, 4.9:1). The alternative is a darker button blue so that white passes.
2. **Proposed colours.** Win `#2FD27F`, loss `#FF5A66`, breakeven `#8F99AD`, and impact orange `#FF9F43` / yellow `#F5D547`.
3. **Fly app name** `trading-portal-jamie` in London (`lhr`). Change it in `fly.toml` before `fly apps create` if you want another.

## What you need to do (once)
1. `fly auth login` if `fly auth whoami` fails.
2. From the repo: `bash scripts/claude-setup.sh`. It runs `make setup`, the plugin installs, `make test`, `make lint` and a read-only `fly apps list`. Then tell Claude "setup script finished".
3. Create the keys. Never paste them into chat.
   - Context7 key (free): https://context7.com/dashboard
   - Fine-grained GitHub token, **only** `jamier4mo-byte/TradingPortal`, with Contents, Issues, Pull requests and Actions read/write: https://github.com/settings/personal-access-tokens/new
4. In a separate Terminal tab, replace `YOUR_KEY` and run:
   ```
   claude mcp add --scope user --transport http context7 https://mcp.context7.com/mcp --header "Authorization: Bearer YOUR_KEY"
   claude mcp add --scope user --transport http github https://api.githubcopilot.com/mcp --header "Authorization: Bearer YOUR_KEY"
   ```
5. When you're happy, push the first commit: `git push -u origin main`. CI runs, but deploys are skipped until the `FLY_API_TOKEN` secret exists.
6. Restart Claude Code in the repo (`claude`), approve the three project MCP servers, and check that `claude mcp list` shows all five connected.

### `/plugin` lines (only if the script says there's no `claude plugin` CLI)
```
/plugin marketplace add anthropics/claude-plugins-official
/plugin install security-guidance@claude-plugins-official
/plugin install code-review@claude-plugins-official
/plugin install typescript-lsp@claude-plugins-official
/plugin install pyright-lsp@claude-plugins-official
/plugin marketplace add anthropics/skills
/plugin install example-skills@anthropic-agent-skills
```

### Needs a Claude Code restart
- `.mcp.json`
- the context7 and github servers
- all plugins
- `.claude/settings.json` (the hook)
- the agent, command and skills
