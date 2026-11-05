# Planning docs

These are exported on 5 Nov 2026 from the living Claude Docs. The live versions are still the source of truth for comments and edits:

- [Trading Portal Foundations](https://claude.ai/artifact/1mZQfVkYcQWed5hfR6ZbZw) → `trading-portal-foundations.md`
- [Trading Portal Foundations: Review & Build Kit](https://claude.ai/artifact/2EusRPBxcDE2wy4WyUYGtr) → `trading-portal-review-and-build-kit.md`
- `claude-tooling-masterprompt.md`: the original Claude Code tooling prompt. It's historical; that tooling is now built into this repo.

Export notes:

- The four brand images are dropped from the Foundations export. They are in `frontend/public/brand/` (`tradingportal-logo.png`, `t-tile.png`, `replayjournal-logo.png`, `newsroom-logo.png`).
- The "Build order · 6 phases, 5 gates" diagram in the Review & Build Kit is an embed. It only shows in the live doc.

**Heads-up:** the Review & Build Kit was written when the plan was to reuse the old Replay Journal code. Its "Decisions" row ("Moved into Desktop/Trading Portal; new look, same code base") and top action 1 ("re-skin the existing repo") are superseded. This repo is a fresh start, so the importer, analytics, auth and export it calls "already built" need building here.
