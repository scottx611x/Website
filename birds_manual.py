#!/usr/bin/env python3
"""Add birds photographed but never posted to Instagram into the /birds gallery.

The bird gallery is normally synced from Instagram. This is the manual path for
sightings that never made it to a post — they're written to birds/manual_birds.json
(committed, so reviewable) and merged into the gallery at load time, so an IG
sync never clobbers them.

Usage:
    # one folder per species under birds_incoming/, folder name = the caption:
    #   birds_incoming/Piping Plover/                 -> species only
    #   birds_incoming/Common Loon @ Sand Pond/       -> species + location
    # each folder becomes ONE carousel post (files sorted = carousel order).
    python birds_manual.py [dir]

Each image is re-encoded EXIF-stripped (no GPS leak), resized, and uploaded to
S3 under birds/images + birds/thumbs (same layout the IG sync uses, so the
gallery's thumbnailing just works). Re-runs are idempotent by content hash.
"""
import datetime
import hashlib
import json
import os
import sys
from io import BytesIO

HERE = os.path.dirname(os.path.abspath(__file__))
MANUAL = os.path.join(HERE, "birds", "manual_birds.json")
DEFAULT_DIR = os.path.join(HERE, "birds_incoming")
BUCKET = os.environ.get("BIRDS_S3_BUCKET", "birds-scott-ouellette")
PREFIX = "birds"
FULL_MAX = 1600   # lightbox copy
THUMB_MAX = 640   # grid copy
EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def _folder_caption(name):
    """Parse a folder name into (species, location, away).

    "Common Loon"                       -> ("Common Loon", "", False)
    "Common Loon @ Sand Pond"           -> ("Common Loon", "Sand Pond", False)
    "Hooded Crow @ Oslo !away"          -> ("Hooded Crow", "Oslo", True)  (out-of-area)
    """
    away = False
    if name.strip().endswith("!away"):
        away = True
        name = name.rsplit("!away", 1)[0]
    if "@" in name:
        sp, loc = name.split("@", 1)
        return sp.strip(), loc.strip(), away
    return name.strip(), "", away


def _exif_date(im, path):
    try:
        ex = im.getexif()
        raw = (ex.get_ifd(0x8769).get(36867) or ex.get(36867) or ex.get(306))
        if raw:
            return datetime.datetime.strptime(raw[:10], "%Y:%m:%d").date().isoformat()
    except Exception:  # noqa: BLE001
        pass
    return datetime.date.fromtimestamp(os.path.getmtime(path)).isoformat()


def _encode(im, max_w, quality):
    from PIL import Image, ImageOps

    im = ImageOps.exif_transpose(im).convert("RGB")
    if im.width > max_w:
        im = im.resize((max_w, max(1, round(im.height * max_w / im.width))), Image.LANCZOS)
    out = BytesIO()
    im.save(out, "JPEG", quality=quality, optimize=True, progressive=True)
    return out.getvalue(), [im.width, im.height]


def _load():
    try:
        with open(MANUAL) as fh:
            data = json.load(fh)
            return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def process(src_dir):
    import boto3
    from PIL import Image

    if not os.path.isdir(src_dir):
        sys.exit("No such folder: %s\nMake %s/<Species Name>/ and drop photos in it."
                 % (src_dir, src_dir))
    s3 = boto3.client("s3")
    manual = _load()
    known = {img for e in manual for img in e.get("images", [])}
    base_url = "https://%s.s3.amazonaws.com/%s" % (BUCKET, PREFIX)
    added_posts = added_imgs = skipped = 0

    for entry_dir in sorted(os.listdir(src_dir)):
        folder = os.path.join(src_dir, entry_dir)
        if not os.path.isdir(folder):
            continue
        species, location, away = _folder_caption(entry_dir)
        files = sorted(f for f in os.listdir(folder)
                       if os.path.splitext(f)[1].lower() in EXTS)
        if not files:
            continue

        images, dims, dates = [], [], []
        for name in files:
            path = os.path.join(folder, name)
            with open(path, "rb") as fh:
                raw = fh.read()
            img_id = hashlib.sha1(raw).hexdigest()[:12]
            url = "%s/images/%s.jpg" % (base_url, img_id)
            if url in known:
                skipped += 1
                images.append(url)  # keep it in this post's carousel
                try:
                    im = Image.open(BytesIO(raw))
                    dims.append(list(_encode(im, FULL_MAX, 85)[1]))
                    dates.append(_exif_date(Image.open(BytesIO(raw)), path))
                except Exception:  # noqa: BLE001
                    dims.append(None)
                continue
            try:
                full, dim = _encode(Image.open(BytesIO(raw)), FULL_MAX, 85)
                thumb, _ = _encode(Image.open(BytesIO(raw)), THUMB_MAX, 78)
                date = _exif_date(Image.open(BytesIO(raw)), path)
            except Exception as exc:  # noqa: BLE001
                print("  ! skip %s (%s)" % (name, exc))
                continue
            for kind, blob in (("images", full), ("thumbs", thumb)):
                s3.put_object(
                    Bucket=BUCKET, Key="%s/%s/%s.jpg" % (PREFIX, kind, img_id),
                    Body=blob, ContentType="image/jpeg",
                    CacheControl="public, max-age=31536000, immutable")
            images.append(url)
            dims.append(list(dim))
            dates.append(date)
            added_imgs += 1

        # Skip a folder whose every image was already published in a prior run.
        post_id = "manual-" + hashlib.sha1("|".join(images).encode()).hexdigest()[:12]
        if any(e["id"] == post_id for e in manual):
            continue

        date = min((d for d in dates if d), default=datetime.date.today().isoformat())
        pretty = datetime.date.fromisoformat(date).strftime("%b %-d, %Y")
        n = len(images)
        cap_loc = " - %s" % location if location else ""
        # A leading ⚠️ marks the whole post out-of-area (parsed + stripped by
        # _caption_area_species, so the species name stays clean).
        warn = "⚠️ " if away else ""
        caption = "%s%s%s\n\n%s" % (warn, species, cap_loc, pretty)
        frame_cap = " · ".join([species] + ([location] if location else []) + [pretty])
        manual.append({
            "id": post_id,
            "images": images,
            "image_dims": dims,
            "image_species": [species] * n,
            "image_locations": [location or None] * n,
            "image_videos": [None] * n,
            "image_indices": list(range(n)),
            "captions": [frame_cap] * n,
            "caption": caption,
            "species": species,
            "species_list": [species],
            "location": location or None,
            "locations": [location] if location else [],
            "date": pretty,
            "timestamp": date + "T12:00:00+0000",
            "weight": 0.5,
            "manual": True,
        })
        added_posts += 1
        print("  + %s (%d photo%s)%s" % (species, n, "" if n == 1 else "s",
                                         " @ " + location if location else ""))

    manual.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
    os.makedirs(os.path.dirname(MANUAL), exist_ok=True)
    with open(MANUAL, "w") as fh:
        json.dump(manual, fh, indent=2)
    print("\n%d posts added (%d new images, %d already published). Manifest: %s"
          % (added_posts, added_imgs, skipped, os.path.relpath(MANUAL, HERE)))
    if added_posts:
        print("Review birds/manual_birds.json, commit it, and deploy.")


if __name__ == "__main__":
    process(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DIR)
