"""Where does the full-size originals archive actually stand?

    BIRDS_USE_S3=1 .venv/bin/python tools/originals_audit.py

Every frame on the site should have a full-resolution copy in Glacier — that
is what the Christmas photo books get printed from. Three separate paths can
put a frame on the site, and each has its own way of forgetting:

  pipeline (Instagram)  archive_originals() runs at post time — but only if
                        the container has been restarted since it was added
  birds_manual.py       archives as it uploads (it did NOT until 2026-10-11,
                        which cost 68 frames)
  historic backfill     tools/match_originals.py + upload_originals.py

Coverage drifted from "basically complete" to 33% missing without anything
failing loudly, because nothing ever asked the question. This asks it. Run it
after any batch of posts; a rising "no source anywhere" number is the only one
that should worry you.
"""
import os
import sys

sys.path.insert(0, "/Users/scott/Website")
import birds  # noqa: E402

if not os.environ.get("BIRDS_USE_S3"):
    sys.exit("BIRDS_USE_S3=1 is required — without it the archive listing is "
             "empty and every frame reports as missing.")


def main():
    g = birds._load_gallery_uncached()
    shots = g[0] if isinstance(g, tuple) else g

    tot = miss = 0
    man_tot = man_miss = 0
    missing_posts = {}
    for s in shots:
        manual = bool(s.get("manual"))
        for im in (s.get("images") or []):
            url = im.get("url") if isinstance(im, dict) else str(im)
            if not birds.original_key(url):
                continue                      # not re-hosted: none expected
            tot += 1
            if manual:
                man_tot += 1
            if birds.has_original(url):
                continue
            miss += 1
            if manual:
                man_miss += 1
            missing_posts.setdefault(s.get("id"), 0)
            missing_posts[s.get("id")] += 1

    pct = 100.0 * (tot - miss) / tot if tot else 100.0
    print("  frames on the site      : %d" % tot)
    print("  with archived original  : %d  (%.1f%%)" % (tot - miss, pct))
    print("  MISSING                 : %d" % miss)
    print()
    print("  manual-post frames      : %d, of which %d missing" % (man_tot, man_miss))
    print("  posts with any gap      : %d" % len(missing_posts))
    if man_miss:
        print()
        print("  -> run tools/archive_manual_originals.py (matches by content")
        print("     hash against ~/Desktop/birbs and birds_incoming/)")
    if miss - man_miss:
        print()
        print("  -> the rest are historic: tools/lightroom_catalog.py says which")
        print("     are still re-exportable, worksheet at")
        print("     ~/Desktop/lightroom-reexport.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
