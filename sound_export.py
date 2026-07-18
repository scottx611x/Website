#!/usr/bin/env python3
"""Publish BirdNET-Go detections to S3 for the /birds/live viewer.

Runs on the listening-station "brain" (wherever BirdNET-Go runs). Reads its HTTP
API (stable, gives common names + confidence + isNew flags), rolls the data up
into one small JSON, and writes it to S3 under birds/sounds/ — where the site's
Lambda reads it (it already has birds/* read access). S3 is the rendezvous; the
brain's SQLite stays the full-history source of truth.

  BNG_URL          BirdNET-Go base URL         (default http://localhost:8080)
  BIRDS_S3_BUCKET  media bucket                (default birds-scott-ouellette)
  AWS_*            the birdpi-sound-exporter creds (scoped to birds/sounds/*)

    python sound_export.py            # build + upload to S3
    python sound_export.py --dry-run  # build + print, no upload
"""
import datetime as dt
import json
import os
import sys
import urllib.request

BNG = os.environ.get("BNG_URL", "http://localhost:8080").rstrip("/")
BUCKET = os.environ.get("BIRDS_S3_BUCKET", "birds-scott-ouellette")
KEY = "birds/sounds/recent.json"
RECENT_N = 40
DAILY_DAYS = 90


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


def build():
    dets = fetch_detections()
    dets.sort(key=lambda d: d.get("timestamp", ""), reverse=True)  # newest first
    species = api("/api/v2/analytics/species/summary")  # all-time, with names
    today = dt.date.today().isoformat()

    def det(d):
        return {
            "common": d.get("commonName"), "sci": d.get("scientificName"),
            "code": d.get("speciesCode"), "t": d.get("timestamp"),
            "conf": round(d.get("confidence", 0), 3),
            "new": bool(d.get("isNewSpecies")), "verified": d.get("verified"),
            "clip": d.get("clipName"),
        }

    # daily call counts + cumulative distinct species (for the timeline)
    per_day = {}
    for d in dets:
        per_day[d.get("date")] = per_day.get(d.get("date"), 0) + 1
    first_by_sp = {}
    for s in species:
        fh = (s.get("first_heard") or "")[:10]
        if fh:
            first_by_sp[s["common_name"]] = fh
    days = sorted(d for d in per_day)[-DAILY_DAYS:]
    seen, daily = set(), []
    for day in days:
        for sp, fh in first_by_sp.items():
            if fh <= day:
                seen.add(sp)
        daily.append({"d": day, "n": per_day[day], "cum": len(seen)})

    sp_out = [{
        "common": s["common_name"], "sci": s["scientific_name"], "code": s["species_code"],
        "count": s["count"], "first": s["first_heard"], "last": s["last_heard"],
        "maxConf": round(s.get("max_confidence", 0), 3),
    } for s in species]

    today_sp = sorted({d["commonName"] for d in dets if d.get("date") == today and d.get("commonName")})

    return {
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "station": {"source": (dets[0]["source"]["displayName"] if dets else "BirdPi Mic")},
        "recent": [det(d) for d in dets[:RECENT_N]],
        "species": sp_out,
        "today": today_sp,
        "daily": daily,
        "counts": {
            "speciesAllTime": len(species),
            "callsAllTime": sum(per_day.values()),
            "speciesToday": len(today_sp),
            "callsToday": per_day.get(today, 0),
        },
    }


def main():
    dry = "--dry-run" in sys.argv
    payload = build()
    body = json.dumps(payload, separators=(",", ":")).encode()
    # local copy for debugging / commit-as-mirror
    here = os.path.dirname(os.path.abspath(__file__))
    local = os.path.join(here, "birds", "sounds_recent.json")
    os.makedirs(os.path.dirname(local), exist_ok=True)
    with open(local, "wb") as fh:
        fh.write(body)
    print("built: %d species, %d recent calls, %d calls today (%d bytes)" % (
        payload["counts"]["speciesAllTime"], len(payload["recent"]),
        payload["counts"]["callsToday"], len(body)))
    if dry:
        print("--dry-run: not uploading. Sample:")
        print(json.dumps(payload, indent=2)[:900])
        return
    import boto3
    boto3.client("s3").put_object(
        Bucket=BUCKET, Key=KEY, Body=body,
        ContentType="application/json", CacheControl="max-age=30")
    print("uploaded s3://%s/%s" % (BUCKET, KEY))


if __name__ == "__main__":
    main()
