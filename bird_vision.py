"""Per-image species assignment by looking at the photos — fully local, no cloud.

A caption naming N species for a post of M>N images can't say which image is
which bird, so any caption-only heuristic guesses (and drops species). This does
a CONSTRAINED zero-shot classification with OpenCLIP: rank each image against the
caption's species (a small candidate set that plays to CLIP's strengths), then
assign so every named species gets at least one image (a species Scott named, he
photographed) — an optimal matching that structurally prevents dropped species.

No API, no account gating, no cost: an open CLIP model on CPU. torch/open_clip
are imported LAZILY here and only when classifying, so importing this module (or
the site, which never does) stays cheap. Runs offline to produce
vision_species.json; the web app just reads that JSON.
"""
import io
import os
import urllib.request

_MODEL = os.environ.get("BIRD_VISION_CLIP", "ViT-L-14")
_PRETRAINED = os.environ.get("BIRD_VISION_CLIP_PRETRAINED", "laion2b_s32b_b82k")
_TEMPLATES = ["a photo of a {}", "a photo of a {}, a bird",
              "a close-up photo of a {} bird", "{}, a species of bird"]
_state = {}


def _model():
    if "m" not in _state:
        import torch
        import open_clip
        m, _, pp = open_clip.create_model_and_transforms(_MODEL, pretrained=_PRETRAINED)
        m.eval()
        _state.update(m=m, pp=pp, tok=open_clip.get_tokenizer(_MODEL), torch=torch)
    return _state


def _load_img(src):
    """Open a PIL image from raw bytes, or from a URL (with retry — anonymous S3
    GETs can 403 under burst; callers with creds should pass bytes instead)."""
    import time
    from PIL import Image
    if isinstance(src, (bytes, bytearray)):
        return Image.open(io.BytesIO(src)).convert("RGB")
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0"})
            return Image.open(io.BytesIO(urllib.request.urlopen(req, timeout=30).read())).convert("RGB")
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise last


def _assign(sim, species):
    """sim: images x species similarity. Return a species per image such that every
    species is used at least once (matched to its best distinct image), and any
    remaining images go to their top match."""
    import numpy as np
    from scipy.optimize import linear_sum_assignment
    n, ns = sim.shape
    out = [None] * n
    if n >= ns:  # cover each species with its best free image (optimal assignment)
        rows, cols = linear_sum_assignment(-sim.T)  # species(rows) x images(cols)
        for sp_i, im_i in zip(rows, cols):
            out[im_i] = int(sp_i)
    for i in range(n):
        if out[i] is None:
            out[i] = int(np.asarray(sim[i]).argmax())
    return [species[j] for j in out]


def classify(images, species):
    """Assign each image to one of `species`. `images` is a list of URLs or raw
    image bytes. Returns a same-length list (each an item of `species`), or None
    on any failure — callers fall back to the caption heuristic so a model hiccup
    never breaks the pipeline."""
    species = [s for s in dict.fromkeys(species) if s]
    if len(images) < 2 or len(species) < 2:
        return None  # unambiguous — nothing to resolve
    image_urls = images
    try:
        import numpy as np
        st = _model()
        torch, m, pp, tok = st["torch"], st["m"], st["pp"], st["tok"]
        tfeats = []
        for s in species:  # prompt-ensembled text embedding per species
            t = tok([tmpl.format(s) for tmpl in _TEMPLATES])
            with torch.no_grad():
                f = m.encode_text(t); f /= f.norm(dim=-1, keepdim=True)
                f = f.mean(0); f /= f.norm()
            tfeats.append(f)
        tf = torch.stack(tfeats)
        n = len(image_urls)
        sim = np.zeros((n, len(species)))
        for i, u in enumerate(image_urls):
            im = pp(_load_img(u)).unsqueeze(0)
            with torch.no_grad():
                f = m.encode_image(im); f /= f.norm(dim=-1, keepdim=True)
            sim[i] = (f @ tf.T).numpy()[0]
        out = _assign(sim, species)
        return out if len(out) == n and all(s in species for s in out) else None
    except Exception as e:  # noqa: BLE001 - never let the classifier break a sync
        print("bird_vision: classify failed:", e)
        return None


def needs_vision(shot, species):
    """Worth classifying: 2+ images and 2+ distinct caption species (grouping
    across images is otherwise unknowable from the caption text)."""
    return len(shot.get("images") or []) >= 2 and len({s for s in species if s}) >= 2
