#!/bin/sh
# cron.sh install|remove: add or remove the hourly bird sync in root's crontab.
# The crontab lives on the read-only root filesystem, so this briefly
# remounts it read-write. A firmware update would undo it; run install again.

CRON=/etc/crontab/root
LINE="17 * * * * /bin/sh /mnt/us/extensions/birdscreen/bin/sync.sh"
EXT=/mnt/us/extensions/birdscreen

say() {
    # Print on the Kindle's screen (KUAL closes its menu while an action runs).
    if [ -x /mnt/us/koreader/fbink ]; then
        /mnt/us/koreader/fbink -qpm -y -6 "$1" >/dev/null 2>&1
    else
        eips 0 35 "$1" >/dev/null 2>&1
    fi
    echo "$(date '+%Y-%m-%d %H:%M') $1" >> "$EXT/sync.log"
}

restart_cron() {
    restart cron >/dev/null 2>&1 || /etc/init.d/cron restart >/dev/null 2>&1
}

case "$1" in
install)
    if grep -q birdscreen "$CRON" 2>/dev/null; then
        say "Bird screen: hourly sync already on"
    else
        mntroot rw
        echo "$LINE" >> "$CRON"
        mntroot ro
        restart_cron
        if grep -q birdscreen "$CRON"; then
            say "Bird screen: hourly sync on"
        else
            say "Bird screen: could not edit the crontab"
            exit 1
        fi
    fi
    # Sync right away rather than waiting for the hour.
    /bin/sh "$EXT/bin/sync.sh" &
    ;;
remove)
    mntroot rw
    sed -i '/birdscreen/d' "$CRON"
    mntroot ro
    restart_cron
    say "Bird screen: hourly sync off"
    ;;
*)
    echo "usage: $0 install|remove" >&2
    exit 2
    ;;
esac
