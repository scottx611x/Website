"""Verify archived originals really are the photo they claim to be.

    BIRDS_USE_S3=1 .venv/bin/python tools/verify_originals.py [--since ISO] [--delete]

The crop-aware (ORB) matcher produced at least one false positive: a posted
close-up of a grackle was archived against a distant bird on bare branches.
Sparse sky-and-twig images carry little structure, so raw keypoint counts climb
on coincidence alone -- the same weakness that made the dhash cutoff unsafe at
d=8.

Raw match COUNT is the wrong test. A genuine crop is related to its original by
a homography: every matching keypoint must agree on one consistent transform.
So fit one with RANSAC and count INLIERS. A real crop yields a tight,
high-inlier fit; a coincidental match scatters and collapses.

A wrong original is worse than a missing one -- it prints the wrong photograph
and nothing downstream questions it -- so anything that fails is removed and the
frame simply goes back to being unarchived.
"""
import argparse
import io
import os
import subprocess
import sys
import urllib.request

sys.path.insert(0, "/Users/scott/Website")
import numpy as np  # noqa: E402
import cv2  # noqa: E402
import birds  # noqa: E402

if not os.environ.get("BIRDS_USE_S3"):
    sys.exit("BIRDS_USE_S3=1 is required.")

BUCKET = os.environ.get("BIRDS_S3_BUCKET", "birds-scott-ouellette")
ORB = cv2.ORB_create(2000)
BF = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)


def gray(data, side=640):
    arr = np.frombuffer(data, np.uint8)
    im = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if im is None:
        return None
    h, w = im.shape
    sc = float(side) / max(h, w)
    return cv2.resize(im, (max(1, int(w * sc)), max(1, int(h * sc))))


def inliers(a, b):
    """RANSAC homography inliers between posted frame and claimed original."""
    if a is None or b is None:
        return 0
    k1, d1 = ORB.detectAndCompute(a, None)
    k2, d2 = ORB.detectAndCompute(b, None)
    if d1 is None or d2 is None or len(k1) < 10 or len(k2) < 10:
        return 0
    m = [x for x in BF.match(d1, d2) if x.distance < 56]
    if len(m) < 12:
        return 0
    src = np.float32([k1[x.queryIdx].pt for x in m]).reshape(-1, 1, 2)
    dst = np.float32([k2[x.trainIdx].pt for x in m]).reshape(-1, 1, 2)
    H, mask = cv2.findHomography(src, dst, cv2.RANSAC, 4.0)
    if H is None or mask is None:
        return 0
    return int(mask.sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2026-10-13T18:00:00Z")
    ap.add_argument("--delete", action="store_true")
    ap.add_argument("--min-inliers", type=int, default=25)
    args = ap.parse_args()

    out = subprocess.run(
        ["aws", "s3api", "list-objects-v2", "--bucket", BUCKET,
         "--prefix", "birds/originals/",
         "--query", "Contents[?LastModified>=`%s`].Key" % args.since,
         "--output", "text"], capture_output=True, text=True).stdout
    keys = [k for k in out.split() if k.endswith(".jpg")]
    print("  candidates: %d" % len(keys))

    g = birds._load_gallery_uncached()
    shots = g[0] if isinstance(g, tuple) else g
    thumb = {}
    for s in shots:
        for im in (s.get("images") or []):
            u = im.get("url") if isinstance(im, dict) else str(im)
            k = birds.original_key(u)
            if k:
                thumb[k] = birds.thumb_url(u)

    import boto3
    s3 = boto3.client("s3")
    bad, good, skipped = [], 0, 0
    for n, key in enumerate(keys, 1):
        turl = thumb.get(key)
        if not turl:
            skipped += 1
            continue
        try:
            with urllib.request.urlopen(turl, timeout=30) as r:
                a = gray(r.read())
            b = gray(s3.get_object(Bucket=BUCKET, Key=key)["Body"].read())
        except Exception as exc:  # noqa: BLE001
            print("  ! %s (%s)" % (key, exc))
            continue
        k = inliers(a, b)
        if k >= args.min_inliers:
            good += 1
        else:
            bad.append((key, k))
            print("  SUSPECT %-30s inliers=%d" % (key.rsplit("/", 1)[-1], k))
        if n % 50 == 0:
            print("    ...%d/%d checked" % (n, len(keys)), flush=True)

    print()
    print("  verified ok : %d" % good)
    print("  suspect     : %d" % len(bad))
    print("  no frame    : %d" % skipped)
    if bad and args.delete:
        for key, _k in bad:
            s3.delete_object(Bucket=BUCKET, Key=key)
        print("  deleted %d wrong originals (frames revert to unarchived)" % len(bad))


if __name__ == "__main__":
    main()
