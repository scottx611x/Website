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
    if shuffle:
        return order_gallery(shots)
    # Stable view (curation): strict highest-likes-first (weight ~ like percentile),
    # tie-broken by most recent.
    return sorted(
        shots,
        key=lambda s: (s.get("weight") or 0, s.get("timestamp") or ""),
        reverse=True,
    )


def order_gallery(shots):
    """Order for display: liked posts trend toward the top, species de-clumped.

    1. Weighted shuffle by popularity ``weight`` (Efraimidis-Spirakis), so it
       favors well-liked posts without being a strict descending leaderboard.
    2. Greedy pass that avoids placing the same species back-to-back, walking the
       weighted order from the front so the popularity bias is preserved.
    """
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
        shots.append(
            {
                "id": item["id"],
                "images": images,
                "captions": _frame_captions(
                    caption, len(images), captured.strftime("%b %-d, %Y") if captured else None
                ),
                "caption": caption,
                "species": _guess_species(caption),
                "date": captured.strftime("%b %-d, %Y") if captured else None,
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


def _species_lines(caption):
    """Species labels from the caption's first block of lines.

    Scott's multi-bird carousels list one species per line at the top, before a
    blank line (e.g. "Barred Owl - Rea St.\\nNorthern Flicker - Weir Hill"), one
    per carousel image. We take that leading block so each image can be labeled.
    """
    block = []
    for line in (caption or "").splitlines():
        stripped = line.strip()
        if not stripped:
            if block:
                break  # end of the leading block
            continue  # skip leading blank lines
        if stripped.startswith("#"):
            break
        block.append(stripped)
    return [s for s in (_clean_species(line) for line in block) if s]


def _guess_species(caption):
    """The single best species label for a post (its first species line)."""
    lines = _species_lines(caption)
    return lines[0] if lines else None


def _frame_captions(caption, n_images, date):
    """A display caption per carousel image.

    If the number of species lines matches the number of images, pair them up so
    each frame shows its own bird; otherwise use the post's species for all.
    """
    lines = _species_lines(caption)
    if len(lines) == n_images:
        per_image = lines
    else:
        per_image = [lines[0] if lines else None] * n_images
    return [" · ".join(p for p in (species, date) if p) for species in per_image]


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
    """De-duplicated, normalized species names, in first-seen order."""
    seen, out = set(), []
    for shot in shots:
        name = normalize_species(shot.get("species"))
        if name and name.lower() not in seen:
            seen.add(name.lower())
            out.append(name)
    return out


if __name__ == "__main__":  # manual run: python birds.py
    written = instagram_sync()
    print("Wrote {} top shots to {}".format(len(written), LOCAL_MANIFEST))
