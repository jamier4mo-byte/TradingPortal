#!/usr/bin/env bash
# One-off: install the Mac-side Claude Code tooling for the Trading Portal repo.
# Run from the repo root on your Mac:   bash scripts/claude-setup.sh
# - Uses NO keys or tokens. Context7 and GitHub are added by you separately (see the report).
# - Never touches ~/ReplayJournal/data.
# - Each step is tried twice; failures are logged and the script carries on.
# Output goes to docs/claude-setup/setup-run.log (git-ignored) so Claude can read it back.
set -u
cd "$(dirname "$0")/.."
LOG="docs/claude-setup/setup-run.log"
mkdir -p docs/claude-setup
: > "$LOG"
say() { printf '%s\n' "$*" | tee -a "$LOG"; }
run() {  # run "label" cmd...  (retry once)
  local label="$1"; shift
  say ""; say "### $label"; say "\$ $*"
  if "$@" >>"$LOG" 2>&1; then say "→ OK"; return 0; fi
  say "→ failed, retrying once"; sleep 2
  if "$@" >>"$LOG" 2>&1; then say "→ OK (2nd try)"; return 0; fi
  say "→ FAILED: $label"; return 1
}

say "Claude tooling setup — $(date)"; say "repo: $(pwd)  branch: $(git branch --show-current)"

say ""; say "## STEP 0 — preflight"
for c in "claude --version" "node --version" "npm --version" "python3 --version" "git --version"; do
  say "\$ $c"; $c >>"$LOG" 2>&1 || say "→ missing: $c"
done
if ! command -v fly >/dev/null 2>&1; then run "install flyctl" brew install flyctl; fi
run "fly version" fly version
say "\$ fly auth whoami"; fly auth whoami >>"$LOG" 2>&1 || say "→ not signed in to Fly: run 'fly auth login' yourself, then re-run this script"
if claude plugin --help >/dev/null 2>&1; then PLUGIN_CLI=1; say "claude plugin CLI: available"; else PLUGIN_CLI=0; say "claude plugin CLI: NOT available — use the /plugin lines in SETUP-REPORT.md"; fi
run "claude mcp list (before)" claude mcp list

say ""; say "## Project setup (venv + node_modules)"
[ -x backend/.venv/bin/ruff ] || run "make setup-backend" make setup-backend
[ -d frontend/node_modules ] || run "make setup-frontend" make setup-frontend

say ""; say "## STEP 6 prerequisites — language servers"
run "npm i -g typescript-language-server typescript" npm i -g typescript-language-server typescript
run "npm i -g pyright" npm i -g pyright

if [ "$PLUGIN_CLI" = 1 ]; then
  say ""; say "## STEPS 6–7 — plugins"
  claude plugin marketplace list 2>/dev/null | grep -q claude-plugins-official || \
    run "marketplace: claude-plugins-official" claude plugin marketplace add anthropics/claude-plugins-official
  for p in security-guidance code-review typescript-lsp pyright-lsp; do
    run "plugin: $p" claude plugin install "$p@claude-plugins-official"
  done
  claude plugin marketplace list 2>/dev/null | grep -q anthropic-agent-skills || \
    run "marketplace: anthropics/skills" claude plugin marketplace add anthropics/skills
  run "plugin: example-skills" claude plugin install example-skills@anthropic-agent-skills
  run "claude plugin list" claude plugin list
fi

say ""; say "## STEP 10 — checks"
run "claude mcp list (after)" claude mcp list
run "make test" make test
run "make lint" make lint
say "\$ fly apps list (read only; the trading-portal app is not created yet)"; fly apps list >>"$LOG" 2>&1 || say "→ fly apps list failed (sign in with 'fly auth login')"
say ""; say "Done. Tell Claude: 'setup script finished'."
