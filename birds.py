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
import zlib

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
    # Whole-post exclusions are baked in at sync time, but a LIVE hide on the
    # deployed site writes only excluded.json — so drop excluded ids at serve
    # time too, and the hide shows on the next request rather than the next sync.
    excluded = load_excluded()
    if excluded:
        shots = [s for s in shots if s.get("id") not in excluded]
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
# normalize_species() name -> (display name, family group). Broad coverage of the
# birds regularly occurring in the continental US so Scott never has to have a new
# species hand-added; anything still unrecognized falls into _OTHER_FAMILY (see
# _canon_species_list) rather than being dropped. Family order follows eBird
# taxonomy. Display names match how Scott writes them in captions (e.g. "American
# Herring Gull", "Northern House Wren") so existing overrides keep resolving.
_OTHER_FAMILY = "Other birds"

_TAXONOMY = [
    ("Ducks, Geese & Swans", [
        "Snow Goose", "Ross's Goose", "Greater White-fronted Goose", "Brant", "Cackling Goose",
        "Canada Goose", "Mute Swan", "Trumpeter Swan", "Tundra Swan", "Wood Duck",
        "Blue-winged Teal", "Cinnamon Teal", "Northern Shoveler", "Gadwall", "American Wigeon",
        "Eurasian Wigeon", "Mallard", "American Black Duck", "Mottled Duck", "Northern Pintail",
        "Green-winged Teal", "Canvasback", "Redhead", "Ring-necked Duck", "Greater Scaup",
        "Lesser Scaup", "King Eider", "Common Eider", "Harlequin Duck", "Surf Scoter",
        "White-winged Scoter", "Black Scoter", "Long-tailed Duck", "Bufflehead", "Common Goldeneye",
        "Barrow's Goldeneye", "Hooded Merganser", "Common Merganser", "Red-breasted Merganser",
        "Ruddy Duck"]),
    ("Turkeys & Grouse", [
        "Wild Turkey", "Ruffed Grouse", "Spruce Grouse", "Northern Bobwhite", "Ring-necked Pheasant"]),
    ("Grebes", [
        "Pied-billed Grebe", "Horned Grebe", "Red-necked Grebe", "Eared Grebe", "Western Grebe"]),
    ("Pigeons & Doves", [
        "Rock Pigeon", "Band-tailed Pigeon", "Eurasian Collared-Dove", "Common Ground Dove",
        "White-winged Dove", "Mourning Dove"]),
    ("Cuckoos", ["Yellow-billed Cuckoo", "Black-billed Cuckoo"]),
    ("Nightjars", ["Common Nighthawk", "Eastern Whip-poor-will", "Chuck-will's-widow"]),
    ("Swifts", ["Chimney Swift"]),
    ("Hummingbirds", [
        "Ruby-throated Hummingbird", "Rufous Hummingbird", "Anna's Hummingbird",
        "Black-chinned Hummingbird"]),
    ("Rails, Gallinules & Coots", [
        "Clapper Rail", "Virginia Rail", "Sora", "Common Gallinule", "American Coot"]),
    ("Cranes", ["Sandhill Crane"]),
    ("Stilts & Avocets", ["Black-necked Stilt", "American Avocet"]),
    ("Oystercatchers", ["American Oystercatcher"]),
    ("Plovers", [
        "Black-bellied Plover", "American Golden-Plover", "Killdeer", "Semipalmated Plover",
        "Piping Plover", "Wilson's Plover"]),
    ("Sandpipers", [
        "Upland Sandpiper", "Whimbrel", "Marbled Godwit", "Ruddy Turnstone", "Red Knot",
        "Sanderling", "Dunlin", "Purple Sandpiper", "Least Sandpiper", "White-rumped Sandpiper",
        "Semipalmated Sandpiper", "Western Sandpiper", "Short-billed Dowitcher", "Long-billed Dowitcher",
        "American Woodcock", "Wilson's Snipe", "Spotted Sandpiper", "Solitary Sandpiper",
        "Greater Yellowlegs", "Willet", "Lesser Yellowlegs", "Pectoral Sandpiper"]),
    ("Gulls & Terns", [
        "Bonaparte's Gull", "Laughing Gull", "Ring-billed Gull", "American Herring Gull",
        "Great Black-backed Gull", "Lesser Black-backed Gull", "Iceland Gull", "Glaucous Gull",
        "Least Tern", "Caspian Tern", "Black Tern", "Common Tern", "Forster's Tern", "Royal Tern",
        "Black Skimmer"]),
    ("Loons", ["Red-throated Loon", "Common Loon"]),
    ("Cormorants", ["Double-crested Cormorant", "Great Cormorant"]),
    ("Anhingas", ["Anhinga"]),
    ("Pelicans", ["American White Pelican", "Brown Pelican"]),
    ("Herons & Egrets", [
        "American Bittern", "Least Bittern", "Great Blue Heron", "Great Egret", "Snowy Egret",
        "Little Blue Heron", "Tricolored Heron", "Reddish Egret", "Cattle Egret", "Green Heron",
        "Black-crowned Night Heron", "Yellow-crowned Night Heron"]),
    ("Ibises & Spoonbills", ["White Ibis", "Glossy Ibis", "Roseate Spoonbill"]),
    ("New World Vultures", ["Black Vulture", "Turkey Vulture"]),
    ("Ospreys", ["Osprey"]),
    ("Hawks & Eagles", [
        "Golden Eagle", "Northern Harrier", "Sharp-shinned Hawk", "Cooper's Hawk", "Northern Goshawk",
        "Bald Eagle", "Mississippi Kite", "Swallow-tailed Kite", "Red-shouldered Hawk",
        "Broad-winged Hawk", "Red-tailed Hawk", "Rough-legged Hawk", "Swainson's Hawk"]),
    ("Owls", [
        "Barn Owl", "Eastern Screech-Owl", "Great Horned Owl", "Snowy Owl", "Barred Owl",
        "Long-eared Owl", "Short-eared Owl", "Northern Saw-whet Owl"]),
    ("Kingfishers", ["Belted Kingfisher"]),
    ("Woodpeckers", [
        "Red-headed Woodpecker", "Red-bellied Woodpecker", "Yellow-bellied Sapsucker",
        "Downy Woodpecker", "Hairy Woodpecker", "Northern Flicker", "Pileated Woodpecker"]),
    ("Falcons", ["American Kestrel", "Merlin", "Peregrine Falcon"]),
    ("Tyrant Flycatchers", [
        "Eastern Wood-Pewee", "Acadian Flycatcher", "Alder Flycatcher", "Willow Flycatcher",
        "Least Flycatcher", "Eastern Phoebe", "Great Crested Flycatcher", "Eastern Kingbird"]),
    ("Shrikes", ["Loggerhead Shrike", "Northern Shrike"]),
    ("Vireos", [
        "White-eyed Vireo", "Yellow-throated Vireo", "Blue-headed Vireo", "Warbling Vireo",
        "Philadelphia Vireo", "Red-eyed Vireo"]),
    ("Crows & Jays", ["Blue Jay", "American Crow", "Fish Crow", "Common Raven"]),
    ("Larks", ["Horned Lark"]),
    ("Chickadees & Titmice", ["Black-capped Chickadee", "Carolina Chickadee", "Tufted Titmouse"]),
    ("Swallows", [
        "Northern Rough-winged Swallow", "Purple Martin", "Tree Swallow", "Bank Swallow",
        "Barn Swallow", "Cliff Swallow"]),
    ("Kinglets", ["Golden-crowned Kinglet", "Ruby-crowned Kinglet"]),
    ("Nuthatches", ["Red-breasted Nuthatch", "White-breasted Nuthatch", "Brown-headed Nuthatch"]),
    ("Creepers", ["Brown Creeper"]),
    ("Gnatcatchers", ["Blue-gray Gnatcatcher"]),
    ("Wrens", [
        "Carolina Wren", "Northern House Wren", "Winter Wren", "Sedge Wren", "Marsh Wren"]),
    ("Starlings", ["European Starling"]),
    ("Mockingbirds & Thrashers", ["Gray Catbird", "Brown Thrasher", "Northern Mockingbird"]),
    ("Thrushes", [
        "Eastern Bluebird", "Veery", "Gray-cheeked Thrush", "Swainson's Thrush", "Hermit Thrush",
        "Wood Thrush", "American Robin"]),
    ("Waxwings", ["Cedar Waxwing", "Bohemian Waxwing"]),
    ("Old World Sparrows", ["House Sparrow"]),
    ("Pipits", ["American Pipit"]),
    ("Finches", [
        "Evening Grosbeak", "Pine Grosbeak", "House Finch", "Purple Finch", "Common Redpoll",
        "Red Crossbill", "White-winged Crossbill", "Pine Siskin", "American Goldfinch"]),
    ("Longspurs", ["Lapland Longspur", "Snow Bunting"]),
    ("New World Sparrows", [
        "Eastern Towhee", "American Tree Sparrow", "Chipping Sparrow", "Field Sparrow",
        "Vesper Sparrow", "Savannah Sparrow", "Grasshopper Sparrow", "Fox Sparrow", "Song Sparrow",
        "Lincoln's Sparrow", "Swamp Sparrow", "White-throated Sparrow", "White-crowned Sparrow",
        "Dark-eyed Junco", "Saltmarsh Sparrow", "Nelson's Sparrow", "Seaside Sparrow"]),
    ("Blackbirds & Orioles", [
        "Bobolink", "Red-winged Blackbird", "Eastern Meadowlark", "Orchard Oriole", "Baltimore Oriole",
        "Brown-headed Cowbird", "Rusty Blackbird", "Common Grackle", "Boat-tailed Grackle",
        "Great-tailed Grackle"]),
    ("Wood-Warblers", [
        "Ovenbird", "Worm-eating Warbler", "Louisiana Waterthrush", "Northern Waterthrush",
        "Blue-winged Warbler", "Golden-winged Warbler", "Black-and-white Warbler", "Prothonotary Warbler",
        "Tennessee Warbler", "Nashville Warbler", "Common Yellowthroat", "American Redstart",
        "Cape May Warbler", "Northern Parula", "Magnolia Warbler", "Bay-breasted Warbler",
        "Blackburnian Warbler", "Yellow Warbler", "Chestnut-sided Warbler", "Blackpoll Warbler",
        "Black-throated Blue Warbler", "Palm Warbler", "Pine Warbler", "Yellow-rumped Warbler",
        "Yellow-throated Warbler", "Prairie Warbler", "Black-throated Green Warbler", "Canada Warbler",
        "Wilson's Warbler", "Hooded Warbler"]),
    ("Cardinals & Allies", [
        "Summer Tanager", "Scarlet Tanager", "Northern Cardinal", "Rose-breasted Grosbeak",
        "Blue Grosbeak", "Indigo Bunting", "Dickcissel"]),
]

# Colloquial / merged-name -> canonical key handled by _SPECIES_ALIAS below.
_FAMILY_ORDER = [fam for fam, _ in _TAXONOMY] + [_OTHER_FAMILY]

_BIRDS = {}
for _family, _names in _TAXONOMY:
    for _n in _names:
        _BIRDS[_n.lower()] = (_n, _family)

# Hyphen/space-insensitive index onto the canonical keys, so "White Throated
# Sparrow" finds "white-throated sparrow" (Scott isn't consistent with hyphens).
_BIRDS_FLAT = {k.replace("-", " "): k for k in _BIRDS}

# Caption junk / merged-line / casing quirks -> canonical key in _BIRDS (or None to drop).
_SPECIES_ALIAS = {
    "a very wet barred owl": "barred owl",
    "a very wet red-tailed hawk": "red-tailed hawk",
    "house wren": "northern house wren",
    "european starling juvenile": "european starling",
    "eastern wood pewee": "eastern wood-pewee",  # Scott writes it un-hyphenated
    "red-bellied wookpecker": "red-bellied woodpecker",  # caption typo
    "cooper's hawk barred owl": "barred owl",
    "red-tailed hawk blue jay": "red-tailed hawk",
    "canadian goose": "canada goose",  # colloquial name for Canada Goose
    "not a north andover bird": None,
}

# Irregular plurals normalize_species can't get by stripping a trailing "s".
_IRREGULAR_PLURALS = {"geese": "goose"}


def _canon_species(name):
    """(display name, family) for a raw species label, or None if not a real bird.

    Tolerant of how Scott actually types captions: an explicit alias wins, then an
    exact match, then a hyphen/space-insensitive match ("White Throated Sparrow"),
    then a tightly-guarded fuzzy match for one-off typos ("Northen Flicker"). A
    label that still doesn't land on a known bird returns None (dropped)."""
    base = normalize_species(name)
    if not base:
        return None
    key = base.lower()
    if key in _SPECIES_ALIAS:
        alias = _SPECIES_ALIAS[key]
        if alias is None:
            return None
        key = alias
    if key in _BIRDS:
        return _BIRDS[key]
    flat = key.replace("-", " ")
    if flat in _BIRDS_FLAT:
        return _BIRDS[_BIRDS_FLAT[flat]]
    fuzzy = _fuzzy_species_key(flat)
    return _BIRDS[fuzzy] if fuzzy else None


def _fuzzy_species_key(flat):
    """Canonical _BIRDS key for a hyphen-flattened label that's a near-miss of a
    real species — catches caption typos like "Northen Flicker" without inventing
    matches. Guarded hard: only same-word-count candidates, high similarity cutoff,
    and the runner-up must be clearly worse, so genuinely different species (Cooper's
    vs Sharp-shinned Hawk) never collapse together."""
    n_words = len(flat.split())
    candidates = [k for k in _BIRDS_FLAT if len(k.split()) == n_words]
    close = difflib.get_close_matches(flat, candidates, n=2, cutoff=0.86)
    if not close:
        return None
    best = difflib.SequenceMatcher(None, flat, close[0]).ratio()
    if len(close) > 1:
        runner = difflib.SequenceMatcher(None, flat, close[1]).ratio()
        if best - runner < 0.06:  # ambiguous near-tie -> don't guess
            return None
    return _BIRDS_FLAT[close[0]] if best >= 0.86 else None


# A single frame can hold more than one species (e.g. a Cooper's Hawk mobbing a
# roosting Barred Owl); per-image labels join them with " & ".
_SPECIES_SPLIT_RE = re.compile(r"\s*[&+/]\s*")


# Connective/attribution words that never appear standalone in a bird's common
# name — their mere presence marks a caption line as a note, not a species.
_NOTE_MARKERS = {
    "and", "with", "of", "the", "a", "an", "by", "captured", "help", "eating",
    "nest", "nesting", "rookery", "not",
}
# Words that describe an individual, not the species; a line made only of these
# (e.g. "Parents") is a note. Real qualified birds ("Juvenile Barred Owl") resolve
# via _canon_species first, so these never wrongly reject a known bird.
_NOTE_WORDS = _NOTE_MARKERS | {
    "pair", "parent", "parents", "juvenile", "juveniles", "juv", "immature",
    "adult", "baby", "babies", "fledgling", "fledglings", "male", "female",
    "young", "north", "andover", "bird",
}


def _looks_like_bird(text):
    """Heuristic: does ``text`` read like a bird's name we just don't know yet?

    Keeps genuinely-new species (proper-case, 1-4 alphabetic words, not a place or
    date) so they're never silently dropped, while rejecting caption notes/junk
    ("and parent", "Heron Rookery", "Captured by ...", street names). Real, mapped
    birds go through _canon_species first; this only catches the unmapped tail."""
    name = _clean_species(text)
    if not name:
        return False
    words = [w.lower() for w in name.split()]
    if not (1 <= len(words) <= 4):
        return False
    if not name[0].isupper() or any(ch.isdigit() for ch in name):
        return False
    if _is_location_line(name):
        return False
    # A lone possessive ("Taki's") is a place/person, never a bird — real
    # possessive bird names carry the group word too ("Cooper's Hawk").
    if len(words) == 1 and words[0].endswith("'s"):
        return False
    if any(w in _NOTE_MARKERS for w in words):
        return False
    return not all(w in _NOTE_WORDS for w in words)


def _canon_species_list(raw):
    """All distinct (display, family) species named in one per-image label.

    An unrecognized but bird-like label is kept under ``_OTHER_FAMILY`` rather than
    dropped, so a species not yet in the taxonomy still shows, counts, and can be a
    lifer — it just lands in "Other birds" until it's slotted into a family."""
    out = []
    for part in _SPECIES_SPLIT_RE.split(raw or ""):
        canon = _canon_species(part)
        if not canon and _looks_like_bird(part):
            canon = (_clean_species(part), _OTHER_FAMILY)
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
        canons = _canon_species_list(head[0])
        if canons:
            for c in canons:  # a line may list several species ("A & B")
                block.append((c[0], warned, len(head) > 1))
        elif _DATE_RE.search(text):
            flush(False)
        elif block:
            flush(warned)         # a shared location line tags the block above it
        elif warned:
            note_warned[0] = True  # a ⚠️ header tags the block that follows
    flush(False)
    return clean, ooa


def out_of_area_species(shots):
    """Set of display names that only ever appear out-of-area — i.e. NOT North
    Andover birds. A species seen local even once counts as local.

    Derived from the per-frame ``image_areas`` (caption ⚠️ marker *plus* any
    manual curate override), so hand-marking a frame out-of-area flows through
    to the species-level 'spotted elsewhere' set. Falls back to the raw caption
    marker for shots not yet run through ``apply_overrides``.
    """
    clean, ooa = set(), set()
    for shot in shots:
        areas = shot.get("image_areas")
        if not areas:  # not override-applied yet: use the caption marker directly
            c, o = _caption_area_species(shot.get("caption") or "")
            clean |= c
            ooa |= o
            continue
        isp = shot.get("image_species") or []
        for i in range(len(shot.get("images") or [])):
            raw = isp[i] if i < len(isp) and isp[i] else shot.get("species")
            area = areas[i] if i < len(areas) else "local"
            for name, _ in _canon_species_list(raw):
                (ooa if area == "away" else clean).add(name)
    return ooa - clean


def _species_in_caption(display, caption_lc):
    """Whether a canonical species is mentioned in the caption text — as a phrase
    (hyphen/punctuation-insensitive) or, failing that, with every word fuzzily
    present (so caption typos like 'Northen Flicker' / 'Wookpecker' don't count as
    a reclassification). Genuinely different species still don't match."""
    phrase = re.sub(r"[^a-z]+", " ", display.lower()).strip()
    if not phrase:
        return False
    if phrase in caption_lc:
        return True
    cwords = caption_lc.split()
    words = [w for w in phrase.split() if len(w) > 2]
    return bool(words) and all(
        w in cwords or difflib.get_close_matches(w, cwords, 1, 0.82) for w in words
    )


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
    areas = shot.get("image_areas") or []
    raw = isp[i] if i < len(isp) and isp[i] else shot.get("species")
    canons = _canon_species_list(raw)
    display = " & ".join(c[0] for c in canons) or (shot.get("species") or "")
    loc = canonical_location(iloc[i] if i < len(iloc) and iloc[i] else shot.get("location"))
    dims = shot.get("image_dims") or []
    _sd = _capture_date_obj(shot.get("caption") or "", shot.get("timestamp"))
    return {
        "id": "%s-%d" % (shot.get("id"), i),
        "_sort": _sd.isoformat() if _sd else "",
        "_posted": shot.get("timestamp") or "",
        "post_id": shot.get("id"),
        "images": [images[i]],
        "image_dims": [dims[i] if i < len(dims) else None],
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
    }, canons


def _interleave_buckets(buckets):
    """Deal one frame per post per round (interleaved so a single shoot doesn't
    clump together in the grid)."""
    buckets = [b for b in buckets if b]
    out = []
    while buckets:
        for bucket in buckets:
            out.append(bucket.pop(0))
        buckets = [b for b in buckets if b]
    return out


def images_filtered(shots, bird=None, family=None, area=None, ooa_only=(), media=None,
                    month=None):
    """Interleaved single-image frames matching ALL active filters (composable):
    ``bird`` (species display name), ``family`` (Merlin group), ``area``
    ('local' = North Andover, 'elsewhere' = ⚠️ out-of-area-only species),
    ``media`` ('video' = only videos, 'photo' = only stills), and ``month``
    (1–12: frames captured that month in any year — the phenology-matrix cells)."""
    bird_set = {b.strip().lower() for b in (bird or "").split(",") if b.strip()}
    fam = (family or "").strip()
    want_elsewhere = area in ("elsewhere", "away")
    has_area = area in ("local", "elsewhere", "away")
    want_video = media == "video"
    want_photo = media == "photo"
    month_key = "-%02d-" % month if month else None
    ooa_lower = {n.lower() for n in ooa_only}
    buckets = []
    for shot in shots:
        bucket = []
        for i in range(len(shot.get("images") or [])):
            frame, canons = _pseudo_frame(shot, i)
            names = [c[0].lower() for c in canons]
            if not names:
                continue
            if bird_set and bird_set.isdisjoint(names):
                continue
            if fam and not any(c[1] == fam for c in canons):
                continue
            if month_key and month_key not in (frame.get("_sort") or ""):
                continue
            if has_area:
                is_elsewhere = all(nm in ooa_lower for nm in names)
                if is_elsewhere != want_elsewhere:
                    continue
            if want_video and not frame["image_videos"][0]:
                continue
            if want_photo and frame["image_videos"][0]:
                continue
            bucket.append(frame)
        if bucket:
            buckets.append(bucket)
    return _interleave_buckets(buckets)


def has_videos(shots):
    """Whether any frame in the gallery is a video (to show the Videos filter)."""
    return any(v for s in shots for v in (s.get("image_videos") or []))


def media_counts(shots, bird=None, family=None, area=None, ooa_only=(), month=None):
    """(photo_count, video_count) of frames matching the species/family/area/month
    filter (ignoring any media filter) — for the live, clickable totals."""
    bird_set = {b.strip().lower() for b in (bird or "").split(",") if b.strip()}
    fam = (family or "").strip()
    has_area = area in ("local", "elsewhere")
    want_elsewhere = area == "elsewhere"
    ooa_lower = {n.lower() for n in ooa_only}
    photos = videos = 0
    for shot in shots:
        if month:
            d = _capture_date_obj(shot.get("caption") or "", shot.get("timestamp"))
            if not d or d.month != month:
                continue
        isp = shot.get("image_species") or []
        vids = shot.get("image_videos") or []
        for i in range(len(shot.get("images") or [])):
            raw = isp[i] if i < len(isp) and isp[i] else shot.get("species")
            canons = _canon_species_list(raw)
            names = [c[0].lower() for c in canons]
            if not names:
                continue
            if bird_set and bird_set.isdisjoint(names):
                continue
            if fam and not any(c[1] == fam for c in canons):
                continue
            if has_area and (all(n in ooa_lower for n in names) != want_elsewhere):
                continue
            if i < len(vids) and vids[i]:
                videos += 1
            else:
                photos += 1
    return photos, videos


def images_for_review(shots, review, reid_keys=()):
    """Exploded frames for a curate review filter — the specific IMAGES acted on:
    'reclassified' (species not in the IG caption) or 'reid' (flagged frames)."""
    reid_keys = set(reid_keys)
    buckets = []
    for shot in shots:
        caption_lc = re.sub(r"[^a-z]+", " ", (shot.get("caption") or "").lower())
        bucket = []
        for i in range(len(shot.get("images") or [])):
            frame, canons = _pseudo_frame(shot, i)
            if review == "reclassified":
                if not (caption_lc.strip() and canons
                        and any(not _species_in_caption(c[0], caption_lc) for c in canons)):
                    continue
            elif review == "reid":
                key = "%s-%s" % (frame["post_id"], frame["image_indices"][0])
                if key not in reid_keys:
                    continue
            else:
                continue
            bucket.append(frame)
        if bucket:
            buckets.append(bucket)
    return _interleave_buckets(buckets)


def images_hidden(shots):
    """Exploded HIDDEN frames (per-image exclusions), so they can be reviewed and
    un-hidden. ``shots`` must be loaded with exclusions OFF (full-length arrays)."""
    overrides = load_overrides()
    buckets = []
    for shot in shots:
        excl = set(overrides.get(shot.get("id"), {}).get("exclude_images") or [])
        if not excl:
            continue
        bucket = [_pseudo_frame(shot, i)[0] for i in range(len(shot.get("images") or []))
                  if i in excl]
        if bucket:
            buckets.append(bucket)
    return _interleave_buckets(buckets)


def all_photos_shuffled(shots):
    """Every frame in the gallery, in plain random order (fresh each load)."""
    frames = []
    for shot in shots:
        for i in range(len(shot.get("images") or [])):
            frame, _ = _pseudo_frame(shot, i)
            frames.append(frame)
    random.shuffle(frames)
    return frames


def sort_frames(frames, order):
    """Order a frame list by date. ``order`` is 'recent' / 'oldest' (capture
    date, from the caption) or 'posted' (Instagram post time — photos are often
    posted weeks after they're shot, so this answers "what went up lately?").
    Undated frames always go to the end; same-date frames keep their existing
    relative order (stable)."""
    key = "_posted" if order == "posted" else "_sort"
    dated = [f for f in frames if f.get(key)]
    undated = [f for f in frames if not f.get(key)]
    dated.sort(key=lambda f: f[key], reverse=(order in ("recent", "posted")))
    return dated + undated


def start_ordered(shots, tokens):
    """Every frame in random order, but with the exact frames named by ``tokens``
    pinned to the front, in that order. Each token is ``"<post_id>.<image_index>"``
    where the index is the image's ORIGINAL position in its post (stable across
    loads — plain positional order isn't, since images are reshuffled each load).
    Lets a click on the home preview open the gallery with those same photos
    leading, in the same order they were shown."""
    frames = all_photos_shuffled(shots)
    by_key = {}
    for f in frames:
        oi = (f.get("image_indices") or [None])[0]
        by_key.setdefault((f.get("post_id"), oi), f)
    front, seen = [], set()
    for tok in tokens:
        pid, _, idx = tok.partition(".")
        try:
            oi = int(idx)
        except ValueError:
            continue
        f = by_key.get((pid, oi))
        if f and f["id"] not in seen:
            front.append(f)
            seen.add(f["id"])
    rest = [f for f in frames if f["id"] not in seen]
    return front + rest


def filter_shots(shots, bird=None, family=None, area=None, ooa_only=()):
    """Whole posts that contain at least one frame matching ALL active filters.
    Used by curate mode, which edits whole-post cards (not exploded frames)."""
    bird_set = {b.strip().lower() for b in (bird or "").split(",") if b.strip()}
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
            if bird_set and bird_set.isdisjoint(names):
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
    # Only snap to a real species for close typos (e.g. "Grat Blue Heron"); a
    # loose cutoff mapped unrelated notes like "Heron Rookery" -> "Hairy Woodpecker".
    match = difflib.get_close_matches(query, names, n=1, cutoff=0.75)
    return match[0] if match else query


def resolve_species_list(query, groups):
    """Resolve a comma-separated species query to a de-duped, order-preserving list
    of real species names — the gallery's multi-species filter (``?bird=A,B,C``)."""
    out = []
    for part in (query or "").split(","):
        name = resolve_species(part, groups)
        if name and name not in out:
            out.append(name)
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
    # Efraimidis-Spirakis: weight decays by original position (Scott puts favorites
    # first), so the cover + carousel vary per load but lean toward those favorites.
    order = sorted(range(n), key=lambda i: random.random() ** (1.0 / (n - i)), reverse=True)
    for key in ("images", "captions", "image_species", "image_locations", "image_areas",
                "image_indices", "image_videos", "image_dims"):
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
    return set(_load_curation(EXCLUDED_FILE, list))


def add_exclusion(post_id):
    excluded = load_excluded()
    excluded.add(post_id)
    _save_curation(EXCLUDED_FILE, sorted(excluded))
    # Locally, drop it from the committed manifest right away so the change shows
    # without a re-sync. In prod the exclusion applies at serve time (load_gallery
    # filters excluded ids), so no manifest rewrite is needed on read-only Lambda.
    if not os.environ.get("BIRDS_USE_S3"):
        shots = [s for s in (_load_local_manifest() or []) if s.get("id") != post_id]
        _atomic_write_json(LOCAL_MANIFEST, shots)
    return excluded


# Re-ID queue: specific frames (post id + image index) Scott has flagged in curate
# mode for Claude to re-identify. Lives in birds/reid_queue.json.
REID_QUEUE_FILE = os.path.join(HERE, "birds", "reid_queue.json")


def load_lifers():
    """Per-species life-list backdrop choices: {species: {"src": thumb_url,
    "pos": 0..1 vertical framing}}. Lets curation pick which photo of a species
    fills the life-list 'sky' and how it's cropped, since auto-picking the best
    shot doesn't always frame the bird well."""
    return _load_curation(LIFERS_FILE, dict)


def set_lifer(species, src=None, pos=None, posx=None, zoom=None):
    """Set (or clear) the curated backdrop for one species: which photo (src),
    its framing (pos / posx 0..1, vertical / horizontal) and how tight it's
    cropped (zoom). Passing none of them removes the entry, falling back to the
    auto choice."""
    species = (species or "").strip()
    if not species:
        return {}
    lifers = load_lifers()
    if not src and pos is None and posx is None and zoom is None:
        lifers.pop(species, None)
    else:
        entry = dict(lifers.get(species) or {})
        if src:
            entry["src"] = src
        if pos is not None:
            entry["pos"] = max(0.0, min(1.0, float(pos)))
        if posx is not None:
            entry["posx"] = max(0.0, min(1.0, float(posx)))
        if zoom is not None:
            entry["zoom"] = max(1.0, min(3.0, float(zoom)))
        lifers[species] = entry
    _save_curation(LIFERS_FILE, lifers)
    return lifers.get(species, {})


def load_reid_queue():
    return _load_curation(REID_QUEUE_FILE, list)


def _save_reid_queue(queue):
    _save_curation(REID_QUEUE_FILE, queue)


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
    _save_curation(EXCLUDED_FILE, sorted(excluded))
    return excluded


# --- Manual species/caption fixes (curation) -------------------------------
# Instagram captions are parsed heuristically, so some posts get no species or
# several. `overrides.json` holds hand-typed corrections, keyed by post id, and
# is applied on every load + sync so it survives re-syncs (like excluded.json).
def load_overrides():
    return _load_curation(OVERRIDES_FILE, dict)


def _is_ambiguous(shot):
    """Needs review when no species was parsed, or several distinct ones were."""
    names = {normalize_species(s) for s in (shot.get("species_list") or []) if s}
    return len(names) != 1


def _caption_image_species(caption, n):
    """The per-frame species implied by the caption, for a post's ``n`` frames.

    When the caption pins one species per frame (line count matches the image
    count) each frame gets its own. When there are fewer species than frames — a
    carousel with several photos per bird — we distribute the species
    contiguously in caption order, as evenly as possible, with earlier species
    taking any remainder (the headliner usually leads with more shots). A single
    species covers every frame. Frames a caption says nothing about come back None.

    Contiguous distribution (not "every frame = the primary species") is what
    stops a 9-photo post captioned "Chimney Swift / American Crow / Red-tailed
    Hawk" from labelling the crow and hawk photos as swifts. It's a rough base
    the curate editor refines; when it's wrong the fix is a per-frame edit.

    This is also the base a partial per-image override overlays onto, so editing
    one frame's species never bleeds onto the post's other frames: the un-edited
    frames keep their own caption species instead of collapsing to the edited value.
    """
    names = [p[0] for p in _species_pairs(caption)]
    if not names:
        return [None] * n
    if len(names) == 1:
        return [names[0]] * n
    if len(names) == n:
        return names
    if len(names) < n:
        base, extra = divmod(n, len(names))
        out = []
        for i, nm in enumerate(names):
            out.extend([nm] * (base + (1 if i < extra else 0)))
        return out
    return names[:n]  # more species than frames (unusual): one each, in order


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
            n = len(shot.get("images") or [])
            if override.get("images"):
                per_image = override["images"]
                # Overlay the explicit per-image edits onto the caption-derived
                # species so an un-edited frame keeps its own species rather than
                # falling back to the (now-edited) cover species — otherwise
                # editing one frame silently relabels every other frame in the post.
                base = _caption_image_species(shot.get("caption") or "", n)
                shot["image_species"] = [
                    (per_image.get(str(i)) or base[i]) for i in range(n)
                ]
                assigned = [s for s in shot["image_species"] if s]
                if assigned:
                    shot["species"] = override.get("species") or assigned[0]
                    shot["species_list"] = list(dict.fromkeys(assigned))
            # Per-image location override applies on its own, so a location-only
            # edit works too (not just alongside a species override).
            if override.get("images") or override.get("image_locations"):
                per_loc = override.get("image_locations") or {}
                shot["image_locations"] = [(per_loc.get(str(i)) or None) for i in range(n)]
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
        # Posts without a per-image species edit still need per-frame species
        # pinned from the caption — otherwise a multi-species carousel with no
        # baked image_species falls back to the cover species on every frame
        # (the same collapse that made a crow and a hawk read as Chimney Swifts).
        # Preserve any per-frame species already present; only fill the gaps.
        if not (override and override.get("images")):
            n = len(shot.get("images") or [])
            base = _caption_image_species(shot.get("caption") or "", n)
            existing = shot.get("image_species") or []
            filled = [(existing[i] if i < len(existing) and existing[i] else base[i])
                      for i in range(n)]
            if any(filled):
                shot["image_species"] = filled
        shot["ambiguous"] = (not override) and _is_ambiguous(shot)
        shot["image_areas"] = _image_areas(shot)
        # Manual out-of-area overrides overlay the caption-derived areas.
        if override and override.get("image_areas"):
            per_area = override["image_areas"]
            for i in range(len(shot["image_areas"])):
                if str(i) in per_area:
                    shot["image_areas"][i] = per_area[str(i)]
        shot["caption_species"] = caption_species(shot.get("caption") or "")
        current = []
        for raw in (shot.get("image_species") or shot.get("species_list") or []):
            for canon in _canon_species_list(raw):
                if canon[0] not in current:
                    current.append(canon[0])
        caption_lc = re.sub(r"[^a-z]+", " ", (shot.get("caption") or "").lower())
        shot["reclassified"] = bool(shot.get("caption")) and any(
            not _species_in_caption(s, caption_lc) for s in current)
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
                "image_areas", "image_videos", "image_dims"):
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
        locs = {k: v for k, v in locs.items() if v}
        if locs:
            entry["image_locations"] = locs
        else:
            entry.pop("image_locations", None)
    if isinstance(fields.get("image_areas"), dict):
        # 'away' marks a frame out-of-area; anything else clears the override
        # back to the caption-derived default.
        areas = entry.get("image_areas", {})
        for idx, val in fields["image_areas"].items():
            if val == "away":
                areas[str(idx)] = "away"
            else:
                areas.pop(str(idx), None)
        if areas:
            entry["image_areas"] = areas
        else:
            entry.pop("image_areas", None)
    if entry:
        overrides[post_id] = entry
    else:  # a fully-reverted post leaves no override at all
        overrides.pop(post_id, None)
    _save_curation(OVERRIDES_FILE, overrides)
    # Locally, re-bake the committed manifest so the change shows without a
    # re-sync. In prod, apply_overrides runs at serve time (load_gallery), so
    # the edit shows on the next request without touching the read-only fs.
    shots = _load_local_manifest() or []
    if shots and not os.environ.get("BIRDS_USE_S3"):
        apply_overrides(shots, overrides, apply_exclusions=False)
        _atomic_write_json(LOCAL_MANIFEST, shots)
    return next((s for s in shots if s.get("id") == post_id), None)


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
    _save_curation(OVERRIDES_FILE, overrides)
    return excluded


def _load_local_manifest():
    try:
        with open(LOCAL_MANIFEST) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


# The manifest only changes on a sync, but a warm Lambda serves many requests.
# We cache the raw bytes in-process AND bust them the instant S3 changes: each
# read is a *conditional* GET (If-None-Match on the cached ETag), so an unchanged
# manifest is a tiny 304 (no 1 MB re-download) while a fresh sync is picked up at
# once. We return a FRESH json.loads each call (~10 ms) so callers like
# apply_overrides can mutate the shot dicts without corrupting the cache.
# `data_version` exposes the ETag so pages can bust their own caches on the same
# signal.
_manifest_cache = {"etag": None, "raw": None}


def data_version():
    """Short token identifying the current backing data — the manifest ETag on
    S3, else a hash of the local manifest's mtime+size for dev. Feeds page
    ETags so stats/map/etc. bust the moment a sync lands."""
    if _manifest_cache["etag"]:
        return _manifest_cache["etag"].strip('"')[:16]
    try:
        st = os.stat(LOCAL_MANIFEST)
        return "local-%x-%x" % (int(st.st_mtime), st.st_size)
    except OSError:
        return "none"


def _load_manifest_from_s3():
    if not os.environ.get("BIRDS_USE_S3"):
        return None
    try:
        import boto3
        from botocore.exceptions import ClientError

        params = dict(Bucket=S3_BUCKET, Key="{}/manifest.json".format(S3_PREFIX))
        if _manifest_cache["etag"]:
            params["IfNoneMatch"] = _manifest_cache["etag"]
        try:
            obj = boto3.client("s3").get_object(**params)
        except ClientError as exc:
            # 304 Not Modified -> the cached raw is still current.
            if exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 304:
                return json.loads(_manifest_cache["raw"]) if _manifest_cache["raw"] else None
            raise
        raw = obj["Body"].read()
        shots = json.loads(raw)  # validate before caching
        _manifest_cache.update(etag=obj.get("ETag"), raw=raw)
        return shots
    except Exception:  # noqa: BLE001 - any S3/parse error => fall back to repo copy
        return json.loads(_manifest_cache["raw"]) if _manifest_cache["raw"] else None


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------
TOKEN_FILE = os.path.join(HERE, ".ig_token")
EXCLUDED_FILE = os.path.join(HERE, "birds", "excluded.json")
OVERRIDES_FILE = os.path.join(HERE, "birds", "overrides.json")
LIFERS_FILE = os.path.join(HERE, "birds", "lifers.json")
LOC_OVERRIDES_FILE = os.path.join(HERE, "birds", "location_overrides.json")
PROJECTS_FILE = os.path.join(HERE, "static", "projects.json")
TAGLINES_FILE = os.path.join(HERE, "static", "taglines.json")
FACTS_FILE = os.path.join(HERE, "static", "facts.json")
PHOTOS_FILE = os.path.join(HERE, "static", "img", "photography", "manifest.json")


# --- Curation storage: repo files locally, S3 objects in production ----------
# The read-only Lambda filesystem can't persist a live edit, so when BIRDS_USE_S3
# is set the curation JSON (overrides / excluded / re-ID queue) reads and writes
# go to S3 instead — cached in-process with a conditional GET and updated
# write-through, so a live edit shows on the very next request. S3 becomes the
# source of truth once live curation is on; the committed repo copies are the
# versioned mirror (refreshed via `pull_curations`).
_CURATION_S3 = {
    EXCLUDED_FILE: "{}/excluded.json".format(S3_PREFIX),
    OVERRIDES_FILE: "{}/overrides.json".format(S3_PREFIX),
    REID_QUEUE_FILE: "{}/reid_queue.json".format(S3_PREFIX),
    LIFERS_FILE: "{}/lifers.json".format(S3_PREFIX),
    LOC_OVERRIDES_FILE: "{}/location_overrides.json".format(S3_PREFIX),
    PROJECTS_FILE: "{}/projects.json".format(S3_PREFIX),
    TAGLINES_FILE: "{}/taglines.json".format(S3_PREFIX),
    FACTS_FILE: "{}/facts.json".format(S3_PREFIX),
    PHOTOS_FILE: "{}/photos.json".format(S3_PREFIX),
}
_curation_cache = {}  # path -> {"etag":..., "raw": bytes}


def _read_repo_curation(path, default):
    try:
        with open(path) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default() if callable(default) else default


def _load_curation(path, default):
    """Read a curation JSON. In prod (BIRDS_USE_S3) reads S3, seeding from the
    deployed repo copy the first time (before any live edit); else the repo file.
    `default` may be a factory (dict/list/set) for the empty case."""
    if not (os.environ.get("BIRDS_USE_S3") and path in _CURATION_S3):
        return _read_repo_curation(path, default)
    key = _CURATION_S3[path]
    cached = _curation_cache.get(path)
    try:
        import boto3
        from botocore.exceptions import ClientError

        params = dict(Bucket=S3_BUCKET, Key=key)
        if cached and cached.get("etag"):
            params["IfNoneMatch"] = cached["etag"]
        try:
            obj = boto3.client("s3").get_object(**params)
        except ClientError as exc:
            code = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            err = exc.response.get("Error", {}).get("Code")
            if code == 304 and cached:
                return json.loads(cached["raw"])
            if err in ("NoSuchKey", "404"):  # not seeded on S3 yet -> repo copy
                return _read_repo_curation(path, default)
            raise
        raw = obj["Body"].read()
        json.loads(raw)  # validate before caching
        _curation_cache[path] = {"etag": obj.get("ETag"), "raw": raw}
        return json.loads(raw)
    except Exception:  # noqa: BLE001 - S3 hiccup: last-known cache, else repo copy
        if cached:
            return json.loads(cached["raw"])
        return _read_repo_curation(path, default)


def pull_curations():
    """Download the live (S3) curation files into the repo copies so they can be
    committed — the versioned mirror of the deployed site's edits. Returns the
    list of repo-relative paths that changed. No-op without S3 access."""
    if not os.environ.get("BIRDS_USE_S3"):
        return []
    import boto3
    from botocore.exceptions import ClientError

    s3 = boto3.client("s3")
    changed = []
    for path, key in _CURATION_S3.items():
        try:
            data = json.loads(s3.get_object(Bucket=S3_BUCKET, Key=key)["Body"].read())
        except (ClientError, ValueError):
            continue  # not on S3 yet / unreadable
        if _read_repo_curation(path, None) != data:
            _atomic_write_json(path, data, sort_keys=(path == OVERRIDES_FILE))
            changed.append(os.path.relpath(path, HERE))
    return changed


def push_curations():
    """Upload the repo curation files to S3 — makes local edits live, and seeds
    S3 the first time. Returns the repo-relative paths pushed. No-op without S3."""
    if not os.environ.get("BIRDS_USE_S3"):
        return []
    pushed = []
    for path in _CURATION_S3:
        data = _read_repo_curation(path, None)
        if data is None:
            continue
        _save_curation(path, data)
        pushed.append(os.path.relpath(path, HERE))
    return pushed


# --- Photography gallery (non-bird, published from raw files) ----------------
_PHOTO_FIELDS = ("title", "species", "location", "date", "tags")


def load_photos():
    """The /photography gallery entries (S3-backed curation store in prod)."""
    return _load_curation(PHOTOS_FILE, list)


def set_photo(photo_id, fields):
    """Update one photo's editable metadata (title/species/location/date/tags)
    from the curate editor. Returns the updated entry, or None if unknown."""
    photos = load_photos()
    for p in photos:
        if p.get("id") == photo_id:
            for k in _PHOTO_FIELDS:
                if k in fields:
                    if k == "tags":
                        seen, tags = set(), []
                        for t in fields[k] or []:
                            t = (t or "").strip()
                            if t and t.lower() not in seen:
                                seen.add(t.lower())
                                tags.append(t)
                        p["tags"] = tags
                    else:
                        p[k] = (fields[k] or "").strip()
            _save_curation(PHOTOS_FILE, photos)
            return p
    return None


def photo_tags(photos):
    """Distinct tags across all photos, most-used first (the filter chips)."""
    counts = {}
    for p in photos:
        for t in p.get("tags") or []:
            counts[t] = counts.get(t, 0) + 1
    return [t for t, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0].lower()))]


# --- Sound station: read the BirdNET-Go detection rollup the exporter writes ---
def load_sounds():
    """The live bird-sound rollup (birds/sounds/recent.json) the listening station
    exports to S3. None when it hasn't run yet (the /birds/live page then shows a
    'coming online' state)."""
    key = "{}/sounds/recent.json".format(S3_PREFIX)
    if os.environ.get("BIRDS_USE_S3"):
        try:
            import boto3

            body = boto3.client("s3").get_object(Bucket=S3_BUCKET, Key=key)["Body"].read()
            return json.loads(body)
        except Exception:  # noqa: BLE001 - not published yet / unreachable
            return None
    try:  # local dev mirror written by sound_export.py
        with open(os.path.join(HERE, "birds", "sounds_recent.json")) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def species_covers(shots):
    """Every grid thumbnail per canonical species (best-weight first, de-duped) —
    the pool the /birds/live viewer draws from when it hears a species you've also
    photographed, so it can vary the photo instead of always showing one."""
    pool = {}
    for s in shots:
        isp = s.get("image_species") or []
        imgs = s.get("images") or []
        w = s.get("weight") or 0
        for i in range(len(imgs)):
            raw = isp[i] if i < len(isp) and isp[i] else s.get("species")
            url = thumb_url(imgs[i])
            for name, _ in _canon_species_list(raw):
                pool.setdefault(name, []).append((w, url))
    out = {}
    for name, items in pool.items():
        items.sort(key=lambda wu: -wu[0])
        seen, urls = set(), []
        for _, u in items:
            if u not in seen:
                seen.add(u)
                urls.append(u)
        out[name] = urls
    return out


def pick_cover(urls, seed):
    """Pick one thumbnail from a species' pool, deterministically by ``seed`` (a
    detection timestamp, or a species name). Varies the photo across detections
    while staying stable across the live page's 60s polls — and identical across
    Lambda processes, which a bare hash() would not be (PYTHONHASHSEED)."""
    if not urls:
        return None
    return urls[zlib.crc32((seed or "").encode("utf-8")) % len(urls)]


def _save_curation(path, data):
    """Persist a curation JSON: to S3 in prod (write-through cache), else repo."""
    if os.environ.get("BIRDS_USE_S3") and path in _CURATION_S3:
        try:
            import boto3

            raw = json.dumps(data, indent=2, sort_keys=(path == OVERRIDES_FILE)).encode()
            resp = boto3.client("s3").put_object(
                Bucket=S3_BUCKET, Key=_CURATION_S3[path], Body=raw,
                ContentType="application/json", CacheControl="no-store")
            _curation_cache[path] = {"etag": resp.get("ETag"), "raw": raw}
            return
        except Exception:  # noqa: BLE001 - fall through to a local write
            pass
    _atomic_write_json(path, data, sort_keys=(path == OVERRIDES_FILE))


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

    # Carry image dimensions forward for frames whose thumbs already exist
    # (their bytes aren't re-downloaded, so dims can't be recomputed).
    for prev in _load_local_manifest() or []:
        for i, dims in enumerate(prev.get("image_dims") or []):
            if dims:
                _THUMB_DIMS.setdefault("{}-{}".format(prev.get("id"), i), dims)

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
                "image_dims": [_THUMB_DIMS.get("{}-{}".format(item["id"], i))
                               for i in range(len(images))],
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
    just won't last. A grid-sized thumbnail rides along under thumbs/ (see
    ``thumb_url``); the full-resolution copy stays for the lightbox.
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
            _ensure_thumb(s3, media_id)  # backfill thumbs for older archives
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
        _ensure_thumb(s3, media_id, resp.content)
        return public_url
    except Exception:  # noqa: BLE001 - S3 unavailable: serve Instagram's URL directly
        return src_url


# Grid thumbnails: the masonry/preview grids only ever render ~640 CSS px wide
# images, but IG originals run 300-700 KB. A 640px progressive JPEG is ~8x
# lighter; the lightbox still opens the full-resolution copy.
THUMB_WIDTH = 640


def thumb_url(url):
    """The grid-sized thumbnail URL for a re-hosted image (falls back to the
    original for anything not in our archive, e.g. local-dev IG URLs)."""
    marker = "/{}/images/".format(S3_PREFIX)
    if marker in (url or ""):
        return url.replace(marker, "/{}/thumbs/".format(S3_PREFIX))
    return url


# Thumb pixel sizes gathered while syncing ("<post id>-<index>" -> [w, h]).
# Rendered as width/height attributes so the grid reserves space before images
# load (no layout jumps). Seeded from the previous manifest for already-archived
# frames, filled fresh whenever a thumbnail is (re)generated.
_THUMB_DIMS = {}


def _make_thumb(data):
    """(jpeg bytes, [w, h]) of the grid thumbnail for one full image."""
    from io import BytesIO

    from PIL import Image, ImageOps

    im = ImageOps.exif_transpose(Image.open(BytesIO(data))).convert("RGB")
    if im.width > THUMB_WIDTH:
        im = im.resize(
            (THUMB_WIDTH, max(1, round(im.height * THUMB_WIDTH / im.width))),
            Image.LANCZOS,
        )
    out = BytesIO()
    im.save(out, "JPEG", quality=78, optimize=True, progressive=True)
    return out.getvalue(), [im.width, im.height]


def _ensure_thumb(s3, media_id, data=None):
    """Create thumbs/{id}.jpg if it doesn't exist yet. Best-effort: on any
    failure (Pillow unavailable, corrupt image) the grid's error handler falls
    back to the full image, so a missing thumb never breaks the gallery."""
    key = "{}/thumbs/{}.jpg".format(S3_PREFIX, media_id)
    try:
        s3.head_object(Bucket=S3_BUCKET, Key=key)
        return
    except Exception:  # noqa: BLE001 - not there yet
        pass
    try:
        if data is None:
            data = s3.get_object(
                Bucket=S3_BUCKET, Key="{}/images/{}.jpg".format(S3_PREFIX, media_id)
            )["Body"].read()
        body, dims = _make_thumb(data)
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=body,
            ContentType="image/jpeg",
            CacheControl="public, max-age=31536000, immutable",
        )
        _THUMB_DIMS[media_id] = dims
    except Exception:  # noqa: BLE001
        pass


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
    r"hill|pond|lake|forest|woodlot|reservoir|reservation|"
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
            elif _looks_like_bird(s):
                pending.append(_clean_species(s))    # unmapped-but-plausible bird
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


def _singularize(word):
    """Best-effort singular of a species' last word, preserving case: irregulars
    first ("Geese"->"Goose"), then "-es" plurals ("Finches"->"Finch", not the
    naive "Finche"), then a plain trailing "s" ("Owls"->"Owl")."""
    low = word.lower()
    if low in _IRREGULAR_PLURALS:
        repl = _IRREGULAR_PLURALS[low]
        return repl.capitalize() if word[:1].isupper() else repl
    if len(low) > 4 and low.endswith(("ches", "shes", "sses", "xes", "zes")):
        return word[:-2]  # "-es" plural: drop "es"
    if len(low) > 3 and low.endswith("s") and not low.endswith("ss"):
        return word[:-1]
    return word


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
    words[-1] = _singularize(words[-1])
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


# Street-suffix synonyms folded to one token so "Rea St." / "Rea Street" (and
# Dr/Drive, Ln/Lane, Ct/Court, …) count as one place. Full word -> abbreviation;
# the abbreviated forms already collapse to the same token once punctuation is
# stripped. Applied as whole words only, so it never touches a name mid-string.
_LOC_SUFFIX = {
    "street": "st", "avenue": "ave", "road": "rd", "drive": "dr", "lane": "ln",
    "court": "ct", "boulevard": "blvd", "place": "pl", "terrace": "ter",
    "highway": "hwy", "extension": "ext", "circle": "cir", "square": "sq",
    "parkway": "pkwy", "trail": "trl", "heights": "hts", "point": "pt",
}
_LOC_SUFFIX_RE = re.compile(
    r"\b(%s)\b" % "|".join(sorted(_LOC_SUFFIX, key=len, reverse=True)))


def _loc_key(loc):
    """Normalized key so street-suffix variants ('Rea St.' / 'Rea Street',
    'Sargent Dr' / 'Sargent Drive') count as one place. Lowercases, strips
    punctuation, folds the suffix synonyms, and collapses whitespace."""
    k = re.sub(r"[^a-z0-9 ]", "", (loc or "").lower()).strip()
    k = _LOC_SUFFIX_RE.sub(lambda m: _LOC_SUFFIX[m.group(1)], k)
    return re.sub(r"\s+", " ", k)


# Canonical display: every street suffix consistently abbreviated with a period
# ("Rea Street"/"Rea St" -> "Rea St.", "Molly Towne Road" -> "Molly Towne Rd."),
# so a location reads the same everywhere it's shown — no override backfill, and
# it survives every re-sync. Both the full word and the bare abbreviation map to
# the same "Abbr." form.
# Clear street-type suffixes only. Square / Heights / Point / Trail are left
# alone — they're usually proper place names (Post Office Square, Harvard
# Square), not addressable suffixes, and read wrong abbreviated.
_LOC_ABBR = {
    "street": "St.", "st": "St.", "avenue": "Ave.", "ave": "Ave.",
    "road": "Rd.", "rd": "Rd.", "drive": "Dr.", "dr": "Dr.",
    "lane": "Ln.", "ln": "Ln.", "court": "Ct.", "ct": "Ct.",
    "boulevard": "Blvd.", "blvd": "Blvd.", "place": "Pl.", "pl": "Pl.",
    "terrace": "Ter.", "ter": "Ter.", "highway": "Hwy.", "hwy": "Hwy.",
    "extension": "Ext.", "ext": "Ext.", "circle": "Cir.", "cir": "Cir.",
    "parkway": "Pkwy.", "pkwy": "Pkwy.",
}
_LOC_ABBR_RE = re.compile(
    r"\b(%s)\b\.?" % "|".join(sorted(_LOC_ABBR, key=len, reverse=True)), re.I)
# Known spelling typos, fixed before abbreviation (whole word, any case).
_LOC_TYPO = {"abbot": "Abbott", "waverley": "Waverly"}
_LOC_TYPO_RE = re.compile(r"\b(%s)\b" % "|".join(_LOC_TYPO), re.I)


_pin_display_cache = None


def _pin_display(key):
    """The geocoded pin's canonical name for an EXACT normalized-key match, so a
    location that IS a mapped place displays as that pin's name (fixing period /
    separator drift like 'Annie L Sargent School' or 'Harborwalk - Boston').
    Exact-match only, so a sub-location ('… Access Rd.') is never collapsed in."""
    global _pin_display_cache
    if _pin_display_cache is None:
        _pin_display_cache = {_loc_key(p["name"]): p["name"] for p in load_locations()}
    return _pin_display_cache.get(key)


def canonical_location(loc):
    """Canonical display for a location: fix known typos, abbreviate every street
    suffix to a consistent 'Abbr.' form, then snap an exact match to its map pin's
    name. Non-suffix words and unmapped places pass through."""
    if not loc:
        return loc
    s = " ".join(loc.split())
    s = _LOC_TYPO_RE.sub(lambda m: _LOC_TYPO[m.group(1).lower()], s)
    s = _LOC_ABBR_RE.sub(lambda m: _LOC_ABBR[m.group(1).lower()], s)
    return _pin_display(_loc_key(s)) or s


LOCATIONS_FILE = os.path.join(HERE, "static", "locations.json")


def load_locations():
    """Geocoded shooting spots for the sightings map (static/locations.json).
    Each place: name, lat, lng, area, and `match` — normalized _loc_key aliases;
    a frame belongs to the place when its key equals or extends an alias. Live
    curation of a spot's local/away status is overlaid from an S3-backed store."""
    try:
        with open(LOCATIONS_FILE) as fh:
            places = json.load(fh)
    except (OSError, ValueError):
        return []
    overrides = load_location_overrides()
    if overrides:
        for p in places:
            ov = overrides.get(p["name"])
            if ov and ov.get("area") in ("local", "away"):
                p["area"] = ov["area"]
    return places


def load_location_overrides():
    """Curated per-spot corrections: {place name: {"area": "local"|"away"}}."""
    return _load_curation(LOC_OVERRIDES_FILE, dict)


def set_location_override(name, area):
    """Set (or clear) a spot's local/away override. area=None removes it."""
    name = (name or "").strip()
    if not name:
        return {}
    ovs = load_location_overrides()
    if area in ("local", "away"):
        ovs[name] = {"area": area}
    else:
        ovs.pop(name, None)
    _save_curation(LOC_OVERRIDES_FILE, ovs)
    return ovs.get(name, {})


def _place_index(places):
    """alias -> place lookups, longest aliases first so the most specific wins
    (e.g. 'harborwalk holocaust memorial boston' before 'harborwalk boston')."""
    pairs = [(alias, p) for p in places for alias in p.get("match", [])]
    return sorted(pairs, key=lambda ap: -len(ap[0]))


def _match_place(loc, alias_index):
    key = _loc_key(loc)
    if not key:
        return None
    for alias, place in alias_index:
        if key == alias or key.startswith(alias + " "):
            return place
    return None


def map_points(shots, places=None, species_filter=None):
    """Aggregate every frame onto its geocoded place: count, species set, and
    top species per pin. Frames whose location isn't in locations.json are
    skipped (they still show in the gallery, just not on the map). Pass
    ``species_filter`` to keep only frames of one species — the map then shows
    exactly where that bird turns up."""
    import collections
    places = places if places is not None else load_locations()
    idx = _place_index(places)
    counts = collections.Counter()
    species = collections.defaultdict(collections.Counter)
    monthly = collections.defaultdict(collections.Counter)  # place -> "YYYY-MM" -> n
    best_img = collections.defaultdict(lambda: (-1, None))  # place -> (weight, url)
    for shot in shots:
        iloc = shot.get("image_locations") or []
        isp = shot.get("image_species") or []
        images = shot.get("images") or []
        weight = shot.get("weight") or 0
        d = _capture_date_obj(shot.get("caption") or "", shot.get("timestamp"))
        ym = d.isoformat()[:7] if d else None
        for i in range(len(images)):
            loc = iloc[i] if i < len(iloc) and iloc[i] else shot.get("location")
            if not loc:
                continue
            place = _match_place(loc, idx)
            if not place:
                continue
            raw = isp[i] if i < len(isp) and isp[i] else shot.get("species")
            names = [c[0] for c in _canon_species_list(raw)]
            if species_filter and species_filter not in names:
                continue
            counts[place["name"]] += 1
            if ym:
                monthly[place["name"]][ym] += 1
            for nm in names:
                species[place["name"]][nm] += 1
            if weight > best_img[place["name"]][0]:  # the shot the pin wears
                best_img[place["name"]] = (weight, images[i])
    out = []
    for p in places:
        n = counts.get(p["name"], 0)
        if not n:
            continue
        sp = species[p["name"]]
        img = best_img[p["name"]][1]
        out.append({
            "name": p["name"], "lat": p["lat"], "lng": p["lng"], "area": p["area"],
            "count": n, "species": len(sp),
            "top": [s for s, _ in sp.most_common(3)],
            "months": dict(monthly[p["name"]]),
            "img": thumb_url(img) if img else None,
        })
    out.sort(key=lambda p: -p["count"])
    return out


def images_at_place(shots, place, species=None):
    """Every frame taken at ``place`` (a locations.json entry), for /birds?loc=.
    Interleaved one-frame-per-post like the other filters, so a single long
    shoot doesn't sit in the grid as one solid block. Pass ``species`` to also
    require that bird (the combined ?bird=&loc= filter deep-linked from a
    species map pin)."""
    idx = _place_index([place])
    species_l = (species or "").strip().lower()
    buckets = []
    for shot in shots:
        bucket = []
        for i in range(len(shot.get("images") or [])):
            frame, canons = _pseudo_frame(shot, i)
            if not (frame.get("location") and _match_place(frame["location"], idx)):
                continue
            if species_l and species_l not in [c[0].lower() for c in canons]:
                continue
            bucket.append(frame)
        if bucket:
            buckets.append(bucket)
    return _interleave_buckets(buckets)


def images_posted_on(shots, day):
    """Every frame from posts PUBLISHED on ``day`` (ISO date) — the click-through
    for the lightbox's post date, complementing images_on_date's sighting day."""
    buckets = []
    for shot in shots:
        if (shot.get("timestamp") or "")[:10] != day:
            continue
        bucket = [_pseudo_frame(shot, i)[0]
                  for i in range(len(shot.get("images") or []))]
        if bucket:
            buckets.append(bucket)
    return _interleave_buckets(buckets)


def location_places(shots):
    """Map each canonical location label used by any frame to its geocoded place
    name (locations.json), so UI labels can link to /birds?loc=. Keyed by the
    canonical display (matching the frame's shown location); places that don't
    resolve to a pin are simply absent."""
    idx = _place_index(load_locations())
    out = {}
    for shot in shots:
        for loc in (shot.get("image_locations") or []) + [shot.get("location")]:
            cloc = canonical_location(loc)
            if cloc and cloc not in out:
                place = _match_place(cloc, idx)
                if place:
                    out[cloc] = place["name"]
    return out


def gallery_stats(shots):
    """Aggregate numbers for the 'by the numbers' page: counts, families, top
    species/locations, seasonal activity, and the date span. Derived entirely
    from the existing gallery data (no network)."""
    import collections
    species_ct = collections.Counter()
    family_ct = collections.Counter()
    loc_ct = collections.Counter()
    loc_display = {}
    by_month = [0] * 12
    by_year = collections.Counter()
    species_family = {}
    photos = videos = local = away = 0
    dates = []
    for shot in shots:
        images = shot.get("images") or []
        isp = shot.get("image_species") or []
        iloc = shot.get("image_locations") or []
        areas = shot.get("image_areas") or []
        vids = shot.get("image_videos") or []
        d = _capture_date_obj(shot.get("caption") or "", shot.get("timestamp"))
        for i in range(len(images)):
            if i < len(vids) and vids[i]:
                videos += 1
            else:
                photos += 1
            if (areas[i] if i < len(areas) else "local") == "away":
                away += 1
            else:
                local += 1
            loc = iloc[i] if i < len(iloc) and iloc[i] else shot.get("location")
            if loc:
                k = _loc_key(loc)
                if k:
                    loc_ct[k] += 1
                    loc_display.setdefault(k, canonical_location(loc))
            if d:
                dates.append(d)
                by_month[d.month - 1] += 1
                by_year[d.year] += 1
            raw = isp[i] if i < len(isp) and isp[i] else shot.get("species")
            for c in _canon_species_list(raw):
                species_ct[c[0]] += 1
                family_ct[c[1]] += 1
                species_family[c[0]] = c[1]
    fam_order = {f: n for n, f in enumerate(_FAMILY_ORDER)}
    families = sorted(family_ct.items(), key=lambda kv: fam_order.get(kv[0], 999))
    return {
        "species": len(species_ct),
        "photos": photos,
        "videos": videos,
        "local": local,
        "away": away,
        "families": families,
        "family_species": {f: sum(1 for s, fam in species_family.items() if fam == f)
                           for f in family_ct},
        "top_species": [(s, c, species_family.get(s, "")) for s, c in species_ct.most_common(15)],
        "top_locations": [(loc_display[k], c) for k, c in loc_ct.most_common(12)],
        "by_month": by_month,
        "years": sorted(by_year.items()),
        "first": min(dates) if dates else None,
        "last": max(dates) if dates else None,
    }


def stats_series(shots, top_n=15):
    """Data for the stats page charts, derived from capture dates:

    - ``per_day``: date -> {n, sp} photo count + species list (calendar heatmap,
      with click-through to /birds?on=<date> and species in the tooltip).
    - ``pheno``: EVERY species' monthly rhythm with family + total (the full
      phenology matrix), in family/taxonomic order, plus the best photo per
      month so hovering a cell previews that species in that time pocket.
    - ``accum``: the cumulative life list — each species with the date AND the
      photo of its first sighting, so the timeline can show the actual lifer shot.
    - ``top``: most-photographed leaderboard with an avatar image per species.
    """
    import collections
    per_day_n = collections.Counter()
    per_day_sp = collections.defaultdict(set)
    day_best = {}    # date -> (post weight, image url) for the calendar preview
    sp_month = collections.defaultdict(lambda: [0] * 12)
    sp_month_best = collections.defaultdict(lambda: [None] * 12)  # (weight, img)
    sp_total = collections.Counter()
    sp_family = {}
    first_seen = {}  # name -> (date, first-sighting image url)
    best_shot = {}   # name -> (post weight, image url) for the avatar
    sp_imgs = collections.defaultdict(dict)  # name -> {image url: best weight}
    for shot in shots:
        d = _capture_date_obj(shot.get("caption") or "", shot.get("timestamp"))
        if not d:
            continue
        key = d.isoformat()
        isp = shot.get("image_species") or []
        images = shot.get("images") or []
        weight = shot.get("weight") or 0
        for i in range(len(images)):
            per_day_n[key] += 1
            if key not in day_best or weight > day_best[key][0]:
                day_best[key] = (weight, images[i])
            raw = isp[i] if i < len(isp) and isp[i] else shot.get("species")
            for name, family in _canon_species_list(raw):
                per_day_sp[key].add(name)
                sp_month[name][d.month - 1] += 1
                sp_total[name] += 1
                sp_family[name] = family
                cur = sp_month_best[name][d.month - 1]
                if cur is None or weight > cur[0]:
                    sp_month_best[name][d.month - 1] = (weight, images[i])
                if name not in first_seen or d < first_seen[name][0]:
                    first_seen[name] = (d, images[i])
                if name not in best_shot or weight > best_shot[name][0]:
                    best_shot[name] = (weight, images[i])
                img = images[i]
                if weight > sp_imgs[name].get(img, -1):
                    sp_imgs[name][img] = weight
    fam_order = {f: n for n, f in enumerate(_FAMILY_ORDER)}
    lifers = load_lifers()

    def lifer_cands(name):
        """Every distinct shot of a species, best first — what the curation UI
        cycles through when choosing a life-list backdrop."""
        ranked = sorted(sp_imgs[name], key=lambda u: sp_imgs[name][u], reverse=True)
        return [thumb_url(u) for u in ranked]
    # Every preview here renders small (tooltips, avatars, the lifer card), so
    # they all ride the grid thumbnails rather than full-resolution copies.
    pheno = [{"name": s, "fam": sp_family[s], "months": sp_month[s], "total": sp_total[s],
              "imgs": [thumb_url(b[1]) if b else None for b in sp_month_best[s]]}
             for s in sorted(sp_total, key=lambda s: (fam_order.get(sp_family[s], 999), s))]
    def accum_entry(s, d, img):
        cur = lifers.get(s) or {}
        cands = lifer_cands(s)
        # Curated backdrop wins; otherwise the best shot of the species (which
        # frames the bird better than its very first, often rougher, sighting).
        src = cur.get("src") or (thumb_url(best_shot[s][1]) if s in best_shot else thumb_url(img))
        return {"d": d.isoformat(), "s": s, "img": src, "fam": sp_family[s],
                "total": sp_total[s], "pos": cur.get("pos", 0.35),  # bias toward heads
                "posx": cur.get("posx", 0.5), "zoom": cur.get("zoom"), "cands": cands}
    accum = [accum_entry(s, d, img)
             for s, (d, img) in sorted(first_seen.items(), key=lambda kv: kv[1][0])]
    top = [{"name": s, "n": n, "fam": sp_family[s], "img": thumb_url(best_shot[s][1])}
           for s, n in sp_total.most_common(top_n)]
    return {
        "per_day": {k: {"n": n, "sp": sorted(per_day_sp[k]), "img": thumb_url(day_best[k][1])}
                    for k, n in per_day_n.items()},
        "pheno": pheno,
        "accum": accum,
        "top": top,
    }


def activity_river(shots, top_n=None):
    """Photo activity as a streamgraph 'river' — one flowing band per species that
    was active in the window (``top_n`` = None means every one), counts binned by
    calendar month. Each band carries its best photo (thumbnail), total, family,
    and busiest month, so touching a current can bloom that bird. Bands are in
    rank order (biggest first) so colors + faces are stable; the month axis is
    continuous and trimmed to the active window so the river fills the frame."""
    import collections
    bins = collections.defaultdict(collections.Counter)
    sp_total = collections.Counter()
    sp_fam, sp_best = {}, {}
    for shot in shots:
        d = _capture_date_obj(shot.get("caption") or "", shot.get("timestamp"))
        if not d:
            continue
        ym = "%04d-%02d" % (d.year, d.month)
        isp = shot.get("image_species") or []
        images = shot.get("images") or []
        weight = shot.get("weight") or 0
        for i in range(len(images)):
            raw = isp[i] if i < len(isp) and isp[i] else shot.get("species")
            for name, family in _canon_species_list(raw):
                bins[ym][name] += 1
                sp_total[name] += 1
                sp_fam[name] = family
                if name not in sp_best or weight > sp_best[name][0]:
                    sp_best[name] = (weight, images[i])
    if not bins:
        return {"months": [], "series": []}
    y0, m0 = (int(x) for x in min(bins).split("-"))
    y1, m1 = (int(x) for x in max(bins).split("-"))
    months = []
    while (y0, m0) <= (y1, m1):
        months.append("%04d-%02d" % (y0, m0))
        m0 += 1
        if m0 > 12:
            m0, y0 = 1, y0 + 1
    start = next((i for i, mo in enumerate(months)
                  if sum(bins[mo].values()) >= 5), 0)
    months = months[start:]

    def busiest(name):
        ym = max(bins, key=lambda k: bins[k][name])
        return ym, bins[ym][name]

    series = []
    for n in sp_total.most_common(top_n):
        name = n[0]
        vals = [bins[mo].get(name, 0) for mo in months]
        if not any(vals):
            continue  # never appears in the trimmed window — no current to draw
        b_ym, b_n = busiest(name)
        series.append({
            "name": name, "fam": sp_fam.get(name, ""), "total": sp_total[name],
            "img": thumb_url(sp_best[name][1]),
            "values": vals,
            "busiest": b_ym, "busiest_n": b_n,
        })
    return {"months": months, "series": series}


def images_on_date(shots, day):
    """Every frame captured on ``day`` (ISO date string) — the click-through
    target for the shooting-days calendar (/birds?on=YYYY-MM-DD). Uses the same
    post-level capture date as the calendar counts, so the numbers always agree.

    All frames share a capture date here, so plain date sorting would be a
    no-op: ``_sort`` gets the post time appended (newest/oldest fall back to
    posting order) and the default order is a fresh shuffle, like the gallery.
    """
    buckets = []
    for shot in shots:
        d = _capture_date_obj(shot.get("caption") or "", shot.get("timestamp"))
        if not d or d.isoformat() != day:
            continue
        bucket = []
        for i in range(len(shot.get("images") or [])):
            frame, _ = _pseudo_frame(shot, i)
            frame["_sort"] = "%sT%s" % (day, (shot.get("timestamp") or "")[11:19])
            bucket.append(frame)
        if bucket:
            buckets.append(bucket)
    random.shuffle(buckets)
    return _interleave_buckets(buckets)


def ticker_species(shots):
    """De-duplicated, normalized species names across all posts, first-seen order.

    Uses each post's full species list (not just the first) so every bird shows
    up in the ticker, including ones only featured alongside others.
    """
    seen, out = set(), []
    for shot in shots:
        names = shot.get("species_list") or ([shot["species"]] if shot.get("species") else [])
        for raw in names:
            # Canonicalize so only real birds appear (drops caption notes like
            # "Heron Rookery") and the ticker shows current names.
            for canon in _canon_species_list(raw):
                name = canon[0]
                if name.lower() not in seen:
                    seen.add(name.lower())
                    out.append(name)
    return out


if __name__ == "__main__":  # manual run: python birds.py
    written = instagram_sync()
    print("Wrote {} top shots to {}".format(len(written), LOCAL_MANIFEST))
