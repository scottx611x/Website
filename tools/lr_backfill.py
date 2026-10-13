"""Autonomous 1-at-a-time Lightroom backfill of missing full-size originals.

    BIRDS_USE_S3=1 .venv/bin/python tools/lr_backfill.py --plan <plan.json> [--limit N]
                                                         [--no-denoise] [--dry-run]

One photo at a time, so the disk never accumulates:

    find in Lightroom -> denoise if absent -> Export with Previous
                      -> match against the missing frames -> ship to Glacier
                      -> delete the local file -> next

Why this shape and not a bulk export: 5,534 assets is too taxing, and the only
reliable way to *target* one photo turned out to be Lightroom's search.

What was learned the hard way driving this UI:

  * `Cmd+F` focuses the search box. Clicking it by coordinate does NOT reliably
    focus it, and when it misses, the photo name you type is interpreted as
    keyboard SHORTCUTS — which is how a stray "November 2025" set star ratings.
    Never type at this app without `Cmd+F` first.
  * Searching a filename works and narrows to that photo. Searching a date
    does NOT filter — neither "2025-11-29" nor "November 2025".
  * `File > Export with Previous` is a real menu item, so the export needs no
    button hunting; AppleScript can click it. The plain Export button is
    custom-drawn and invisible to the accessibility tree.
  * Lightroom previews are content-addressed and carry no link back to a
    catalog asset, so a frame cannot be mapped to one filename. Hence per-DAY
    candidates, with the content hash deciding afterwards which export was
    actually wanted.

Resumable: every processed filename is journalled, so a crash or a stop picks
up where it left off.
"""
import argparse
import hashlib
import re
import io
import json
import os
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, "/Users/scott/Website")
from PIL import Image  # noqa: E402
import birds  # noqa: E402

if not os.environ.get("BIRDS_USE_S3"):
    sys.exit("BIRDS_USE_S3=1 is required.")

BIRBS = os.environ.get("BIRBS_DIR") or os.path.expanduser("~/Desktop/birbs")
STATE = os.path.join(os.path.dirname(BIRBS), ".lr_backfill_state.json")
BUCKET = os.environ.get("BIRDS_S3_BUCKET", "birds-scott-ouellette")
ASPECTS = [None, 0.800, 0.847, 1.000, 1.250]
Image.MAX_IMAGE_PIXELS = None


# ---------------------------------------------------------------- hashing
def dhash(im, s=8):
    im = im.convert("L").resize((s + 1, s), Image.LANCZOS)
    px = list(im.getdata())
    b = 0
    for r in range(s):
        for c in range(s):
            b = (b << 1) | (px[r * (s + 1) + c] < px[r * (s + 1) + c + 1])
    return b


def crop_to(im, ar):
    w, h = im.size
    if ar is None:
        return im
    if w / h > ar:
        nw = int(h * ar)
        return im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    nh = int(w / ar)
    return im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))


def ham(a, b):
    return bin(a ^ b).count("1")


def hash_local(path):
    with Image.open(path) as im:
        im.draft("L", (1024, 1024))
        im = im.convert("L")
        return [dhash(crop_to(im, a)) for a in ASPECTS]


# ---------------------------------------------------------------- lightroom
def osa(script):
    return subprocess.run(["osascript", "-e", script],
                          capture_output=True, text=True).returncode == 0


def activate():
    osa('tell application "Adobe Lightroom" to activate')
    time.sleep(1.2)


def click(seq):
    subprocess.run(["cliclick"] + seq, capture_output=True)


def clear_search():
    """Empty the search field.

    Searches become TOKEN CHIPS, and neither Cmd+A nor backspace removes them:
    Cmd+A does nothing and backspace edits the last chip's text one character at
    a time (it turned "DSC_6117" into "dSC_6117"). Leaving them in place ANDs
    every search together, so the view stops changing and the same photo gets
    exported forever — which is exactly what happened for 458 iterations.

    Only the field's clear button empties it. The button has no accessibility
    entry, so find it by sight: once focused, the field draws an accent-blue
    outline, and the button sits at that outline's right edge. Measured per
    call because the window gets resized.
    """
    from PIL import Image as _I
    shot = "/tmp/lrclear.png"

    # Click the field's clear button, located by sight each time: once focused
    # the field draws an accent-blue outline and the button sits at its right
    # edge. Position is measured per call because the window moves — it was
    # even on a SECOND DISPLAY for a while (origin x=-1018), which is why every
    # earlier click silently missed.
    #
    # Deliberately NOT verified here. An earlier version tried to confirm the
    # field was empty by counting "chip-coloured" pixels; the band it measured
    # covered the whole toolbar, so the count never dropped and it reported
    # failure on a field it had actually cleared. The real proof comes later and
    # for free: Lightroom names each export after its SOURCE photo, so if the
    # search did not take, the filename says so.
    for _ in range(3):
        click(["kd:cmd", "t:f", "ku:cmd"])
        time.sleep(0.8)
        subprocess.run(["screencapture", "-x", "-o", shot], capture_output=True)
        try:
            im = _I.open(shot).convert("RGB")
        except Exception:  # noqa: BLE001
            return True
        xs = [x for y in range(100, 190, 2) for x in range(60, im.size[0])
              if (lambda p: p[2] > 140 and p[2] - p[0] > 55 and p[2] - p[1] > 35)(
                  im.getpixel((x, y)))]
        if not xs:
            continue
        click(["c:%d,%d" % ((max(xs) - 16) // 2, 68)])
        time.sleep(1.0)
        return True
    return True


def find_photo(name):
    """Narrow Lightroom to one photo by filename. Cmd+F FIRST — see module docstring."""
    activate()
    clear_search()
    click(["kd:cmd", "t:f", "ku:cmd"])
    time.sleep(0.6)
    click(["t:" + os.path.splitext(name)[0].lower()])
    time.sleep(0.6)
    click(["kp:return"])
    time.sleep(5.0)
    select_found()
    return True


def menu(bar, item):
    return osa('tell application "System Events" to tell process "Adobe Lightroom" '
               'to click menu item "%s" of menu 1 of menu bar item "%s" '
               'of menu bar 1' % (item, bar))


def select_found():
    """Make the search result the SELECTION.

    Filtering the grid does not change what is selected, and Export acts on the
    selection — so without this every export is whatever was selected last.
    That cost 468 wasted iterations: the files differed (EXIF timestamps) while
    the image was byte-for-byte the same photo every time.

    Menu items rather than keystrokes, because "g" for grid view types a letter
    into the search field whenever focus is still there.
    """
    menu("View", "Photo Grid")
    time.sleep(1.6)
    menu("Edit", "Select All")
    time.sleep(1.2)


def export_with_previous():
    """File > Export with Previous — a menu item, so no coordinates involved."""
    for label in ("Export with Previous...", "Export with Previous"):
        if menu("File", label):
            return True
    return False


def stem_of(name):
    """"DSC_3992-4.jpg" -> "DSC_3992" (Lightroom suffixes -N to avoid clobbering)."""
    base = os.path.splitext(os.path.basename(name))[0]
    return re.sub(r"-\d+$", "", base)


def wait_for_export(before, timeout=180):
    """The filename Lightroom writes is its own business; just watch the folder."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        now = set(os.listdir(BIRBS))
        new = [n for n in now - before if n.lower().endswith((".jpg", ".jpeg"))]
        if new:
            p = os.path.join(BIRBS, new[0])
            last = -1
            while True:                      # let the write finish
                sz = os.path.getsize(p)
                if sz == last and sz > 0:
                    return p
                last = sz
                time.sleep(1.0)
        time.sleep(1.5)
    return None


# ---------------------------------------------------------------- targets
def load_targets():
    """[(key, posted_thumb_hash)] for every frame with no archived original."""
    g = birds._load_gallery_uncached()
    shots = g[0] if isinstance(g, tuple) else g
    out = []
    for s in shots:
        for i, im in enumerate(s.get("images") or []):
            u = im.get("url") if isinstance(im, dict) else str(im)
            key = birds.original_key(u)
            if key and not birds.has_original(u):
                out.append((key, birds.thumb_url(u)))
    return out


def hashed_targets(targets, cache):
    if os.path.exists(cache):
        return {k: v for k, v in json.load(open(cache))}
    got = []
    for key, url in targets:
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                got.append((key, dhash(Image.open(io.BytesIO(r.read())))))
        except Exception:  # noqa: BLE001
            continue
    json.dump(got, open(cache, "w"))
    return dict(got)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--no-denoise", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    state = json.load(open(STATE)) if os.path.exists(STATE) else {"done": [], "shipped": 0}
    done = set(state["done"])

    targets = load_targets()
    cache = os.path.join(os.path.dirname(BIRBS), ".lr_backfill_targets.json")
    TH = hashed_targets(targets, cache)
    print("  missing frames to satisfy : %d" % len(TH))

    plan = json.load(open(args.plan))
    queue = [(d["day"], fn) for d in plan for fn in d["assets"] if fn not in done]
    if args.limit:
        queue = queue[:args.limit]
    print("  candidates queued         : %d" % len(queue))
    if args.dry_run:
        for day, fn in queue[:10]:
            print("    %s  %s" % (day, fn))
        return

    import boto3
    s3 = boto3.client("s3")

    # If the search ever stops narrowing, Lightroom re-exports the SAME photo
    # and every comparison returns an identical distance. That is a broken run,
    # not a run with no matches, and it is cheap to detect: bail after a few
    # byte-identical exports in a row rather than burning hours.
    last_sig, repeats, misses = None, 0, 0

    for n, (day, fn) in enumerate(queue, 1):
        before = set(os.listdir(BIRBS))
        find_photo(fn)
        if not export_with_previous():
            print("  ! export menu failed on %s — stopping" % fn)
            break
        path = wait_for_export(before)
        if not path:
            print("  ! no export appeared for %s" % fn)
            done.add(fn)
            state["done"] = sorted(done)
            json.dump(state, open(STATE, "w"))
            continue

        if stem_of(path).lower() != stem_of(fn).lower():
            os.remove(path)
            misses += 1
            print("  [%d/%d] %s — got %s instead; retrying"
                  % (n, len(queue), stem_of(fn), stem_of(path)))
            if misses >= 4:
                print("  ! four misses in a row — the search is not taking. Stopping.")
                break
            continue
        misses = 0

        try:
            hs = hash_local(path)
            sig = hs[0]                 # perceptual, not byte-level
            repeats = repeats + 1 if sig == last_sig else 0
            last_sig = sig
            if repeats >= 3:
                print("  ! %s is the 4th visually identical export in a row — "
                      "the selection is not following the search. Stopping." % fn)
                os.remove(path)
                path = None
                break
            hit, best = None, 99
            for key, th in TH.items():
                d = min(ham(th, x) for x in hs)
                if d < best:
                    best, hit = d, key
            if hit and best <= 6:
                s3.upload_file(path, BUCKET, hit,
                               ExtraArgs={"ContentType": "image/jpeg",
                                          "StorageClass": "GLACIER_IR"})
                del TH[hit]
                state["shipped"] += 1
                print("  [%d/%d] %s  ->  %s  (d=%d)"
                      % (n, len(queue), fn, hit.rsplit("/", 1)[-1], best))
            else:
                print("  [%d/%d] %s  — no frame wanted it (best d=%d)"
                      % (n, len(queue), fn, best))
        finally:
            if path and os.path.exists(path):
                os.remove(path)             # disk stays flat, always
            done.add(fn)
            state["done"] = sorted(done)
            json.dump(state, open(STATE, "w"))

        if not TH:
            print("  every missing frame satisfied.")
            break

    print("  shipped this run: %d   remaining missing: %d" % (state["shipped"], len(TH)))


if __name__ == "__main__":
    main()
