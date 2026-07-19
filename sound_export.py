#!/usr/bin/env python3
"""Publish BirdNET-Go detections to S3 for the /birds/live viewer.

Runs on the listening-station "brain" (wherever BirdNET-Go runs). Reads its HTTP
API (stable, gives common names + confidence + isNew flags), rolls the data up
into one small JSON, and writes it to S3 under birds/sounds/ — where the site's
Lambda reads it (it already has birds/* read access). S3 is the rendezvous; the
brain's SQLite stays the full-history source of truth.

Also publishes the audio itself: for the newest detections it transcodes the
WAV clip to AAC (afconvert, ships with macOS) and uploads it plus BirdNET-Go's
real spectrogram PNG to birds/sounds/clips/, so the site can play what the mic
heard over the actual picture of the sound.

BirdNET-Go's container runs in UTC, so its date/time fields are UTC; all date
bucketing here (today, hours, daily) is done in this machine's local timezone,
and the page renders clock times client-side from the ISO timestamps.

  BNG_URL          BirdNET-Go base URL         (default http://localhost:8080)
  BNG_CLIPS_DIR    clip storage on disk        (default ~/birdnet-go/data/clips)
  BIRDS_S3_BUCKET  media bucket                (default birds-scott-ouellette)
  AWS_*            the birdpi-sound-exporter creds (scoped to birds/sounds/*)

    python sound_export.py            # build + upload to S3
    python sound_export.py --dry-run  # build + print, no upload
"""
import datetime as dt
import json
import os
import subprocess
import sys
import tempfile
import urllib.request

BNG = os.environ.get("BNG_URL", "http://localhost:8080").rstrip("/")
BUCKET = os.environ.get("BIRDS_S3_BUCKET", "birds-scott-ouellette")
CLIPS_DIR = os.path.expanduser(os.environ.get("BNG_CLIPS_DIR", "~/birdnet-go/data/clips"))
KEY = "birds/sounds/recent.json"
LOG_KEY = "birds/sounds/log.json"    # the full browsable detection log (its own file)
CLIP_PREFIX = "birds/sounds/clips/"
RECENT_N = 80         # feed backlog: the live page consolidates + scrolls these
LOG_N = 1500          # detections in the log page's backlog
MEDIA_N = 25          # newest detections that get audio + spectrogram published
DAILY_DAYS = 400      # enough runway for the year view


def api(path):
    with urllib.request.urlopen(BNG + path, timeout=20) as r:
        return json.load(r)


def fetch_detections():
    """All detections, paged by offset (the API caps a single page)."""
    out, offset, page = [], 0, 500
    while offset < 50000:
        r = api("/api/v2/detections?queryType=all&numResults=%d&offset=%d" % (page, offset))
        data = r.get("data", [])
        out += data
        offset += page
        if offset >= r.get("total", len(out)) or not data:
            break
    return out


def local(ts):
    """ISO UTC timestamp -> aware datetime in this machine's timezone."""
    return dt.datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone()


def find_clip(name):
    """Locate a clip file under CLIPS_DIR (BirdNET-Go nests by year/month)."""
    for root, _, files in os.walk(CLIPS_DIR):
        if name in files:
            return os.path.join(root, name)
    return None


# The site's palette, as an energy ramp: ink -> deep green -> neon -> bright.
# Extra low stops make faint detail glow instead of vanishing into the ink.
_SPEC_STOPS = [
    (0.00, (13, 18, 14)),     # --ink
    (0.12, (15, 40, 27)),
    (0.30, (26, 84, 54)),
    (0.52, (47, 125, 79)),    # --green
    (0.74, (56, 224, 138)),   # --neon
    (0.90, (150, 240, 180)),
    (1.00, (240, 250, 225)),  # near paper, the hottest harmonics
]


def render_spectrogram(wav_path, out_path, height=480, width=2200, max_hz=11000):
    """Draw the clip's spectrogram in the site's own colors — bright, detailed.

    A log-frequency axis gives the low-mid band where birds actually sing most
    of the vertical space (so harmonics read as structure, not a smear at the
    bottom), per-band noise-floor removal keeps the ink clean, and a bright ramp
    with a low gamma makes faint calls glow. BirdNET-Go renders its own PNGs
    lazily and in a foreign palette; this one belongs to the site.
    """
    import wave

    import numpy as np
    from PIL import Image

    with wave.open(wav_path) as w:
        rate, n = w.getframerate(), w.getnframes()
        raw = np.frombuffer(w.readframes(n), dtype=np.int16)
        if w.getnchannels() > 1:
            raw = raw.reshape(-1, w.getnchannels()).mean(axis=1)
    x = raw.astype(np.float64) / 32768.0

    nfft = 2048
    hop = max(1, (len(x) - nfft) // width)  # ~`width` columns regardless of length
    frames = np.lib.stride_tricks.sliding_window_view(x, nfft)[::hop] * np.hanning(nfft)
    mag = np.abs(np.fft.rfft(frames, axis=1)).T  # (freq, time), low freq first
    freqs = np.fft.rfftfreq(nfft, 1.0 / rate)

    # Resample the linear frequency bins onto a log axis (~150 Hz .. max_hz), so
    # the bird band gets the pixels. Interp per time column (fast enough).
    f_hi = min(max_hz, rate / 2.0)
    log_f = np.geomspace(150.0, f_hi, height)
    mag_log = np.empty((height, mag.shape[1]))
    for t in range(mag.shape[1]):
        mag_log[:, t] = np.interp(log_f, freqs, mag[:, t])

    db = 20 * np.log10(mag_log + 1e-9)
    db -= np.median(db, axis=1, keepdims=True)   # drop each band's steady hiss
    # Brighten: 5 dB above the floor already glows, ~28 dB is white-hot; gamma
    # < 1 lifts the mid-tones so structure is visible, not just the loudest hit.
    norm = np.clip((db - 5.0) / 28.0, 0, 1) ** 0.55

    pos = np.array([p for p, _ in _SPEC_STOPS])
    rgb = np.array([c for _, c in _SPEC_STOPS], dtype=np.float64)
    img = np.stack([np.interp(norm, pos, rgb[:, i]) for i in range(3)], axis=-1)
    out = Image.fromarray(img[::-1].astype(np.uint8))  # flip: low freq at bottom
    out.save(out_path, optimize=True)


def _aac_cmd(src, dst):
    """WAV -> AAC/m4a using whatever encoder this box has.

    afconvert ships with macOS (the laptop brain); ffmpeg is everywhere else
    (the Pi). Same 96k AAC either way, so clips are identical wherever the
    exporter runs.
    """
    import shutil
    if shutil.which("afconvert"):
        return ["afconvert", "-f", "m4af", "-d", "aac", "-b", "96000", src, dst]
    if shutil.which("ffmpeg"):
        return ["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-c:a", "aac", "-b:a", "96k", dst]
    return None


def publish_media(dets, s3):
    """Transcode + upload audio and spectrograms for the newest detections.

    Returns {clipName: {"audio": key-basename, "spec": key-basename}} for
    everything that made it (now or on a previous run). Uploads are immutable
    (clip names embed the timestamp), so existing keys are skipped wholesale.

    Existence is probed per-key with HeadObject (covered by the exporter's
    GetObject grant) rather than a bucket ListObjects, so the S3 key stays
    scoped to exactly PutObject/GetObject on birds/sounds/* — no ListBucket.
    """
    def have(name):
        if s3 is None:
            return False
        try:
            s3.head_object(Bucket=BUCKET, Key=CLIP_PREFIX + name)
            return True
        except Exception:
            return False

    refs = {}
    for d in dets[:MEDIA_N]:
        clip = d.get("clipName")
        if not clip:
            continue
        base = os.path.splitext(os.path.basename(clip))[0]
        # _v3: 2200x480 (2x for retina + the full-screen zoom). _v2 is the old
        # 1100x240 render, kept as a fallback for clips whose WAV is gone.
        m4a, spec, old_spec = base + ".m4a", base + "_v3.png", base + "_v2.png"
        ref = {}

        wav = find_clip(os.path.basename(clip))
        if not wav:
            # The WAV rotated off disk — reuse whatever was published while we
            # had it instead of silently dropping the refs.
            if have(m4a):
                ref["audio"] = m4a
            if have(spec):
                ref["spec"] = spec
            elif have(old_spec):
                ref["spec"] = old_spec
        if wav:
            if have(m4a):
                ref["audio"] = m4a
            elif s3 is not None:
                with tempfile.TemporaryDirectory() as td:
                    out = os.path.join(td, m4a)
                    cmd = _aac_cmd(wav, out)
                    if cmd is None:
                        print("no AAC encoder (need afconvert or ffmpeg)", file=sys.stderr)
                    else:
                        r = subprocess.run(cmd, capture_output=True)
                        if r.returncode == 0:
                            s3.upload_file(out, BUCKET, CLIP_PREFIX + m4a, ExtraArgs={
                                "ContentType": "audio/mp4",
                                "CacheControl": "public, max-age=31536000, immutable"})
                            ref["audio"] = m4a
                        else:
                            print("%s failed for %s: %s" % (cmd[0], clip, r.stderr.decode()[:200]),
                                  file=sys.stderr)
            if have(spec):
                ref["spec"] = spec
            elif s3 is not None:
                try:
                    with tempfile.TemporaryDirectory() as td:
                        png = os.path.join(td, spec)
                        render_spectrogram(wav, png)
                        s3.upload_file(png, BUCKET, CLIP_PREFIX + spec, ExtraArgs={
                            "ContentType": "image/png",
                            "CacheControl": "public, max-age=31536000, immutable"})
                        ref["spec"] = spec
                except Exception as e:
                    print("spectrogram failed for %s: %s" % (clip, e), file=sys.stderr)
                    if have(old_spec):
                        ref["spec"] = old_spec
        if ref:
            refs[clip] = ref
    return refs


def build(s3=None):
    dets = fetch_detections()
    dets.sort(key=lambda d: d.get("timestamp", ""), reverse=True)  # newest first
    species = api("/api/v2/analytics/species/summary")  # all-time, with names
    media = publish_media(dets, s3)
    now = dt.datetime.now().astimezone()
    today = now.date().isoformat()

    def det(d):
        out = {
            "common": d.get("commonName"), "sci": d.get("scientificName"),
            "code": d.get("speciesCode"), "t": d.get("timestamp"),
            "conf": round(d.get("confidence", 0), 3),
            "new": bool(d.get("isNewSpecies")), "verified": d.get("verified"),
        }
        out.update(media.get(d.get("clipName"), {}))
        return out

    # local-day call counts (+ per-species) and hour-of-day rhythm for today
    per_day, day_sp, hours = {}, {}, [0] * 24
    for d in dets:
        when = local(d["timestamp"]) if d.get("timestamp") else None
        if when is None:
            continue
        day = when.date().isoformat()
        per_day[day] = per_day.get(day, 0) + 1
        sp = day_sp.setdefault(day, {})
        name = d.get("commonName") or "?"
        sp[name] = sp.get(name, 0) + 1
        if day == today:
            hours[when.hour] += 1

    # cumulative distinct species per day (life-list-by-ear curve)
    first_by_sp = {}
    for s in species:
        fh = (s.get("first_heard") or "")[:10]
        if fh:
            first_by_sp[s["common_name"]] = fh
    days = sorted(per_day)[-DAILY_DAYS:]
    seen, daily = set(), []
    for day in days:
        for sp, fh in first_by_sp.items():
            if fh <= day:
                seen.add(sp)
        daily.append({"d": day, "n": per_day[day], "cum": len(seen), "sp": day_sp[day]})

    sp_out = [{
        "common": s["common_name"], "sci": s["scientific_name"], "code": s["species_code"],
        "count": s["count"], "first": s["first_heard"], "last": s["last_heard"],
        "maxConf": round(s.get("max_confidence", 0), 3),
    } for s in species]

    today_sp = sorted(day_sp.get(today, {}))

    generated = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    return {
        "generated": generated,
        "station": {"source": (dets[0]["source"]["displayName"] if dets else "BirdPi Mic")},
        "recent": [det(d) for d in dets[:RECENT_N]],
        "species": sp_out,
        "today": today_sp,
        "daily": daily,
        "hours": hours,
        "counts": {
            "speciesAllTime": len(species),
            "callsAllTime": sum(per_day.values()),
            "speciesToday": len(today_sp),
            "callsToday": per_day.get(today, 0),
        },
        # Split out in main(): the full detection log lives in its own file so
        # recent.json (polled every 60s) stays tiny.
        "log": [det(d) for d in dets[:LOG_N]],
    }


def main():
    dry = "--dry-run" in sys.argv
    s3 = None
    if not dry:
        import boto3
        s3 = boto3.client("s3")
    payload = build(s3)
    # The detection log ships in its own file; keep it out of recent.json.
    log = payload.pop("log", [])
    log_payload = {"generated": payload["generated"], "log": log}
    body = json.dumps(payload, separators=(",", ":")).encode()
    log_body = json.dumps(log_payload, separators=(",", ":")).encode()
    # local copy for debugging / commit-as-mirror
    here = os.path.dirname(os.path.abspath(__file__))
    local_path = os.path.join(here, "birds", "sounds_recent.json")
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    with open(local_path, "wb") as fh:
        fh.write(body)
    with_audio = sum(1 for r in payload["recent"] if r.get("audio"))
    print("built: %d species, %d recent (%d w/audio), %d log entries, %d calls today (%d+%d bytes)" % (
        payload["counts"]["speciesAllTime"], len(payload["recent"]), with_audio,
        len(log), payload["counts"]["callsToday"], len(body), len(log_body)))
    if dry:
        print("--dry-run: not uploading. Sample:")
        print(json.dumps(payload, indent=2)[:900])
        return
    s3.put_object(
        Bucket=BUCKET, Key=KEY, Body=body,
        ContentType="application/json", CacheControl="max-age=30")
    s3.put_object(
        Bucket=BUCKET, Key=LOG_KEY, Body=log_body,
        ContentType="application/json", CacheControl="max-age=30")
    print("uploaded s3://%s/%s and %s" % (BUCKET, KEY, LOG_KEY))


if __name__ == "__main__":
    main()
