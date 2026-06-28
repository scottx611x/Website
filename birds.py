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
import json
import os
import random
import re

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
LOCAL_MANIFEST = os.path.join(HERE, "birds", "manifest.json")

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


def images_for_species(shots, bird):
    """Single-image pseudo-shots for every frame of ``bird`` (its display name),
    so the gallery can render a filtered grid of just that species' photos. Photos
    are round-robin interleaved across posts (rather than clumped by post) so a
    single shoot doesn't dominate a run of the grid.
    """
    target = (bird or "").strip().lower()
    buckets = []
    for shot in shots:
        images = shot.get("images") or []
        isp = shot.get("image_species") or []
        iloc = shot.get("image_locations") or []
        caps = shot.get("captions") or []
        bucket = []
        for i, url in enumerate(images):
            raw = isp[i] if i < len(isp) and isp[i] else shot.get("species")
            canons = _canon_species_list(raw)
            if not any(c[0].lower() == target for c in canons):
                continue
            display = " & ".join(c[0] for c in canons)  # show co-occurring species
            loc = iloc[i] if i < len(iloc) and iloc[i] else shot.get("location")
            bucket.append({
                "id": "%s-%d" % (shot.get("id"), i),
                "images": [url],
                "captions": [caps[i] if i < len(caps) else ""],
                "image_species": [display],
                "image_locations": [loc],
                "species": display,
                "location": loc,
                "date": shot.get("date"),
                "caption": shot.get("caption") or "",
            })
        if bucket:
            buckets.append(bucket)
    # Deal one photo from each post per round so the same shoot is spread out.
    out = []
    buckets = [b for b in buckets if b]
    while buckets:
        for bucket in buckets:
            out.append(bucket.pop(0))
        buckets = [b for b in buckets if b]
    return out


def _shuffle_images_weighted(shot):
    """Reorder a post's frames with a weighted shuffle that favors the earlier
    images. Scott puts his favorites first, so the cover + carousel vary per load
    but lean toward those favorites. Keeps the parallel per-image arrays in sync,
    and the card's species/location follow the new cover image.
    """
    n = len(shot.get("images") or [])
    if n < 2:
        return
    # Efraimidis-Spirakis with weight decaying by original position (favorites first).
    order = sorted(range(n), key=lambda i: random.random() ** (1.0 / (n - i)), reverse=True)
    for key in ("images", "captions", "image_species", "image_locations"):
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


def apply_overrides(shots, overrides=None):
    """Apply hand-typed corrections and (re)compute the review flag in place."""
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
        shot["ambiguous"] = (not override) and _is_ambiguous(shot)
    return shots


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
    with open(OVERRIDES_FILE, "w") as fh:
        json.dump(overrides, fh, indent=2, sort_keys=True)
    shots = _load_local_manifest() or []
    apply_overrides(shots, overrides)
    with open(LOCAL_MANIFEST, "w") as fh:
        json.dump(shots, fh, indent=2)
    return next((s for s in shots if s.get("id") == post_id), None)


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
        images = []
        for i, src in enumerate(_post_images(item)):
            hosted = _rehost_image("{}-{}".format(item["id"], i), src)
            if hosted:
                images.append(hosted)
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

    apply_overrides(shots)  # bake in hand-typed corrections so prod gets them too
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
        with open(LOCAL_MANIFEST, "w") as fh:
            fh.write(payload)
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


def _species_pairs(caption):
    """List of (species, location, date) for a post, across caption formats.

    - Inline:  "Species - Location" (location may embed a date, may differ per
      species, and old posts may have a per-line date).
    - Block:   "Species" / blank / "Location" / blank / "Date" — the location is
      the block after the species block.
    """
    blocks = _blocks(caption)
    if not blocks:
        return []

    triples, inline = [], False
    for line in blocks[0]:
        if " - " in line:
            name, rest = line.split(" - ", 1)
            location, date = _split_loc_date(rest)
            triples.append((_clean_species(name), location, date))
            inline = True
        else:
            triples.append((_clean_species(line), None, None))
    triples = [(sp, loc, dt) for sp, loc, dt in triples if sp]

    # No inline locations: a following block (that isn't the date) is the location.
    if not inline and triples and len(blocks) > 1:
        candidate = ", ".join(blocks[1])
        if not _DATE_RE.search(candidate):
            location = _clean_location(candidate)
            if location:
                triples = [(sp, location, dt) for sp, _, dt in triples]
    return triples


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
