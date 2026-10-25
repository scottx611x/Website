"""Does each birds/originals/<name> actually depict the same photo as the
frame the site shows under that name?

    BIRDS_USE_S3=1 .venv/bin/python tools/originals_verify.py [--bird "Cedar Waxwing"]

tools/originals_audit.py asks whether an original EXISTS. It has never asked
whether it is the RIGHT ONE, and the historic backfill
(tools/match_originals.py) matched old frames by crop-tolerant hashing — which
can pick the wrong frame out of a burst, where every exposure looks alike.
Nothing downstream would notice: original_key() is a pure filename map, so a
mis-named upload is served forever as that frame's "full size".

Comparing the two images directly does not work, because the web copy is
usually a CROP of the original — a 1:1 Instagram crop out of a 3:2 exposure
hashes 25-40 away from its own original. So instead: look for the published
frame INSIDE the original across scale and position. If it is there, it is the
same photograph and the distance collapses to single digits. If the best
placement anywhere still does not look like the published frame, the original
is a different photo.
"""
import argparse
import io
import os
import sys
import threading
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

import birds  # noqa: E402


# ---------------------------------------------------------------------------
# Finding the published frame inside the original.
#
# A direct comparison is useless here: the web copy is usually a CROP of the
# original, and a 1:1 crop out of a 3:2 exposure hashes 25-40 away from its own
# original. Searching for it across scale and position collapses that to single
# digits when it IS the same photograph, and leaves it high when it is not —
# which is the whole test.
# ---------------------------------------------------------------------------
def fetch(url, timeout=240):
    return urllib.request.urlopen(url, timeout=timeout).read()


def dhash(im, size=8):
    im = im.convert("L").resize((size + 1, size), Image.LANCZOS)
    px = list(im.getdata())
    bits = 0
    for r in range(size):
        for c in range(size):
            bits = (bits << 1) | (1 if px[r * (size + 1) + c] > px[r * (size + 1) + c + 1] else 0)
    return bits


def gray(im, w):
    h = max(1, round(im.height * w / im.width))
    return np.asarray(im.convert("L").resize((w, h), Image.LANCZOS), dtype=np.float32)


def _ncc(big, small):
    """NCC of `small` at every position in `big`.

    Via FFT and integral images, NOT sliding_window_view: that materialises
    one window per position — about 270 MB for a single call at these sizes —
    and a pool of workers doing it in parallel simply runs the machine out of
    memory. This is the same number, in a few MB.
    """
    bh, bw = big.shape
    sh, sw = small.shape
    if sh > bh or sw > bw:
        return None
    s = small - small.mean()
    s_norm = float(np.sqrt((s * s).sum()))
    if s_norm == 0:
        return None
    # Cross-correlation is convolution with the kernel mirrored.
    corr = np.fft.irfft2(np.fft.rfft2(big, s=(bh, bw)) *
                         np.fft.rfft2(s[::-1, ::-1], s=(bh, bw)), s=(bh, bw))
    num = corr[sh - 1:bh, sw - 1:bw]
    # Per-window mean and variance from summed-area tables.
    ii = np.pad(np.cumsum(np.cumsum(big, 0), 1), ((1, 0), (1, 0)))
    ii2 = np.pad(np.cumsum(np.cumsum(big * big, 0), 1), ((1, 0), (1, 0)))

    def wsum(I):
        return (I[sh:bh + 1, sw:bw + 1] - I[0:bh - sh + 1, sw:bw + 1]
                - I[sh:bh + 1, 0:bw - sw + 1] + I[0:bh - sh + 1, 0:bw - sw + 1])

    n = sh * sw
    ws, ws2 = wsum(ii), wsum(ii2)
    wvar = ws2 - ws * ws / n
    return num / (np.sqrt(np.maximum(wvar, 1e-9)) * s_norm)


def locate(web, orig, work=320):
    """Best (score, box, scale) of the published crop inside the original."""
    big = gray(orig, work)
    best = (-2.0, None, None)

    def scan(fracs):
        nonlocal best
        for f in fracs:
            sw = int(round(work * f))
            if sw < 24 or sw > big.shape[1]:
                continue
            sm = gray(web, sw)
            if sm.shape[0] > big.shape[0]:
                continue
            m = _ncc(big, sm)
            if m is None:
                continue
            i = int(np.argmax(m))
            y, x = divmod(i, m.shape[1])
            if m[y, x] > best[0]:
                best = (float(m[y, x]), (x, y, sm.shape[1], sm.shape[0]), float(f))

    scan(np.arange(0.30, 1.0001, 0.05))
    if best[1] is None:
        return best
    scan(np.arange(max(0.25, best[2] - 0.05), min(1.0, best[2] + 0.05) + 1e-9, 0.0125))
    score, (x, y, w, h), f = best
    k = orig.width / big.shape[1]
    box = (max(0, int(round(x * k))), max(0, int(round(y * k))),
           min(orig.width, int(round((x + w) * k))),
           min(orig.height, int(round((y + h) * k))))
    return score, box, f


#: Same gate the cropper uses: 0-8 is "the same picture", and a genuinely
#: different frame from the same burst still lands well above it.
MATCH_MAX = 8
_lock = threading.Lock()


def log(m):
    with _lock:
        print(m, flush=True)


def check(name, src):
    try:
        web = Image.open(io.BytesIO(fetch(src))).convert("RGB")
        ourl = birds.original_url(src, expires=7200)
        if not ourl:
            return name, None, "no presigned url", None
        orig = Image.open(io.BytesIO(fetch(ourl))).convert("RGB")
    except Exception as e:  # noqa: BLE001
        return name, None, "fetch: %s" % e, None
    try:
        score, box, _f = locate(web, orig)
    except Exception as e:  # noqa: BLE001
        return name, None, "locate: %s" % e, None
    if not box:
        return name, 99, "no placement found", None
    cut = orig.crop(box)
    d = bin(dhash(web) ^ dhash(cut)).count("1")
    detail = "%dx%d -> %dx%d ncc=%.2f" % (web.width, web.height,
                                          orig.width, orig.height, score)
    # Hand the decoded images back ONLY for a mismatch, and shrink them first.
    # Returning them for every frame kept a 6000x4000 RGB bitmap (~72 MB)
    # alive per result for as long as its future was referenced, and the run
    # died of memory around frame 260 of 1773.
    ims = None
    if d > MATCH_MAX:
        ims = []
        for im in (web, orig, cut):
            t = im.copy()
            t.thumbnail((420, 300))
            ims.append(t)
        ims = tuple(ims)
    return name, d, detail, ims


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bird", default="", help="limit to one species")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--sheet", default="", help="write a contact sheet of the failures here")
    args = ap.parse_args()
    if not os.environ.get("BIRDS_USE_S3"):
        sys.exit("BIRDS_USE_S3=1 is required.")

    shots = birds.load_gallery(shuffle=False)
    frames = birds.images_filtered(shots, bird=args.bird) if args.bird else None
    todo, seen = [], set()
    if frames is not None:
        src_iter = [((f.get("images") or [None])[0], f) for f in frames]
    else:
        src_iter = [(u, s) for s in shots for u in (s.get("images") or [])]
    for url, meta in src_iter:
        if not url or not birds.has_original(url):
            continue
        name = birds.original_key(url).rsplit("/", 1)[-1]
        if name in seen:
            continue
        seen.add(name)
        todo.append((name, url, meta))
    if args.limit:
        todo = todo[:args.limit]
    log("verifying %d frames%s" % (len(todo), (" of %s" % args.bird) if args.bird else ""))

    results, bad = [], []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(check, n, u): (n, u, m) for n, u, m in todo}
        # as_completed + pop: a finished future must stop referencing its
        # result, or every decoded image stays live until the whole run ends.
        for i, fut in enumerate(as_completed(list(futs)), 1):
            name, d, detail, ims = fut.result()
            n_, u_, meta = futs.pop(fut)
            where = (meta.get("location") if isinstance(meta, dict) else None) or ""
            when = ((meta.get("_sort") if isinstance(meta, dict) else "") or "")[:10]
            results.append((d, name, where, when, detail))
            if d is None or d > MATCH_MAX:
                bad.append((d, name, where, when, detail, ims))
                log("  MISMATCH  %-28s d=%-4s %-26s %s  %s" %
                    (name, d, where[:24], when, detail))
            elif i % 20 == 0:
                log("  ...%d/%d checked" % (i, len(futs)))

    ok = [r for r in results if r[0] is not None and r[0] <= MATCH_MAX]
    log("\n--- %d checked ---" % len(results))
    log("  same photo      : %d" % len(ok))
    log("  MISMATCHED      : %d" % len([r for r in results if r[0] is not None and r[0] > MATCH_MAX]))
    log("  could not check : %d" % len([r for r in results if r[0] is None]))

    if args.sheet and bad:
        cells = [b for b in bad if b[5]]
        CW, CH = 420, 300
        sheet = Image.new("RGB", (CW * 3, CH * len(cells)), (18, 22, 18))
        for r, (d, name, where, when, detail, ims) in enumerate(cells):
            for c, im in enumerate(ims):          # web | original | best placement
                im = im.copy()
                im.thumbnail((CW, CH))
                sheet.paste(im, (c * CW + (CW - im.width) // 2, r * CH + (CH - im.height) // 2))
            log("  sheet row %d = %s (d=%s) %s %s" % (r, name, d, where, when))
        sheet.save(args.sheet, quality=88)
        log("wrote %s  [web | original | best placement found]" % args.sheet)


if __name__ == "__main__":
    main()
