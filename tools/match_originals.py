"""Crop-tolerant match of web images to full-res originals.

Many posts are cropped to 4:5 or 1:1 for Instagram, so a whole-frame hash of
the export does not match the posted copy. Hash the original at the handful of
aspect ratios Instagram actually serves, centre-cropped, and match against any.
"""
import io, json, os, sys, urllib.request, glob
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, "/Users/scott/Website")
from PIL import Image
import birds

# Without this the manifest loader returns [], so "0 of 0 matched" means the
# manifest never loaded, not that there was nothing to match. Fail loudly.
if not os.environ.get("BIRDS_USE_S3"):
    sys.exit("BIRDS_USE_S3=1 is required — without it the manifest is empty "
             "and every number below is a silent zero.")

BIRBS = os.path.expanduser("~/Desktop/birbs")
Image.MAX_IMAGE_PIXELS = None
ASPECTS = [None, 0.800, 0.847, 1.000, 1.250]      # full, 4:5, IG tall, square, 5:4

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
    if w / h > ar:                      # too wide -> trim sides
        nw = int(h * ar); x = (w - nw) // 2
        return im.crop((x, 0, x + nw, h))
    nh = int(w / ar); y = (h - nh) // 2
    return im.crop((0, y, w, y + nh))

def hash_local(p):
    try:
        with Image.open(p) as im:
            im.draft("L", (1024, 1024))
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

locals_ = sorted(glob.glob(os.path.join(BIRBS, "*.jpg")))
print("  hashing %d originals at %d crops..." % (len(locals_), len(ASPECTS)), flush=True)
with ThreadPoolExecutor(8) as ex:
    LH = {p: hs for p, hs in ex.map(hash_local, locals_) if hs}

index = {}
for p, hs in LH.items():
    for h in hs:
        index.setdefault(h, set()).add(p)

raw = birds._load_manifest_from_s3() or []
web = [(s.get("id"), i, u) for s in raw for i, u in enumerate(s.get("images") or [])]
print("  hashing %d web images..." % len(web), flush=True)
with ThreadPoolExecutor(16) as ex:
    WH = dict(ex.map(hash_url, [birds.thumb_url(u) for _, _, u in web]))

# Ground truth first. For the posts the pipeline recorded, files[] names the
# export for each frame directly — no inference needed, and it catches frames
# whose crop defeats a content hash. Hashing is the fallback for the 244 posts
# that predate the record system.
from_record = {}
for r in birds._load_post_records() or []:
    key = (birds._norm_caption(r.get("caption")), len(r.get("files") or []))
    for s_ in raw:
        if (birds._norm_caption(s_.get("caption")),
                len(s_.get("images") or [])) != key:
            continue
        for i_, f_ in enumerate(r.get("files") or []):
            local = os.path.join(BIRBS, os.path.basename(f_))
            if os.path.exists(local):
                from_record[(s_.get("id"), i_)] = local

out, unmatched, amb = [], [], []
for pid, i, u in web:
    rec_hit = from_record.get((pid, i))
    if rec_hit:
        out.append((pid, i, rec_hit, -1))      # -1 = named by the record
        continue
    h = WH.get(birds.thumb_url(u))
    if h is None: unmatched.append((pid, i)); continue
    hit = index.get(h)
    if hit and len(hit) == 1: out.append((pid, i, next(iter(hit)), 0)); continue
    if hit and len(hit) > 1: amb.append((pid, i)); continue
    best, bd = None, 99
    for p, hs in LH.items():
        d = min(ham(h, x) for x in hs)
        if d < bd: bd, best = d, p
    if bd <= 6: out.append((pid, i, best, bd))
    else: unmatched.append((pid, i))

json.dump([{"post": p, "idx": i, "file": f, "d": d} for p, i, f, d in out],
          open("/tmp/orig_map.json", "w"), indent=1)
sz = sum(os.path.getsize(f) for f in {f for _, _, f, _ in out})
print()
print("  matched   : %d of %d  (was 723)" % (len(out), len(web)))
print("  ambiguous : %d   unmatched: %d" % (len(amb), len(unmatched)))
print("  unique originals to upload: %d, %.2f GB" % (len({f for _,_,f,_ in out}), sz/1e9))
