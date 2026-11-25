#!/bin/sh
# toggle.sh sync|cycle|menu: flip one Bird screen feature and relabel the KUAL menu.
#
#   sync   hourly cron job that keeps the birds current (bin/sync.sh)
#   cycle  show a different bird every hour while the Kindle sleeps (bin/cycle.sh)
#   menu   just rewrite menu.json to match the current state
#
# Both live in root's crontab, on the read-only root filesystem, so this
# briefly remounts it read-write. A firmware update would undo them; toggle
# them on again.

US=${BIRDSCREEN_US:-/mnt/us}
EXT=$US/extensions/birdscreen
CRON=${BIRDSCREEN_CRON:-/etc/crontab/root}
SYNC_LINE="17 * * * * /bin/sh $EXT/bin/sync.sh # birdscreen-sync"
# The cycler is a background process; cron restarts it after a reboot.
CYCLE_LINE="*/5 * * * * /bin/sh $EXT/bin/cycle.sh ensure # birdscreen-cycle"

say() {
    if [ -x "$US/koreader/fbink" ]; then
        "$US/koreader/fbink" -qpm -y -6 "$1" >/dev/null 2>&1
    else
        eips 0 35 "$1" >/dev/null 2>&1
    fi
    echo "$(date '+%Y-%m-%d %H:%M') $1" >> "$EXT/sync.log"
}

is_on() { grep -q "birdscreen-$1" "$CRON" 2>/dev/null; }

edit_cron() { # edit_cron add LINE | edit_cron del TAG
    command -v mntroot >/dev/null && mntroot rw
    if [ "$1" = add ]; then echo "$2" >> "$CRON"; else sed -i "/birdscreen-$2/d" "$CRON"; fi
    command -v mntroot >/dev/null && mntroot ro
    restart cron >/dev/null 2>&1 || /etc/init.d/cron restart >/dev/null 2>&1
}

write_menu() {
    if is_on sync; then sync_label="Hourly sync: ON (tap to turn off)"; else sync_label="Hourly sync: OFF (tap to turn on)"; fi
    if is_on cycle; then cycle_label="Change bird while asleep: ON (tap to turn off)"; else cycle_label="Change bird while asleep: OFF (tap to turn on)"; fi
    cat > "$EXT/menu.json.tmp" <<EOF
{
    "items": [
        {
            "name": "Bird screen",
            "priority": 0,
            "items": [
                {"name": "Bird mode", "priority": 0, "action": "/bin/sh", "params": "$EXT/bin/birdmode.sh", "status": false},
                {"name": "$sync_label", "priority": 1, "action": "/bin/sh", "params": "$EXT/bin/toggle.sh sync", "exitmenu": false, "refresh": true},
                {"name": "$cycle_label", "priority": 2, "action": "/bin/sh", "params": "$EXT/bin/toggle.sh cycle", "exitmenu": false, "refresh": true},
                {"name": "Sync now", "priority": 3, "action": "/bin/sh", "params": "$EXT/bin/sync.sh manual", "exitmenu": false}
            ]
        }
    ]
}
EOF
    mv -f "$EXT/menu.json.tmp" "$EXT/menu.json"
}

case "$1" in
sync)
    if is_on sync; then
        edit_cron del sync
        say "Bird screen: hourly sync OFF"
    else
        edit_cron add "$SYNC_LINE"
        if is_on sync; then
            say "Bird screen: hourly sync ON"
            /bin/sh "$EXT/bin/sync.sh" manual & # first sync now, not in an hour
        else
            say "Bird screen: could not edit the crontab"
        fi
    fi
    ;;
cycle)
    if is_on cycle; then
        edit_cron del cycle
        /bin/sh "$EXT/bin/cycle.sh" stop
        say "Bird screen: change bird while asleep OFF"
    else
        edit_cron add "$CYCLE_LINE"
        if is_on cycle; then
            /bin/sh "$EXT/bin/cycle.sh" ensure
            say "Bird screen: change bird while asleep ON (hourly)"
        else
            say "Bird screen: could not edit the crontab"
        fi
    fi
    ;;
menu) ;;
*)
    echo "usage: $0 sync|cycle|menu" >&2
    exit 2
    ;;
esac
write_menu
