"""Rebuild birds/sounds/media_index.json from the clips actually in S3.

The exporter's index (clipName -> {audio, spec}) is meant to grow forever, but a
failed read used to make a run start from {} and overwrite it, forgetting every
older clip while the files themselves stayed in S3. This lists clips/ and merges
what it finds UNDER the live index (live entries win), so it only ever adds.

    python tools/rebuild_media_index.py           # dry run: counts only
    python tools/rebuild_media_index.py --write   # back up, then upload the merge

Needs ListBucket on the bucket (your own creds, not the Pi's scoped key). The
exporter on the Pi picks the restored entries up on its next 60s pass and
rebuilds species_clips.json from them.
"""
import json
import os
import re
import sys
import time

import boto3

BUCKET = os.environ.get("BIRDS_S3_BUCKET", "birds-scott-ouellette")
INDEX_KEY = "birds/sounds/media_index.json"
CLIP_PREFIX = "birds/sounds/clips/"
_MEDIA = re.compile(r"(.+?)(\.m4a|_v3\.png|_v2\.png)$")


def listed_refs(s3):
    refs = {}
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix=CLIP_PREFIX):
        for o in page.get("Contents", []):
            name = o["Key"][len(CLIP_PREFIX):]
            m = _MEDIA.match(name)
            if not m:
                continue
            base, ext = m.groups()
            r = refs.setdefault(base + ".wav", {})
            if ext == ".m4a":
                r["audio"] = name
            elif ext == "_v3.png":
                r["spec"] = name
            else:
                r.setdefault("spec", name)  # _v2 only when there is no _v3
    return refs


def merge(listed, live):
    out = dict(listed)
    for k, v in live.items():
        if v or k not in out:
            out[k] = v
    return out


def main():
    write = "--write" in sys.argv
    s3 = boto3.client("s3")
    raw = s3.get_object(Bucket=BUCKET, Key=INDEX_KEY)["Body"].read()
    live = json.loads(raw)
    listed = listed_refs(s3)
    merged = merge(listed, live)
    print("live %d · in S3 %d · merged %d (+%d)" % (len(live), len(listed), len(merged),
                                                     len(merged) - len(live)))
    if not write:
        print("dry run; pass --write to upload")
        return
    backup = "%s.bak-%d" % (INDEX_KEY, int(time.time()))
    s3.put_object(Bucket=BUCKET, Key=backup, Body=raw, ContentType="application/json")
    s3.put_object(Bucket=BUCKET, Key=INDEX_KEY,
                  Body=json.dumps(merged, separators=(",", ":")).encode(),
                  ContentType="application/json", CacheControl="no-cache")
    print("backed up to %s, wrote %s" % (backup, INDEX_KEY))


if __name__ == "__main__":
    main()
