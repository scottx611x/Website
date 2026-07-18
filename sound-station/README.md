# Bird sound station — the Pi brain

The always-on box that turns yard sound into what you see at
[`/birds/live`](https://www.scott-ouellette.com/birds/live). One Raspberry Pi
(4 or 5, ARM64) does all three jobs:

```
USB mic ──▶ BirdNET-Go (neural net, Docker) ──▶ sound_export.py ──▶ S3 birds/sounds/ ──▶ the site
           (local ALSA capture, no RTSP)        (systemd timer, 60s)
```

No laptop, no streaming hop — the mic plugs straight into the Pi and the whole
pipeline lives on one ~5W device. This replaces the old split where a Pi Zero
streamed RTSP to a BirdNET-Go running on the Mac (which slept).

## Files here
- `bootstrap.sh` — idempotent installer, run on the Pi
- `config.yaml` — the tuned BirdNET-Go config (created during migration; sound-card source, not RTSP)
- `birdnet-export.service` / `.timer` — systemd units for the exporter (the Linux equivalent of the Mac's launchd agent)
- `exporter.env.example` — template for the scoped AWS key + paths
- `sound_export.py` — symlink/copy of the repo's exporter (afconvert on macOS, ffmpeg on the Pi)

## First-time setup
1. **Flash** Raspberry Pi OS Lite **64-bit** (required for Pi 5). In the Imager's
   pre-config: hostname `birdbrain`, SSH + your public key, user `scott`, WiFi, timezone.
   Use a real 5V/5A supply on a Pi 5 or the USB ports throttle.
2. **Plug the USB mic** into a blue USB 3.0 port; boot.
3. From the Mac, copy the tuned config + exporter over and find the mic:
   ```
   scp ~/birdnet-go/config/config.yaml sound_export.py scott@birdbrain.local:~/birdnet-station-src/
   ssh scott@birdbrain.local 'arecord -l'      # note the USB mic's card
   ```
4. Fill `exporter.env` with the scoped `birdpi-sound-exporter` key
   (`tofu apply` in `infra/website` mints it).
5. Run it:
   ```
   ssh scott@birdbrain.local
   cd ~/birdnet-station-src && MIC_DEVICE=plughw:CARD=<mic> ./bootstrap.sh
   ```

## Tuning (already baked into config.yaml)
`overlap 2.5` · `threshold 0.7` · `sensitivity 1.0` · dynamic-threshold `min 0.5`
· false-positive-filter `level 2` · include-list of owls + nightjars the eBird
range filter mutes. Bias: cleaner over noisier, because the feed auto-publishes
unverified. See the chat history / commit log for the reasoning.

## Operating
- BirdNET-Go UI: `http://birdbrain.local:8080`
- Exporter schedule: `systemctl list-timers birdnet-export.timer`
- Exporter logs: `journalctl -u birdnet-export.service -f`
- Restart the brain: `docker restart birdnet-go`
