# Live bird-sound station — design draft

A solar-powered listening post in the yard that identifies birds by ear in real
time and feeds a **"heard right now"** view on the site, cross-linked to the photo
gallery. The emotional hook: it turns your two datasets into one story — *what
you've heard* vs *what you've photographed* — and hands you a shot list of birds
that are around but not yet in the gallery.

Status: **draft for Scott to react to.** Nothing built yet. Open decisions are at
the bottom.

---

## 1. The recommendation in one paragraph

Use a **Raspberry Pi Zero 2 W + a USB mic running [BirdNET-Go]**, not the Android
phone. BirdNET is Cornell's bird-sound neural net; BirdNET-Go is a single, low-power
Go binary built for exactly this — continuous listening, on-device inference,
local SQLite of detections, a built-in web UI, and clean export hooks. The Pi
**writes detections (and short audio clips) straight to S3** under a `sounds/`
prefix with a narrow IAM key — the same "S3 is the source of truth, the site is a
mirror" model the curation files already use. The site grows a read-only
`/birds/live` view (later `live.scott-ouellette.com`) that reads a small rolled-up
JSON. No new always-on server, no ingest endpoint to secure, nothing that fights
the Lambda deploy.

Keep the **Android phone as a fallback experiment**, not the primary — see §7.

[BirdNET-Go]: https://github.com/tphakala/birdnet-go

---

## 2. Why RPi over the Android phone

| | **Raspberry Pi + BirdNET-Go** | **Old Android + BirdNET app / TFLite** |
|---|---|---|
| Built for 24/7 unattended? | Yes — headless, auto-start, watchdog | No — app lifecycle, dozing, OS kills background work |
| Power control for solar | Fine-grained (duty-cycle, disable HDMI/LEDs, ~0.5–1.5 W) | Coarse; radios + screen fight you; hard to get low |
| Mic input | USB mic "just works" via ALSA | USB-OTG mic support is device-specific and flaky |
| Detection export | Native (SQLite + HTTP/MQTT/S3-friendly) | You'd script around an app not meant for streaming |
| Weatherproofing | Small board, easy to pot into a box | Whole phone incl. battery that hates heat/cold |
| Failure recovery | systemd restart, read-only rootfs option | Reboots land on a lock screen |

The phone *can* run the model — the BirdNET app exists — but it's designed for a
human holding it, not a mailbox-mounted sensor running for months. For a
solar-on-a-whim deployment, the Pi is the low-risk path.

**Board choice:** Pi Zero 2 W is the low-power sweet spot (quad A53, 512 MB) and
BirdNET-Go runs on arm64. RAM is tight — if a week of testing shows it struggling,
step up to a **Pi 3A+/4** (more headroom, ~2–4 W, bigger panel). Decide after the
Phase 0 soak test, not before.

---

## 3. Architecture

```
  [ mic ]→[ Pi: BirdNET-Go ]───────────────┐  (buffered, retried on reconnect)
     24/7 or dawn/dusk        detections    │
     3s windows               + clips       ▼
                                      S3  s3://birds-scott-ouellette/sounds/
                                        detections/2026-07-12.ndjson   (append-only, per day)
                                        clips/<species>-<ts>.opus       (short, high-conf/novel only)
                                        recent.json                     (rolled-up, site reads this)
                                                 ▲
                    daily Lambda (reuse scheduled_sync pattern):
                    roll up today + last N days → recent.json, prune old clips
                                                 │
                                                 ▼
                             Flask/Lambda  /birds/live  reads recent.json
                             cross-links species → existing gallery pages
```

Design principles, matched to what already exists:

- **S3 is the source of truth** for detections, exactly like `overrides.json` /
  `excluded.json`. The Pi's local SQLite is the *upstream* truth; S3 is the
  published mirror; the site never writes detections.
- **The Pi writes, never the site.** A dedicated IAM user scoped to
  `PutObject` on `sounds/*` only. No new public endpoint to defend, no shared
  secret in a device on a pole. (Contrast with the curate cookie, which guards
  a *write* path exposed to the internet — we don't need one here.)
- **Cheap reads.** The site only ever loads `recent.json` (small, rolled up),
  cached with the same conditional-GET + write-through helpers in `birds.py`.
  The daily Lambda does the heavy rollup, not the request path.
- **Survives flaky links.** A solar node may be on marginal wifi/LTE.
  BirdNET-Go keeps everything locally and we batch-upload with retry, so a
  dropout loses nothing — it backfills when the link returns.

### Data model (proposed)

One detection line (NDJSON):

```json
{"ts":"2026-07-12T06:14:22-04:00","species":"Wood Thrush","sci":"Hylocichla mustelina",
 "conf":0.87,"clip":"clips/wood-thrush-20260712-061422.opus","station":"yard"}
```

`recent.json` (what the site reads) — a rollup, not raw:

```json
{"generated":"2026-07-12T23:59:00-04:00",
 "today":[{"species":"Wood Thrush","first":"06:14","last":"19:02","n":38,"max_conf":0.94,
           "photographed":true,"clip":"clips/wood-thrush-20260712-061422.opus"}],
 "heard_not_photographed":["Veery","Great Crested Flycatcher"],
 "counts":{"species_today":14,"species_all_time":63}}
```

`photographed` is computed by canonicalizing the detected species against the
existing gallery species index (`birds._canon_species` — the tolerant matcher we
just hardened handles "Northern House Wren" vs "House Wren" etc.). This is the
join that makes the two datasets one.

---

## 4. What it looks like on the site

A new `/birds/live` (later `live.scott-ouellette.com`; the Host handling already
exists for `birds.` so the pattern's known):

- **Heard today** — species with first/last time, count, top confidence, newest
  first. Each name links to its gallery species page. A ▶ button plays the clip.
- **Heard, not yet photographed** — the shot list. This is the feature that
  earns its place: the mic finds birds the lens hasn't, and tells you they're
  *right there*. A Veery calling at dawn you've never gotten a photo of → go out.
- **Two life lists** — "by lens" (photographed, today's gallery count) and "by
  ear" (acoustic). The union is your real yard list.
- **Dawn-chorus timeline / species-by-hour heatmap** — you've got the dataviz
  skill; a day's detections make a genuinely nice chart. Real data only, in
  keeping with the no-gimmicks rule.

Tone stays first-person and honest: show confidence, don't launder BirdNET's
guesses as certainties (see §6).

---

## 5. Hardware — bill of materials (approx, verify current prices)

| Item | Note | ~USD |
|---|---|---|
| Raspberry Pi Zero 2 W | The compute. Pi 3A+/4 if Zero struggles | 15–35 |
| USB lavalier/electret mic, or a **PUC/EMF-mic + USB sound card** | Mic quality drives ID quality more than the board does | 15–60 |
| microSD (endurance/high-endurance) | 24/7 writes kill cheap cards — get an endurance-rated one | 12 |
| Solar panel 10–20 W | Size to §8; 20 W is safer for 24/7 in a NE winter | 25–50 |
| Solar charge controller (MPPT small) | | 15–25 |
| LiFePO4 battery (e.g. 6–20 Ah 3.2 V or a 12 V pack + buck) | LiFePO4 tolerates cold/cycles far better than LiPo | 25–60 |
| Weatherproof enclosure + cable glands | Mic needs an acoustically-open but rain-shielded port | 20–40 |
| Optional: LTE hat / use phone hotspot | Only if out of home-wifi range | 0–50 |

Ballpark **$130–300** depending on mic and connectivity. The mic and the SD card
are where *not* to cheap out.

---

## 6. Accuracy & trust (BirdNET has false positives)

- **Location + week filtering.** BirdNET narrows its species list by lat/long and
  time of year — set North Andover's coordinates and it stops hallucinating
  western/tropical birds. Big accuracy win, free.
- **Confidence threshold + min-detections.** Only surface species over a
  threshold (start ~0.7) and/or seen N times in a window, to kill one-off blips.
- **A curate/confirm loop, mirroring your photo curation.** Reuse the existing
  curate-auth model so *you* can confirm or reject a detection from the live page;
  confirmed ones feed a trusted "heard" list, rejects train your threshold. Same
  muscle as the photo curation you already do.
- **Be honest in the UI.** Show confidence; label the acoustic list as "heard
  (auto-ID)" distinct from the curated/confirmed list. Don't imply a machine
  guess is a sighting.

---

## 7. Android as a fallback experiment

If you want to try the phone first (zero purchase, instant): install the BirdNET
app, point it at the yard, and it'll do live ID with a nice UI — good for
**proving the idea and scouting mic placement** before buying a Pi. What it won't
do well is run untended for months on solar or export a clean detection stream to
the site. Treat it as the **Phase 0 probe**, then move the durable station to the
Pi. (A rooted phone running a TFLite BirdNET service 24/7 is possible but is more
work than a Pi and fights the OS the whole way.)

---

## 8. Power & siting notes (solar)

- **Budget.** Pi Zero 2 W + mic ≈ 0.5–1.5 W. Over 24 h that's ~12–36 Wh/day.
  A 20 W panel makes that easily on a sunny day; the battery covers night + a
  cloudy stretch. NE winter (short days, snow on the panel) is the hard case —
  size the panel/battery for December, not July, or duty-cycle (below).
- **Duty-cycling.** Birds are loudest at **dawn and dusk**. Recording just those
  windows (say 05:00–09:00 and 18:00–21:00) cuts power and storage a lot while
  catching the chorus. 24/7 catches owls and migration-night flight calls. This
  is a real decision — see below.
- **Ruggedizing.** Strip the Pi (disable HDMI, onboard LEDs, Bluetooth if unused),
  consider read-only rootfs so a brownout can't corrupt the card, add a systemd
  watchdog. Mic port faces down/shielded so rain doesn't hit the diaphragm.
- **Connectivity.** Home wifi if the yard's in range; otherwise a phone hotspot
  or a cheap LTE hat. Everything's buffered locally, so the link can be
  intermittent.

---

## 9. Phased plan

- **Phase 0 — prove it (a weekend, ~$0).** BirdNET app on the Android phone, or
  BirdNET-Go on a Pi you power from mains on the porch. Run a week. Judge ID
  quality and mic placement for *your* yard. Decide Zero 2 W vs Pi 4.
- **Phase 1 — publish read-only (site work).** IAM user + `sounds/` prefix; Pi
  exports detections to S3; daily rollup Lambda; `/birds/live` reads `recent.json`
  and shows "heard today" with species→gallery links. No clips yet.
- **Phase 2 — the join & charts.** "Heard, not photographed" shot list; by-ear vs
  by-lens life lists; dawn-chorus timeline / hourly heatmap.
- **Phase 3 — durable + rich.** Solar + enclosure + duty-cycle; store short audio
  clips for high-conf/novel detections with ▶ playback; curate/confirm loop.

Each phase is independently useful and ships on its own, matching how the gallery
was built.

---

## 10. Open decisions (need your call)

1. **Listening window:** 24/7 (owls, night flight calls, but more power/storage)
   vs **dawn+dusk duty-cycle** (easier on solar, catches the chorus). Leaning
   duty-cycle for a first solar build.
2. **Audio clips:** store short clips for playback (great feature, more storage +
   a privacy angle to a 24/7 yard mic) vs **detections-only** to start. Leaning
   detections-only for Phase 1, clips in Phase 3.
3. **Surface:** `live.scott-ouellette.com` subdomain vs a `/birds/live` page
   under the existing site. Leaning `/birds/live` first (no DNS work), promote to
   a subdomain later if it earns it.
4. **Board:** commit to Pi Zero 2 W now, or buy a Pi 4 for headroom? Leaning
   decide-after-Phase-0.
5. **Do you actually have a spare Pi**, or should the BOM assume buying one?
