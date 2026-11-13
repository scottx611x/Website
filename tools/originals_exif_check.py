"""Does each archived original's CAPTURE DATE match the frame it is named for?

    BIRDS_USE_S3=1 .venv/bin/python tools/originals_exif_check.py [--suspect]

The pixel-matching route (verify_originals.py, and a dhash variant that should
never have been written) is guesswork dressed up as measurement: a published
frame is a crop, often of empty sky, and both keypoints and hashes match on
coincidence there. lightroom_catalog.py already said the right thing —

    "Capture date is a far better signal than image content: an export can be
     cropped beyond recognition, but it cannot change the day it was taken."

— and it applies just as well to the archived JPEG, which carries the camera's
EXIF DateTimeOriginal. So compare that to the capture date the site already
knows for the frame. Same day: the original belongs to that frame, whatever it
was cropped to. Different day: it is a different shoot, full stop. No
thresholds, no calibration, nothing to tune.

Cheap, too. EXIF sits at the head of the file, so this reads a range request of
a few hundred KB instead of pulling a 16 MB exposure.

Blind spots, stated plainly: it cannot separate two frames from the SAME
shoot — a burst sibling shares the day — and a frame whose own capture date is
unknown cannot be judged at all. It is a sieve for wrong SHOOTS, which is where
the hash backfill did its damage.
"""
import argparse
import io
import os
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import birds  # noqa: E402

HEAD_BYTES = 400_000          # EXIF lives at the head of the JPEG


def exif_day(url):
    """YYYY-MM-DD from DateTimeOriginal, or None."""
    req = urllib.request.Request(url, headers={"Range": "bytes=0-%d" % HEAD_BYTES})
    raw = urllib.request.urlopen(req, timeout=120).read()
    try:
        ex = Image.open(io.BytesIO(raw)).getexif()
    except Exception:  # noqa: BLE001 - a truncated head still yields EXIF
        return None
    if not ex:
        return None
    sub = ex.get_ifd(0x8769) if hasattr(ex, "get_ifd") else {}
    val = sub.get(36867) or sub.get(36868) or ex.get(306)
    if not val:
        return None
    return str(val)[:10].replace(":", "-")


def frame_day(shot, i):
    """The capture day the site shows for this frame."""
    dates = shot.get("image_dates") or []
    if i < len(dates) and dates[i]:
        return str(dates[i])[:10]
    d = birds._frame_dates(shot)[i] if i < len(shot.get("images") or []) else None
    if d:
        return d.isoformat()[:10]
    return (shot.get("_sort") or "")[:10] or None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--suspect", action="store_true",
                    help="check birds/originals_suspect/ instead (did we quarantine wrongly?)")
    args = ap.parse_args()
    if not os.environ.get("BIRDS_USE_S3"):
        sys.exit("BIRDS_USE_S3=1 is required.")

    import boto3
    s3 = boto3.client("s3")
    prefix = "birds/originals_suspect/" if args.suspect else "birds/originals/"

    todo, seen = [], set()
    for shot in birds.load_gallery(shuffle=False):
        for i, url in enumerate(shot.get("images") or []):
            key = birds.original_key(url)
            if not key:
                continue
            name = key.rsplit("/", 1)[-1]
            if name in seen:
                continue
            seen.add(name)
            todo.append((name, frame_day(shot, i), shot.get("location")))
    if args.suspect:
        have = set()
        for page in s3.get_paginator("list_objects_v2").paginate(
                Bucket=birds.S3_BUCKET, Prefix=prefix):
            for o in page.get("Contents", []):
                have.add(o["Key"].rsplit("/", 1)[-1])
        todo = [t for t in todo if t[0] in have]
    else:
        todo = [t for t in todo
                if birds.has_original("https://x/birds/images/" + t[0])]
    if args.limit:
        todo = todo[:args.limit]
    print("checking %d originals under %s\n" % (len(todo), prefix))

    def one(name, fday, loc):
        url = s3.generate_presigned_url(
            "get_object", Params={"Bucket": birds.S3_BUCKET, "Key": prefix + name},
            ExpiresIn=7200)
        try:
            eday = exif_day(url)
        except Exception as e:  # noqa: BLE001
            return name, fday, None, loc, "fetch: %s" % str(e)[:40]
        return name, fday, eday, loc, ""

    rows = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(one, n, d, l): n for n, d, l in todo}
        for f in as_completed(list(futs)):
            rows.append(f.result())
            futs.pop(f)

    import datetime as _dt
    import json

    def delta(a, b):
        try:
            return abs((_dt.date.fromisoformat(a) - _dt.date.fromisoformat(b)).days)
        except Exception:  # noqa: BLE001
            return None

    known = [r for r in rows if r[2] and r[1]]
    unknown = [r for r in rows if not r[2] or not r[1]]
    scored = [(delta(r[1], r[2]), r) for r in known]
    same = [r for d, r in scored if d == 0]
    # EXIF is the camera's LOCAL time; the frame's date comes from the caption
    # or the post. An evening shot therefore lands a day apart with nothing
    # wrong, and whole posts shift together when it does — so one day is noise,
    # not evidence. Two or more days apart is a different shoot.
    tz = [(d, r) for d, r in scored if d in (1,)]
    wrong = sorted([(d, r) for d, r in scored if d and d >= 2], key=lambda x: -x[0])

    print("WRONG SHOOT — capture day differs by 2+ days (%d):" % len(wrong))
    for d, (name, fday, eday, loc, _) in wrong:
        print("   %-30s frame %s   original %s   %4d days   %s"
              % (name, fday, eday, d, (loc or "")[:24]))
    print("\nsame day              : %d" % len(same))
    print("one day apart (tz)    : %d  — treated as noise, whole posts shift together" % len(tz))
    print("unknown               : %d  (no EXIF, or no capture date)" % len(unknown))
    json.dump([r[0] for _, r in wrong], open("/tmp/exif_wrong.json", "w"), indent=1)
    print("\nwrote /tmp/exif_wrong.json")


if __name__ == "__main__":
    main()
