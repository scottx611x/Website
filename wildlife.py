#!/usr/bin/env python3
"""Publish non-bird wildlife photos to the /photography gallery.

The birds gallery comes from Instagram; this is the manual path for everything
else (mammals, reptiles, insects, macro, landscapes) straight from raw files.

Usage:
    # drop photos into wildlife_incoming/<Category>/  (folder name = category),
    # name the files for the subject ("Red Fox.jpg", "red-fox-ipswich.jpg"), then:
    make wildlife                       # or: python wildlife.py [dir]

Each photo is re-encoded with **EXIF stripped** (so the shoot's GPS never leaks),
resized, and uploaded to the shared S3 bucket under wildlife/images + wildlife/
thumbs. A small manifest at static/img/photography/manifest.json (committed, so
the change is reviewable) points the page at the S3 URLs.

Re-runs are idempotent: an image already uploaded (matched by content hash) is
skipped and its manifest entry — including any title/category you hand-edited —
is left untouched. So to rename or re-file a photo, just edit the manifest.
"""
import datetime
import hashlib
import json
import os
import re
import sys
from io import BytesIO

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "static", "img", "photography", "manifest.json")
DEFAULT_DIR = os.path.join(HERE, "wildlife_incoming")
BUCKET = os.environ.get("BIRDS_S3_BUCKET", "birds-scott-ouellette")
PREFIX = "wildlife"
FULL_MAX = 2048   # lightbox copy — plenty sharp, still light
THUMB_MAX = 640   # grid copy (matches the birds gallery)
EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def _title_from_filename(filename):
    """"red-fox_ipswich-river.JPG" -> "Red Fox Ipswich River" (editable later)."""
    stem = os.path.splitext(os.path.basename(filename))[0]
    words = re.split(r"[\s_\-]+", stem.strip())
    return " ".join(w[:1].upper() + w[1:] for w in words if w)


def _exif_date(im, path):
    """Capture date: EXIF DateTimeOriginal if present, else the file's mtime."""
    try:
        raw = im.getexif().get(36867) or im.getexif().get(306)  # DateTimeOriginal/DateTime
        if raw:
            return datetime.datetime.strptime(raw[:10], "%Y:%m:%d").date().isoformat()
    except Exception:  # noqa: BLE001 - bad/missing EXIF is fine
        pass
    return datetime.date.fromtimestamp(os.path.getmtime(path)).isoformat()


def _encode(im, max_w, quality):
    """JPEG bytes + [w, h] for a copy of the image, EXIF stripped, orientation
    baked in, capped at ``max_w`` wide."""
    from PIL import Image, ImageOps

    im = ImageOps.exif_transpose(im).convert("RGB")
    if im.width > max_w:
        im = im.resize((max_w, max(1, round(im.height * max_w / im.width))), Image.LANCZOS)
    out = BytesIO()
    im.save(out, "JPEG", quality=quality, optimize=True, progressive=True)
    return out.getvalue(), [im.width, im.height]


def _load_manifest():
    try:
        with open(MANIFEST) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return []


def process(src_dir):
    import boto3
    from PIL import Image

    if not os.path.isdir(src_dir):
        sys.exit("No such folder: %s\nMake %s/<Category>/ and drop photos in it."
                 % (src_dir, src_dir))
    s3 = boto3.client("s3")
    manifest = _load_manifest()
    by_id = {e["id"]: e for e in manifest}
    added = skipped = 0

    for root, _dirs, files in os.walk(src_dir):
        category = os.path.basename(root)
        if os.path.abspath(root) == os.path.abspath(src_dir):
            category = "Wildlife"  # files dropped loose at the top get a default
        for name in sorted(files):
            if os.path.splitext(name)[1].lower() not in EXTS:
                continue
            path = os.path.join(root, name)
            with open(path, "rb") as fh:
                data = fh.read()
            img_id = hashlib.sha1(data).hexdigest()[:12]
            if img_id in by_id:
                skipped += 1
                continue
            try:
                im = Image.open(BytesIO(data))
                full, dims = _encode(im, FULL_MAX, 85)
                im = Image.open(BytesIO(data))  # re-open; encode consumes it
                thumb, _ = _encode(im, THUMB_MAX, 78)
                date = _exif_date(Image.open(BytesIO(data)), path)
            except Exception as exc:  # noqa: BLE001
                print("  ! skip %s (%s)" % (name, exc))
                continue
            for kind, blob in (("images", full), ("thumbs", thumb)):
                s3.put_object(
                    Bucket=BUCKET, Key="%s/%s/%s.jpg" % (PREFIX, kind, img_id),
                    Body=blob, ContentType="image/jpeg",
                    CacheControl="public, max-age=31536000, immutable",
                )
            base = "https://%s.s3.amazonaws.com/%s" % (BUCKET, PREFIX)
            entry = {
                "id": img_id,
                "image": "%s/images/%s.jpg" % (base, img_id),
                "thumb": "%s/thumbs/%s.jpg" % (base, img_id),
                "title": _title_from_filename(name),
                "category": category,
                "date": date,
                "w": dims[0], "h": dims[1],
            }
            manifest.append(entry)
            by_id[img_id] = entry
            added += 1
            print("  + %-24s %s" % (category, entry["title"]))

    # Newest first within each category (the page groups by category).
    manifest.sort(key=lambda e: (e.get("category", ""), e.get("date", "")), reverse=True)
    with open(MANIFEST, "w") as fh:
        json.dump(manifest, fh, indent=2)
    print("\n%d added, %d already published. Manifest: %s"
          % (added, skipped, os.path.relpath(MANIFEST, HERE)))
    if added:
        print("Review static/img/photography/manifest.json, commit it, and deploy.")


if __name__ == "__main__":
    process(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DIR)
