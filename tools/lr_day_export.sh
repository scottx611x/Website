#!/usr/bin/env bash
# Export a set of shoot days from Lightroom's DATE SIDEBAR.
#
# The sidebar (left panel, Cloud > year > month > day) is the thing that makes
# this tractable: clicking a day scopes the whole grid to it, so Edit > Select
# All is bounded to that day instead of grabbing all 5,534 photos — which is
# what used to summon a stack of "AI Update Required" modals.
#
# Rows are a constant 28 logical px apart. Pass "y" coordinates measured from a
# screenshot of the sidebar; the exported FILENAMES verify afterwards which day
# was really hit, because the catalog maps every filename to its capture date.
#
#   tools/lr_day_export.sh 208 432 628
set -u

SIDEBAR_X=142
# Two dialogs can interrupt an export; both are confirmations, not errors, so
# both get "Export" rather than "Cancel".
#
#   AI Update Required    - some photos need AI settings refreshed first
#   Choose Export Location - "Export with Previous" forgot its destination.
#     This happens when the remembered folder becomes unreadable (TCC took
#     ~/Desktop away mid-session once). The picker already points at birbs, so
#     confirming it both exports AND re-establishes the destination.
#
# Left unhandled these silently STACK and every later day exports nothing.
dialog_guard() {
  local d x y
  d=$(osascript -e 'tell application "System Events" to tell process "Adobe Lightroom" to get position of window "AI Update Required"' 2>/dev/null)
  if [ -n "$d" ]; then
    x=$(echo "$d" | cut -d, -f1 | tr -d ' '); y=$(echo "$d" | cut -d, -f2 | tr -d ' ')
    cliclick c:$((x+405)),$((y+321)) >/dev/null 2>&1
    echo "    (AI dialog -> Export)"
  fi
  d=$(osascript -e 'tell application "System Events" to tell process "Adobe Lightroom" to get position of window "Choose Export Location"' 2>/dev/null)
  if [ -n "$d" ]; then
    x=$(echo "$d" | cut -d, -f1 | tr -d ' '); y=$(echo "$d" | cut -d, -f2 | tr -d ' ')
    cliclick c:$((x+743)),$((y+417)) >/dev/null 2>&1
    echo "    (location dialog -> Export)"
  fi
}

for Y in "$@"; do
  echo "  --- row at y=$Y ---"
  osascript -e 'tell application "Adobe Lightroom" to activate' >/dev/null 2>&1
  sleep 1
  cliclick c:$SIDEBAR_X,$Y >/dev/null 2>&1
  sleep 3
  osascript -e 'tell application "System Events" to tell process "Adobe Lightroom" to click menu item "Select All" of menu 1 of menu bar item "Edit" of menu bar 1' >/dev/null 2>&1
  sleep 1.5
  before=$(ls ~/Desktop/birbs | wc -l | tr -d ' ')
  osascript -e 'tell application "System Events" to tell process "Adobe Lightroom" to click menu item "Export with Previous..." of menu 1 of menu bar item "File" of menu bar 1' >/dev/null 2>&1

  # wait for the export to finish: the folder stops growing for 3 checks running
  stable=0; last=$before
  for i in $(seq 1 90); do
    sleep 10
    dialog_guard
    now=$(ls ~/Desktop/birbs | wc -l | tr -d ' ')
    if [ "$now" = "$last" ]; then stable=$((stable+1)); else stable=0; fi
    last=$now
    [ "$stable" -ge 3 ] && [ "$now" -gt "$before" ] && break
    [ "$stable" -ge 6 ] && break          # nothing ever arrived; move on
  done
  echo "    exported $((last - before)) files"
done
