"""Bird gallery backend for birds.scott-ouellette.com.

Top-shots are derived from Scott's own @birdsofnorthandover posts, ranked by
Instagram like count. ``instagram_sync()`` runs on a schedule (see
zappa_settings.json), pulls the account's media via the Instagram Graph API,
re-hosts the top images to S3 (Instagram CDN URLs expire), and writes a
``manifest.json``. The web app reads that manifest -- never Instagram directly --
so the gallery is always fast and survives Instagram outages.

Instagram's API cannot read *likes you gave other people's* posts, so
"top-shots" means your own posts with the most likes. See birds/README.md for the
one-time token setup.

Environment variables (only needed for the sync job, not for serving):
    INSTAGRAM_ACCESS_TOKEN  long-lived token for the @birdsofnorthandover account
    INSTAGRAM_USER_ID       optional; resolved from the token if omitted
    BIRDS_S3_BUCKET         bucket to re-host images + manifest (default: zappa bucket)
    BIRDS_S3_PREFIX         key prefix (default: "birds")
    BIRDS_TOP_N             how many top shots to keep (default: 24)
"""

import bisect
import datetime
import difflib
import json
import os
import random
import re

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
LOCAL_MANIFEST = os.path.join(HERE, "birds", "manifest.json")


def _atomic_write_json(path, data, sort_keys=False):
    """Write JSON via a temp file + rename so a concurrent reader never sees a
    half-written (or empty) file."""
    tmp = "%s.tmp.%d" % (path, os.getpid())
    with open(tmp, "w") as fh:
        json.dump(data, fh, indent=2, sort_keys=sort_keys)
    os.replace(tmp, path)

GRAPH_BASE = "https://graph.instagram.com"
MEDIA_FIELDS = (
    "id,caption,media_type,media_url,thumbnail_url,permalink,timestamp,like_count,"
    "children{media_type,media_url,thumbnail_url}"
)

S3_BUCKET = os.environ.get("BIRDS_S3_BUCKET", "zappa-0206au0bc")
S3_PREFIX = os.environ.get("BIRDS_S3_PREFIX", "birds")
# Safety cap on how many posts to include (we consider all posts; this just
# bounds an unexpectedly huge account). Posts you hide via curation never count.
MAX_POSTS = int(os.environ.get("BIRDS_MAX_POSTS", "500"))

# Long-lived token lives in SSM Parameter Store (SecureString) so it can be
# rotated without redeploying. An INSTAGRAM_ACCESS_TOKEN env var overrides it
# (handy for local one-off runs). Mint the first token with auth.py.
SSM_TOKEN_PARAM = os.environ.get("INSTAGRAM_TOKEN_SSM_PARAM", "/birds/instagram_token")


# ---------------------------------------------------------------------------
# Serving
# ---------------------------------------------------------------------------
def load_gallery(shuffle=True):
    """Return the list of post dicts for rendering.

    Prefers the freshly-synced manifest cached in S3; falls back to the copy
    committed in the repo so the gallery renders even with no network/creds
    (e.g. local dev and CI). Shuffled by default so it feels fresh; pass
    ``shuffle=False`` for a stable order (used by curation mode).
    """
    shots = _load_manifest_from_s3()
    if shots is None:
        shots = _load_local_manifest()
    shots = list(shots or [])
    apply_overrides(shots)
    shots = [s for s in shots if s.get("images")]  # drop fully image-excluded posts
    if shuffle:
        return order_gallery(shots)
    # Stable view (curation): strict highest-likes-first (weight ~ like percentile),
    # tie-broken by most recent.
    return sorted(
        shots,
        key=lambda s: (s.get("weight") or 0, s.get("timestamp") or ""),
        reverse=True,
    )


# Bird taxonomy for Merlin-style family grouping. Keyed by the lower-cased
# normalize_species() name -> (display name, family group). Family order below
# roughly follows eBird taxonomy.
_FAMILY_ORDER = [
    "Ducks, Geese & Swans", "Turkeys & Grouse", "Pigeons & Doves", "Hummingbirds",
    "Plovers", "Sandpipers", "Gulls & Terns", "Loons", "Cormorants", "Pelicans",
    "Herons & Egrets", "New World Vultures", "Ospreys", "Hawks & Eagles", "Owls",
    "Woodpeckers", "Falcons", "Shrikes", "Tyrant Flycatchers", "Crows & Jays",
    "Chickadees & Titmice", "Swallows", "Kinglets", "Nuthatches", "Creepers",
    "Wrens", "Starlings", "Mockingbirds & Thrashers", "Thrushes", "Waxwings",
    "Old World Sparrows", "Finches", "New World Sparrows", "Blackbirds & Orioles",
    "Wood-Warblers", "Cardinals & Allies",
]


def _fam(names, family):
    return {n: (n.title() if n.islower() else n, family) for n in names}


_BIRDS = {}
for _names, _family in [
    (["Mallard", "American Black Duck", "Wood Duck", "Ring-necked Duck", "Bufflehead",
      "Hooded Merganser", "Red-breasted Merganser", "Common Eider", "Surf Scoter",
      "Canada Goose", "Mute Swan"], "Ducks, Geese & Swans"),
    (["Wild Turkey"], "Turkeys & Grouse"),
    (["Mourning Dove", "Rock Pigeon"], "Pigeons & Doves"),
    (["Ruby-throated Hummingbird"], "Hummingbirds"),
    (["Killdeer"], "Plovers"),
    (["Sanderling"], "Sandpipers"),
    (["American Herring Gull", "Ring-billed Gull"], "Gulls & Terns"),
    (["Common Loon"], "Loons"),
    (["Double-crested Cormorant"], "Cormorants"),
    (["Brown Pelican"], "Pelicans"),
    (["Great Blue Heron", "Great Egret", "Little Blue Heron", "Tricolored Heron"], "Herons & Egrets"),
    (["Turkey Vulture"], "New World Vultures"),
    (["Osprey"], "Ospreys"),
    (["Red-tailed Hawk", "Cooper's Hawk", "Sharp-shinned Hawk", "Red-shouldered Hawk",
      "Broad-winged Hawk", "Northern Harrier", "Bald Eagle"], "Hawks & Eagles"),
    (["Barred Owl"], "Owls"),
    (["Downy Woodpecker", "Hairy Woodpecker", "Red-bellied Woodpecker",
      "Pileated Woodpecker", "Northern Flicker", "Yellow-bellied Sapsucker"], "Woodpeckers"),
    (["Peregrine Falcon"], "Falcons"),
    (["Loggerhead Shrike"], "Shrikes"),
    (["Eastern Phoebe", "Eastern Kingbird"], "Tyrant Flycatchers"),
    (["Blue Jay", "American Crow"], "Crows & Jays"),
    (["Black-capped Chickadee", "Tufted Titmouse"], "Chickadees & Titmice"),
    (["Tree Swallow"], "Swallows"),
    (["Ruby-crowned Kinglet", "Golden-crowned Kinglet"], "Kinglets"),
    (["White-breasted Nuthatch"], "Nuthatches"),
    (["Brown Creeper"], "Creepers"),
    (["Carolina Wren", "House Wren"], "Wrens"),
    (["European Starling"], "Starlings"),
    (["Northern Mockingbird", "Gray Catbird"], "Mockingbirds & Thrashers"),
    (["American Robin", "Eastern Bluebird"], "Thrushes"),
    (["Cedar Waxwing"], "Waxwings"),
    (["House Sparrow"], "Old World Sparrows"),
    (["House Finch", "American Goldfinch", "Evening Grosbeak"], "Finches"),
    (["White-throated Sparrow", "Song Sparrow", "Chipping Sparrow", "American Tree Sparrow",
      "Fox Sparrow", "Savannah Sparrow", "Dark-eyed Junco"], "New World Sparrows"),
    (["Red-winged Blackbird", "Common Grackle", "Boat-tailed Grackle",
      "Brown-headed Cowbird"], "Blackbirds & Orioles"),
    (["Black-and-white Warbler", "Yellow-rumped Warbler", "Pine Warbler", "Ovenbird",
      "American Redstart", "Common Yellowthroat"], "Wood-Warblers"),
    (["Northern Cardinal"], "Cardinals & Allies"),
]:
    for _n in _names:
        _BIRDS[_n.lower()] = (_n, _family)

# Caption junk / merged-line / casing quirks -> canonical key in _BIRDS (or None to drop).
_SPECIES_ALIAS = {
    "a very wet barred owl": "barred owl",
    "a very wet red-tailed hawk": "red-tailed hawk",
    "northern house wren": "house wren",
    "european starling juvenile": "european starling",
    "cooper's hawk barred owl": "barred owl",
    "red-tailed hawk blue jay": "red-tailed hawk",
    "not a north andover bird": None,
}


def _canon_species(name):
    """(display name, family) for a raw species label, or None if not a real bird."""
    base = normalize_species(name)
    if not base:
        return None
    key = base.lower()
    if key in _SPECIES_ALIAS:
        alias = _SPECIES_ALIAS[key]
        if alias is None:
            return None
        key = alias
    return _BIRDS.get(key)


# A single frame can hold more than one species (e.g. a Cooper's Hawk mobbing a
# roosting Barred Owl); per-image labels join them with " & ".
_SPECIES_SPLIT_RE = re.compile(r"\s*[&+/]\s*")


def _canon_species_list(raw):
    """All distinct (display, family) species named in one per-image label."""
    out = []
    for part in _SPECIES_SPLIT_RE.split(raw or ""):
        canon = _canon_species(part)
        if canon and canon not in out:
            out.append(canon)
    return out


def _caption_area_species(caption):
    """Split one post's species into (local, out_of_area) display-name sets using
    Scott's ⚠️ marker. Handles inline "⚠️ Species - Place" and block form where
    species lines share a trailing "⚠️ Place" line; a leading "⚠️ <note>" tags the
    block that follows.
    """
    clean, ooa = set(), set()
    block = []            # [(display, warned_inline, has_inline_location)]
    note_warned = [False]  # a ⚠️ note/header with no species -> tags following block

    def flush(loc_warned):
        for display, w_inline, has_loc in block:
            warned = w_inline or note_warned[0] or (loc_warned and not has_loc)
            (ooa if warned else clean).add(display)
        block.clear()
        note_warned[0] = False

    for raw in (caption or "").splitlines():
        s = raw.strip()
        if not s:
            continue
        if s == "---":
            flush(False)
            continue
        warned = "⚠" in s
        text = s.replace("️", "").replace("⚠", "").strip()
        head = re.split(r"\s+[-–]\s+", text, maxsplit=1)
        canon = _canon_species(head[0])
        if canon:
            block.append((canon[0], warned, len(head) > 1))
        elif _DATE_RE.search(text):
            flush(False)
        elif block:
            flush(warned)         # a shared location line tags the block above it
        elif warned:
            note_warned[0] = True  # a ⚠️ header tags the block that follows
    flush(False)
    return clean, ooa


def out_of_area_species(shots):
    """Set of display names that only ever appear out-of-area (⚠️) — i.e. NOT
    North Andover birds. A species seen cleanly even once counts as local.
    """
    clean, ooa = set(), set()
    for shot in shots:
        c, o = _caption_area_species(shot.get("caption") or "")
        clean |= c
        ooa |= o
    return ooa - clean


def caption_species(caption):
    """Distinct species ORIGINALLY detected from a post's Instagram caption — the
    baseline to compare manual edits / AI re-classifications against in curate."""
    out = []
    for sp, _, _ in _species_pairs(caption):
        canon = _canon_species(sp)
        if canon and canon[0] not in out:
            out.append(canon[0])
    return out


def species_groups(shots):
    """The life list grouped Merlin-style by family. Returns an ordered list of
    ``(family, [(species, photo_count), ...])``; counts every frame of the species
    (matching the filtered view).
    """
    counts = {}
    for shot in shots:
        images = shot.get("images") or []
        isp = shot.get("image_species") or []
        for i in range(len(images)):
            raw = isp[i] if i < len(isp) and isp[i] else shot.get("species")
            for canon in _canon_species_list(raw):
                counts[canon] = counts.get(canon, 0) + 1
    by_family = {}
    for (display, family), count in counts.items():
        by_family.setdefault(family, []).append((display, count))
    order = {f: i for i, f in enumerate(_FAMILY_ORDER)}
    out = []
    for family in sorted(by_family, key=lambda f: order.get(f, 999)):
        species = sorted(by_family[family], key=lambda kv: (-kv[1], kv[0]))
        out.append((family, species))
    return out


def species_count(shots):
    return sum(len(sp) for _, sp in species_groups(shots))


def _pseudo_frame(shot, i):
    """A single-image 'pseudo-shot' for frame ``i`` of ``shot`` (used by filtered
    grids). Returns (frame_dict, canon_species_list)."""
    images = shot.get("images") or []
    isp = shot.get("image_species") or []
    iloc = shot.get("image_locations") or []
    caps = shot.get("captions") or []
    rts = shot.get("image_ratings") or []
    areas = shot.get("image_areas") or []
    raw = isp[i] if i < len(isp) and isp[i] else shot.get("species")
    canons = _canon_species_list(raw)
    display = " & ".join(c[0] for c in canons) or (shot.get("species") or "")
    loc = iloc[i] if i < len(iloc) and iloc[i] else shot.get("location")
    return {
        "id": "%s-%d" % (shot.get("id"), i),
        "post_id": shot.get("id"),
        "images": [images[i]],
        "captions": [caps[i] if i < len(caps) else ""],
        "image_species": [display],
        "image_locations": [loc],
        "image_areas": [areas[i] if i < len(areas) else "local"],
        "image_videos": [(shot.get("image_videos") or [None] * len(images))[i]
                         if i < len(shot.get("image_videos") or []) else None],
        "image_indices": [(shot.get("image_indices") or [])[i]
                          if i < len(shot.get("image_indices") or []) else i],
        "caption_species": shot.get("caption_species") or [],
        "species": display,
        "location": loc,
        "date": shot.get("date"),
        "caption": shot.get("caption") or "",
        "rating": rts[i] if i < len(rts) else 0,
    }, canons


def _interleave_buckets(buckets):
    """Highest-rated posts lead; deal one frame per post per round (interleaved so a
    single shoot doesn't clump)."""
    for bucket in buckets:
        bucket.sort(key=lambda f: f["rating"], reverse=True)  # best of each post first
    buckets = [b for b in buckets if b]
    buckets.sort(key=lambda b: b[0]["rating"], reverse=True)
    out = []
    while buckets:
        for bucket in buckets:
            out.append(bucket.pop(0))
        buckets = [b for b in buckets if b]
    return out


def images_filtered(shots, bird=None, family=None, area=None, ooa_only=(), media=None,
                     rating=None):
    """Interleaved single-image frames matching ALL active filters (composable):
    ``bird`` (species display name), ``family`` (Merlin group), ``area``
    ('local' = North Andover, 'elsewhere' = ⚠️ out-of-area-only species), ``media``
    ('video' = only videos), and ``rating`` ('unrated' = 0 stars, or 'N' = >= N)."""
    bird_l = (bird or "").strip().lower()
    fam = (family or "").strip()
    want_elsewhere = area in ("elsewhere", "away")
    has_area = area in ("local", "elsewhere", "away")
    want_video = media == "video"
    min_rating = int(rating) if (rating or "").isdigit() else None
    want_unrated = rating == "unrated"
    ooa_lower = {n.lower() for n in ooa_only}
    buckets = []
    for shot in shots:
        bucket = []
        for i in range(len(shot.get("images") or [])):
            frame, canons = _pseudo_frame(shot, i)
            names = [c[0].lower() for c in canons]
            if not names:
                continue
            if bird_l and bird_l not in names:
                continue
            if fam and not any(c[1] == fam for c in canons):
                continue
            if has_area:
                is_elsewhere = all(nm in ooa_lower for nm in names)
                if is_elsewhere != want_elsewhere:
                    continue
            if want_video and not frame["image_videos"][0]:
                continue
            if want_unrated and frame["rating"]:
                continue
            if min_rating is not None and frame["rating"] < min_rating:
                continue
            bucket.append(frame)
        if bucket:
            buckets.append(bucket)
    return _interleave_buckets(buckets)


def has_videos(shots):
    """Whether any frame in the gallery is a video (to show the Videos filter)."""
    return any(v for s in shots for v in (s.get("image_videos") or []))


def filter_shots(shots, bird=None, family=None, area=None, ooa_only=()):
    """Whole posts that contain at least one frame matching ALL active filters.
    Used by curate mode, which edits whole-post cards (not exploded frames)."""
    bird_l = (bird or "").strip().lower()
    fam = (family or "").strip()
    want_elsewhere = area in ("elsewhere", "away")
    has_area = area in ("local", "elsewhere", "away")
    ooa_lower = {n.lower() for n in ooa_only}
    out = []
    for shot in shots:
        for i in range(len(shot.get("images") or [])):
            _, canons = _pseudo_frame(shot, i)
            names = [c[0].lower() for c in canons]
            if not names:
                continue
            if bird_l and bird_l not in names:
                continue
            if fam and not any(c[1] == fam for c in canons):
                continue
            if has_area and (all(nm in ooa_lower for nm in names) != want_elsewhere):
                continue
            out.append(shot)
            break
    return out


def resolve_species(query, groups):
    """Snap a typed species query to a real species name (exact -> substring ->
    fuzzy), so the filter box tolerates partial entries and small typos."""
    query = (query or "").strip()
    if not query:
        return ""
    names = [name for _, sp in groups for name, _ in sp]
    low = query.lower()
    for n in names:
        if n.lower() == low:
            return n
    subs = [n for n in names if low in n.lower()]
    if subs:
        return min(subs, key=len)
    match = difflib.get_close_matches(query, names, n=1, cutoff=0.5)
    return match[0] if match else query


def _shuffle_images_weighted(shot):
    """Reorder a post's frames with a weighted shuffle that favors the earlier
    images. Scott puts his favorites first, so the cover + carousel vary per load
    but lean toward those favorites. Keeps the parallel per-image arrays in sync,
    and the card's species/location follow the new cover image.
    """
    n = len(shot.get("images") or [])
    if n < 2:
        return
    ratings = shot.get("image_ratings") or []
    # Efraimidis-Spirakis: weight decays by original position (favorites first), and
    # a curate-mode star rating boosts a frame so the best shots surface as the cover.
    def weight(i):
        rating = ratings[i] if i < len(ratings) else 0
        return (n - i) + 4.0 * rating
    order = sorted(range(n), key=lambda i: random.random() ** (1.0 / weight(i)), reverse=True)
    for key in ("images", "captions", "image_species", "image_locations", "image_ratings", "image_areas", "image_indices", "image_videos"):
        seq = shot.get(key)
        if isinstance(seq, list) and len(seq) == n:
            shot[key] = [seq[i] for i in order]
    if shot.get("image_species"):
        shot["species"] = shot["image_species"][0] or shot.get("species")
    if shot.get("image_locations"):
        shot["location"] = shot["image_locations"][0] or shot.get("location")


def order_gallery(shots):
    """Order for display: liked posts trend toward the top, species de-clumped.

    1. Weighted shuffle by popularity ``weight`` (Efraimidis-Spirakis), so it
       favors well-liked posts without being a strict descending leaderboard.
    2. Greedy pass that avoids placing the same species back-to-back, walking the
       weighted order from the front so the popularity bias is preserved.

    Each post's frames are also weight-shuffled (favorites-first) so the cover and
    carousel order feel fresh on every visit.
    """
    for shot in shots:
        _shuffle_images_weighted(shot)

    def weighted_key(shot):
        weight = (shot.get("weight") or 0) + 0.05  # keep zero-weight posts in play
        return random.random() ** (1.0 / weight)

    pool = sorted(shots, key=weighted_key, reverse=True)
    ordered, last = [], None
    while pool:
        pick = 0
        for i, shot in enumerate(pool):
            if normalize_species(shot.get("species")) != last:
                pick = i
                break
        chosen = pool.pop(pick)
        ordered.append(chosen)
        last = normalize_species(chosen.get("species"))
    return ordered


def _assign_weights(shots):
    """Replace each post's raw like count with a 0–1 popularity percentile.

    We keep only the percentile in the manifest (never the raw count) so likes
    influence ordering without ever being stored or shown.
    """
    likes = sorted(shot.get("_like", 0) for shot in shots)
    total = len(likes)
    for shot in shots:
        like = shot.pop("_like", 0)
        shot["weight"] = round(bisect.bisect_right(likes, like) / total, 3) if total else 1.0


# ---------------------------------------------------------------------------
# Curation — a persisted set of post ids to hide, respected by every sync.
# ---------------------------------------------------------------------------
def load_excluded():
    try:
        with open(EXCLUDED_FILE) as fh:
            return set(json.load(fh))
    except (OSError, ValueError):
        return set()


def add_exclusion(post_id):
    excluded = load_excluded()
    excluded.add(post_id)
    with open(EXCLUDED_FILE, "w") as fh:
        json.dump(sorted(excluded), fh, indent=2)
    # Drop it from the live manifest immediately so the change shows without a
    # full re-sync (the next scheduled sync will also respect it + backfill).
    shots = [s for s in (_load_local_manifest() or []) if s.get("id") != post_id]
    with open(LOCAL_MANIFEST, "w") as fh:
        json.dump(shots, fh, indent=2)
    return excluded


# Re-ID queue: specific frames (post id + image index) Scott has flagged in curate
# mode for Claude to re-identify. Lives in birds/reid_queue.json.
REID_QUEUE_FILE = os.path.join(HERE, "birds", "reid_queue.json")


def load_reid_queue():
    try:
        with open(REID_QUEUE_FILE) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return []


def _save_reid_queue(queue):
    with open(REID_QUEUE_FILE, "w") as fh:
        json.dump(queue, fh, indent=2)


def toggle_reid(post_id, index, current="", note=""):
    """Flag (or un-flag, if already present) one frame for re-identification.
    Returns ``(queue, is_queued)``.
    """
    index = int(index)
    queue = load_reid_queue()
    kept = [e for e in queue if not (e.get("id") == post_id and int(e.get("index", -1)) == index)]
    if len(kept) != len(queue):  # was present -> toggle off
        _save_reid_queue(kept)
        return kept, False
    kept.append({
        "id": post_id,
        "index": index,
        "current": current,
        "note": note,
        "flagged_at": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z",
    })
    _save_reid_queue(kept)
    return kept, True


def reid_keys():
    """Set of ``"<post id>-<index>"`` strings for frames awaiting re-ID."""
    return {"%s-%s" % (e.get("id"), e.get("index")) for e in load_reid_queue()}


def remove_exclusion(post_id):
    excluded = load_excluded()
    excluded.discard(post_id)
    with open(EXCLUDED_FILE, "w") as fh:
        json.dump(sorted(excluded), fh, indent=2)
    return excluded


# --- Manual species/caption fixes (curation) -------------------------------
# Instagram captions are parsed heuristically, so some posts get no species or
# several. `overrides.json` holds hand-typed corrections, keyed by post id, and
# is applied on every load + sync so it survives re-syncs (like excluded.json).
def load_overrides():
    try:
        with open(OVERRIDES_FILE) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _is_ambiguous(shot):
    """Needs review when no species was parsed, or several distinct ones were."""
    names = {normalize_species(s) for s in (shot.get("species_list") or []) if s}
    return len(names) != 1


def apply_overrides(shots, overrides=None, apply_exclusions=True):
    """Apply hand-typed corrections and (re)compute the review flag in place.

    ``apply_exclusions`` drops per-image-excluded frames (display path). It's left
    off when re-baking the saved manifest so the stored arrays stay full-length and
    re-application keeps the original-index keys aligned.
    """
    if overrides is None:
        overrides = load_overrides()
    for shot in shots:
        override = overrides.get(shot.get("id"))
        if override:
            if override.get("images"):
                per_image = override["images"]
                per_loc = override.get("image_locations") or {}
                n = len(shot.get("images") or [])
                shot["image_species"] = [(per_image.get(str(i)) or None) for i in range(n)]
                shot["image_locations"] = [(per_loc.get(str(i)) or None) for i in range(n)]
                assigned = [s for s in shot["image_species"] if s]
                if assigned:
                    shot["species"] = override.get("species") or assigned[0]
                    shot["species_list"] = list(dict.fromkeys(assigned))
                    locs = [l for l in shot["image_locations"] if l]
                    if locs:
                        shot["location"] = locs[0]
            if override.get("species"):
                shot["species"] = override["species"]
                if not override.get("images"):
                    shot["species_list"] = [override["species"]]
            if "location" in override:
                shot["location"] = override["location"] or None
            if override.get("date"):
                shot["date"] = override["date"]
            if override.get("ratings"):
                n = len(shot.get("images") or [])
                rt = override["ratings"]
                shot["image_ratings"] = [int(rt.get(str(i)) or 0) for i in range(n)]
        shot["ambiguous"] = (not override) and _is_ambiguous(shot)
        shot["image_areas"] = _image_areas(shot)
        cap = caption_species(shot.get("caption") or "")
        shot["caption_species"] = cap
        current = []
        for raw in (shot.get("image_species") or shot.get("species_list") or []):
            canon = _canon_species(raw)
            if canon and canon[0] not in current:
                current.append(canon[0])
        shot["reclassified"] = bool(cap) and any(s not in cap for s in current)
        if apply_exclusions:
            _apply_image_exclusions(shot, set((override or {}).get("exclude_images") or []))
        else:
            shot["image_indices"] = list(range(len(shot.get("images") or [])))
    return shots


def _apply_image_exclusions(shot, excluded):
    """Drop individual excluded frames from a post. Records each surviving frame's
    original index in ``image_indices`` so per-image edits still target the right
    frame after the array is re-indexed."""
    n = len(shot.get("images") or [])
    keep = [i for i in range(n) if i not in excluded]
    shot["image_indices"] = keep
    if len(keep) == n:
        return
    for key in ("images", "captions", "image_species", "image_locations",
                "image_ratings", "image_areas", "image_videos"):
        seq = shot.get(key)
        if isinstance(seq, list) and len(seq) == n:
            shot[key] = [seq[i] for i in keep]
    # cover species/location follow the surviving frames
    assigned = [s for s in (shot.get("image_species") or []) if s]
    if assigned:
        if shot.get("species") not in assigned:
            shot["species"] = assigned[0]
        shot["species_list"] = list(dict.fromkeys(assigned))
    locs = [l for l in (shot.get("image_locations") or []) if l]
    if locs and shot.get("location") not in locs:
        shot["location"] = locs[0]


def _image_areas(shot):
    """Per-frame 'local' / 'away' tag from the ⚠️ caption marker — a frame is 'away'
    when every species in it is out-of-area for that post."""
    clean, ooa = _caption_area_species(shot.get("caption") or "")
    isp = shot.get("image_species") or []
    n = len(shot.get("images") or [])
    areas = []
    for i in range(n):
        raw = isp[i] if i < len(isp) and isp[i] else shot.get("species")
        names = [c[0] for c in _canon_species_list(raw)]
        away = bool(names) and all(nm in ooa and nm not in clean for nm in names)
        areas.append("away" if away else "local")
    return areas


def set_override(post_id, fields):
    """Persist a correction for one post and reflect it in the local manifest now."""
    overrides = load_overrides()
    entry = overrides.get(post_id, {})
    for key in ("species", "location", "date"):
        if key in fields:
            entry[key] = (fields.get(key) or "").strip()
    if isinstance(fields.get("images"), dict):
        images = entry.get("images", {})
        for idx, name in fields["images"].items():
            images[str(idx)] = (name or "").strip()
        entry["images"] = {k: v for k, v in images.items() if v}
    if isinstance(fields.get("image_locations"), dict):
        locs = entry.get("image_locations", {})
        for idx, name in fields["image_locations"].items():
            locs[str(idx)] = (name or "").strip()
        entry["image_locations"] = {k: v for k, v in locs.items() if v}
    overrides[post_id] = entry
    _atomic_write_json(OVERRIDES_FILE, overrides, sort_keys=True)
    shots = _load_local_manifest() or []
    if shots:  # never clobber the manifest with an empty/failed read
        apply_overrides(shots, overrides, apply_exclusions=False)
        _atomic_write_json(LOCAL_MANIFEST, shots)
    return next((s for s in shots if s.get("id") == post_id), None)


def set_rating(post_id, index, rating):
    """Persist a 0-5 star rating for one frame (0 clears it) and reflect it in the
    local manifest now. Ratings boost a frame's prominence in the gallery."""
    rating = max(0, min(5, int(rating or 0)))
    overrides = load_overrides()
    entry = overrides.get(post_id, {})
    ratings = entry.get("ratings", {})
    if rating:
        ratings[str(index)] = rating
    else:
        ratings.pop(str(index), None)
    if ratings:
        entry["ratings"] = ratings
    else:
        entry.pop("ratings", None)
    overrides[post_id] = entry
    _atomic_write_json(OVERRIDES_FILE, overrides, sort_keys=True)
    shots = _load_local_manifest() or []
    if shots:  # never clobber the manifest with an empty/failed read
        apply_overrides(shots, overrides, apply_exclusions=False)
        _atomic_write_json(LOCAL_MANIFEST, shots)
    return rating


def toggle_image_exclusion(post_id, index):
    """Hide (or un-hide) a single frame of a post by its ORIGINAL image index.
    Returns the new excluded state. The frame is dropped at display time, so the
    rest of the carousel and the original-index overrides stay intact."""
    index = int(index)
    overrides = load_overrides()
    entry = overrides.get(post_id, {})
    excl = set(entry.get("exclude_images") or [])
    excluded = index not in excl
    if excluded:
        excl.add(index)
    else:
        excl.discard(index)
    if excl:
        entry["exclude_images"] = sorted(excl)
    else:
        entry.pop("exclude_images", None)
    overrides[post_id] = entry
    _atomic_write_json(OVERRIDES_FILE, overrides, sort_keys=True)
    return excluded


def _load_local_manifest():
    try:
        with open(LOCAL_MANIFEST) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _load_manifest_from_s3():
    if not os.environ.get("BIRDS_USE_S3"):
        return None
    try:
        import boto3

        obj = boto3.client("s3").get_object(
            Bucket=S3_BUCKET, Key="{}/manifest.json".format(S3_PREFIX)
        )
        return json.loads(obj["Body"].read())
    except Exception:  # noqa: BLE001 - any S3/parse error => fall back to repo copy
        return None


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------
TOKEN_FILE = os.path.join(HERE, ".ig_token")
EXCLUDED_FILE = os.path.join(HERE, "birds", "excluded.json")
OVERRIDES_FILE = os.path.join(HERE, "birds", "overrides.json")


def resolve_token():
    """Return the access token: env var, then local .ig_token file, then SSM."""
    token = os.environ.get("INSTAGRAM_ACCESS_TOKEN")
    if token:
        return token.strip()
    if os.path.isfile(TOKEN_FILE):
        with open(TOKEN_FILE) as fh:
            token = fh.read().strip()
        if token:
            return token
    return _ssm_get(SSM_TOKEN_PARAM)


def refresh_long_lived_token(token):
    """Extend a long-lived token's life (~60 more days). Token must be >24h old."""
    resp = requests.get(
        "{}/refresh_access_token".format(GRAPH_BASE),
        params={"grant_type": "ig_refresh_token", "access_token": token},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def scheduled_sync(event=None, context=None):
    """Entry point for the daily Lambda: refresh the token, persist it, then sync.

    Accepts (event, context) so it can be invoked directly as a Lambda handler.
    """
    token = resolve_token()
    if not token:
        raise RuntimeError(
            "No Instagram token found (env INSTAGRAM_ACCESS_TOKEN or SSM "
            "{}). Mint one with auth.py — see birds/README.md.".format(SSM_TOKEN_PARAM)
        )
    try:  # best-effort: keep the token alive so it never lapses while we run
        token = refresh_long_lived_token(token)
        _ssm_put(SSM_TOKEN_PARAM, token)
    except Exception:  # noqa: BLE001 - token may be <24h old; proceed regardless
        pass
    return instagram_sync(token=token)


def _ssm_get(name):
    try:
        import boto3

        resp = boto3.client("ssm").get_parameter(Name=name, WithDecryption=True)
        return resp["Parameter"]["Value"]
    except Exception:  # noqa: BLE001 - not configured / unavailable locally
        return None


def _ssm_put(name, value):
    try:
        import boto3

        boto3.client("ssm").put_parameter(
            Name=name, Value=value, Type="SecureString", Overwrite=True
        )
        return True
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------------
# Syncing
# ---------------------------------------------------------------------------
def instagram_sync(token=None):
    """Fetch all posts, skip hidden ones, re-host every still, write the manifest.

    Returns the list of post dicts that were written.
    """
    token = token or resolve_token()
    if not token:
        raise RuntimeError(
            "No Instagram token found; mint one with auth.py (see birds/README.md)."
        )

    excluded = load_excluded()
    media = _fetch_all_media(token)
    media = [m for m in media if m.get("id") not in excluded]
    media = media[:MAX_POSTS]

    shots = []
    for item in media:
        # Re-host every still image in the post (carousel frames included, video
        # thumbnails for clips) so the modal can page through them all.
        images, videos = [], []
        for i, (still, video) in enumerate(_post_media(item)):
            hosted = _rehost_image("{}-{}".format(item["id"], i), still)
            if not hosted:
                continue
            images.append(hosted)
            videos.append(_rehost_video("{}-{}".format(item["id"], i), video) if video else None)
        if not images:
            continue
        caption = (item.get("caption") or "").strip()
        captured = _capture_date_obj(caption, item.get("timestamp"))
        date = captured.strftime("%b %-d, %Y") if captured else None
        pairs = _species_pairs(caption)
        species_list = [sp for sp, _, _ in pairs]
        locations = [loc for _, loc, _ in pairs]
        shots.append(
            {
                "id": item["id"],
                "images": images,
                "image_videos": videos if any(videos) else [],
                "captions": _frame_captions(caption, len(images), date),
                "caption": caption,
                "species": species_list[0] if species_list else None,
                "species_list": species_list,
                "location": next((loc for loc in locations if loc), None),
                "locations": locations,
                "date": date,
                "permalink": item.get("permalink"),
                "timestamp": item.get("timestamp"),
                "_like": item.get("like_count") or 0,  # → popularity weight, then dropped
                "_captured": captured.isoformat() if captured else "",
            }
        )

    # Stable/curate order = newest capture date first (matches the date on cards).
    shots.sort(key=lambda s: s.pop("_captured"), reverse=True)
    _assign_weights(shots)  # converts _like → weight (0–1 percentile)

    # Durability guard: never clobber a good manifest with an empty result
    # (e.g. Instagram hiccup / token expiry). Keep the last known-good gallery.
    if not shots:
        return load_gallery()

    # Bake hand-typed corrections so prod gets them too, but keep arrays full-length
    # (exclusions are a display-time filter; baking them would misalign indices).
    apply_overrides(shots, apply_exclusions=False)
    _write_manifest(shots)
    return shots


def _fetch_all_media(token):
    user_id = os.environ.get("INSTAGRAM_USER_ID", "me")
    url = "{}/{}/media".format(GRAPH_BASE, user_id)
    params = {"fields": MEDIA_FIELDS, "access_token": token, "limit": 100}
    media = []
    while url:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
        media.extend(payload.get("data", []))
        url = payload.get("paging", {}).get("next")
        params = None  # the "next" URL already carries query params
    return media


def _still_url(media):
    """A single still-image URL for one media object (post or carousel child)."""
    if media.get("media_type") == "VIDEO":
        return media.get("thumbnail_url") or media.get("media_url")
    return media.get("media_url") or media.get("thumbnail_url")


def _post_images(item):
    """Every still image in a post, in order.

    - IMAGE / VIDEO: a single still (video → thumbnail frame).
    - CAROUSEL_ALBUM: one still per child (video children → their thumbnails),
      so the modal can page through the whole carousel.
    """
    if item.get("media_type") == "CAROUSEL_ALBUM":
        children = (item.get("children") or {}).get("data") or []
        urls = [_still_url(c) for c in children]
        urls = [u for u in urls if u]
        if urls:
            return urls
    url = _still_url(item)
    return [url] if url else []


def _post_media(item):
    """``(still_url, video_url_or_None)`` for every frame in a post, in order.
    Video frames carry both a poster still (thumbnail) and the playable video."""
    def frame(media):
        still = _still_url(media)
        video = media.get("media_url") if media.get("media_type") == "VIDEO" else None
        return (still, video) if still else None

    if item.get("media_type") == "CAROUSEL_ALBUM":
        children = (item.get("children") or {}).get("data") or []
        out = [f for f in (frame(c) for c in children) if f]
        if out:
            return out
    f = frame(item)
    return [f] if f else []


def _rehost_video(media_id, src_url):
    """Re-host a video file to S3 (Instagram's URLs expire) and return its public
    URL. Falls back to the Instagram URL when S3 isn't configured (local dev)."""
    if not src_url:
        return None
    if not os.environ.get("BIRDS_USE_S3"):
        return src_url
    key = "{}/videos/{}.mp4".format(S3_PREFIX, media_id)
    public_url = "https://{}.s3.amazonaws.com/{}".format(S3_BUCKET, key)
    try:
        import boto3

        s3 = boto3.client("s3")
        try:
            s3.head_object(Bucket=S3_BUCKET, Key=key)
            return public_url
        except Exception:  # noqa: BLE001 - not archived yet
            pass
        resp = requests.get(src_url, timeout=120)
        resp.raise_for_status()
        s3.put_object(
            Bucket=S3_BUCKET, Key=key, Body=resp.content, ContentType="video/mp4",
            CacheControl="public, max-age=31536000, immutable",
        )
        return public_url
    except Exception:  # noqa: BLE001 - S3 unavailable: serve Instagram's URL directly
        return src_url


def _rehost_image(media_id, src_url):
    """Re-host an image to S3 and return its public URL.

    Instagram's own URLs expire, so in production we copy the still into S3 and
    serve from there. When S3 isn't available (e.g. local dev with no AWS creds)
    we fall back to the Instagram URL so the gallery still renders — those links
    just won't last.
    """
    if not src_url:
        return None
    # No S3 in this environment (e.g. local dev): use Instagram's URL directly,
    # and don't waste time downloading. Production sets BIRDS_USE_S3.
    if not os.environ.get("BIRDS_USE_S3"):
        return src_url
    key = "{}/images/{}.jpg".format(S3_PREFIX, media_id)
    public_url = "https://{}.s3.amazonaws.com/{}".format(S3_BUCKET, key)
    try:
        import boto3

        s3 = boto3.client("s3")
        # Already archived? Keep it — that copy survives even if IG removes the
        # post, and we avoid re-downloading. Images are keyed by immutable media id.
        try:
            s3.head_object(Bucket=S3_BUCKET, Key=key)
            return public_url
        except Exception:  # noqa: BLE001 - not there yet, fetch + upload below
            pass

        resp = requests.get(src_url, timeout=30)
        resp.raise_for_status()
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=resp.content,
            ContentType="image/jpeg",
            CacheControl="public, max-age=31536000, immutable",
        )
        return public_url
    except Exception:  # noqa: BLE001 - S3 unavailable: serve Instagram's URL directly
        return src_url


def _write_manifest(shots):
    payload = json.dumps(shots, indent=2)
    # Cache to S3 for the running Lambda...
    try:
        import boto3

        boto3.client("s3").put_object(
            Bucket=S3_BUCKET,
            Key="{}/manifest.json".format(S3_PREFIX),
            Body=payload.encode("utf-8"),
            ContentType="application/json",
            CacheControl="public, max-age=300",
        )
    except Exception:  # noqa: BLE001 - S3 may be unavailable when run locally
        pass
    # ...and update the committed copy so it's reviewable/diffable in git.
    try:
        _atomic_write_json(LOCAL_MANIFEST, shots)
    except OSError:
        pass


def _clean_species(line):
    """Trim one caption line to a species label (drop location/parenthetical/emoji)."""
    line = (line or "").split(" - ")[0].split(" (")[0].strip()
    line = re.sub(r"[^A-Za-z0-9\s'\-]", "", line).strip()  # drop emoji/symbols
    return line[:60] or None


def _clean_location(text):
    """Tidy a location string (keep commas/periods, drop emoji)."""
    text = re.sub(r"[^A-Za-z0-9\s,.'/\-]", "", text or "").strip(" ,-")
    return text[:80] or None


def _blocks(caption):
    """Caption split into blocks of consecutive non-empty, non-hashtag lines."""
    blocks, current = [], []
    for line in (caption or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            if current:
                blocks.append(current)
                current = []
            if stripped.startswith("#"):
                break
            continue
        current.append(stripped)
    if current:
        blocks.append(current)
    return blocks


def _split_loc_date(text):
    """Pull a trailing/embedded date out of an inline location string.

    Handles "Lake Cochichewick 11-13-25" -> ("Lake Cochichewick", date) and a
    bare "1-23-26" -> (None, date).
    """
    date = None
    match = _DATE_RE.search(text or "")
    if match:
        month, day, year = (int(p) for p in match.groups())
        if year < 100:
            year += 2000
        try:
            date = datetime.date(year, month, day)
        except ValueError:
            date = None
        text = (text[: match.start()] + " " + text[match.end():]).strip()
    return _clean_location(text), date


# Tokens that mark a line as a location rather than a species (street/place types
# and the places Scott shoots). Used to classify ambiguous bare lines.
_LOC_HINT = re.compile(
    r"\b(st|ave|rd|road|street|blvd|dr|drive|ln|lane|ct|way|bridge|beach|park|"
    r"square|wharf|harborwalk|harbor|dock|docks|refuge|sanctuary|wildlife|"
    r"memorial|school|sargent|cochichewick|shawsheen|ma|me|nh|fl|maine|florida|"
    r"boston|andover|ipswich|concord|lincoln|westborough|lewiston|litchfield|"
    r"york|cambridge|gloucester|dorchester|seaport|congress)\b\.?",
    re.I,
)


def _is_location_line(text):
    text = text or ""
    return bool(_DATE_RE.search(text) or "," in text or _LOC_HINT.search(text))


def _is_species_line(text):
    """A line names a bird if it's a known species, or simply doesn't look like a
    location/date (so unmapped birds still parse)."""
    return _canon_species(_clean_species(text)) is not None or not _is_location_line(text)


def _split_known(text):
    """If ``text`` is one or more known birds (possibly "A & B"), the cleaned
    species strings; else None. Parentheticals/notes are trimmed before the lookup
    so 'Juvenile Barred Owl ("Mojo")' still resolves."""
    cleaned = [_clean_species(p) for p in _SPECIES_SPLIT_RE.split(text or "")]
    cleaned = [c for c in cleaned if c]
    if cleaned and all(_canon_species(c) for c in cleaned):
        return cleaned
    return None


def _species_pairs(caption):
    """List of (species, location, date) for a post, robust across formats:

    - Inline:  "Species - Location" (optionally ⚠️-prefixed, location may embed a
      per-line date, and may differ per species).
    - Block:   bare "Species" lines that share a trailing "Location" line — even
      across a "---" separator, and even when the location carries the ⚠️ marker.

    Bare lines are classified species vs. location/date via the bird taxonomy and
    location hints, so trailing out-of-area blocks no longer drop their location.
    """
    triples = []
    pending = []  # species still awaiting a shared location line

    def flush(location, date):
        for sp in pending:
            triples.append((sp, location, date))
        del pending[:]

    for raw in (caption or "").splitlines():
        s = raw.strip()
        if s.startswith("#"):
            break
        s = s.replace("️", "").replace("⚠", "").strip()
        if not s:
            continue
        if set(s) <= set("-–—"):  # a "---" style separator ends the current block
            flush(None, None)
            continue
        parts = re.split(r"\s+[-–]\s+", s, 1)
        if len(parts) > 1 and _is_species_line(parts[0]):
            location, date = _split_loc_date(parts[1])
            for nm in _split_known(parts[0]) or [_clean_species(parts[0])]:
                if location or date:
                    triples.append((nm, location, date))
                else:
                    pending.append(nm)
        else:
            names = _split_known(s)
            if names:
                pending.extend(names)               # bare species (maybe "A & B")
            elif _is_location_line(s):
                location, date = _split_loc_date(s)  # shared location / bare date
                flush(location, date)
            # else: a note line -> ignore
    flush(None, None)
    return [(sp, loc, dt) for sp, loc, dt in triples if sp]


def _species_lines(caption):
    """Just the species names for a post (used by the ticker)."""
    return [sp for sp, _, _ in _species_pairs(caption)]


def _guess_species(caption):
    """The single best species label for a post (its first species)."""
    pairs = _species_pairs(caption)
    return pairs[0][0] if pairs else None


def _joined_label(pairs):
    """One label for a post we can't map per-image (more photos than species)."""
    locations = {loc for _, loc, _ in pairs}
    if len(locations) == 1 and None not in locations:
        return ", ".join(sp for sp, _, _ in pairs) + " · " + pairs[0][1]
    return ", ".join(
        sp + (" ({})".format(loc) if loc else "") for sp, loc, _ in pairs
    )


def _frame_captions(caption, n_images, date):
    """A display caption (species · location · date) per carousel image.

    Posts list one "Species - Location" per line. When that count matches the
    image count we pair them up so each frame shows its own bird + place (and its
    own date, for old per-line-dated posts). Otherwise (more photos than species)
    we can't pin each image, so we show the post's full species list.
    """
    pairs = _species_pairs(caption)
    if not pairs:
        return [date or "" for _ in range(n_images)]
    if len(pairs) == n_images:
        labels = []
        for species, location, line_date in pairs:
            when = line_date.strftime("%b %-d, %Y") if line_date else date
            labels.append(" · ".join(p for p in (species, location, when) if p))
        return labels
    label = _joined_label(pairs)
    return [" · ".join(p for p in (label, date) if p)] * n_images


# Words that describe an individual, not the species — dropped when normalizing.
_SPECIES_QUALIFIERS = {
    "baby", "babies", "juvenile", "juv", "immature", "fledgling", "fledglings",
    "adult", "male", "female", "pair", "nesting", "young",
}


def normalize_species(name):
    """Canonical species name for grouping (e.g. the ticker).

    Strips emoji/punctuation, drops qualifier words ("Baby", "Juvenile", ...),
    and de-pluralizes the last word so "Barred Owls", "Baby Barred Owl", and
    "Barred Owl Baby" all collapse to "Barred Owl".
    """
    if not name:
        return None
    cleaned = re.sub(r"[^A-Za-z\s'\-]", " ", name)  # drop emoji, symbols, digits
    words = [w for w in cleaned.split() if w.lower() not in _SPECIES_QUALIFIERS]
    if not words:
        return None
    last = words[-1]
    if len(last) > 3 and last.lower().endswith("s") and not last.lower().endswith("ss"):
        words[-1] = last[:-1]
    return " ".join(words)


_DATE_RE = re.compile(r"\b(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})\b")


def _capture_date_obj(caption, timestamp):
    """The capture date as a ``date``.

    Scott writes the real shoot date in the caption (e.g. "3-27-26"), which is
    more accurate than the post time (he posts days/weeks later), so we parse that
    first and fall back to the Instagram timestamp.
    """
    match = _DATE_RE.search(caption or "")
    if match:
        month, day, year = (int(part) for part in match.groups())
        if year < 100:
            year += 2000
        try:
            return datetime.date(year, month, day)
        except ValueError:
            pass
    if timestamp:
        try:
            return datetime.datetime.strptime(timestamp[:10], "%Y-%m-%d").date()
        except ValueError:
            pass
    return None


def _capture_date(caption, timestamp):
    """Capture date as a display string like "Mar 27, 2026" (or None)."""
    dt = _capture_date_obj(caption, timestamp)
    return dt.strftime("%b %-d, %Y") if dt else None


def ticker_species(shots):
    """De-duplicated, normalized species names across all posts, first-seen order.

    Uses each post's full species list (not just the first) so every bird shows
    up in the ticker, including ones only featured alongside others.
    """
    seen, out = set(), []
    for shot in shots:
        names = shot.get("species_list") or ([shot["species"]] if shot.get("species") else [])
        for raw in names:
            name = normalize_species(raw)
            if name and name.lower() not in seen:
                seen.add(name.lower())
                out.append(name)
    return out


if __name__ == "__main__":  # manual run: python birds.py
    written = instagram_sync()
    print("Wrote {} top shots to {}".format(len(written), LOCAL_MANIFEST))
