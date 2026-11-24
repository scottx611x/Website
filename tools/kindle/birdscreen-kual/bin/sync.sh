#!/bin/sh
# Bird screen sync, run hourly by cron (and from KUAL > Bird screen > Sync now).
#
# Keeps the latest POOL starred birds from scott-ouellette.com on the Kindle,
# whatever reader is open:
#   /mnt/us/koreader/birdscreen/<key>.png     KOReader's sleep screen folder
#   /mnt/us/linkss/screensavers/bird-NN.png   Amazon's (ScreenSavers hack)
# Only birds it lacks are downloaded; birds that left the pool are dropped.
# With no Wi-Fi it does nothing. Logs to sync.log beside this folder.

SITE="https://www.scott-ouellette.com/birds"
US=${BIRDSCREEN_US:-/mnt/us} # overridable for testing off-device
EXT=$US/extensions/birdscreen
KO=$US/koreader/birdscreen
LINKSS=$US/linkss/screensavers
POOL=60 # matches kindle.POOL on the site
LOG="$EXT/sync.log"
KEYS="$EXT/keys.txt"
LOCK=/tmp/birdscreen.lock
[ "$1" = manual ] && MANUAL=1

# /mnt/us is gone while the Kindle is mounted over USB.
[ -d "$EXT" ] || exit 0
mkdir "$LOCK" 2>/dev/null || exit 0
trap 'rmdir "$LOCK"' EXIT INT TERM

log() {
    echo "$(date '+%Y-%m-%d %H:%M') $*" >> "$LOG"
    # From KUAL's "Sync now", also show it on screen.
    [ "$MANUAL" = 1 ] && [ -x "$US/koreader/fbink" ] && "$US/koreader/fbink" -qpm -y -6 "Bird screen: $*" >/dev/null 2>&1
}

# The firmware's CA list is old; KOReader ships a current one.
CA=""
[ -s "$US/koreader/data/ca-bundle.crt" ] && CA="--cacert $US/koreader/data/ca-bundle.crt"

# fetch URL DEST: download via a .part file so a half-written PNG never shows.
fetch() {
    if curl -fsSL --connect-timeout 15 --max-time 90 $CA -o "$2.part" "$1" && [ -s "$2.part" ]; then
        mv -f "$2.part" "$2"
        return 0
    fi
    rm -f "$2.part"
    return 1
}

if ! fetch "$SITE/kindle.json" "$EXT/pool.json"; then
    log "offline or site unreachable; nothing changed"
    exit 0
fi
# {"frames": ["123-0", "456-1", ...]} -> one key per line, newest first.
tr -c '0-9-' '\n' < "$EXT/pool.json" | grep -E '^[0-9]+-[0-9]+$' > "$KEYS.new"
n=$(wc -l < "$KEYS.new" | tr -d ' ')
if [ "$n" -eq 0 ]; then
    log "empty bird list; nothing changed"
    rm -f "$KEYS.new"
    exit 0
fi
mv -f "$KEYS.new" "$KEYS"

mkdir -p "$KO"
new=0
failed=0
while read -r key; do
    [ -s "$KO/$key.png" ] && continue
    if fetch "$SITE/kindle.png?frame=$key" "$KO/$key.png"; then
        new=$((new + 1))
    else
        failed=$((failed + 1))
    fi
done < "$KEYS"

dropped=0
for f in "$KO"/*.png; do
    [ -e "$f" ] || continue
    if ! grep -qx "$(basename "$f" .png)" "$KEYS"; then
        rm -f "$f"
        dropped=$((dropped + 1))
    fi
done

# Amazon's folder: fixed names bird-00..bird-59 filled in pool order (wrapping
# when there are fewer stars), rewriting only slots whose bird changed.
changed=0
if [ -d "$LINKSS" ]; then
    slot=0
    while [ "$slot" -lt "$POOL" ]; do
        key=$(sed -n "$((slot % n + 1))p" "$KEYS")
        src="$KO/$key.png"
        dest=$(printf '%s/bird-%02d.png' "$LINKSS" "$slot")
        if [ -s "$src" ] && ! cmp -s "$src" "$dest"; then
            cp -f "$src" "$dest.part" && mv -f "$dest.part" "$dest" && changed=$((changed + 1))
        fi
        slot=$((slot + 1))
    done
fi

log "$n birds: $new new, $dropped dropped, $failed failed, $changed Amazon slots updated"

# Keep the log short.
tail -n 200 "$LOG" > "$LOG.tmp" && mv -f "$LOG.tmp" "$LOG"
exit 0
