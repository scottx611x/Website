import datetime
import math
import hashlib
import hmac
import json
import os
import random

from flask import Flask, abort, redirect, render_template, request
from flask_compress import Compress

import birds
import blog

app = Flask(__name__)
app.debug = False
Compress(app)  # gzip/brotli responses — the gallery page is ~3 MB of HTML otherwise

# The one canonical origin. Every page's <link rel="canonical">, og:url,
# sitemap, and structured data are built from this (never request.host) so the
# www/apex split can't create duplicate-content variants in search.
SITE_URL = "https://www.scott-ouellette.com"

# Static assets get immutable-style caching; templates append ?v=<asset_v> to
# css/js so a deploy busts the cache (see _asset_version below).
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 31536000

# Gallery grids render S3 thumbnails; the lightbox keeps the full image.
app.add_template_filter(birds.thumb_url, "thumb")
app.add_template_filter(birds._species_slug, "slug")  # species name -> /birds/species/<slug>


@app.template_filter("shuffle")
def _shuffle_filter(seq):
    items = list(seq)
    random.shuffle(items)
    return items


def _asset_version():
    """Cache-buster derived from the newest css/js mtime, fixed at boot."""
    newest = 0
    for root, _dirs, files in os.walk(app.static_folder):
        for name in files:
            if name.endswith((".css", ".js")):
                newest = max(newest, os.path.getmtime(os.path.join(root, name)))
    return format(int(newest), "x")


def _app_version():
    """The deployed commit's short SHA. Deploy writes version.txt (git isn't on
    Lambda); locally we read live git. Used in the footer AND folded into the
    cache key, so every deploy busts caches even when only inline template code
    changed (mtime/manifest alone don't always move)."""
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "version.txt")) as fh:
            v = fh.read().strip()
            if v:
                return v
    except OSError:
        pass
    try:
        import subprocess
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stderr=subprocess.DEVNULL).decode().strip() or "dev"
    except Exception:  # noqa: BLE001
        return "dev"


APP_VERSION = _app_version()
# Fold the commit into the asset version so a code-only deploy still busts.
ASSET_V = "{}-{}".format(_asset_version(), APP_VERSION)


@app.context_processor
def _inject_asset_version():
    return {"asset_v": ASSET_V, "app_version": APP_VERSION, "site_url": SITE_URL,
            "curate_authed": (not _is_local()) and _curate_authed()}


@app.route("/robots.txt")
def robots():
    body = "User-agent: *\nAllow: /\nSitemap: {}/sitemap.xml\n".format(SITE_URL)
    return app.response_class(body, mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap():
    paths = ["/", "/projects", "/birds", "/birds/stats", "/birds/live",
             "/birds/live/log", "/birds/heard", "/birds/map"]
    if "photography" not in HIDDEN_PAGES:
        paths.append("/photography")
    if "blog" not in HIDDEN_PAGES:
        paths.append("/blog")
        paths += ["/blog/%s" % p["slug"] for p in blog.list_posts()]
    # Every species hub page — the long-tail entry points ("<bird> north andover").
    shots = birds.load_gallery(shuffle=False)
    paths += sorted("/birds/species/%s" % slug
                    for slug in birds.species_index(shots, birds.load_sounds()))
    urls = "".join("<url><loc>{}{}</loc></url>".format(SITE_URL, p) for p in paths)
    xml = ('<?xml version="1.0" encoding="UTF-8"?>'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
           + urls + "</urlset>")
    return app.response_class(xml, mimetype="application/xml")


@app.after_request
def _page_cache(resp):
    """Every HTML page revalidates against a body-hash ETag instead of being
    heuristically cached by the browser. `no-cache` means the browser always
    checks; an unchanged page comes back as a tiny 304, but the instant a deploy
    bumps the asset version (new css/js ?v=) or a sync/curate edit changes the
    numbers, the body hash changes and the page busts. This is what stops
    browsers from serving stale HTML that still points at last deploy's assets."""
    if (resp.status_code == 200 and request.method == "GET" and not _is_local()
            and not resp.direct_passthrough
            and (resp.content_type or "").startswith("text/html")):
        resp.set_etag(hashlib.md5(resp.get_data()).hexdigest())
        resp.headers["Cache-Control"] = "no-cache"
        return resp.make_conditional(request)
    return resp

TITLE = "Scott Ouellette"


# Swappable background images. Drop a file in static/img/backgrounds/ and add its
# name to static/img/backgrounds/manifest.json (paths are relative to static/img)
# and it joins the rotation. Falls back to the original photo if none are listed.
DEFAULT_BACKGROUNDS = ["fall.jpg"]
_BACKGROUNDS_MANIFEST = os.path.join(
    app.static_folder, "img", "backgrounds", "manifest.json"
)


def load_backgrounds():
    try:
        with open(_BACKGROUNDS_MANIFEST) as fh:
            images = json.load(fh)
        if images:
            return images
    except (OSError, ValueError):
        pass
    return DEFAULT_BACKGROUNDS


def load_facts():
    """Rotating footer facts about me — S3-backed curation (static/facts.json is
    the repo mirror), editable from the home-page curate UI, local or live. An
    empty list means no fact line."""
    return birds._load_curation(birds.FACTS_FILE, list)


@app.context_processor
def _inject_facts():
    # The footer (in base.html) renders on every page, so facts must be available
    # to all templates, not just the home context.
    return {"facts": load_facts()}


def load_taglines():
    """Rotating hero taglines that complete 'Software Infrastructure Engineer that …'
    — S3-backed curation (static/taglines.json is the repo mirror), editable from
    the home-page curate UI, local or live."""
    return birds._load_curation(birds.TAGLINES_FILE, list) or ["builds things"]


# Pages temporarily hidden everywhere (nav, home page, direct URL). To bring one
# back, drop it from this set.
HIDDEN_PAGES = {"blog"}


def _home_context():
    shots = birds.load_gallery()
    stats = birds.gallery_stats(shots)
    # A varied home-page preview of the photography gallery: one per subject,
    # newest first, capped at five (matches the birds strip).
    all_photos = birds.load_photos()
    seen, wildlife = set(), []
    for p in sorted(all_photos, key=lambda p: p.get("date") or "", reverse=True):
        key = (p.get("species") or p.get("title") or "").lower()
        if key and key in seen:
            continue
        seen.add(key)
        wildlife.append(p)
        if len(wildlife) >= 5:
            break
    # The home page is "favorite shots from around my hometown", so keep
    # out-of-area birds (e.g. a Hooded Crow photographed while traveling) off it.
    # The featured grid needs a LOCAL cover frame; the species ticker keeps any
    # bird with at least one North Andover photo (drops travel-only species).
    def _local_cover(s):
        areas = s.get("image_areas") or []
        return not areas or areas[0] != "away"
    def _has_local(s):
        areas = s.get("image_areas")
        return not areas or any(a != "away" for a in areas)
    home_preview = [s for s in shots if _local_cover(s)][:5]
    local_shots = [s for s in shots if _has_local(s)]
    return {
        "title": TITLE,
        "bird_stats": {
            "species": stats["species"],
            "photos": stats["photos"] + stats["videos"],
            "places": len(birds.map_points(shots)),
        },
        "background_image": random.choice(load_backgrounds()),
        "posts": [] if "blog" in HIDDEN_PAGES else blog.list_posts()[:3],
        "shots": shots,
        "home_preview": home_preview,
        "wildlife": wildlife,
        "wildlife_count": len(all_photos),
        "projects": load_projects(),
        "taglines": load_taglines(),
        "species": birds.ticker_species(local_shots),
        "curate": _curate_on(),
        "local": _is_local(),
    }


@app.errorhandler(404)
def not_found(_e):
    return render_template("404.html", title="Not found"), 404


@app.before_request
def canonical_host_redirect():
    """Send the bare apex to the canonical www host with a permanent 301, so
    scott-ouellette.com never serves a duplicate of www.scott-ouellette.com."""
    host = (request.host or "").split(":")[0]
    if host == "scott-ouellette.com":
        return redirect(SITE_URL + request.full_path.rstrip("?"), code=301)


@app.before_request
def serve_birds_subdomain():
    """birds.scott-ouellette.com serves the gallery at its root."""
    host = (request.host or "").split(":")[0]
    if host.startswith("birds.") and request.path == "/":
        return birds_gallery()


# ---------------------------------------------------------------------------
# New site
# ---------------------------------------------------------------------------
@app.route("/", methods=["GET"])
def index():
    return render_template("home.html", **_home_context())


@app.route("/blog", methods=["GET"])
def blog_index():
    if "blog" in HIDDEN_PAGES:
        abort(404)
    return render_template("blog_list.html", title="Blog", posts=blog.list_posts())


@app.route("/blog/<slug>", methods=["GET"])
def blog_post(slug):
    if "blog" in HIDDEN_PAGES:
        abort(404)
    post = blog.get_post(slug)
    if post is None:
        abort(404)
    return render_template("blog_post.html", title=post["title"], post=post)


@app.route("/photography", methods=["GET"])
def photography():
    if "photography" in HIDDEN_PAGES:
        abort(404)
    photos = birds.load_photos()
    # Hidden photos stay in the store (and on S3) but leave the public gallery;
    # curate mode still shows them, dimmed, so a hide can be undone.
    if not _curate_on():
        photos = [p for p in photos if not p.get("hidden")]
    tag = (request.args.get("tag") or "").strip()
    shown = [p for p in photos if not tag or tag in (p.get("tags") or [])]
    if _curate_on():
        # stable, one card per photo: the edit fields are per-photo
        shown.sort(key=lambda p: p.get("date") or "", reverse=True)
        groups = [dict(p, group=[p]) for p in shown]
    else:
        # One card per SUBJECT: five deer shots become one card whose lightbox
        # is a 1/5 carousel, like a multi-image post in the bird gallery.
        by_key, groups = {}, []
        for p in sorted(shown, key=lambda p: (p.get("date") or "", p.get("id") or "")):
            key = (p.get("title") or p.get("species") or "").strip().lower()
            if key and key in by_key:
                by_key[key]["group"].append(p)
            else:
                g = dict(p, group=[p])
                groups.append(g)
                if key:
                    by_key[key] = g
        random.shuffle(groups)  # a fresh order each visit
    # Per-category counts for the filter bar, and the subject/date span for the
    # header stat strip.
    tag_counts = {}
    for p in photos:
        for t in (p.get("tags") or []):
            tag_counts[t] = tag_counts.get(t, 0) + 1
    subjects = {(p.get("title") or p.get("species") or p.get("id") or "").strip().lower()
                for p in photos}
    years = sorted({(p.get("date") or "")[:4] for p in photos if (p.get("date") or "")[:4].isdigit()})
    return render_template(
        "photography.html", title="Photography", photos=groups,
        all_tags=birds.photo_tags(photos), tag_counts=tag_counts, active_tag=tag,
        photo_count=len(photos), subject_count=len(subjects),
        year_from=years[0] if years else None, year_to=years[-1] if years else None,
        curate=_curate_on(), local=_is_local(),
    )


@app.route("/photography/edit", methods=["POST"])
def photography_edit():
    if not _curate_on():
        abort(404)
    data = request.get_json(silent=True) or {}
    pid = (data.get("id") or "").strip()
    if not pid:
        abort(400)
    fields = {k: data[k] for k in ("title", "species", "location", "date", "tags", "hidden")
              if k in data}
    photo = birds.set_photo(pid, fields)
    return {"ok": bool(photo), "photo": photo}


# Curation mode (click-to-hide X buttons, editable species, ratings, re-ID flags)
# is only ever available when serving locally, so production never exposes edit
# controls. Locally it's a runtime toggle (cookie), defaulting to BIRDS_CURATE.
def _is_local():
    if os.environ.get("BIRDS_LOCAL") == "1":
        return True
    host = (request.host or "").rsplit(":", 1)[0]
    return host in ("127.0.0.1", "localhost", "0.0.0.0") or host.endswith(".local")


# Live curation on the deployed site is unlocked by visiting /curate/login?key=
# with a secret held in SSM (rotatable, no user accounts). The cookie stores an
# HMAC of the secret — never the secret itself — so a leaked cookie can't be
# replayed as the login key, and rotating the SSM value invalidates every cookie.
CURATE_SSM_PARAM = os.environ.get("CURATE_SECRET_SSM_PARAM", "/birds/curate_secret")
_curate_secret_cache = {}


def _curate_secret():
    if "v" not in _curate_secret_cache:
        _curate_secret_cache["v"] = birds._ssm_get(CURATE_SSM_PARAM)
    return _curate_secret_cache["v"]


def _curate_cookie_token(secret):
    return hmac.new(secret.encode(), b"curate-cookie-v1", hashlib.sha256).hexdigest()


def _curate_authed():
    """True if this request carries the valid live-curate unlock cookie."""
    secret = _curate_secret()
    if not secret:
        return False
    token = request.cookies.get("curate_key") or ""
    return hmac.compare_digest(token, _curate_cookie_token(secret))


def _curate_on():
    # Local dev: the existing cookie / BIRDS_CURATE env toggle.
    if _is_local():
        cookie = request.cookies.get("curate")
        if cookie is not None:
            return cookie == "1"
        return os.environ.get("BIRDS_CURATE") == "1"
    # Production: you must be unlocked (the persistent auth cookie). Once you
    # are, curate stays alive across browsing; the `curate` cookie is a
    # lightweight view toggle (default on) that pauses/resumes the edit UI
    # WITHOUT logging you out. Everyone unauthed gets the read-only site.
    if not _curate_authed():
        return False
    return request.cookies.get("curate", "1") == "1"


@app.route("/curate/login")
def curate_login():
    secret = _curate_secret()
    key = request.args.get("key") or ""
    if not secret or not hmac.compare_digest(key, secret):
        abort(404)  # wrong/missing key: reveal nothing
    nxt = request.args.get("next") or "/birds"
    if not nxt.startswith("/"):
        nxt = "/birds"
    resp = redirect(nxt)
    resp.set_cookie("curate_key", _curate_cookie_token(secret),
                    max_age=60 * 60 * 24 * 180, httponly=True,
                    secure=not _is_local(), samesite="Lax")
    return resp


@app.route("/curate/logout")
def curate_logout():
    resp = redirect("/birds")
    resp.delete_cookie("curate_key")
    return resp


@app.route("/curate/toggle")
def curate_toggle():
    # Local dev, or an unlocked prod session — either can pause/resume the UI.
    if not (_is_local() or _curate_authed()):
        abort(404)
    # Return to exactly where you were (preserving filters), via an explicit ?next=
    # rather than the flaky Referer header.
    nxt = request.args.get("next") or request.referrer or "/birds"
    if not nxt.startswith("/"):  # only ever redirect within the site
        nxt = "/birds"
    resp = redirect(nxt)
    resp.set_cookie("curate", "0" if _curate_on() else "1", max_age=31536000,
                    samesite="Lax", secure=not _is_local())
    return resp


@app.route("/birds", methods=["GET"])
def birds_gallery():
    curate = _curate_on()
    # A stable ?seed pins the shuffled order on ANY view, so reloading — and
    # especially round-tripping through the curate toggle — lands on exactly
    # the same arrangement. Plain /birds redirects to a fresh seed; the
    # "shuffle" control mints a new seed each click (a same-URL navigation
    # can be served from cache, which made shuffle look dead on filtered
    # views like ?loc=).
    seed = request.args.get("seed") or ""
    unscoped = not any(request.args.get(k) for k in (
        "bird", "family", "area", "media", "loc", "on", "posted",
        "month", "sort", "review", "start"))
    if not seed.isdigit() and unscoped:
        # Public: a fresh seed each visit (feels fresh), pinned per URL so
        # reloads/back are stable. Curate: a STABLE seed derived from the data
        # version, so the order never shifts under an edit and only re-pins when
        # the manifest changes. Either way the toggle carries ?seed via next=,
        # so flipping in/out of curate keeps the exact arrangement.
        if curate:
            n = int(hashlib.sha1(birds.data_version().encode()).hexdigest()[:8], 16)
        else:
            n = random.randrange(1_000_000_000)
        return redirect("/birds?seed=%d" % n)
    if seed.isdigit():
        random.seed(int(seed))
    # Curate now renders the same exploded+shuffled frame view as the public
    # gallery, so load the posts the same way (shuffle=True) — with the seed
    # applied above, the curate grid then matches the gallery you toggled from.
    all_shots = birds.load_gallery(shuffle=True)
    groups = birds.species_groups(all_shots)
    out_of_area = birds.out_of_area_species(all_shots)
    active_birds = birds.resolve_species_list(request.args.get("bird") or "", groups)
    bird = ",".join(active_birds)  # canonical comma-list for the frame filters
    family = (request.args.get("family") or "").strip()
    if family not in birds._FAMILY_ORDER:
        family = ""
    area = (request.args.get("area") or "").strip()
    if area not in ("local", "elsewhere"):
        area = ""
    media = (request.args.get("media") or "").strip()
    if media not in ("photo", "video"):
        media = ""
    sort = (request.args.get("sort") or "").strip()
    if sort not in ("recent", "oldest", "posted"):
        sort = ""
    # Location filter (from a sightings-map pin): resolves against locations.json.
    loc_q = (request.args.get("loc") or "").strip().lower()
    place = next((p for p in birds.load_locations()
                  if p["name"].lower() == loc_q), None) if loc_q else None
    # Day filters, both strict ISO dates: `on` = sighting (capture) day, from
    # the calendar / lightbox sighting date; `posted` = Instagram post day,
    # from the lightbox post date.
    on = (request.args.get("on") or "").strip()
    try:
        on_date = datetime.date.fromisoformat(on) if on else None
    except ValueError:
        on, on_date = "", None
    posted = (request.args.get("posted") or "").strip()
    try:
        posted_date = datetime.date.fromisoformat(posted) if posted else None
    except ValueError:
        posted, posted_date = "", None
    # Month filter (from a phenology-matrix cell): 1-12, any year; composable
    # with the species/family/area/media filters.
    try:
        month = int(request.args.get("month") or 0)
    except ValueError:
        month = 0
    month = month if 1 <= month <= 12 else 0
    # Ordered lead-in from a home-page preview click: pin these exact frames
    # ("<post_id>.<image_index>") to the front in the given order (ignored under
    # any active filter).
    start_tokens = [s for s in (request.args.get("start") or "").split(",") if s][:12]
    # Curate-only review facets.
    review = (request.args.get("review") or "") if curate else ""
    if review not in ("reclassified", "reid", "hidden"):
        review = ""
    reid_keyset = birds.reid_keys() if curate else set()
    overrides = birds.load_overrides() if curate else {}
    review_counts = {
        "reclassified": len(birds.images_for_review(all_shots, "reclassified")),
        "reid": len(reid_keyset),
        "hidden": sum(len(v.get("exclude_images") or []) for v in overrides.values()),
    } if curate else {}
    if review in ("reclassified", "reid"):
        # Review filters explode to the specific IMAGES acted on, not whole posts.
        shots = birds.images_for_review(all_shots, review, reid_keys=reid_keyset)
    elif review == "hidden":
        raw = list(birds._load_manifest_from_s3() or birds._load_local_manifest() or [])
        birds.apply_overrides(raw, apply_exclusions=False)
        shots = birds.images_hidden(raw)
    elif place:
        # ?loc= alone shows the place; ?bird=&loc= (from a species map pin) also
        # requires that species.
        shots = birds.images_at_place(all_shots, place, species=bird or None)
    elif on:
        shots = birds.images_on_date(all_shots, on)
    elif posted:
        shots = birds.images_posted_on(all_shots, posted)
    elif bird or family or area or media or month:
        shots = birds.images_filtered(all_shots, bird, family, area, out_of_area,
                                      media=media, month=month or None)
    elif curate:
        # Exploded single-image frames, same as the public gallery — so the grid
        # you edit matches what visitors see, the lightbox carousel cycles the
        # grid 1:1, and (with ?seed) curate lands exactly where you toggled from.
        # Every edit is per-frame via the lightbox (species/location/area/hide).
        shots = birds.all_photos_shuffled(all_shots)
    elif start_tokens:
        shots = birds.start_ordered(all_shots, start_tokens)  # home-preview lead-in
    else:
        shots = birds.all_photos_shuffled(all_shots)  # plain random order
    # Chronological ordering applies to any frame view (default or filtered),
    # overriding the random/lead-in order. Curate now renders the same exploded
    # frames as the public gallery, so the sort applies there too (it used to be
    # skipped for the old whole-post curate view).
    if sort:
        shots = birds.sort_frames(shots, sort)
    random.seed()  # drop any ?seed determinism before other random consumers
    total = sum(len(sp) for _, sp in groups)
    away = sum(1 for _, sp in groups for name, _ in sp if name in out_of_area)
    # The species/family dropdowns are constrained to the selected area, so picking
    # "spotted elsewhere" narrows them to just the out-of-area birds.
    if area == "elsewhere":
        keep = lambda n: n in out_of_area
    elif area == "local":
        keep = lambda n: n not in out_of_area
    else:
        keep = lambda n: True
    display_groups = [
        (fam, [(n, c) for n, c in sp if keep(n)]) for fam, sp in groups
    ]
    display_groups = [(fam, sp) for fam, sp in display_groups if sp]
    family_counts = {fam: sum(c for _, c in sp) for fam, sp in display_groups}
    bird_family = ""
    if len(active_birds) == 1:  # the "· family · where I find it" line is single-species
        for fam, sp in groups:
            if any(name == active_birds[0] for name, _ in sp):
                bird_family = fam
                break
    return render_template(
        "birds.html",
        title="Birds of North Andover",
        shots=shots,
        species_groups=display_groups,
        family_counts=family_counts,
        species_count=total,
        local_count=total - away,
        away_count=away,
        out_of_area=out_of_area,
        active_bird=bird,
        active_birds=active_birds,
        active_family=family,
        active_area=area,
        active_media=media,
        active_sort=sort,
        active_loc=place["name"] if place else "",
        active_seed=seed if seed.isdigit() else "",
        active_on=on,
        active_on_display=on_date.strftime("%b %-d, %Y") if on_date else "",
        active_posted=posted,
        active_posted_display=posted_date.strftime("%b %-d, %Y") if posted_date else "",
        loc_place_map=birds.location_places(all_shots),
        active_month=month,
        active_month_display=datetime.date(2000, month, 1).strftime("%B") if month else "",
        active_review=review,
        review_counts=review_counts,
        media_n=dict(zip(("photos", "videos"),
                         birds.media_counts(all_shots, bird, family, area, out_of_area,
                                            month=month or None))),
        has_videos=birds.has_videos(all_shots),
        bird_family=bird_family,
        curate=curate,
        local=_is_local(),
        reid_queued=sorted(birds.reid_keys()) if curate else [],
    )


@app.route("/birds/field", methods=["GET"])
def birds_field():
    """The gallery as an endless field: the same masonry tiles, but pannable in
    any direction. Tiles are drawn from a sequence built round-robin across
    species, so a bird's share of the field tracks how often it was actually
    photographed and the same species never lands beside itself."""
    shots = birds.load_gallery(shuffle=False)

    by_species, order = {}, []
    tiles = []
    for sh in shots:
        imgs = sh.get("images") or []
        if not imgs:
            continue
        dm = (sh.get("image_dims") or [None])[0]
        names = birds._canon_species_list(sh.get("species"))
        nm, fam = (names[0] if names else (sh.get("species") or "Unknown", "Other birds"))
        vlist = sh.get("image_videos") or []
        t = {
            "src": birds.thumb_url(imgs[0]),
            # the real clip lives in image_videos; images[0] is just its poster
            "vsrc": (vlist[0] if (vlist and vlist[0]) else None),
            "w": (dm[0] if dm else 0), "h": (dm[1] if dm else 0),
            "name": nm, "fam": fam, "slug": birds._species_slug(nm),
            "n": len(imgs),
            "vid": 1 if (vlist and vlist[0]) else 0,
            "away": 1 if ((sh.get("image_areas") or [None])[0] == "away") else 0,
        }
        idx = len(tiles)
        t["post_n"] = t["n"]          # images in THIS post
        tiles.append(t)
        if nm not in by_species:
            by_species[nm] = []
            order.append(nm)
        by_species[nm].append(idx)

    # A tile opens the SPECIES, so the badge should read that bird's whole
    # count, not how many images happened to be in this one post — showing 6
    # for a House Finch that has 28 pictures is just confusing.
    #
    # Counted per FRAME, not per post: a post can hold several species, so
    # crediting every image in it to the post's primary bird over-counts
    # (it made Barred Owl 228 against the species page's 202).
    totals = {}
    for sh in shots:
        isp = sh.get("image_species") or []
        for i in range(len(sh.get("images") or [])):
            raw = isp[i] if i < len(isp) and isp[i] else sh.get("species")
            for nm, _fam in birds._canon_species_list(raw):
                totals[nm] = totals.get(nm, 0) + 1
    for t in tiles:
        t["n"] = totals.get(t["name"], t["post_n"])

    # Round-robin across species: one tile each per pass, so a bird only recurs
    # after every other species with frames left has had a turn.
    #
    # Capped, though. Uncapped, the tail of the sequence is whatever species
    # still has frames — Barred Owl holds 41 of 353 — so the end degenerates
    # into the same bird over and over. Capping keeps every pass wide and the
    # spacing between repeats roughly the number of species.
    CAP = 8
    seq, any_left = [], True
    while any_left:
        any_left = False
        for nm in order:
            lst = by_species[nm]
            if lst and sum(1 for i in seq if tiles[i]["name"] == nm) < CAP:
                seq.append(lst.pop(0))
                any_left = True

    # Column c is the sequence rotated by c*STRIDE. If STRIDE lands near a
    # multiple of the species count, neighbouring columns sit in phase and show
    # the same birds — which is exactly what 97-against-95-species did. Pick the
    # stride that spreads the nearby columns furthest apart in that cycle.
    L, P = len(seq), max(1, len(order))
    best, stride = -1, 1
    for cand in range(7, max(8, L)):
        if L % cand == 0:
            continue
        worst = min(min((cand * c) % P, P - (cand * c) % P) for c in range(1, 9))
        if worst > best:
            best, stride = worst, cand

    # The rail was reporting len(tiles) as "frames" (those are posts: 353 vs
    # 1,754 actual frames) and len(order) as species (that counts only each
    # post's primary bird: 95 vs 114). Use the gallery's own figures.
    gstats = birds.gallery_stats(shots)
    return render_template(
        "birds_field.html", title="Birds of North Andover",
        tiles=tiles, seq=seq, species_n=gstats["species"], stride=stride,
        photos_n=gstats["photos"], videos_n=gstats["videos"],
        curate=_curate_on(), local=_is_local())


@app.route("/birds/species/<slug>.json", methods=["GET"])
def birds_species_json(slug):
    """Everything the site knows about one bird, as JSON, for the gallery's
    per-species detail view.
    species_profile() already gathers across all four views — gallery, stats,
    map and the mic — so this just trims it to what the overlay renders."""
    names = birds.species_index()
    name = names.get(slug)
    if not name:
        return app.json.response({"error": "unknown species"}), 404
    p = birds.species_profile(name) or {}
    frames = []
    # No arbitrary cap: the modal is where you go to see ALL of a bird.
    # Even the heaviest species (Barred Owl, ~200) is a few tens of KB,
    # fetched lazily on open and lazy-loaded thumb by thumb.
    for f in (p.get("frames") or []):
        imgs = f.get("images") or []
        if not imgs:
            continue
        locs = f.get("image_locations") or []
        vids = f.get("image_videos") or []
        idxs = f.get("image_indices") or []
        areas = f.get("image_areas") or []
        frames.append({"thumb": birds.thumb_url(imgs[0]), "full": imgs[0],
                       "date": f.get("_sort") or f.get("date"),
                       "where": (locs[0] if locs else None),
                       "vid": 1 if (vids and vids[0]) else 0,
                       # identity, so curate can act on the exact frame shown
                       "pid": f.get("post_id"),
                       "idx": (idxs[0] if idxs else 0),
                       "away": 1 if (areas and areas[0] == "away") else 0})
    heard = p.get("heard") or {}
    # best_call can be empty even for a heavily-recorded bird (Barred Owl has
    # 1,199 detections and 40 clips, yet no "best"), so pick the highest
    # confidence clip ourselves rather than settling for the latest — a clean
    # recording matters more than a fresh one.
    # species_profile can surface no calls at all for a bird that plainly has
    # clips (Red-tailed Hawk: 4 detections, 3 clips on file, all_calls empty),
    # so read the per-species clip file directly as well and merge.
    alls = list(p.get("all_calls") or [])
    if not alls:
        for c in (birds.load_species_clips().get(p.get("name")) or []):
            if c.get("audio"):
                alls.append({"audio": c.get("audio"), "spec": c.get("spec"),
                             "conf": c.get("conf"), "t": c.get("t"),
                             "when": c.get("when"), "node": c.get("node")})
    # Rank by cleanliness, but let recency break near-ties: a 95% from last
    # week should beat a 96% from two years ago, while a 100% still wins
    # outright. The bonus decays over ~4 months and is capped at 12%, so it
    # nudges rather than reorders.
    _now = datetime.datetime.now(datetime.timezone.utc)

    def _score(c):
        conf = c.get("conf") or 0
        try:
            t = datetime.datetime.fromisoformat(c.get("t") or "")
            if t.tzinfo is None:
                t = t.replace(tzinfo=datetime.timezone.utc)
            days = max(0.0, (_now - t).total_seconds() / 86400.0)
        except (TypeError, ValueError):
            return conf
        return conf * (1 + 0.12 * math.exp(-days / 120.0))

    alls.sort(key=lambda c: -_score(c))
    call = p.get("best_call") or (alls[0] if alls else {}) or p.get("recent_call") or {}
    call_kind = "clearest"
    out = {
        "name": p.get("name"), "slug": p.get("slug"), "family": p.get("family"),
        "rank": p.get("rank"), "total": p.get("total_lifers"),
        "count": p.get("count"), "frames": frames,
        "videos": sum(1 for f in frames if f["vid"]),
        "images": sum(1 for f in frames if not f["vid"]),
        "months": (p.get("pheno") or {}).get("months") or [],
        "places": [{"name": q.get("name"), "count": q.get("count"),
                    "area": q.get("area"), "lat": q.get("lat"), "lng": q.get("lng")}
                   for q in (p.get("places") or [])[:8]],
        "heard": {"count": heard.get("count") or 0,
                  "first": (heard.get("first") or "")[:10],
                  "last": (heard.get("last") or "")[:10],
                  "max": heard.get("maxConf")} if heard else None,
        "call": {"audio": call.get("audio"), "spec": call.get("spec"),
                 "conf": call.get("conf"), "when": call.get("when"),
                 "node": call.get("node"), "kind": call_kind} if call.get("audio") else None,
        # a shortlist, so you can hear more than the single best
        "calls": [{"audio": c.get("audio"), "spec": c.get("spec"),
                   "conf": c.get("conf"), "when": c.get("when"),
                   "node": c.get("node")}
                  for c in alls[:5] if c.get("audio")],
        "nodes": p.get("heard_nodes") or [],
    }
    resp = app.json.response(out)
    resp.cache_control.max_age = 300
    return resp


@app.route("/birds/species/<slug>", methods=["GET"])
def birds_species(slug):
    """The hub page for one bird — its photos, lifer rank, seasonal rhythm, the
    call heard by the yard mic, and where it turns up, all in one place."""
    shots = birds.load_gallery(shuffle=False)
    sound = birds.load_sounds()
    name = birds.species_index(shots, sound).get(slug)
    if not name:
        abort(404)
    profile = birds.species_profile(name, shots, sound)
    if not profile:
        abort(404)
    return render_template(
        "species.html", title=profile["name"], sp=profile,
        local=_is_local(), curate=_curate_on(),
    )


@app.route("/birds/map", methods=["GET"])
def birds_map():
    shots = birds.load_gallery(shuffle=False)
    # ?bird= focuses the map on where one species turns up (deep-linked from a
    # species/gallery view); it resolves against the same species index.
    groups = birds.species_groups(shots)
    bird = birds.resolve_species(request.args.get("bird") or "", groups)
    fam = (request.args.get("family") or "").strip()
    if bird or fam not in birds._FAMILY_ORDER:
        fam = ""
    points = birds.map_points(shots, species_filter=bird or None,
                              family_filter=fam or None)
    return render_template(
        "map.html",
        title=("Where I find " + (bird or fam)) if (bird or fam) else "Bird sightings map",
        points=points,
        mapped=sum(p["count"] for p in points),
        active_bird=bird,
        active_family=fam,
        local=_is_local(),
        curate=_curate_on(),
    )


def _live_view():
    """Sound-station rollup enriched with gallery cross-links, for page + poll."""
    data = birds.load_sounds()
    shots = birds.load_gallery(shuffle=False)
    groups = birds.species_groups(shots)
    photographed = {n for _, sp in groups for n, _ in sp}
    covers = birds.species_covers(shots)
    # Seed the photo pick by species + day: every instance of a species on the
    # screen (hero, feed rows, wall) shows the SAME shot, it's stable across the
    # 60s polls, and it rotates to a different shot day to day.
    day = datetime.date.today().isoformat()

    def enrich(entry):
        common = entry.get("common") if isinstance(entry, dict) else entry
        canon = birds._canon_species(common or "")
        disp = canon[0] if canon else (common or "")
        out = {"common": common, "display": disp,
               "fam": canon[1] if canon else "Other birds",
               "photo": birds.pick_cover(covers.get(disp), disp + "|" + day),
               "shot": disp in photographed}
        if isinstance(entry, dict):
            out.update({k: entry[k] for k in
                        ("t", "conf", "new", "count", "first", "last", "maxConf",
                         "audio", "spec", "node") if k in entry})
        return out

    view = {"station": {}, "recent": [], "species": [], "counts": {},
            "daily": [], "hours": [], "missing": [], "generated": None,
            "weather": None, "nodes": []}
    if data:
        view["generated"] = data.get("generated")
        view["station"] = data.get("station", {})
        view["nodes"] = data.get("nodes") or []
        view["weather"] = data.get("weather")
        view["counts"] = data.get("counts", {})
        view["daily"] = data.get("daily", [])
        view["hours"] = data.get("hours", [])
        view["hoursHist"] = data.get("hoursHist", [])  # all-time typical-day overlay
        view["recent"] = [enrich(r) for r in data.get("recent", [])]
        # Give each species its full photo pool (best-first, capped) so the "just
        # heard" hero can pick a fresh portrait each page load instead of the one
        # per-day cover — variety on refresh without flickering across polls.
        def with_pool(s):
            e = enrich(s)
            e["photos"] = (covers.get(e["display"]) or [])[:12]
            return e
        view["species"] = sorted((with_pool(s) for s in data.get("species", [])),
                                 key=lambda s: s.get("last") or "", reverse=True)
        miss = [s for s in view["species"] if not s["shot"]]
        view["missing"] = miss
        n = len(view["species"])
        view["hv"] = {"heard": n, "shot": n - len(miss), "miss": len(miss)}
        # The full day's recordings (curated log, last ~30h so the viewer's local
        # "today" is covered in any tz), so the live page's hour strip shows the
        # WHOLE day — not just the recent window — and tapping any hour (even 6am,
        # long aged out of `recent`) shows those recordings inline. This is the
        # curated log, so hidden clips are already dropped.
        log = birds.load_sound_log() or {}
        cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=30)
        dayrecs = []  # NB: not `day` — that name is the date seed enrich() closes over
        for r in (log.get("log") or []):
            try:
                if datetime.datetime.fromisoformat(r["t"]) >= cutoff:
                    dayrecs.append(enrich(r))
            except (KeyError, ValueError, TypeError):
                continue
        view["dayrecs"] = dayrecs
        # The "heard vs shot" wall is scoped to the active day AND clip-hide-aware:
        # derive today's species from the day's VISIBLE recordings (dayrecs is the
        # curated log, so hidden clips are gone), not the raw daily rollup. Hiding
        # every clip of a species therefore drops it from the wall too.
        _daily = data.get("daily") or []
        station_today = (_daily[-1].get("d") if (_daily and isinstance(_daily[-1], dict)) else None)
        today_keys = {birds._sound_canon_key(r.get("display") or r.get("common"))
                      for r in dayrecs if station_today and (r.get("t") or "")[:10] == station_today}
        today_sp = [s for s in view["species"]
                    if birds._sound_canon_key(s.get("display") or s.get("common")) in today_keys]
        miss_t = [s for s in today_sp if not s["shot"]]
        view["speciesToday"] = today_sp
        view["hvToday"] = {"heard": len(today_sp), "shot": len(today_sp) - len(miss_t), "miss": len(miss_t)}
    return view


@app.route("/birds/live", methods=["GET"])
def birds_live():
    """What the porch mic is hearing, cross-linked to the photo gallery."""
    view = _live_view()
    curate = _curate_on()
    return render_template(
        "birds_live.html", title="Live from the yard", sound=view,
        has_data=bool(view["recent"]), generated=view["generated"],
        suppressed=(birds.load_sound_curation()["species"] if curate else []),
        curate=curate, local=_is_local())


@app.route("/birds/live.json", methods=["GET"])
def birds_live_json():
    """The same rollup as JSON, so the page can refresh itself in place."""
    resp = app.json.response(_live_view())
    resp.cache_control.max_age = 30
    return resp


@app.route("/birds/live/history.json", methods=["GET"])
def birds_live_history_json():
    """The curated recording log (last 60 days), lightly enriched — feeds the
    live page's soundtrack day-stepper and last-7-days comparison. Fetched
    lazily, only when someone steps off 'today'."""
    log = birds.load_sound_log() or {}
    shots = birds.load_gallery(shuffle=False)
    photographed = {n for _, sp in birds.species_groups(shots) for n, _ in sp}
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=60)
    out = []
    for r in (log.get("log") or []):
        try:
            if datetime.datetime.fromisoformat(r["t"]) < cutoff:
                continue
        except (KeyError, ValueError, TypeError):
            continue
        canon = birds._canon_species(r.get("common") or "")
        disp = canon[0] if canon else (r.get("common") or "")
        out.append({"t": r["t"], "display": disp,
                    "fam": canon[1] if canon else "Other birds",
                    "shot": disp in photographed, "conf": r.get("conf"),
                    "audio": r.get("audio"), "spec": r.get("spec"),
                    "node": r.get("node")})
    resp = app.json.response({"recs": out})
    resp.cache_control.max_age = 300
    return resp


@app.route("/birds/heard", methods=["GET"])
def birds_heard():
    """Every species the porch mic has ever heard — the all-time roll, its own
    page so 'species heard all-time' leads somewhere that says exactly that."""
    view = _live_view()
    daily = view.get("daily") or []
    since = None
    if daily:
        try:
            since = datetime.datetime.strptime(daily[0]["d"], "%Y-%m-%d").strftime("%b %-d, %Y")
        except (ValueError, KeyError, TypeError):
            since = None
    return render_template(
        "heard.html", title="Every species heard from the yard",
        sound=view, has_data=bool(view["species"]), since=since,
        local=_is_local())


def _log_view():
    """The full browsable detection log, enriched with display names + photos."""
    data = birds.load_sound_log()
    shots = birds.load_gallery(shuffle=False)
    groups = birds.species_groups(shots)
    photographed = {n for _, sp in groups for n, _ in sp}
    covers = birds.species_covers(shots)

    def enrich(entry):
        common = entry.get("common") or ""
        canon = birds._canon_species(common)
        disp = canon[0] if canon else common
        out = {"common": common, "display": disp,
               "slug": birds._species_slug(disp),
               "fam": canon[1] if canon else "Other birds",
               "photo": birds.pick_cover(covers.get(disp), disp),
               "shot": disp in photographed}
        for k in ("t", "conf", "new", "audio", "spec", "sci", "node"):
            if k in entry:
                out[k] = entry[k]
        return out

    log = data.get("log", []) if data else []
    enriched = [enrich(e) for e in log]
    # Distinct nodes seen in the log, newest first — so the log can filter by node.
    seen, nodes = set(), []
    for e in enriched:
        nm = e.get("node")
        if nm and nm not in seen:
            seen.add(nm)
            nodes.append(nm)
    return {"generated": (data or {}).get("generated"),
            "log": enriched, "nodes": nodes}


@app.route("/birds/live/log", methods=["GET"])
def birds_live_log():
    """Every detection the mic has logged — grouped, paginated, filterable."""
    view = _log_view()
    return render_template(
        "sound_log.html", title="Detection log", log=view["log"],
        nodes=view["nodes"], generated=view["generated"], has_data=bool(view["log"]),
        curate=_curate_on(), local=_is_local())


@app.route("/birds/stats", methods=["GET"])
def birds_stats():
    shots = birds.load_gallery(shuffle=False)
    _stats_covers = birds.species_covers(shots)  # best thumb per species (ghost-row avatar)
    stats = birds.gallery_stats(shots)
    span_months = 0
    if stats["first"] and stats["last"]:
        span_months = ((stats["last"].year - stats["first"].year) * 12
                       + stats["last"].month - stats["first"].month + 1)
    # Fold top locations onto their geocoded place (map pin) when we have one,
    # so caption spelling variants ("Harborwalk, Boston" / "... Boston MA")
    # collapse into a single clickable row under the pin's canonical name.
    place_index = birds._place_index(birds.load_locations())
    loc_place, loc_area, merged, by_name = {}, {}, [], {}
    for loc, count in stats["top_locations"]:
        place = birds._match_place(loc, place_index)
        name = place["name"] if place else loc
        if name in by_name:
            by_name[name][1] += count
        else:
            row = [name, count]
            by_name[name] = row
            merged.append(row)
            if place:
                loc_place[name] = place["name"]
                loc_area[name] = place.get("area", "local")
    merged.sort(key=lambda r: -r[1])
    stats["top_locations"] = [tuple(r) for r in merged]
    # The mic's side of the story: per-species call counts + daily volume,
    # cross-linked to the photo gallery (avatar when shot, feather when not).
    sound = birds.load_sounds()
    ear = None
    if sound and sound.get("species"):
        photographed = {nm for _, sp in birds.species_groups(shots) for nm, _ in sp}
        heard = []
        for s in sound["species"]:
            canon = birds._canon_species(s.get("common") or "")
            disp = canon[0] if canon else (s.get("common") or "")
            heard.append({"name": disp, "fam": canon[1] if canon else "Other birds",
                          "n": s.get("count") or 0,
                          "img": (_stats_covers.get(disp) or [None])[0],
                          "shot": disp in photographed,
                          "last": s.get("last") or "", "first": s.get("first") or ""})
        heard.sort(key=lambda x: (-x["n"], x["name"]))

        def _d(k):
            try:
                return datetime.datetime.strptime(k, "%Y-%m-%d").strftime("%b %-d")
            except (TypeError, ValueError):
                return k
        daily = sound.get("daily") or []
        busiest = max(daily, key=lambda d: d.get("n") or 0) if daily else None
        ear = {"heard": heard,
               "calls": (sound.get("counts") or {}).get("callsAllTime") or 0,
               "shot": sum(1 for x in heard if x["shot"]),
               "since": _d(daily[0]["d"]) if daily else None,
               "busiest": {"d": _d(busiest["d"]), "n": busiest.get("n") or 0} if busiest else None,
               "daily": [{"d": _d(d.get("d")), "n": d.get("n") or 0} for d in daily[-30:]]}
    # The yard's daily rhythm (species x hour-of-day) and geography (species x
    # listening node), from the all-time patterns aggregate. Each species is
    # mapped to its display name + gallery avatar exactly like the `ear` block, so
    # the charts cross-link to the photos and know what's been shot.
    pat = birds.load_patterns()
    rhythm = geo = None
    if pat:
        photographed = {nm for _, sp in birds.species_groups(shots) for nm, _ in sp}

        def _card(name):
            canon = birds._canon_species(name or "")
            disp = canon[0] if canon else (name or "")
            return {"name": disp, "fam": canon[1] if canon else "Other birds",
                    "img": (_stats_covers.get(disp) or [None])[0],
                    "shot": disp in photographed}

        # Each species becomes a ridge: a filled area over the 24h day, normalized
        # to ITS OWN busiest hour (gamma-lifted) so the SHAPE reads regardless of
        # volume. Rows are ordered by peak hour into a dawn->night cascade.
        def _hlab(h):
            return "%d%s" % (h % 12 or 12, "a" if h < 12 else "p")

        # The ridges were 30 identical mint curves — the cascade they are already
        # sorted into was invisible. Colour by WHEN a bird peaks, so the dawn
        # chorus, the midday lull and the owls read as bands at a glance. This is
        # a cyclical sequential encoding (time), not 30 arbitrary categories.
        _BANDS = [(5, 8,   "#b1560b", "dawn"),
                  (8, 12,  "#2f7d4f", "morning"),
                  (12, 17, "#028779", "afternoon"),
                  (17, 21, "#950259", "dusk")]

        def _band(h):
            for lo, hi, col, lab in _BANDS:
                if lo <= h < hi:
                    return col, lab
            return "#3a539c", "night"      # 21:00-05:00 wraps midnight

        def _spark(intens):  # closed area path, viewBox 0 0 100 26, baseline at 26
            n = len(intens)
            body = " ".join("L%.2f,%.2f" % (i / (n - 1) * 100.0, 26.0 - v * 24.0)
                            for i, v in enumerate(intens))
            return "M0,26 %s L100,26 Z" % body

        rrows = []
        for s in (pat.get("rhythm") or [])[:30]:
            hrs = s.get("hours") or [0] * 24
            rmax = max(hrs) or 1
            intens = [round((c / rmax) ** 0.6, 3) for c in hrs]
            peak = max(range(24), key=lambda h: hrs[h]) if any(hrs) else 0
            row = _card(s.get("name"))
            hue, band = _band(peak)
            row.update({"path": _spark(intens), "peak": peak, "peaklab": _hlab(peak),
                        "hue": hue, "band": band,
                        "total": s.get("total") or sum(hrs)})
            rrows.append(row)
        rrows.sort(key=lambda r: (r["peak"], -r["total"]))
        _seen, _legend = set(), []
        for _lo, _hi, _col, _lab in _BANDS + [(0, 0, "#3a539c", "night")]:
            if _lab not in _seen and any(r["band"] == _lab for r in rrows):
                _seen.add(_lab); _legend.append({"label": _lab, "hue": _col})
        rhythm = {"species": rrows, "legend": _legend}

        # Yard geography: which mic hears each species. Node colors match the live
        # page's dots (nodes.js assigns the palette by sorted node position).
        nodes = sorted(pat.get("nodes") or [])
        if len(nodes) >= 2:
            PAL = ["#2a9d9c", "#c25b86", "#3d7ec4", "#b8863b", "#7c6bd0", "#5a8f4e"]
            colors = {nm: PAL[i % len(PAL)] for i, nm in enumerate(nodes)}
            grows = []
            for s in (pat.get("geo") or []):
                bn = s.get("byNode") or {}
                tot = s.get("total") or sum(bn.values())
                row = _card(s.get("name"))
                row.update({"total": tot,
                            "parts": [{"node": nm, "n": bn.get(nm, 0),
                                       "pct": round(bn.get(nm, 0) / tot * 100, 1) if tot else 0}
                                      for nm in nodes]})
                grows.append(row)
            geo = {"nodes": nodes, "nodeTotals": pat.get("nodeTotals") or {},
                   "colors": colors, "species": grows}
    # Single-species OR single-family focus (?bird=X / ?family=F, deep-linked
    # from a profile or the family eyebrow): the headline numbers filter to that
    # context so "by the numbers" actually means ITS numbers, while the charts
    # below still show it against the whole collection.
    focus = None
    fbird = birds.resolve_species(request.args.get("bird") or "", birds.species_groups(shots))
    ffam = (request.args.get("family") or "").strip()
    if ffam not in birds._FAMILY_ORDER:
        ffam = ""
    if fbird:
        fs = birds.species_stats(shots, fbird)
        rec = next((h for h in (ear["heard"] if ear else []) if h["name"] == fbird), None)
        focus = {"bird": fbird, "photos": fs["photos"], "videos": fs["videos"],
                 "active_months": fs["active_months"], "away": fs["away"], "places": fs["places"],
                 "first": fs["first"], "last": fs["last"],
                 "photographed": (fs["photos"] + fs["videos"]) > 0,
                 "recordings": (rec or {}).get("n") or 0}
    elif ffam:
        fs = birds.species_stats(shots, None, family=ffam)
        recs = sum((h.get("n") or 0) for h in (ear["heard"] if ear else []) if h.get("fam") == ffam)
        focus = {"family": ffam, "species": fs["species"],
                 "photos": fs["photos"], "videos": fs["videos"],
                 "active_months": fs["active_months"], "away": fs["away"], "places": fs["places"],
                 "first": fs["first"], "last": fs["last"],
                 "photographed": (fs["photos"] + fs["videos"]) > 0,
                 "recordings": recs}
    return render_template(
        "stats.html",
        title=((focus.get("bird") or focus.get("family")) + " by the numbers") if focus else "Birds by the numbers",
        stats=stats,
        focus=focus,
        loc_area=loc_area,
        series=birds.stats_series(shots),
        river=birds.activity_river(shots),
        species_places=birds.species_places(shots),
        species_ranked=sorted(
            ((nm, c, (_stats_covers.get(nm) or [None])[0])
             for _, sp in birds.species_groups(shots) for nm, c in sp),
            key=lambda kv: -kv[1]),
        loc_place=loc_place,
        map_points=birds.map_points(shots),
        span_months=span_months,
        ear=ear,
        rhythm=rhythm,
        geo=geo,
        local=_is_local(),
        curate=_curate_on(),
    )


@app.route("/curate/exclude", methods=["POST"])
def curate_exclude():
    if not _curate_on():
        abort(404)
    post_id = (request.get_json(silent=True) or {}).get("id")
    if not post_id:
        abort(400)
    birds.add_exclusion(post_id)
    return {"ok": True, "excluded": len(birds.load_excluded())}


@app.route("/curate/sound", methods=["POST"])
def curate_sound():
    """Live-sound curation: suppress a species (a false positive like a dog read
    as a Ruffed Grouse) or hide one detection. Applied at serve time."""
    if not _curate_on():
        abort(404)
    data = request.get_json(silent=True) or {}
    if data.get("species"):
        birds.set_sound_suppress(data["species"], bool(data.get("on", True)))
    if data.get("clip"):
        birds.set_sound_hide(data["clip"], bool(data.get("on", True)))
    cur = birds.load_sound_curation()
    return {"ok": True, "suppressed": cur["species"], "hidden": len(cur["clips"])}


@app.route("/curate/override", methods=["POST"])
def curate_override():
    if not _curate_on():
        abort(404)
    data = request.get_json(silent=True) or {}
    post_id = (data.get("id") or "").strip()
    if not post_id:
        abort(400)
    keys = ("species", "location", "date", "capture_date", "posted", "images", "image_locations", "image_areas")
    fields = {k: data[k] for k in keys if k in data}
    shot = birds.set_override(post_id, fields)
    return {"ok": True, "ambiguous": bool(shot and shot.get("ambiguous"))}


@app.route("/curate/lifer", methods=["POST"])
def curate_lifer():
    if not _curate_on():
        abort(404)
    data = request.get_json(silent=True) or {}
    species = (data.get("species") or "").strip()
    if not species:
        abort(400)
    entry = birds.set_lifer(species, src=data.get("src"), pos=data.get("pos"),
                            posx=data.get("posx"), zoom=data.get("zoom"))
    return {"ok": True, "entry": entry}


@app.route("/curate/location", methods=["POST"])
def curate_location():
    if not _curate_on():
        abort(404)
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    area = (data.get("area") or "").strip()
    if not name or area not in ("local", "away"):
        abort(400)
    entry = birds.set_location_override(name, area)
    return {"ok": True, "entry": entry}


@app.route("/curate/reid", methods=["POST"])
def curate_reid():
    if not _curate_on():
        abort(404)
    data = request.get_json(silent=True) or {}
    post_id = (data.get("id") or "").strip()
    if not post_id or data.get("index") is None:
        abort(400)
    queue, queued = birds.toggle_reid(
        post_id, data["index"], data.get("current", ""), data.get("note", "")
    )
    return {"ok": True, "queued": queued, "count": len(queue)}


@app.route("/curate/exclude-image", methods=["POST"])
def curate_exclude_image():
    if not _curate_on():
        abort(404)
    data = request.get_json(silent=True) or {}
    post_id = (data.get("id") or "").strip()
    if not post_id or data.get("index") is None:
        abort(400)
    excluded = birds.toggle_image_exclusion(post_id, data["index"])
    return {"ok": True, "excluded": excluded}


GITHUB_USER = "scottx611x"


@app.route("/projects", methods=["GET"])
def projects():
    return render_template(
        "projects.html",
        title="Projects",
        github_user=GITHUB_USER,
        projects=load_projects(),
        curate=_curate_on(),
        local=_is_local(),
    )


def load_projects():
    """Curated things I've built (static/projects.json), S3-backed so the live
    curated site can edit it too — same store as the bird curation files."""
    return birds._load_curation(birds.PROJECTS_FILE, list)


@app.route("/curate/projects", methods=["POST"])
def curate_projects():
    """Save the reordered/edited project list (curate mode, local or live)."""
    if not _curate_on():
        abort(404)
    data = request.get_json(silent=True) or {}
    incoming = data.get("projects")
    if not isinstance(incoming, list):
        abort(400)
    clean = []
    for p in incoming:
        if not isinstance(p, dict):
            continue
        name = (p.get("name") or "").strip()
        if not name:
            continue
        entry = {"name": name}
        for key in ("repo", "site", "tech", "description", "year"):
            val = (p.get(key) or "").strip()
            if val:
                entry[key] = val
        if p.get("featured"):
            entry["featured"] = True
        if p.get("hidden"):
            entry["hidden"] = True
        clean.append(entry)
    birds._save_curation(birds.PROJECTS_FILE, clean)
    return {"ok": True, "count": len(clean)}


@app.route("/curate/taglines", methods=["POST"])
def curate_taglines():
    """Save the reordered/edited hero taglines (curate mode, local or live)."""
    if not _curate_on():
        abort(404)
    data = request.get_json(silent=True) or {}
    incoming = data.get("taglines")
    if not isinstance(incoming, list):
        abort(400)
    clean = [s.strip() for s in incoming if isinstance(s, str) and s.strip()]
    birds._save_curation(birds.TAGLINES_FILE, clean)
    return {"ok": True, "count": len(clean)}


@app.route("/curate/facts", methods=["POST"])
def curate_facts():
    """Save the reordered/edited footer facts (curate mode, local or live)."""
    if not _curate_on():
        abort(404)
    data = request.get_json(silent=True) or {}
    incoming = data.get("facts")
    if not isinstance(incoming, list):
        abort(400)
    clean = [s.strip() for s in incoming if isinstance(s, str) and s.strip()]
    birds._save_curation(birds.FACTS_FILE, clean)
    return {"ok": True, "count": len(clean)}


# ---------------------------------------------------------------------------
# Archive (the original site, preserved)
# ---------------------------------------------------------------------------
ARCHIVE_CONTEXT = {"title": "Scott's Website (archive)", "background_image": "fall.jpg"}

# The original site's animated backgrounds, preserved only on /archive.
ARCHIVE_EFFECTS = ["collision", "tilt-shift", "voronoi"]


@app.route("/archive", methods=["GET"])
def archive():
    template = "archive/{}.html".format(random.choice(ARCHIVE_EFFECTS))
    return render_template(template, **ARCHIVE_CONTEXT)


@app.route("/archive/<effect>", methods=["GET"])
def archive_effect(effect):
    if effect not in ARCHIVE_EFFECTS:
        abort(404)
    return render_template("archive/{}.html".format(effect), **ARCHIVE_CONTEXT)


if __name__ == "__main__":
    app.run(debug=True)
