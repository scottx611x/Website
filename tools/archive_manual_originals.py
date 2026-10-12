"""Backfill full-size originals for manually-added bird posts.

    BIRDS_USE_S3=1 .venv/bin/python tools/archive_manual_originals.py [--dry-run]

Manual posts (birds_manual.py) bypass the pipeline, and the pipeline is where
``archive_originals()`` lives — so every manually-added frame reached the site
with no original in Glacier. That was all 63 of them, including the eleven
Kestrels.

birds_manual names each uploaded image ``<sha1(source bytes)[:12]>.jpg``, and
``birds.original_key()`` maps ``images/<name>`` to ``originals/<name>``. So the
backfill is a content-hash lookup: hash every candidate source file we still
have on disk, and whatever matches an unarchived manual frame IS that frame's
original, byte for byte. No inference, no perceptual hashing.

Going forward birds_manual.py archives as it uploads, so this only ever has to
clean up what predates that.
"""
import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, "/Users/scott/Website")
import birds  # noqa: E402

if not os.environ.get("BIRDS_USE_S3"):
    sys.exit("BIRDS_USE_S3=1 is required — without it has_original() sees an "
             "empty archive and reports everything as missing.")

BUCKET = os.environ.get("BIRDS_S3_BUCKET", "birds-scott-ouellette")
SOURCE_DIRS = [os.path.expanduser("~/Desktop/birbs"),
               os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "birds_incoming")]
EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def source_index(dirs):
    """sha1(bytes)[:12] -> path, for every candidate source file."""
    idx = {}
    for d in dirs:
        for root, _dirs, files in os.walk(d):
            for name in files:
                if os.path.splitext(name)[1].lower() not in EXTS:
                    continue
                p = os.path.join(root, name)
                try:
                    with open(p, "rb") as fh:
                        idx.setdefault(hashlib.sha1(fh.read()).hexdigest()[:12], p)
                except OSError:
                    continue
    return idx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    manual = birds._load_manual_birds()
    frames = [(e.get("id"), u) for e in manual for u in (e.get("images") or [])]
    missing = [(pid, u) for pid, u in frames if not birds.has_original(u)]
    print("  manual frames        : %d" % len(frames))
    print("  already archived     : %d" % (len(frames) - len(missing)))
    print("  missing an original  : %d" % len(missing))
    if not missing:
        return

    idx = source_index(SOURCE_DIRS)
    print("  candidate source files: %d" % len(idx))

    import boto3
    s3 = boto3.client("s3")
    done = skipped = 0
    for pid, url in missing:
        name = url.rsplit("/", 1)[-1]            # <img_id>.jpg
        img_id = os.path.splitext(name)[0]
        path = idx.get(img_id)
        if not path:
            skipped += 1
            continue
        key = birds.original_key(url)
        size = os.path.getsize(path)
        print("    %s  <- %s  (%.1f MB)%s"
              % (key.rsplit("/", 1)[-1], os.path.basename(path), size / 1e6,
                 " [dry run]" if args.dry_run else ""))
        if not args.dry_run:
            # GLACIER_IR: these are cold archival copies, read once a year at
            # print time, and the retrieval fee is dwarfed by the storage saved.
            s3.upload_file(path, BUCKET, key,
                           ExtraArgs={"ContentType": "image/jpeg",
                                      "StorageClass": "GLACIER_IR"})
        done += 1
    print("  archived : %d" % done)
    print("  no source on disk: %d" % skipped)


if __name__ == "__main__":
    main()
