#!/bin/bash
# Side Yard Zero: bring the network back by itself.
#
# Nov 24-27 2026 the Zero kept recording but its USB Ethernet adapter
# (ASIX AX88179B on the hub's port 1-1.2) dropped off the network, and nothing
# tried to recover it; it sat offline for three days until a hand power-cycle.
# Run every minute; each failed check escalates:
#   3 min  bounce eth0 and ask NetworkManager to reconnect
#   6 min  re-plug the adapter in software (deauthorize/authorize its USB port;
#          the mic shares the hub, so the hub itself is never reset)
#   15 min reboot, at most once an hour (recording is on disk, nothing is lost)
STATE=/var/lib/sideyard-netwatch
mkdir -p "$STATE"
log() { logger -t sideyard-netwatch "$*"; }

ok() {
  timeout 4 bash -c '</dev/tcp/10.0.0.207/22' 2>/dev/null && return 0
  gw=$(ip route show default 2>/dev/null | awk '{print $3; exit}')
  [ -n "$gw" ] && ping -c1 -W3 "$gw" >/dev/null 2>&1
}

if ok; then
  [ -s "$STATE/fails" ] && [ "$(cat "$STATE/fails")" -gt 0 ] && log "network back after $(cat "$STATE/fails") failed checks"
  echo 0 > "$STATE/fails"
  exit 0
fi

n=$(( $(cat "$STATE/fails" 2>/dev/null || echo 0) + 1 ))
echo "$n" > "$STATE/fails"
log "network check failed ($n in a row)"

adapter() {  # sysfs dir of the ASIX USB device, if the bus still sees it
  for d in /sys/bus/usb/devices/*; do
    [ "$(cat "$d/idVendor" 2>/dev/null)" = 0b95 ] && { echo "$d"; return; }
  done
}

case "$n" in
  3|9|12)
    log "bouncing eth0"
    ip link set eth0 down 2>/dev/null; sleep 2; ip link set eth0 up 2>/dev/null
    nmcli device connect eth0 >/dev/null 2>&1 ;;
  6)
    d=$(adapter)
    if [ -n "$d" ]; then
      log "re-plugging the USB Ethernet adapter ($(basename "$d"))"
      echo 0 > "$d/authorized"; sleep 3; echo 1 > "$d/authorized"
      sleep 10; nmcli device connect eth0 >/dev/null 2>&1
    else
      log "USB Ethernet adapter is missing from the bus"
    fi ;;
esac

if [ "$n" -ge 15 ]; then
  last=$(cat "$STATE/last_reboot" 2>/dev/null || echo 0)
  if [ $(( $(date +%s) - last )) -ge 3600 ]; then
    date +%s > "$STATE/last_reboot"
    echo 0 > "$STATE/fails"
    log "rebooting: network down for $n minutes"
    sync; systemctl reboot
  fi
fi
