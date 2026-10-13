#!/usr/bin/env bash
# Overnight sweep: export a MONTH at a time from Lightroom's date sidebar,
# collect what matches, delete the rest, move on.
#
# A month row scopes the grid to the whole month ("April 2026 — 563 items"), so
# one click covers what would otherwise be ~20 day clicks. Select All is safe
# because the grid is scoped; unscoped it grabs all 5,534 and Lightroom raises
# modals that stack silently.
#
# Collect-and-clean runs between months on purpose: a month is 300-650 photos
# (~3-7 GB) and the disk would not survive the whole library at once.
#
#   tools/lr_overnight.sh 554 498 526 470 ...     # month row y coordinates
set -u
cd /Users/scott/Website

# Where Lightroom is exporting. Desktop is the most TCC-contested folder on
# macOS and this process lost read access to it twice mid-run, which strands
# the exports; Documents has stayed readable.
BIRBS="${BIRBS_DIR:-$HOME/Documents/birbs}"
export BIRBS_DIR="$BIRBS"

SIDEBAR_X=142
LOG=/tmp/overnight.log

confirm_dialogs() {
  local d x y
  for name in "AI Update Required" "Choose Export Location" "Export Results" "Updating AI Settings"; do
    d=$(osascript -e "tell application \"System Events\" to tell process \"Adobe Lightroom\" to get position of window \"$name\"" 2>/dev/null)
    [ -z "$d" ] && continue
    x=$(echo "$d" | cut -d, -f1 | tr -d ' '); y=$(echo "$d" | cut -d, -f2 | tr -d ' ')
    if [ "$name" = "AI Update Required" ]; then
      # UNCHECK "Update affected photos" first. Left checked, confirming kicks
      # off an "Updating AI Settings" pass that wedges (CPU drops to nothing and
      # the count never advances) and blocks the export behind it -- that is how
      # five months in a row exported 0 files. The dialog explicitly offers
      # "continue to export with current settings", which is what we want: we
      # are archiving the edit as it was posted, not re-rendering it.
      cliclick c:$((x+46)),$((y+193)) >/dev/null 2>&1
      sleep 1
      cliclick c:$((x+405)),$((y+321)) >/dev/null 2>&1
    elif [ "$name" = "Choose Export Location" ]; then
      cliclick c:$((x+743)),$((y+417)) >/dev/null 2>&1
    else
      # "Export Results" (a failure report) and a wedged "Updating AI Settings"
      # are MODAL: until dismissed every later month silently re-exports
      # whatever was already selected. That is how September, July, 2025 and
      # August each reported June's exact 318 files. Dismiss via the
      # bottom-right button (OK / Stop), measured from the window's own frame.
      sz=$(osascript -e "tell application \"System Events\" to tell process \"Adobe Lightroom\" to get size of window \"$name\"" 2>/dev/null)
      w=$(echo "$sz" | cut -d, -f1 | tr -d ' '); h=$(echo "$sz" | cut -d, -f2 | tr -d ' ')
      [ -n "$w" ] && cliclick c:$((x + w - 80)),$((y + h - 40)) >/dev/null 2>&1
    fi
    echo "    confirmed: $name" >> "$LOG"
  done
}

for Y in "$@"; do
  echo "=== month row y=$Y  $(date '+%H:%M') ===" >> "$LOG"
  ls "$BIRBS" > /tmp/ov_before.txt 2>/dev/null || { echo "  birbs unreadable" >> "$LOG"; exit 1; }
  before=$(wc -l < /tmp/ov_before.txt | tr -d ' ')

  osascript -e 'tell application "Adobe Lightroom" to activate' >/dev/null 2>&1
  sleep 1
  cliclick c:$SIDEBAR_X,$Y >/dev/null 2>&1
  sleep 4
  osascript -e 'tell application "System Events" to tell process "Adobe Lightroom" to click menu item "Select All" of menu 1 of menu bar item "Edit" of menu bar 1' >/dev/null 2>&1
  sleep 2
  osascript -e 'tell application "System Events" to tell process "Adobe Lightroom" to click menu item "Export with Previous..." of menu 1 of menu bar item "File" of menu bar 1' >/dev/null 2>&1

  # a month can take a long time; wait until the folder stops growing
  stable=0; last=$before
  for i in $(seq 1 540); do          # up to 90 min per month
    sleep 10
    confirm_dialogs
    now=$(ls "$BIRBS" 2>/dev/null | wc -l | tr -d ' ')
    if [ "$now" = "$last" ]; then stable=$((stable+1)); else stable=0; fi
    last=$now
    [ "$stable" -ge 6 ] && [ "$now" -gt "$before" ] && break
    [ "$stable" -ge 12 ] && break
  done
  echo "  exported $((last - before)) files" >> "$LOG"

  BIRDS_USE_S3=1 .venv/bin/python tools/collect_exports.py --since /tmp/ov_before.txt \
    2>/dev/null | grep -E '^\s+(\+|archived|unmatched)' >> "$LOG"

  # delete whatever did not match: never-posted shots, reproducible on demand
  comm -13 <(sort /tmp/ov_before.txt) <(ls "$BIRBS" | sort) > /tmp/ov_left.txt
  .venv/bin/python - <<'PY' >> "$LOG" 2>&1
import os
n=sz=0
for name in open("/tmp/ov_left.txt"):
    p = os.path.join(os.environ["BIRBS_DIR"], name.strip())
    if os.path.exists(p):
        sz += os.path.getsize(p); os.remove(p); n += 1
print("  cleaned %d leftovers, %.2f GB" % (n, sz/1e9))
PY
  echo "  free: $(df -h ~ | tail -1 | awk '{print $4}')" >> "$LOG"
done
echo "=== sweep complete $(date '+%H:%M') ===" >> "$LOG"
