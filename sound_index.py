"""Rebuild the full recordings index from the clips in S3.

The station's exporter writes ``birds/sounds/log.json`` capped at ``LOG_N``
(1,500 detections — about two days), while never deleting the clips it points
at. The result: ~28,000 recordings sit in the bucket with nothing indexing
them, so the site can only reach the most recent two days of an 81-day
archive.

Nothing needs to be re-uploaded to fix that, because every clip's filename
carries what we need::

    sitta_carolinensis_62p_20261006T171811Z.m4a
    └── scientific ──┘ └c┘ └──── UTC ─────┘

Scientific name, confidence and the exact instant. The common name, species
code and canonical scientific spelling come from ``recent.json``, which the
exporter already publishes with all species it has ever heard.

This walks the bucket, merges anything new into ``birds/sounds/archive.json``,
and leaves the exporter's own files alone. It is incremental — existing rows
are kept and only unseen clips are parsed — so it stays cheap to run often.
"""
import datetime
import json
import os
import re

S3_BUCKET = os.environ.get("BIRDS_S3_BUCKET", "birds-scott-ouellette")
S3_PREFIX = "birds"

CLIPS_PREFIX = "{}/sounds/clips/".format(S3_PREFIX)
ARCHIVE_KEY = "{}/sounds/archive.json".format(S3_PREFIX)
RECENT_KEY = "{}/sounds/recent.json".format(S3_PREFIX)
LOG_KEY = "{}/sounds/log.json".format(S3_PREFIX)

# sitta_carolinensis_62p_20261006T171811Z.m4a
CLIP_RE = re.compile(r"^(?P<slug>[a-z_\-]+?)_(?P<conf>\d+)p_(?P<ts>\d{8}T\d{6}Z)\.m4a$")

try:                                    # 3.9+; the Lambda runtime is 3.12
    from zoneinfo import ZoneInfo
    LOCAL_TZ = ZoneInfo("America/New_York")
except Exception:                       # noqa: BLE001 - fall back to UTC
    LOCAL_TZ = datetime.timezone.utc


# Taxa the station has recorded but has since dropped from its species list,
# so recent.json cannot name them. Six birds, 261 recordings — worth a literal
# rather than showing a visitor "Butorides virescens".
RETIRED = {
    "butorides_virescens": ("Green Heron", "Butorides virescens"),
    "numenius_phaeopus": ("Whimbrel", "Numenius phaeopus"),
    "piranga_olivacea": ("Scarlet Tanager", "Piranga olivacea"),
    "sayornis_phoebe": ("Eastern Phoebe", "Sayornis phoebe"),
    "hydroprogne_caspia": ("Caspian Tern", "Hydroprogne caspia"),
    "empidonax_minimus": ("Least Flycatcher", "Empidonax minimus"),
}


def _client():
    import boto3

    return boto3.client("s3")


def _get_json(s3, key):
    try:
        return json.loads(s3.get_object(Bucket=S3_BUCKET, Key=key)["Body"].read())
    except Exception:  # noqa: BLE001 - absent or unreadable is not fatal
        return None


def _slug(sci):
    """`Sitta carolinensis` -> `sitta_carolinensis`, the form clips are named in."""
    return re.sub(r"[^a-z]+", "_", (sci or "").lower()).strip("_")


def species_lookup(s3):
    """slug -> {common, sci, code}, from whatever the station has published.

    recent.json carries every species the station has ever heard; log.json
    fills in anything it has seen lately. A clip whose slug matches neither
    (a taxon renamed since it was recorded — Cooper's Hawk moved from
    Accipiter to Astur, and both spellings are in the bucket) still gets an
    entry built from its own filename, so it is browsable rather than lost.
    """
    out = {}
    recent = _get_json(s3, RECENT_KEY) or {}
    for sp in recent.get("species") or []:
        sci = sp.get("sci")
        if not sci:
            continue
        out[_slug(sci)] = {"common": sp.get("common") or sci,
                           "sci": sci, "code": sp.get("code") or ""}
        # the representative clip pins the slug actually used on disk, which
        # can differ from the slugified scientific name
        audio = sp.get("audio") or ""
        m = re.match(r"(.+?)_\d+p_", audio)
        if m:
            out.setdefault(m.group(1), out[_slug(sci)])
    for slug, (common, sci) in RETIRED.items():
        out.setdefault(slug, {"common": common, "sci": sci, "code": ""})
    for row in (_get_json(s3, LOG_KEY) or {}).get("log") or []:
        m = re.match(r"(.+?)_\d+p_", row.get("audio") or "")
        if m and m.group(1) not in out and row.get("common"):
            out[m.group(1)] = {"common": row["common"], "sci": row.get("sci") or "",
                               "code": row.get("code") or ""}
    return out


def _row(name, names):
    m = CLIP_RE.match(name)
    if not m:
        return None
    slug, conf, ts = m.group("slug"), int(m.group("conf")), m.group("ts")
    try:
        when = datetime.datetime.strptime(ts, "%Y%m%dT%H%M%SZ").replace(
            tzinfo=datetime.timezone.utc).astimezone(LOCAL_TZ)
    except ValueError:
        return None
    sp = names.get(slug) or {}
    # Unknown slug: show the scientific name rather than dropping the
    # recording. `buteo_jamaicensis` -> `Buteo jamaicensis`.
    sci = sp.get("sci") or slug.replace("_", " ").capitalize()
    return {
        "audio": name,
        "spec": name[:-4] + "_v3.png",
        "common": sp.get("common") or sci,
        "sci": sci,
        "code": sp.get("code") or "",
        "conf": round(conf / 100.0, 2),
        "t": when.isoformat(),
        "new": False,
        "node": sp.get("node") or "",
        "verified": "unverified",
    }


def build(s3=None, write=True):
    """Merge every clip in the bucket into the archive. Returns (rows, added)."""
    s3 = s3 or _client()
    existing = _get_json(s3, ARCHIVE_KEY) or {}
    rows = existing.get("log") or []
    seen = {r.get("audio") for r in rows}

    names = species_lookup(s3)
    added = 0
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=CLIPS_PREFIX):
        for obj in page.get("Contents") or []:
            name = obj["Key"].rsplit("/", 1)[-1]
            if not name.endswith(".m4a") or name in seen:
                continue
            row = _row(name, names)
            if row:
                rows.append(row)
                seen.add(name)
                added += 1

    rows.sort(key=lambda r: r.get("t") or "", reverse=True)
    payload = {
        "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "count": len(rows),
        "log": rows,
    }
    if write:
        s3.put_object(Bucket=S3_BUCKET, Key=ARCHIVE_KEY,
                      Body=json.dumps(payload, separators=(",", ":")).encode(),
                      ContentType="application/json",
                      CacheControl="public, max-age=300")
    return rows, added


def refresh(event=None, context=None):
    """Lambda entry point. Deliberately NOT folded into the daily Instagram
    sync, which raises when the IG token is missing — the recordings archive
    should not go stale because a social token lapsed.
    """
    rows, added = build()
    return {"count": len(rows), "added": added,
            "span": [rows[-1]["t"][:10], rows[0]["t"][:10]] if rows else []}


if __name__ == "__main__":
    import sys

    dry = "--dry-run" in sys.argv
    rows, added = build(write=not dry)
    span = (rows[-1]["t"][:10], rows[0]["t"][:10]) if rows else ("?", "?")
    print("archive: %d recordings, %s .. %s (%d new)%s"
          % (len(rows), span[0], span[1], added, " [dry run]" if dry else ""))
