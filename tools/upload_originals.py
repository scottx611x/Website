"""Upload matched full-res originals to S3, mirroring the web copies' names.

birds/originals/<post_id>-<index>.jpg sits beside birds/images/<post_id>-<index>.jpg,
so the site can offer the full frame for anything it already shows. Straight to
GLACIER_IR: millisecond retrieval (so the site can serve it), ~1/6 the price of
Standard, and these files are ~16 MB so the 128 KB transition minimum is moot.

The original Lightroom filename rides along as object metadata, so a frame can
always be traced back to the export it came from.
"""
import json, os, sys, boto3
from concurrent.futures import ThreadPoolExecutor
from botocore.exceptions import ClientError

B = "birds-scott-ouellette"
PREFIX = "birds/originals/"
rows = json.load(open("/tmp/orig_map.json"))
limit = int(sys.argv[1]) if len(sys.argv) > 1 else 0
if limit: rows = rows[:limit]

s3 = boto3.client("s3")

def have(key):
    try:
        s3.head_object(Bucket=B, Key=key); return True
    except ClientError:
        return False

done = skipped = failed = 0
def put(r):
    global done, skipped, failed
    key = "%s%s-%d.jpg" % (PREFIX, r["post"], r["idx"])
    if have(key):
        skipped += 1; return
    try:
        s3.upload_file(r["file"], B, key, ExtraArgs={
            "StorageClass": "GLACIER_IR",
            "ContentType": "image/jpeg",
            "Metadata": {"original": os.path.basename(r["file"]),
                         "match-distance": str(r.get("d", 0))},
        })
        done += 1
    except Exception as e:
        failed += 1
        print("   FAIL %s: %s" % (key, str(e)[:80]))

with ThreadPoolExecutor(6) as ex:
    list(ex.map(put, rows))
print("  uploaded %d, skipped %d (already there), failed %d" % (done, skipped, failed))
