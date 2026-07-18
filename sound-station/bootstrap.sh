#!/usr/bin/env bash
# Stand up the all-in-one bird sound station on a Raspberry Pi (4 or 5, ARM64).
#
# The Pi captures (USB mic), thinks (BirdNET-Go), and publishes (this repo's
# sound_export.py) — no laptop, no RTSP hop. Idempotent: safe to re-run.
#
# Run ON the Pi, from a directory that also contains sound_export.py and a
# tuned config.yaml (scp them over first, or clone this repo). Then:
#
#   MIC_DEVICE=sysdefault ./bootstrap.sh
#
# Credentials: drop the scoped exporter key into exporter.env (see
# exporter.env.example) BEFORE running, or the timer will fail auth.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
USER_NAME="${SUDO_USER:-$USER}"
HOME_DIR="$(eval echo "~$USER_NAME")"
STATION="$HOME_DIR/birdnet-station"          # exporter venv + code + env
BNG_HOME="$HOME_DIR/birdnet-go"              # container config + data
MIC_DEVICE="${MIC_DEVICE:-sysdefault}"       # ALSA device; confirm via `arecord -l`
BNG_IMAGE="ghcr.io/tphakala/birdnet-go:nightly"

echo "==> 1/6  System packages (docker, ffmpeg, python venv)"
sudo apt-get update -qq
sudo apt-get install -y -qq ca-certificates curl ffmpeg python3-venv python3-pip alsa-utils
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER_NAME"
  echo "    (added $USER_NAME to docker group — a re-login may be needed)"
fi

echo "==> 2/6  Directories"
mkdir -p "$STATION" "$BNG_HOME/config" "$BNG_HOME/data/clips"
cp "$HERE/sound_export.py" "$STATION/"
[ -f "$HERE/config.yaml" ] && cp "$HERE/config.yaml" "$BNG_HOME/config/config.yaml"

echo "==> 3/6  BirdNET-Go container (local mic: $MIC_DEVICE)"
sudo docker pull -q "$BNG_IMAGE"
sudo docker rm -f birdnet-go >/dev/null 2>&1 || true
sudo docker run -d --name birdnet-go --restart unless-stopped \
  --device /dev/snd \
  -p 8080:8080 \
  -e TZ="$(cat /etc/timezone 2>/dev/null || echo America/New_York)" \
  -v "$BNG_HOME/config:/config" \
  -v "$BNG_HOME/data:/data" \
  "$BNG_IMAGE"

echo "==> 4/6  Exporter venv (boto3 + spectrogram deps)"
python3 -m venv "$STATION/export-venv"
"$STATION/export-venv/bin/pip" install -q --upgrade pip
"$STATION/export-venv/bin/pip" install -q boto3 numpy pillow

echo "==> 5/6  systemd timer (publish to S3 every 60s)"
sed -e "s|@STATION@|$STATION|g" -e "s|@USER@|$USER_NAME|g" \
    "$HERE/birdnet-export.service" | sudo tee /etc/systemd/system/birdnet-export.service >/dev/null
sudo cp "$HERE/birdnet-export.timer" /etc/systemd/system/birdnet-export.timer
sudo systemctl daemon-reload
sudo systemctl enable --now birdnet-export.timer

echo "==> 6/6  Done."
echo "    BirdNET-Go UI:  http://$(hostname -i | awk '{print $1}'):8080"
echo "    Mic devices:    arecord -l"
echo "    Exporter runs:  systemctl list-timers birdnet-export.timer"
echo "    Exporter logs:  journalctl -u birdnet-export.service -f"
