"""Which un-archived frames are still re-exportable from Lightroom?

    BIRDS_USE_S3=1 .venv/bin/python tools/lightroom_catalog.py

This replaces the verdict in `lightroom_recover.py`, which answered the question
by perceptual-hashing Lightroom's 640px preview cache against the web copies.
That method badly under-reports, and the reason is structural rather than a
tuning problem:

  * the preview renders the CURRENT edit of the raw, while the web copy is an
    older export, usually cropped to 4:5 or 1:1 for Instagram. A re-crop or a
    re-edit moves a dHash well past any threshold tight enough to avoid false
    positives — the real distances here cluster at 12-15 against a cutoff of 6.
  * a preview only exists for assets that have been browsed.

So a hash miss means "could not prove it", not "the asset is gone" — but it was
being reported as "not found anywhere". Measured against the catalog, 545 of
the 562 unarchived frames have a shoot on their exact capture day; the hash
method claimed 154 were recoverable and 408 were lost.

The catalog is the authority on what Lightroom actually holds. It is a SQLite
doc-store (`Managed Catalog.mcat`) whose asset rows are MessagePack blobs; we
pull `fileName` and `captureDate` out of each without a msgpack dependency by
scanning printable tokens, which is enough for a date histogram of every shoot.

Capture date is a far better signal than image content: an export can be
cropped beyond recognition, but it cannot change the day it was taken.
"""
import collections
import datetime
import json
import os
import re
import sqlite3
import sys

sys.path.insert(0, "/Users/scott/Website")
import birds  # noqa: E402

if not os.environ.get("BIRDS_USE_S3"):
    sys.exit("BIRDS_USE_S3=1 is required — without it the manifest is empty "
             "and every number below is a silent zero.")

CATALOG = os.path.expanduser(
    "~/Pictures/Lightroom Library.lrlibrary/"
    "7aa8939dff234cdc89658403083bba94/Managed Catalog.mcat")

TOKEN = re.compile(rb"[ -~]{4,}")
DATE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def catalog_assets(path=CATALOG):
    """[{sub, fn, cap}] for every asset doc in the catalog.

    Read against a COPY: Lightroom keeps the live catalog in WAL mode and may
    hold a write lock, and we never want to be the reason his library breaks.
    """
    import shutil
    import tempfile

    tmp = os.path.join(tempfile.mkdtemp(), "cat.mcat")
    shutil.copyfile(path, tmp)
    db = sqlite3.connect(tmp)
    db.text_factory = bytes
    rows = db.execute("""select d.subtype, r.content from docs d
                         join revs r on r.sequence = d.winningRevSequence
                         where d.type = 'asset'""").fetchall()
    out = []
    for sub, blob in rows:
        toks = [t.decode() for t in TOKEN.findall(bytes(blob))]
        fn = cap = None
        for i, t in enumerate(toks):
            if t == "fileName" and fn is None and i + 1 < len(toks):
                fn = toks[i + 1]
            # captureDate is the EXIF instant; `created`/`importTimestamp` are
            # when Adobe ingested it and are useless for locating a shoot.
            elif t in ("captureDate", "DateTimeOriginal") and cap is None \
                    and i + 1 < len(toks):
                m = DATE.match(toks[i + 1])
                if m:
                    cap = m.group(1)
        out.append({"sub": sub.decode(), "fn": fn, "cap": cap})
    return out


def main():
    assets = catalog_assets()
    shoots = collections.Counter(
        a["cap"] for a in assets if a["sub"] == "image" and a["cap"])
    print("  catalog: %d image assets across %d shoot days (%s .. %s)"
          % (sum(1 for a in assets if a["sub"] == "image"), len(shoots),
             min(shoots), max(shoots)))

    missing = json.load(open("/tmp/lr_missing.json"))
    exact = near = gone = 0
    for r in missing:
        day = (r.get("date") or "")[:10]
        try:
            d = datetime.date.fromisoformat(day)
        except ValueError:
            gone += 1
            r["lr"] = None
            continue
        if shoots.get(day):
            exact += 1
            r["lr"] = "exact"
        elif any(shoots.get(str(d + datetime.timedelta(days=k)))
                 for k in (-1, 1)):
            near += 1
            r["lr"] = "near"
        else:
            gone += 1
            r["lr"] = None

    print("  frames with no archived original : %d" % len(missing))
    print("    shoot on the exact capture day : %d" % exact)
    print("    shoot within a day             : %d" % near)
    print("    no shoot near that day         : %d" % gone)

    json.dump(missing, open("/tmp/lr_catalog.json", "w"), indent=1)
    print("  wrote /tmp/lr_catalog.json")
    return missing, shoots


if __name__ == "__main__":
    main()
