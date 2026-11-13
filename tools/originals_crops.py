"""Find where each posted frame sits inside its full-size original.

    BIRDS_USE_S3=1 .venv/bin/python tools/originals_crops.py [--limit N] [--redo]

The touch loupe in the detail view magnifies the full-size original under the
fingertip. That needs the original and the posted frame to line up. For every
post since mid-2026 they do: the pipeline exports at the post's own aspect, so
the original IS the posted framing. The historic backfill is different. There
the archive holds the whole exposure (6000x4000) and the post is a cut from it,
usually a centre square but often not: off-centre, or tight on the bird.

This finds the cut. Multi-scale template matching of the posted frame against
the original (normalised cross-correlation, coarse over the whole frame, then
fine around the best hit), giving a box in fractions of the original and a
score. A real crop scores 0.98-1.0; the site uses a box only at >= 0.9
(birds.CROP_MIN_SCORE), and a frame without one falls back to the web copy.

Unlike picking WHICH original goes with a frame (where coincidental matches on
empty sky did real damage — see originals_exif_check.py), the original is
already known here; this only asks where inside it to look. The score is the
check on that.

Results go to s3://<bucket>/birds/originals_crops.json, keyed by the
original's filename: {"box": [x0,y0,x1,y1] | null, "score": float, "same": bool}.
"same" means the shapes already agree and no box is needed. Saved every 25
frames, and frames already in the file are skipped, so it can be stopped and
re-run. It reads only the head of each original first (for its dimensions),
and downloads the whole file only when the shapes differ.
"""
import argparse
import io
import json
import os
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import birds  # noqa: E402

SAME = 0.02   # aspect ratios within 2% need no box


def _get(url, head=None):
    hdr = {"Range": "bytes=0-%d" % head} if head else {}
    for k in range(4):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=hdr),
                                          timeout=180).read()
        except Exception:  # noqa: BLE001
            if k == 3:
                raise
            time.sleep(2 * (k + 1))


def _gray(img, long_side):
    img.draft("L", (long_side, long_side))
    g = img.convert("L")
    s = long_side / max(g.size)
    if s < 1:
        g = g.resize((round(g.size[0] * s), round(g.size[1] * s)), Image.LANCZOS)
    return np.asarray(g, dtype=np.float32)


def locate(web_bytes, orig_bytes):
    """(score, [x0, y0, x1, y1]) of the posted frame inside the original."""
    W = _gray(Image.open(io.BytesIO(web_bytes)), 1440)
    aw = W.shape[1] / W.shape[0]
    best = None
    for L, fine in ((640, False), (1600, True)):
        O = _gray(Image.open(io.BytesIO(orig_bytes)), L)
        oh, ow = O.shape
        cmax = min(ow, oh * aw)
        if not fine:
            widths, region = np.geomspace(0.2 * cmax, cmax, 48), (0, 0, ow, oh)
        else:
            bx0, by0, bx1, by1 = best[1]
            cw0 = (bx1 - bx0) * ow
            widths = np.linspace(cw0 * 0.96, min(cmax, cw0 * 1.04), 21)
            pad = 0.03
            region = (max(0, int((bx0 - pad) * ow)), max(0, int((by0 - pad) * oh)),
                      min(ow, int((bx1 + pad) * ow) + 1), min(oh, int((by1 + pad) * oh) + 1))
        sub = O[region[1]:region[3], region[0]:region[2]]
        top = None
        for cw in widths:
            tw, th = int(round(cw)), int(round(cw / aw))
            if tw < 24 or th < 24 or tw > sub.shape[1] or th > sub.shape[0]:
                continue
            T = cv2.resize(W, (tw, th), interpolation=cv2.INTER_AREA)
            _, mx, _, loc = cv2.minMaxLoc(cv2.matchTemplate(sub, T, cv2.TM_CCOEFF_NORMED))
            if top is None or mx > top[0]:
                x0, y0 = loc[0] + region[0], loc[1] + region[1]
                top = (float(mx), [x0 / ow, y0 / oh, (x0 + tw) / ow, (y0 + th) / oh])
        if top:
            best = top
    return best[0], [round(min(1.0, max(0.0, v)), 5) for v in best[1]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--redo", action="store_true", help="ignore existing results")
    args = ap.parse_args()
    if not os.environ.get("BIRDS_USE_S3"):
        sys.exit("BIRDS_USE_S3=1 is required.")
    import boto3
    s3 = boto3.client("s3")
    key = "%s/%s" % (birds.S3_PREFIX, birds.ORIGINAL_CROPS_KEY)
    try:
        done = {} if args.redo else json.loads(
            s3.get_object(Bucket=birds.S3_BUCKET, Key=key)["Body"].read())
    except Exception:  # noqa: BLE001
        done = {}

    g = birds._load_gallery_uncached()
    shots = g[0] if isinstance(g, tuple) else g
    todo, seen = [], set(done)
    for s in shots:
        for u, v in zip(s.get("images") or [], (s.get("image_videos") or []) + [None] * 99):
            k = birds.original_key(u)
            if v or not k or not birds.has_original(u):
                continue
            name = k.rsplit("/", 1)[-1]
            if name not in seen:
                seen.add(name)
                todo.append((name, u, k))
    if args.limit:
        todo = todo[:args.limit]
    print("%d frames to check (%d already done)" % (len(todo), len(done)), flush=True)

    def one(name, url, k):
        web = _get(url)
        signed = s3.generate_presigned_url("get_object", Params={
            "Bucket": birds.S3_BUCKET, "Key": k}, ExpiresIn=3600)
        wsz = Image.open(io.BytesIO(web)).size
        osz = Image.open(io.BytesIO(_get(signed, head=600_000))).size
        if abs((wsz[0] / wsz[1]) / (osz[0] / osz[1]) - 1) < SAME:
            return name, {"box": None, "score": 1.0, "same": True}
        score, box = locate(web, _get(signed))
        return name, {"box": box, "score": round(score, 4), "same": False}

    def save():
        s3.put_object(Bucket=birds.S3_BUCKET, Key=key, Body=json.dumps(done).encode(),
                      ContentType="application/json", CacheControl="no-store")

    n = cropped = weak = failed = 0
    with ThreadPoolExecutor(args.workers) as ex:
        futs = [ex.submit(one, *t) for t in todo]
        for f in as_completed(futs):
            n += 1
            try:
                name, res = f.result()
            except Exception as e:  # noqa: BLE001
                failed += 1
                print("  failed: %s" % str(e)[:80], flush=True)
                continue
            done[name] = res
            if not res["same"]:
                cropped += 1
                if res["score"] < birds.CROP_MIN_SCORE:
                    weak += 1
                    print("  weak %.3f %s" % (res["score"], name), flush=True)
            if n % 25 == 0:
                save()
                print("  %d/%d  cropped %d  weak %d  failed %d" % (n, len(todo), cropped, weak, failed),
                      flush=True)
    save()
    print("done: %d checked, %d cropped (%d too weak to use), %d failed"
          % (n, cropped, weak, failed))


if __name__ == "__main__":
    main()
