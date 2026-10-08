"""Which un-archived frames can still be re-exported from Lightroom?

    BIRDS_USE_S3=1 .venv/bin/python tools/lightroom_recover.py

Re-run this after scrolling the relevant months in Lightroom: it caches a
preview per asset as you browse, and the cache is what this reads. Coverage
was 24-63% when first measured, so a "not found" is weak evidence — browse
the month first, then re-run and the recoverable list grows.


Lightroom CC keeps only 142 originals on this Mac; the rest live in Adobe's
cloud. But it keeps a 640px preview for every asset it knows about, and those
previews are plain JPEGs. Hashing them against the web copies of the frames we
could not archive says, per frame, whether the asset still exists — i.e.
whether re-exporting it is even possible.
"""
import io, json, os, sys, glob, urllib.request
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, "/Users/scott/Website")
from PIL import Image
import birds

LR = os.path.expanduser("~/Pictures/Lightroom Library.lrlibrary/"
                        "7aa8939dff234cdc89658403083bba94/previews")
Image.MAX_IMAGE_PIXELS = None
ASPECTS = [None, 0.800, 0.847, 1.000, 1.250]

def dhash(im, s=8):
    im = im.convert("L").resize((s + 1, s), Image.LANCZOS)
    px = list(im.getdata()); b = 0
    for r in range(s):
        for c in range(s):
            b = (b << 1) | (px[r*(s+1)+c] < px[r*(s+1)+c+1])
    return b

def crop_to(im, ar):
    w, h = im.size
    if ar is None: return im
    if w / h > ar:
        nw = int(h * ar); x = (w - nw)//2; return im.crop((x, 0, x+nw, h))
    nh = int(w / ar); y = (h - nh)//2; return im.crop((0, y, w, y+nh))

def hash_prev(p):
    try:
        with Image.open(p) as im:
            im = im.convert("L")
            return p, [dhash(crop_to(im, a)) for a in ASPECTS]
    except Exception:
        return p, None

def hash_url(u):
    try:
        with urllib.request.urlopen(u, timeout=30) as r:
            return u, dhash(Image.open(io.BytesIO(r.read())))
    except Exception:
        return u, None

def ham(a, b): return bin(a ^ b).count("1")

prevs = [p for p in glob.glob(os.path.join(LR, "*", "*")) if os.path.isfile(p)]
print("  hashing %d Lightroom previews..." % len(prevs), flush=True)
with ThreadPoolExecutor(8) as ex:
    PH = {p: hs for p, hs in ex.map(hash_prev, prevs) if hs}
idx = {}
for p, hs in PH.items():
    for h in hs: idx.setdefault(h, set()).add(p)
print("  usable previews: %d" % len(PH), flush=True)

archived = {(r["post"], r["idx"]) for r in json.load(open("/tmp/orig_map.json"))}
raw = birds._load_manifest_from_s3() or []
missing = [(s, i, u) for s in raw for i, u in enumerate(s.get("images") or [])
           if (s.get("id"), i) not in archived]
print("  frames without an archived original: %d" % len(missing), flush=True)

with ThreadPoolExecutor(16) as ex:
    WH = dict(ex.map(hash_url, [birds.thumb_url(u) for _, _, u in missing]))

rows = []
for s, i, u in missing:
    h = WH.get(birds.thumb_url(u))
    found, d = False, None
    if h is not None:
        if idx.get(h): found, d = True, 0
        else:
            best = 99
            for _p, hs in PH.items():
                dd = min(ham(h, x) for x in hs)
                if dd < best: best = dd
            d = best; found = best <= 6
    isp = s.get("image_species") or []
    rows.append({
        "post": s.get("id"), "idx": i,
        "species": (isp[i] if i < len(isp) and isp[i] else s.get("species")) or "",
        "date": (birds._frame_dates(s)[i].isoformat()
                 if i < len(birds._frame_dates(s) or []) and birds._frame_dates(s)[i] else ""),
        "posted": (s.get("timestamp") or "")[:10],
        "web": u, "in_lightroom": found, "d": d,
    })
json.dump(rows, open("/tmp/lr_missing.json", "w"), indent=1)
ok = sum(1 for r in rows if r["in_lightroom"])
print()
print("  recoverable from Lightroom : %d" % ok)
print("  not found anywhere         : %d" % (len(rows) - ok))
