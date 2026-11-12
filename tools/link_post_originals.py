"""Connect posts to the full-size originals the pipeline archived for them.

    BIRDS_USE_S3=1 .venv/bin/python tools/link_post_originals.py            # dry run
    BIRDS_USE_S3=1 .venv/bin/python tools/link_post_originals.py --upload   # backfill by-file/ from disk
    BIRDS_USE_S3=1 .venv/bin/python tools/link_post_originals.py --apply    # write the links
    BIRDS_USE_S3=1 .venv/bin/python tools/link_post_originals.py --audit    # re-check existing links too

The pipeline uploads each export as originals/by-file/<filename> when it queues
a post. The site then copies it to originals/<post>-<i>.jpg, the name the
full-size link uses. That step needed the exact caption, so a caption edited
after queueing left the files stranded in by-file/ and the post with no
full-size links. Records queued before archiving existed (2026-10-08) never had
their files uploaded at all.

Note: a post's images list is NOT in carousel order — the frame's own URL
(<post>-<k>.jpg) says which frame it is. Always name the original with
birds.original_key(url), never <post>-<list index>.

The daily sync now does this with birds.link_post_originals, which matches
frames by what they look like. This tool runs the same matching on demand,
reading exports from ~/Desktop/birbs when they are there (free) instead of S3.

--upload  pushes record files missing from by-file/ from ~/Desktop/birbs as
          GLACIER_IR, the way the pipeline does — for records queued before
          archiving existed (2026-10-08).
--audit   also re-checks frames that ALREADY have an original. A link is
          called wrong only when its bytes are a copy of a DIFFERENT export in
          the same record (a server-side copy keeps the size); with --apply it
          is replaced. Originals from other sources are not judged.
"""
import argparse
import io
import os
import sys
import urllib.parse
import urllib.request

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import birds  # noqa: E402

BIRBS = os.path.expanduser("~/Desktop/birbs")


def fetch(url):
    """Prefer the local export over downloading it from S3."""
    path = urllib.parse.urlparse(url).path
    if "/originals/by-file/" in path:
        local = os.path.join(BIRBS, urllib.parse.unquote(path.rsplit("/", 1)[-1]))
        if os.path.exists(local):
            return Image.open(local)
    return Image.open(io.BytesIO(urllib.request.urlopen(url, timeout=120).read()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--upload", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--audit", action="store_true")
    args = ap.parse_args()
    if not os.environ.get("BIRDS_USE_S3"):
        sys.exit("BIRDS_USE_S3=1 is required.")
    import boto3
    s3 = boto3.client("s3")
    bucket, pre = birds.S3_BUCKET, birds.S3_PREFIX

    g = birds._load_gallery_uncached()
    shots = g[0] if isinstance(g, tuple) else g
    records = birds._load_post_records()
    byfile = birds._by_file_names()

    sizes = {}
    def size(key):
        if key not in sizes:
            try:
                sizes[key] = s3.head_object(Bucket=bucket, Key=key)["ContentLength"]
            except Exception:  # noqa: BLE001
                sizes[key] = None
        return sizes[key]

    work = []
    for si, ri in birds._pair_posts_with_records(shots, records):
        shot = shots[si]
        missing = [i for i, u in enumerate(shot["images"]) if not birds.has_original(u)]
        if missing or args.audit:
            work.append((shot, records[ri], missing))
    work.sort(key=lambda w: w[0].get("timestamp") or "", reverse=True)

    totals = {"linked": 0, "fixed": 0, "unmatched": 0, "wrong": 0, "foreign": 0}
    for shot, rec, missing in work:
        names = [(f or "").rsplit("/", 1)[-1] for f in rec["files"]]
        if args.upload and missing:
            for n in names:
                local = os.path.join(BIRBS, n)
                if n not in byfile and os.path.exists(local):
                    s3.upload_file(local, bucket, "%s/originals/by-file/%s" % (pre, n),
                                   ExtraArgs={"StorageClass": "GLACIER_IR",
                                              "ContentType": "image/jpeg",
                                              "Metadata": {"original": n}})
                    byfile.add(n)
                    print("   uploaded %s" % n)
        # In a dry run, judge files still only on disk as if uploaded.
        avail = [n for n in names if n in byfile or
                 (not args.upload and os.path.exists(os.path.join(BIRBS, n)))]
        frames = list(range(len(shot["images"]))) if args.audit else missing
        if not avail or not frames:
            continue
        got = birds._assign_frames(shot, avail, frames, fetch=fetch)
        lines = []
        for i in frames:
            dst = birds.original_key(shot["images"][i])   # NOT <post>-<list index>
            name = got.get(i)
            if i in missing:
                if not name:
                    lines.append("    %-26s no confident match — left alone" % dst.rsplit("/", 1)[-1])
                    totals["unmatched"] += 1
                    continue
                act = "link"
                totals["linked"] += 1
            else:
                if not name:
                    continue
                def fsize(n):
                    return (size("%s/originals/by-file/%s" % (pre, n)) if n in byfile
                            else os.path.getsize(os.path.join(BIRBS, n)))
                have = size(dst)
                if have == fsize(name):
                    continue
                # Only call it wrong when the bytes are provably a copy of a
                # DIFFERENT frame of this post. An original that matches no
                # record file came from somewhere else (a Lightroom re-export,
                # the historic backfill) and size says nothing about it.
                other = [n for n in avail if n != name and fsize(n) == have]
                if not other:
                    totals["foreign"] += 1
                    continue
                act = "WRONG FILE (is %s), replace" % other[0]
                totals["wrong"] += 1
            lines.append("    %-26s <- %-22s %s" % (dst.rsplit("/", 1)[-1], name, act))
            if args.apply and name in byfile:
                birds._copy_original(name, dst)
                if act != "link":
                    totals["fixed"] += 1
        if lines:
            print("%s  %s  %r" % ((shot.get("timestamp") or "")[:10], shot["id"],
                                 (shot.get("caption") or "").split("\n")[0][:40]))
            print("\n".join(lines))
    print("\nframes to link: %(linked)d   unmatched: %(unmatched)d   "
          "wrong existing links: %(wrong)d   from another source (not judged): %(foreign)d" % totals)
    if not args.apply:
        print("dry run — nothing linked. --upload backfills from disk, --apply writes.")


if __name__ == "__main__":
    main()
