#!/bin/sh
# Ship Side Yard segments to the brain, RESUMABLY. On a flaky link a full
# transfer rarely fits in one window, so keep partial progress (--partial-dir)
# and resume/append it next time (--append-verify) instead of restarting from 0.
# --whole-file skips delta math (pointless on a tiny AAC over LAN) and
# --remove-source-files deletes only fully-verified files.
SPOOL=/var/spool/sideyard
mkdir -p "$SPOOL/ready"
# cap backlog so a long outage can't fill the SD: keep the newest ~4 days
# (11520 x 30 s, ~3 GB of the card's 25 GB free). It was ~8 h, and the
# Nov 24-27 2026 outage lost everything older than that.
ls -1t "$SPOOL/ready"/seg_*.aac 2>/dev/null | tail -n +11521 | xargs -r rm -f
# move only COMPLETED segments (never the in-progress one)
find "$SPOOL" -maxdepth 1 -name 'seg_*.aac' -mmin +0.6 -exec mv -t "$SPOOL/ready" {} + 2>/dev/null
# ship oldest first, resumable; longer timeout tolerates a slow blip
# birdpi.local needs mDNS, which sometimes fails to resolve; birdpi's eth0 is
# pinned to 10.0.0.207, so fall back to the address rather than skip a ship.
ship() {
  rsync -a --partial --partial-dir=.rsync-partial \
    --remove-source-files --timeout=90 \
    -e "ssh -i /home/scott/.ssh/sideyard_ship -o ConnectTimeout=10 -o BatchMode=yes -o ServerAliveInterval=5 -o ServerAliveCountMax=4 -o StrictHostKeyChecking=accept-new" \
    "$SPOOL/ready/" "scott@$1:/home/scott/sideyard/incoming/" 2>>/tmp/sideyard-ship.log
}
ship birdpi.local || ship 10.0.0.207
