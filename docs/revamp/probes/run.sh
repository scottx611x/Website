#!/usr/bin/env bash
# Headless probe runner.
#
# Every visual/behavioural check in this revamp goes through here rather than a
# browser window — a standing constraint from the session this came out of: do
# NOT open a browser tab, someone else is using the machine.
#
#   docs/revamp/probes/run.sh sweep2          # one probe
#   docs/revamp/probes/run.sh                 # list them
#
# The probes need playwright-core and a chromium; both are installed on demand
# into a directory OUTSIDE the repo so nothing here gets committed by accident.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME="${PROBE_RUNTIME:-$HOME/.cache/birds-probes}"
SERVER="${PROBE_SERVER:-http://127.0.0.1:5055}"

if [ $# -eq 0 ]; then
  echo "probes:"
  for f in "$HERE"/*.js; do echo "  $(basename "$f" .js)"; done
  echo
  echo "server expected at $SERVER  (make run)"
  exit 0
fi

mkdir -p "$RUNTIME"
if [ ! -d "$RUNTIME/node_modules/playwright-core" ]; then
  echo "· installing playwright-core into $RUNTIME"
  (cd "$RUNTIME" && npm i playwright-core@1.56.0 pngjs --silent)
fi

# The probes resolve modules from $SP/node_modules and chromium from the
# playwright cache; a plain `npx playwright install` also works if it is absent.
SHELL_DIR="$HOME/Library/Caches/ms-playwright"
if ! ls "$SHELL_DIR"/chromium_headless_shell-*/chrome-headless-shell-*/chrome-headless-shell >/dev/null 2>&1; then
  echo "· no chrome-headless-shell found in $SHELL_DIR"
  echo "  run:  cd $RUNTIME && npx playwright install chromium"
  exit 1
fi

if ! curl -fsS -o /dev/null --max-time 5 "$SERVER/birds" 2>/dev/null; then
  echo "· $SERVER is not answering — start it with 'make run' first"
  exit 1
fi

name="$1"; shift
SP="$RUNTIME" node "$HERE/$name.js" "$@"
