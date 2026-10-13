"""Collect a batch of Lightroom exports into the Glacier originals archive.

    BIRDS_USE_S3=1 .venv/bin/python tools/collect_exports.py --since <snapshot.txt>
                                                             [--keep] [--dry-run]

Scott exports a shoot day out of Lightroom into the birbs folder ($BIRBS_DIR,
default ~/Desktop/birbs); this takes it
from there. For each newly-appeared file:

    hash it (crop-tolerant) -> find the frame it belongs to -> upload as that
    frame's original -> delete the local copy

Matching is the same crop-tolerant scheme as tools/match_originals.py: the
posted copy is usually cropped to 4:5 or 1:1 for Instagram, so the export is
hashed at each aspect Instagram actually serves and compared against the web
thumbnail. Only frames that currently LACK an original are candidates, so a
re-export can never overwrite an archived original with a different photo.

Exports that match nothing are left on disk and reported — they are simply
photos from that day that were never posted, which is expected: a day with 17
missing frames usually holds 30-odd shots.
"""
import argparse
import io
import json
import os
import sys
import urllib.request

sys.path.insert(0, "/Users/scott/Website")
from PIL import Image  # noqa: E402
import birds  # noqa: E402

if not os.environ.get("BIRDS_USE_S3"):
    sys.exit("BIRDS_USE_S3=1 is required — without it every frame looks missing.")

BIRBS = os.environ.get("BIRBS_DIR") or os.path.expanduser("~/Desktop/birbs")
BUCKET = os.environ.get("BIRDS_S3_BUCKET", "birds-scott-ouellette")
CACHE = os.path.join(os.path.dirname(BIRBS), ".lr_backfill_targets.json")
ASPECTS = [None, 0.800, 0.847, 1.000, 1.250]
Image.MAX_IMAGE_PIXELS = None


def dhash(im, s=8):
    im = im.convert("L").resize((s + 1, s), Image.LANCZOS)
    px = list(im.getdata())
    b = 0
    for r in range(s):
        for c in range(s):
            b = (b << 1) | (px[r * (s + 1) + c] < px[r * (s + 1) + c + 1])
    return b


def crop_to(im, ar):
    w, h = im.size
    if ar is None:
        return im
    if w / h > ar:
        nw = int(h * ar)
        return im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    nh = int(w / ar)
    return im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))


def ham(a, b):
    return bin(a ^ b).count("1")


# ---- crop-aware second stage -------------------------------------------
# The dhash stage only tries CENTRE crops at Instagram's aspect ratios, so a
# frame cropped off-centre is invisible to it -- proven: a posted 4:5 shot of a
# bird over a snowy field scored d=16 against its own original, while ORB found
# 332 matching keypoints. Feature matching is crop- and scale-invariant, so it
# sees the posted frame INSIDE the wider original.
#
# Used only on exports the hash stage rejected: it is far slower, and the hash
# is already reliable for the uncropped majority.
_ORB = None


def _orb():
    global _ORB
    if _ORB is None:
        import cv2
        _ORB = (cv2.ORB_create(1200),
                cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True))
    return _ORB


def feat(path_or_bytes):
    import cv2
    import numpy as np
    arr = (np.frombuffer(path_or_bytes, np.uint8)
           if isinstance(path_or_bytes, bytes)
           else np.fromfile(path_or_bytes, np.uint8))
    im = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if im is None:
        return None
    h, w = im.shape
    sc = 480.0 / max(h, w)
    im = cv2.resize(im, (max(1, int(w * sc)), max(1, int(h * sc))))
    orb, _ = _orb()
    _k, d = orb.detectAndCompute(im, None)
    return d


def orb_score(d1, d2):
    """How many keypoints agree. >=120 has been a true match in every case
    checked by eye; burst frames of the same bird score well under that."""
    if d1 is None or d2 is None:
        return 0
    _, bf = _orb()
    try:
        return len([m for m in bf.match(d1, d2) if m.distance < 48])
    except Exception:  # noqa: BLE001
        return 0


def hash_local(path):
    with Image.open(path) as im:
        im.draft("L", (1024, 1024))
        im = im.convert("L")
        return [dhash(crop_to(im, a)) for a in ASPECTS]


def targets():
    """key -> hash of the posted copy, for frames with no archived original."""
    g = birds._load_gallery_uncached()
    shots = g[0] if isinstance(g, tuple) else g
    want = {}
    for s in shots:
        for im in (s.get("images") or []):
            u = im.get("url") if isinstance(im, dict) else str(im)
            key = birds.original_key(u)
            if key and not birds.has_original(u):
                want[key] = birds.thumb_url(u)

    cached = {}
    if os.path.exists(CACHE):
        cached = dict(json.load(open(CACHE)))
    out, fetched = {}, 0
    for key, url in want.items():
        if key in cached:
            out[key] = cached[key]
            continue
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                out[key] = dhash(Image.open(io.BytesIO(r.read())))
                fetched += 1
        except Exception:  # noqa: BLE001
            continue
    if fetched:
        json.dump(sorted(out.items()), open(CACHE, "w"))
    return out


def target_urls():
    """key -> posted thumbnail URL, for frames still lacking an original."""
    g = birds._load_gallery_uncached()
    shots = g[0] if isinstance(g, tuple) else g
    out = {}
    for s in shots:
        for im in (s.get("images") or []):
            u = im.get("url") if isinstance(im, dict) else str(im)
            key = birds.original_key(u)
            if key and not birds.has_original(u):
                out[key] = birds.thumb_url(u)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", required=True, help="file listing birbs before the export")
    ap.add_argument("--keep", action="store_true", help="do not delete matched locals")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-orb", action="store_true")
    args = ap.parse_args()

    before = {l.strip() for l in open(args.since) if l.strip()}
    now = set(os.listdir(BIRBS))
    new = sorted(n for n in now - before if n.lower().endswith((".jpg", ".jpeg")))
    print("  new exports found : %d" % len(new))
    if not new:
        return

    TH = targets()
    print("  frames still missing an original: %d" % len(TH))

    import boto3
    s3 = boto3.client("s3")

    # Score EVERY (export, frame) pair, then assign globally best-first.
    # A burst of near-identical shots otherwise lets whichever file is
    # processed first claim a frame at d=5 while the true d=0 match for that
    # same frame arrives later and gets pushed onto a different one. Each
    # export and each frame may be used at most once.
    pairs = []
    for name in new:
        try:
            hs = hash_local(os.path.join(BIRBS, name))
        except Exception as exc:  # noqa: BLE001
            print("  ! unreadable %s (%s)" % (name, exc))
            continue
        for key, th in TH.items():
            d = min(ham(th, x) for x in hs)
            if d <= 6:
                pairs.append((d, name, key))
    pairs.sort()

    # Anything the hash stage could not place gets a crop-aware second look.
    hashed_f = {name for _, name, _ in pairs}
    leftover = [n for n in new if n not in hashed_f]
    if leftover and not args.no_orb:
        print("  crop-aware pass over %d unmatched exports..." % len(leftover),
              flush=True)
        urls = target_urls()
        tfeat = {}
        for key in list(TH):
            try:
                with urllib.request.urlopen(urls[key], timeout=30) as r:
                    tfeat[key] = feat(r.read())
            except Exception:  # noqa: BLE001
                tfeat[key] = None
        for name in leftover:
            d1 = feat(os.path.join(BIRBS, name))
            for key, d2 in tfeat.items():
                sc = orb_score(d1, d2)
                if sc >= 120:
                    pairs.append((7, name, key))   # rank below any hash match
        pairs.sort()

    used_f, used_k, shipped = set(), set(), []
    for d, name, key in pairs:
        if name in used_f or key in used_k:
            continue
        used_f.add(name)
        used_k.add(key)
        path = os.path.join(BIRBS, name)
        if not args.dry_run:
            s3.upload_file(path, BUCKET, key,
                           ExtraArgs={"ContentType": "image/jpeg",
                                      "StorageClass": "GLACIER_IR"})
        shipped.append((name, key, d))
        print("  + %-26s -> %s  (d=%d)" % (name, key.rsplit("/", 1)[-1], d))
    unmatched = [(n, None) for n in new if n not in used_f]

    if not args.dry_run and not args.keep:
        for name, _, _ in shipped:
            os.remove(os.path.join(BIRBS, name))

    print()
    print("  archived   : %d" % len(shipped))
    print("  unmatched  : %d  (shots from that day that were never posted)"
          % len(unmatched))
    if not args.dry_run and not args.keep:
        print("  locals for the archived ones deleted; unmatched left in place")


if __name__ == "__main__":
    main()
