#!/bin/sh
# Bird screen sync, run hourly by cron (and from KUAL > Bird screen > Sync now).
#
# Keeps the latest starred birds (the site picks how many) from scott-ouellette.com on the Kindle,
# whatever reader is open:
#   /mnt/us/koreader/birdscreen/<key>.png     KOReader's sleep screen folder
#   /mnt/us/linkss/screensavers/              Amazon's (ScreenSavers hack)
# Only birds it lacks are downloaded; birds that left the pool are dropped.
# With no Wi-Fi it does nothing. Logs to sync.log beside this folder.

SITE="https://www.scott-ouellette.com/birds"
US=${BIRDSCREEN_US:-/mnt/us} # overridable for testing off-device
EXT=$US/extensions/birdscreen
KO=$US/koreader/birdscreen
LINKSS=$US/linkss/screensavers
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
# On failure FETCH_ERR says why (curl's exit code and message).
fetch() {
    if command -v curl >/dev/null 2>&1; then
        FETCH_ERR=$(curl -fsSL --connect-timeout 15 --max-time 90 $CA -o "$2.part" "$1" 2>&1)
        rc=$?
    else
        FETCH_ERR=$(wget -q -T 60 -O "$2.part" "$1" 2>&1)
        rc=$?
        FETCH_ERR="no curl; wget: $FETCH_ERR"
    fi
    if [ "$rc" -eq 0 ] && [ -s "$2.part" ]; then
        mv -f "$2.part" "$2"
        return 0
    fi
    FETCH_ERR="exit $rc: $(echo "$FETCH_ERR" | head -n 1)"
    rm -f "$2.part"
    return 1
}

if ! fetch "$SITE/kindle.json" "$EXT/pool.json"; then
    wifi=$(lipc-get-prop com.lab126.wifid cmState 2>/dev/null)
    log "could not get the bird list (Wi-Fi: ${wifi:-unknown}; $FETCH_ERR); nothing changed"
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

# Amazon's folder holds exactly the pool. The ScreenSavers hack renames its
# images (bg_ssNN) whenever it shuffles them, so birds are matched by content,
# not name: anything that is not a pool bird (its stock images, birds that
# left the pool) goes, and missing birds are copied in.
changed=0
if [ -d "$LINKSS" ]; then
    : > "$EXT/pool.md5"
    while read -r key; do
        [ -s "$KO/$key.png" ] && echo "$(md5sum "$KO/$key.png" | cut -d' ' -f1) $key" >> "$EXT/pool.md5"
    done < "$KEYS"
    : > "$EXT/have.md5"
    for f in "$LINKSS"/*; do
        [ -f "$f" ] || continue
        sum=$(md5sum "$f" | cut -d' ' -f1)
        if grep -q "^$sum " "$EXT/pool.md5" && ! grep -qx "$sum" "$EXT/have.md5"; then
            echo "$sum" >> "$EXT/have.md5"
        else
            rm -f "$f"
            changed=$((changed + 1))
        fi
    done
    while read -r sum key; do
        grep -qx "$sum" "$EXT/have.md5" && continue
        cp -f "$KO/$key.png" "$LINKSS/bird-$key.png.part" && mv -f "$LINKSS/bird-$key.png.part" "$LINKSS/bird-$key.png" && changed=$((changed + 1))
    done < "$EXT/pool.md5"
    rm -f "$EXT/have.md5"
fi

log "$n birds: $new new, $dropped dropped, $failed failed, $changed Amazon files changed"
[ "$failed" -gt 0 ] && log "last download failure: $FETCH_ERR"

# Keep the log short.
tail -n 200 "$LOG" > "$LOG.tmp" && mv -f "$LOG.tmp" "$LOG"
exit 0
