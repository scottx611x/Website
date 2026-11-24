#!/bin/sh
# cycle.sh run|ensure|stop: change the sleep-screen bird while the Kindle sleeps.
#
# Each time the Kindle is about to suspend, set its hardware wake-up alarm
# (powerd's rtcWakeup) for INTERVAL seconds. When that alarm wakes it, draw a
# random bird from the pool straight onto the screen; powerd then suspends it
# again, which sets the next alarm. The screen stays off throughout, and e-ink
# holds the picture with no power. A wake from the power button comes before
# the alarm is due, so it is left alone and the reader comes back as usual.
#
#   run     the loop itself (started in the background by ensure)
#   ensure  start the loop unless it is already running (cron calls this)
#   stop    end the loop

US=${BIRDSCREEN_US:-/mnt/us}
EXT=$US/extensions/birdscreen
POOLDIR=$US/koreader/birdscreen
FBINK=$US/koreader/fbink
INTERVAL=${BIRDSCREEN_INTERVAL:-3600} # seconds between birds
PID=/tmp/birdscreen-cycle.pid
LIPC_PID=/tmp/birdscreen-cycle.lipc.pid
FIFO=/tmp/birdscreen-cycle.fifo
LOG=$EXT/sync.log

log() { echo "$(date '+%Y-%m-%d %H:%M') $*" >> "$LOG"; }

running() { [ -s "$PID" ] && kill -0 "$(cat "$PID")" 2>/dev/null; }

# A random bird from the pool, never the one already on screen ($1).
random_bird() {
    ls "$POOLDIR"/*.png 2>/dev/null |
        awk -v seed="$(date +%s)$$$2" -v last="$1" 'BEGIN { srand(seed) }
            $0 != last { b[++n] = $0 } END { if (n) print b[int(rand() * n) + 1]; else print last }'
}

case "$1" in
run)
    echo $$ > "$PID"
    rm -f "$FIFO"
    mkfifo "$FIFO" || exit 1
    lipc-wait-event -m com.lab126.powerd readyToSuspend,wakeupFromSuspend > "$FIFO" &
    echo $! > "$LIPC_PID"
    log "cycling on: a new bird every $((INTERVAL / 60)) min while asleep"
    due=0
    shown=""
    count=0
    while read -r event _rest; do
        case "$event" in
        readyToSuspend*)
            lipc-set-prop -i com.lab126.powerd rtcWakeup "$INTERVAL"
            due=$(( $(date +%s) + INTERVAL ))
            ;;
        wakeupFromSuspend*)
            # Our alarm, not the power button? (allow a minute of clock slop)
            if [ "$due" -gt 0 ] && [ "$(date +%s)" -ge $((due - 60)) ]; then
                count=$((count + 1))
                bird=$(random_bird "$shown" "$count")
                [ -n "$bird" ] && "$FBINK" -q -c -f -g file="$bird" >/dev/null 2>&1
                shown=$bird
                log "asleep: showing $(basename "$bird" .png)"
            fi
            due=0
            ;;
        esac
    done < "$FIFO"
    rm -f "$FIFO" "$PID" "$LIPC_PID"
    tail -n 200 "$LOG" > "$LOG.tmp" && mv -f "$LOG.tmp" "$LOG"
    ;;
ensure)
    running || /bin/sh "$0" run </dev/null >/dev/null 2>&1 &
    ;;
stop)
    # Ending the event listener closes the FIFO, so the loop exits on its own.
    [ -s "$LIPC_PID" ] && kill "$(cat "$LIPC_PID")" 2>/dev/null
    sleep 1
    running && kill "$(cat "$PID")" 2>/dev/null
    rm -f "$FIFO" "$PID" "$LIPC_PID"
    log "cycling off"
    ;;
*)
    echo "usage: $0 run|ensure|stop" >&2
    exit 2
    ;;
esac
