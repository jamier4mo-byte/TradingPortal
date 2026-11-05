---
description: Run the Playwright smoke suite, then screenshot the changed screens at 360, 375, 430, 768, 1440 and 1920 px
argument-hint: "[screens, e.g. hub,journal,news,calendar — default: work out from the diff]"
allowed-tools: Bash(make *), Bash(cd *), Bash(npx playwright *), Bash(node *), Bash(git diff *), Bash(git status *), Bash(mkdir *), Bash(curl *), Read, Glob, Grep
---

Check the current changes at every screen size. Never use the real data folder (`~/TradingPortal/data`). The smoke suite makes its own throwaway folder, and the screenshot run below uses `/tmp/tp-check-devices`.

1. **Which screens changed.** If `$ARGUMENTS` names screens, use those. Otherwise read `git diff --name-only main...HEAD` plus `git status --short`, and map changed files under `frontend/src/pages/` and `frontend/src/components/` to the screens in `scripts/capture.mjs` (`ROUTES`). A change to `AppShell`, `Card` or `index.css` means every screen. If nothing in the front end changed, say so and stop after step 2.
2. **Smoke suite.** Run `make smoke`. It builds the front end, starts a throwaway backend and runs `frontend/e2e` at 1440 and 375 px. The suite covers health, the Hub, horizontal scroll, 44px targets and axe WCAG 2.2 AA. If Playwright's browser is missing, run `make smoke-browser` once and retry. Report pass/fail counts and the names of failing tests, and don't try to fix failures in this command.
3. **App for screenshots.** Run `TRADING_PORTAL_DATA_DIR=/tmp/tp-check-devices make run PORT=8768` in the background and wait for `curl -s http://127.0.0.1:8768/api/health`.
4. **Screenshots.** From `frontend/`, run `BASE=http://127.0.0.1:8768 OUT=../docs/check-devices/$(date +%Y-%m-%d) SCREENS=<screens> node ../scripts/capture.mjs`. It defaults to 360, 375, 430, 768, 1440 and 1920 px wide.
5. **Look at every screenshot.** For each width, list anything that breaks:
   - horizontal scroll
   - clipped or overlapping text
   - tap targets under 44px
   - unreadable contrast
   - tables that should be cards on a phone
   - wide screens that stretch cards instead of using the space

   Then stop the server.
6. **Report** a table of screen × width → OK or the problem (one line each), plus the smoke-suite result and the screenshot folder. Don't commit the screenshots unless asked.
