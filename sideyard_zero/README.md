# Side Yard Pi Zero: self-healing files

Installed copies of what runs on `birdPiZero` (10.0.0.168, wired via an ASIX
AX88179B USB Ethernet adapter on a hub it shares with the USB mic).
Reach it through birdpi:

    ssh -i ~/.ssh/birdpi_ed25519 -o ProxyJump=scott@birdpi.local scott@10.0.0.168

| file | installed at | what |
|---|---|---|
| sideyard-ship.sh | /usr/local/bin/ | ship segments to birdpi; 4-day buffer; falls back to 10.0.0.207 when mDNS fails |
| sideyard-netwatch.sh | /usr/local/bin/ | every minute: bounce eth0 (3 min), re-plug the adapter in software (6 min), reboot (15 min, max 1/h) |
| sideyard-netwatch.{service,timer} | /etc/systemd/system/ | runs the above |
| journald.conf | /etc/systemd/journald.conf.d/persistent.conf | logs survive reboots (40 MB cap) |
| watchdog.conf | NOT installed | hardware watchdog; the Zero hard-reset during the install that added it (2026-11-27), so it was removed until that is understood |

After installing anything here, run `sudo sync`: a reset before the flush leaves
0-byte files (that happened once).
