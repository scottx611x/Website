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
    # A trailing "-2"/"-8" is a duplicate-name suffix, not part of the name.
    stem = re.sub(r"[\s_\-]+\d+$", "", stem.strip()) or stem
    words = re.split(r"[\s_\-]+", stem.strip())
    return " ".join(w[:1].upper() + w[1:] for w in words if w)


def _exif_date(im, path):
    """Capture date: EXIF DateTimeOriginal if present, else the file's mtime."""
    try:
        ex = im.getexif()
        # DateTimeOriginal lives in the Exif sub-IFD (0x8769); fall back to the
        # top-level DateTimeOriginal/DateTime if a camera puts it there.
        raw = (ex.get_ifd(0x8769).get(36867) or ex.get(36867) or ex.get(306))
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


def _load_meta(src_dir):
    """Optional ``_meta.json`` beside the photos: {"<file name>": {"title",
    "species", "location", "tags"}}. Lets an automated publisher hand over what
    it already knows instead of leaving it all for the curate editor."""
    try:
        with open(os.path.join(src_dir, "_meta.json")) as fh:
            meta = json.load(fh)
        return meta if isinstance(meta, dict) else {}
    except (OSError, ValueError):
        return {}


def process(src_dir, manifest=None, write_manifest=True):
    """Upload every new photo under ``src_dir`` and add a manifest entry for it.
    Returns (manifest, entries added)."""
    import boto3
    from PIL import Image

    if not os.path.isdir(src_dir):
        sys.exit("No such folder: %s\nMake %s/<Category>/ and drop photos in it."
                 % (src_dir, src_dir))
    s3 = boto3.client("s3")
    manifest = _load_manifest() if manifest is None else manifest
    by_id = {e["id"]: e for e in manifest}
    meta = _load_meta(src_dir)
    new = []
    added = skipped = 0

    for root, _dirs, files in os.walk(src_dir):
        top = os.path.abspath(root) == os.path.abspath(src_dir)
        # A subfolder name seeds a starting tag (e.g. Mammals/ -> "mammals");
        # loose files at the top start untagged. Refine tags in the curate editor.
        folder_tags = [] if top else [os.path.basename(root).lower()]
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
            # The untouched source, cold-stored. The web copy is capped at
            # 2048px, so without this the full-resolution file exists only on
            # whatever drive it was imported from. birds_manual.py gained this
            # on 2026-10-11; /photography had the same hole.
            s3.put_object(
                Bucket=BUCKET, Key="%s/originals/%s.jpg" % (PREFIX, img_id),
                Body=data, ContentType="image/jpeg", StorageClass="GLACIER_IR",
            )
            base = "https://%s.s3.amazonaws.com/%s" % (BUCKET, PREFIX)
            entry = {
                "id": img_id,
                "image": "%s/images/%s.jpg" % (base, img_id),
                "thumb": "%s/thumbs/%s.jpg" % (base, img_id),
                "title": _title_from_filename(name),
                "species": "",   # optional — set in the curate editor
                "location": "",  # optional — set in the curate editor
                "date": date,
                # A fresh list per photo: one shared list let a _meta tag on
                # one file (coyote) leak onto every later file in the folder.
                "tags": list(folder_tags),
                "w": dims[0], "h": dims[1],
            }
            m = meta.get(name) or {}
            for k in ("title", "species", "location"):
                if isinstance(m.get(k), str) and m[k].strip():
                    entry[k] = m[k].strip()
            for t in m.get("tags") or []:
                t = str(t).strip().lower()
                if t and t not in entry["tags"]:
                    entry["tags"].append(t)
            manifest.append(entry)
            new.append(entry)
            by_id[img_id] = entry
            added += 1
            print("  + %s%s" % (entry["title"], (" [%s]" % ",".join(entry["tags"])) if entry["tags"] else ""))

    manifest.sort(key=lambda e: e.get("date", ""), reverse=True)  # newest first
    if not write_manifest:
        print("\n%d added, %d already published." % (added, skipped))
        return manifest, new
    with open(MANIFEST, "w") as fh:
        json.dump(manifest, fh, indent=2)
    print("\n%d added, %d already published. Manifest: %s"
          % (added, skipped, os.path.relpath(MANIFEST, HERE)))
    if added:
        print()
        print("Review %s and commit it." % os.path.relpath(MANIFEST, HERE))
        print("NOTE: committing + deploying is NOT enough. In production the")
        print("gallery reads the S3 curation store (birds/photos.json), which")
        print("wins over the deployed repo copy; the new entries must be")
        print("appended there or they will not appear on the live site.")
        print("`make wildlife-publish` does both.")
    return manifest, new


def _read_live_store():
    """The live gallery's store (S3 birds/photos.json), read fresh. Exits rather
    than guess: writing back a store we could not read would drop photos."""
    import birds

    key = birds._CURATION_S3[birds.PHOTOS_FILE]
    try:
        body = birds._s3().get_object(Bucket=birds.S3_BUCKET, Key=key)["Body"].read()
        data = json.loads(body)
    except Exception as exc:  # noqa: BLE001
        sys.exit("Could not read s3://%s/%s (%s); nothing published."
                 % (birds.S3_BUCKET, key, exc))
    if not isinstance(data, list):
        sys.exit("s3://%s/%s is not a list; nothing published." % (birds.S3_BUCKET, key))
    return data


def publish(src_dir):
    """Upload + add to the LIVE gallery in one step.

    Merges into the S3 store rather than pushing the repo copy over it, so
    edits made in curate mode since the last pull survive (`make
    push-curations` would overwrite every curation file). The store is re-read
    just before the write so a curate edit made during the uploads is kept
    too. No deploy is needed: the site reads the store, and the write bumps
    the curation stamp. The repo copy is refreshed to match, for committing.
    """
    import birds

    if not os.environ.get("BIRDS_USE_S3"):
        sys.exit("BIRDS_USE_S3=1 is required (use `make wildlife-publish`).")
    _, new = process(src_dir, manifest=_read_live_store(), write_manifest=False)
    if not new:
        print("Nothing new to publish.")
        return []
    live = _read_live_store()
    have = {e.get("id") for e in live}
    merged = live + [e for e in new if e["id"] not in have]
    merged.sort(key=lambda e: e.get("date", ""), reverse=True)
    birds._save_curation(birds.PHOTOS_FILE, merged)
    # _save_curation falls back to a local write if S3 refuses; check it landed.
    check = {e.get("id") for e in _read_live_store()}
    missing = [e["id"] for e in new if e["id"] not in check]
    if missing:
        sys.exit("S3 store write did not take; %d photos missing: %s"
                 % (len(missing), ", ".join(missing)))
    birds._atomic_write_json(birds.PHOTOS_FILE, merged)
    print("Live: %d new photos in s3://%s/%s (repo copy refreshed: %s)."
          % (len(new), birds.S3_BUCKET, birds._CURATION_S3[birds.PHOTOS_FILE],
             os.path.relpath(MANIFEST, HERE)))
    return new


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--publish"]
    src = args[0] if args else DEFAULT_DIR
    if "--publish" in sys.argv[1:]:
        publish(src)
    else:
        process(src)
