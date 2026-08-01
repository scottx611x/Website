#!/usr/bin/env python3
"""Backfill vision_species.json for ambiguous gallery posts with local CLIP.
Incremental + resumable: saves the store (repo file + S3) every few posts."""
import json, os, sys
sys.path.insert(0, "/Users/scott/Website")
import birds, bird_vision, boto3

LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else 0  # 0 = all
REPO = birds.VISION_FILE
KEY = birds._CURATION_S3[REPO]
s3 = boto3.client("s3")

shots = birds.load_gallery(shuffle=False)

IMG_BUCKET = "birds-scott-ouellette"  # the image bucket (S3_BUCKET is the zappa curation bucket)

def image_bytes(shot):  # fetch re-hosted images AUTHENTICATED (no anon rate-limit)
    n = len(shot.get("images") or [])
    out = []
    for i in range(n):
        key = "%s/images/%s-%d.jpg" % (birds.S3_PREFIX, shot["id"], i)
        try:
            out.append(s3.get_object(Bucket=IMG_BUCKET, Key=key)["Body"].read())
        except Exception:
            return None  # a missing image -> skip vision, keep caption heuristic
    return out

store = {}
if os.path.exists(REPO):
    try: store = json.load(open(REPO))
    except Exception: store = {}

amb = [s for s in shots if s.get("id") and s["id"] not in store
       and bird_vision.needs_vision(s, birds.caption_species(s.get("caption") or ""))]
print("to classify: %d posts (%d already cached)" % (len(amb), len(store)), flush=True)

def persist():
    raw = json.dumps(store, indent=2).encode()
    open(REPO, "wb").write(raw)
    s3.put_object(Bucket=birds.S3_BUCKET, Key=KEY, Body=raw,
                  ContentType="application/json", CacheControl="no-store")

done = 0
for s in amb:
    species = birds.caption_species(s.get("caption") or "")
    imgs = image_bytes(s)
    res = bird_vision.classify(imgs, species) if imgs else None
    if res:
        store[s["id"]] = res; done += 1
        print("  ✓ %s (%d): %s" % (s["id"], len(res), res), flush=True)
    else:
        print("  · %s unresolved — keeps caption heuristic" % s["id"], flush=True)
    if done and done % 5 == 0:
        persist(); print("  …saved (%d)" % done, flush=True)
    if LIMIT and done >= LIMIT:
        break
persist()
print("DONE: %d newly classified, store now %d posts" % (done, len(store)), flush=True)
