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
CLIP_PREFIX = "birds/sounds/clips/"
RECENT_N = 40
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


def publish_media(dets, s3):
    """Transcode + upload audio and spectrograms for the newest detections.

    Returns {clipName: {"audio": key-basename, "spec": key-basename}} for
    everything that made it (now or on a previous run). Uploads are immutable
    (clip names embed the timestamp), so existing keys are skipped wholesale.
    """
    have = set()
    if s3 is not None:
        paginator = s3.get_paginator("list_objects_v2")
        for pg in paginator.paginate(Bucket=BUCKET, Prefix=CLIP_PREFIX):
            for o in pg.get("Contents", []):
                have.add(o["Key"][len(CLIP_PREFIX):])

    refs = {}
    for d in dets[:MEDIA_N]:
        clip = d.get("clipName")
        if not clip:
            continue
        base = os.path.splitext(os.path.basename(clip))[0]
        m4a, spec = base + ".m4a", base + "_514px.png"
        ref = {}

        wav = find_clip(os.path.basename(clip))
        if wav:
            if m4a in have:
                ref["audio"] = m4a
            elif s3 is not None:
                with tempfile.TemporaryDirectory() as td:
                    out = os.path.join(td, m4a)
                    r = subprocess.run(
                        ["afconvert", "-f", "m4af", "-d", "aac", "-b", "96000", wav, out],
                        capture_output=True)
                    if r.returncode == 0:
                        s3.upload_file(out, BUCKET, CLIP_PREFIX + m4a, ExtraArgs={
                            "ContentType": "audio/mp4",
                            "CacheControl": "public, max-age=31536000, immutable"})
                        have.add(m4a)
                        ref["audio"] = m4a
                    else:
                        print("afconvert failed for %s: %s" % (clip, r.stderr.decode()[:200]),
                              file=sys.stderr)
            png = os.path.join(os.path.dirname(wav), spec)
            if spec in have:
                ref["spec"] = spec
            elif s3 is not None and os.path.exists(png):
                s3.upload_file(png, BUCKET, CLIP_PREFIX + spec, ExtraArgs={
                    "ContentType": "image/png",
                    "CacheControl": "public, max-age=31536000, immutable"})
                have.add(spec)
                ref["spec"] = spec
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

    return {
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
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
    }


def main():
    dry = "--dry-run" in sys.argv
    s3 = None
    if not dry:
        import boto3
        s3 = boto3.client("s3")
    payload = build(s3)
    body = json.dumps(payload, separators=(",", ":")).encode()
    # local copy for debugging / commit-as-mirror
    here = os.path.dirname(os.path.abspath(__file__))
    local_path = os.path.join(here, "birds", "sounds_recent.json")
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    with open(local_path, "wb") as fh:
        fh.write(body)
    with_audio = sum(1 for r in payload["recent"] if r.get("audio"))
    print("built: %d species, %d recent calls (%d with audio), %d calls today (%d bytes)" % (
        payload["counts"]["speciesAllTime"], len(payload["recent"]), with_audio,
        payload["counts"]["callsToday"], len(body)))
    if dry:
        print("--dry-run: not uploading. Sample:")
        print(json.dumps(payload, indent=2)[:900])
        return
    s3.put_object(
        Bucket=BUCKET, Key=KEY, Body=body,
        ContentType="application/json", CacheControl="max-age=30")
    print("uploaded s3://%s/%s" % (BUCKET, KEY))


if __name__ == "__main__":
    main()
