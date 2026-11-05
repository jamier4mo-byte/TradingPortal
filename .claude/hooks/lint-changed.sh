#!/usr/bin/env bash
# PostToolUse hook (Edit|Write|MultiEdit): lint the file Claude just changed.
#   backend/**/*.py  -> backend/.venv/bin/ruff check --fix <file>
#   *.ts / *.tsx     -> npx oxlint <file>   (run from frontend/)
# Never blocks an edit: always exits 0. Problems are printed and also handed back to
# Claude as additionalContext so it can fix them on its next step.
set -u
ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"

FILE="$(python3 -c 'import json,sys
try:
    d = json.load(sys.stdin)
except Exception:
    d = {}
print((d.get("tool_input") or {}).get("file_path") or "")' 2>/dev/null)"
[ -z "$FILE" ] && exit 0
case "$FILE" in /*) ;; *) FILE="$ROOT/$FILE" ;; esac
[ -f "$FILE" ] || exit 0
REL="${FILE#"$ROOT"/}"

OUT=""
case "$REL" in
  backend/*.py)
    RUFF="${RUFF_BIN:-$ROOT/backend/.venv/bin/ruff}"  # RUFF_BIN: override for testing
    if [ -x "$RUFF" ]; then
      OUT="$(cd "$ROOT/backend" && "$RUFF" check --fix "$FILE" 2>&1)" || true
      if echo "$OUT" | grep -qE '^All checks passed!?$'; then OUT=""
      elif echo "$OUT" | grep -qE '\(([0-9]+) fixed, 0 remaining\)'; then
        OUT="ruff --fix rewrote $REL (no problems left); re-read it before editing again."
      fi
    else
      OUT="lint-changed: $RUFF not found (run 'make setup-backend'); skipped ruff for $REL"
    fi
    ;;
  *.ts|*.tsx)
    if [ -d "$ROOT/frontend" ]; then
      OUT="$(cd "$ROOT/frontend" && npx --no-install oxlint "$FILE" 2>&1)" || true
      # oxlint prints a summary line even when clean
      echo "$OUT" | grep -qE 'Found 0 warnings and 0 errors' && OUT=""
      echo "$OUT" | grep -qiE 'could not determine executable|npm (ERR|error)' && \
        OUT="lint-changed: oxlint not installed (run 'make setup-frontend'); skipped $REL"
    fi
    ;;
  *) exit 0 ;;
esac

if [ -n "$OUT" ]; then
  printf 'lint-changed: %s\n%s\n' "$REL" "$OUT" >&2
  python3 -c 'import json,sys
print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse",
  "additionalContext": "Lint problems in " + sys.argv[1] + ":\n" + sys.argv[2][:4000]}}))' "$REL" "$OUT"
fi
exit 0
