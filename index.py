import datetime
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
    paths = ["/", "/projects", "/birds", "/birds/stats", "/birds/map"]
    if "blog" not in HIDDEN_PAGES:
        paths.append("/blog")
        paths += ["/blog/%s" % p["slug"] for p in blog.list_posts()]
    urls = "".join("<url><loc>{}{}</loc></url>".format(SITE_URL, p) for p in paths)
    xml = ('<?xml version="1.0" encoding="UTF-8"?>'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
           + urls + "</urlset>")
    return app.response_class(xml, mimetype="application/xml")


@app.after_request
def _page_cache(resp):
    """Data-derived pages (stats, map) revalidate against the backing data
    instead of caching for a fixed window: the ETag folds in the manifest
    version + asset version, and `no-cache` makes the browser check every time.
    An unchanged page comes back as a tiny 304; the instant a sync changes the
    manifest, the ETag changes and the page busts. No stale numbers, no lag."""
    if (request.endpoint in ("birds_stats", "birds_map") and resp.status_code == 200
            and not _is_local() and request.method == "GET"):
        resp.set_etag("{}-{}".format(birds.data_version(), ASSET_V))
        resp.headers["Cache-Control"] = "no-cache"
        return resp.make_conditional(request)
    if (request.endpoint == "projects" and resp.status_code == 200
            and not _is_local() and request.method == "GET"):
        # A live curate edit rewrites the project list, so revalidate against a
        # hash of the rendered body — an unchanged page is a 304, an edited one
        # busts on the next load instead of serving a stale cached copy.
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
        "wildlife": wildlife,
        "wildlife_count": len(all_photos),
        "projects": load_projects(),
        "taglines": load_taglines(),
        "species": birds.ticker_species(shots),
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
    tag = (request.args.get("tag") or "").strip()
    shown = [p for p in photos if not tag or tag in (p.get("tags") or [])]
    if _curate_on():
        shown.sort(key=lambda p: p.get("date") or "", reverse=True)  # stable for editing
    else:
        random.shuffle(shown)  # a fresh order each visit
    return render_template(
        "photography.html", title="Photography", photos=shown,
        all_tags=birds.photo_tags(photos), active_tag=tag, photo_count=len(photos),
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
    fields = {k: data[k] for k in ("title", "species", "location", "date", "tags")
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


@app.route("/birds/map", methods=["GET"])
def birds_map():
    shots = birds.load_gallery(shuffle=False)
    # ?bird= focuses the map on where one species turns up (deep-linked from a
    # species/gallery view); it resolves against the same species index.
    groups = birds.species_groups(shots)
    bird = birds.resolve_species(request.args.get("bird") or "", groups)
    points = birds.map_points(shots, species_filter=bird or None)
    return render_template(
        "map.html",
        title="Bird sightings map",
        points=points,
        mapped=sum(p["count"] for p in points),
        active_bird=bird,
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
                         "audio", "spec") if k in entry})
        return out

    view = {"station": {}, "recent": [], "species": [], "counts": {},
            "daily": [], "hours": [], "missing": [], "generated": None}
    if data:
        view["generated"] = data.get("generated")
        view["station"] = data.get("station", {})
        view["counts"] = data.get("counts", {})
        view["daily"] = data.get("daily", [])
        view["hours"] = data.get("hours", [])
        view["recent"] = [enrich(r) for r in data.get("recent", [])]
        view["species"] = sorted((enrich(s) for s in data.get("species", [])),
                                 key=lambda s: s.get("last") or "", reverse=True)
        miss = [s for s in view["species"] if not s["shot"]]
        view["missing"] = miss
        n = len(view["species"])
        view["hv"] = {"heard": n, "shot": n - len(miss), "miss": len(miss)}
    return view


@app.route("/birds/live", methods=["GET"])
def birds_live():
    """What the porch mic is hearing, cross-linked to the photo gallery."""
    view = _live_view()
    return render_template(
        "birds_live.html", title="Live from the yard", sound=view,
        has_data=bool(view["recent"]), generated=view["generated"],
        curate=_curate_on(), local=_is_local())


@app.route("/birds/live.json", methods=["GET"])
def birds_live_json():
    """The same rollup as JSON, so the page can refresh itself in place."""
    resp = app.json.response(_live_view())
    resp.cache_control.max_age = 30
    return resp


@app.route("/birds/stats", methods=["GET"])
def birds_stats():
    shots = birds.load_gallery(shuffle=False)
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
    return render_template(
        "stats.html",
        title="Birds by the numbers",
        stats=stats,
        loc_area=loc_area,
        series=birds.stats_series(shots),
        river=birds.activity_river(shots),
        loc_place=loc_place,
        span_months=span_months,
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


@app.route("/curate/override", methods=["POST"])
def curate_override():
    if not _curate_on():
        abort(404)
    data = request.get_json(silent=True) or {}
    post_id = (data.get("id") or "").strip()
    if not post_id:
        abort(400)
    keys = ("species", "location", "date", "images", "image_locations", "image_areas")
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
