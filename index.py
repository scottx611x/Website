import json
import os
import random

from flask import Flask, abort, make_response, redirect, render_template, request

import birds
import blog

app = Flask(__name__)
app.debug = False

TITLE = "Scott Ouellette"

# The original animated backgrounds, kept alive as the home-page backdrop.
EFFECTS = ["collision", "tilt-shift", "voronoi"]

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


FACTS_FILE = os.path.join(app.static_folder, "facts.json")


def load_facts():
    """Rotating footer facts about me (curate them in static/facts.json or the
    local curate UI on the home page)."""
    try:
        with open(FACTS_FILE) as fh:
            facts = json.load(fh)
        if facts:
            return facts
    except (OSError, ValueError):
        pass
    return ["builds things"]


@app.context_processor
def _inject_facts():
    # The footer (in base.html) renders on every page, so facts must be available
    # to all templates, not just the home context.
    return {"facts": load_facts()}


TAGLINES_FILE = os.path.join(app.static_folder, "taglines.json")


def load_taglines():
    """Rotating hero taglines that complete 'Software Infrastructure Engineer that …'
    (curate them in static/taglines.json or the local curate UI on the home page)."""
    try:
        with open(TAGLINES_FILE) as fh:
            lines = json.load(fh)
        if lines:
            return lines
    except (OSError, ValueError):
        pass
    return ["builds things"]


# Pages temporarily hidden everywhere (nav, home page, direct URL). To bring one
# back, drop it from this set.
HIDDEN_PAGES = {"blog", "photography"}


# tilt-shift is a subtle image parallax with no animated overlay, so it's opt-in
# only (via the switcher); a fresh visit always gets a visibly animated effect.
ANIMATED_EFFECTS = ["collision", "voronoi"]


def _pick_effect():
    """The effect you last chose (cookie) sticks; first-timers get a random one."""
    chosen = request.cookies.get("effect")
    return chosen if chosen in EFFECTS else random.choice(ANIMATED_EFFECTS)


def _home_context():
    shots = birds.load_gallery()
    stats = birds.gallery_stats(shots)
    return {
        "title": TITLE,
        "bird_stats": {
            "species": stats["species"],
            "photos": stats["photos"] + stats["videos"],
            "places": len(birds.map_points(shots)),
        },
        "effect": _pick_effect(),
        "background_image": random.choice(load_backgrounds()),
        "posts": [] if "blog" in HIDDEN_PAGES else blog.list_posts()[:3],
        "shots": shots,
        "projects": load_projects(),
        "taglines": load_taglines(),
        "species": birds.ticker_species(shots),
        "curate": _curate_on(),
        "local": _is_local(),
    }


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


@app.route("/effects/<name>", methods=["GET"])
def effect(name):
    if name not in EFFECTS:
        abort(404)
    context = _home_context()
    context["effect"] = name
    resp = make_response(render_template("home.html", **context))
    resp.set_cookie("effect", name, max_age=31536000, samesite="Lax")
    return resp


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
    return render_template(
        "photography.html", title="Photography", galleries=load_photography()
    )


# Curation mode (click-to-hide X buttons, editable species, ratings, re-ID flags)
# is only ever available when serving locally, so production never exposes edit
# controls. Locally it's a runtime toggle (cookie), defaulting to BIRDS_CURATE.
def _is_local():
    if os.environ.get("BIRDS_LOCAL") == "1":
        return True
    host = (request.host or "").rsplit(":", 1)[0]
    return host in ("127.0.0.1", "localhost", "0.0.0.0") or host.endswith(".local")


def _curate_on():
    if not _is_local():
        return False
    cookie = request.cookies.get("curate")
    if cookie is not None:
        return cookie == "1"
    return os.environ.get("BIRDS_CURATE") == "1"


@app.route("/curate/toggle")
def curate_toggle():
    if not _is_local():
        abort(404)
    # Return to exactly where you were (preserving filters), via an explicit ?next=
    # rather than the flaky Referer header.
    nxt = request.args.get("next") or request.referrer or "/birds"
    if not nxt.startswith("/"):  # only ever redirect within the site
        nxt = "/birds"
    resp = redirect(nxt)
    resp.set_cookie("curate", "0" if _curate_on() else "1", max_age=31536000, samesite="Lax")
    return resp


@app.route("/birds", methods=["GET"])
def birds_gallery():
    curate = _curate_on()
    all_shots = birds.load_gallery(shuffle=not curate)
    groups = birds.species_groups(all_shots)
    out_of_area = birds.out_of_area_species(all_shots)
    bird = birds.resolve_species(request.args.get("bird") or "", groups)
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
    if sort not in ("recent", "oldest"):
        sort = ""
    # Location filter (from a sightings-map pin): resolves against locations.json.
    loc_q = (request.args.get("loc") or "").strip().lower()
    place = next((p for p in birds.load_locations()
                  if p["name"].lower() == loc_q), None) if loc_q else None
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
        shots = birds.images_at_place(all_shots, place)
    elif bird or family or area or media:
        shots = birds.images_filtered(all_shots, bird, family, area, out_of_area,
                                      media=media)
    elif curate:
        shots = all_shots  # curate default: whole posts (for post-level editing)
    elif start_tokens:
        shots = birds.start_ordered(all_shots, start_tokens)  # home-preview lead-in
    else:
        shots = birds.all_photos_shuffled(all_shots)  # plain random order
    # Chronological ordering applies to any frame view (default or filtered),
    # overriding the random/lead-in order; curate whole-post views are left alone.
    if sort and not curate:
        shots = birds.sort_frames(shots, sort)
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
    if bird:
        for fam, sp in groups:
            if any(name == bird for name, _ in sp):
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
        active_family=family,
        active_area=area,
        active_media=media,
        active_sort=sort,
        active_loc=place["name"] if place else "",
        active_review=review,
        review_counts=review_counts,
        media_n=dict(zip(("photos", "videos"),
                         birds.media_counts(all_shots, bird, family, area, out_of_area))),
        has_videos=birds.has_videos(all_shots),
        bird_family=bird_family,
        curate=curate,
        local=_is_local(),
        reid_queued=sorted(birds.reid_keys()) if curate else [],
    )


@app.route("/birds/map", methods=["GET"])
def birds_map():
    shots = birds.load_gallery(shuffle=False)
    points = birds.map_points(shots)
    return render_template(
        "map.html",
        title="Bird sightings map",
        points=points,
        mapped=sum(p["count"] for p in points),
        local=_is_local(),
        curate=_curate_on(),
    )


@app.route("/birds/stats", methods=["GET"])
def birds_stats():
    shots = birds.load_gallery(shuffle=False)
    stats = birds.gallery_stats(shots)
    span_months = 0
    if stats["first"] and stats["last"]:
        span_months = ((stats["last"].year - stats["first"].year) * 12
                       + stats["last"].month - stats["first"].month + 1)
    return render_template(
        "stats.html",
        title="Birds by the numbers",
        stats=stats,
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
    keys = ("species", "location", "date", "images", "image_locations")
    fields = {k: data[k] for k in keys if k in data}
    shot = birds.set_override(post_id, fields)
    return {"ok": True, "ambiguous": bool(shot and shot.get("ambiguous"))}


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


PROJECTS_FILE = os.path.join(app.static_folder, "projects.json")


def load_projects():
    """Curated things I've built, from a static manifest. (See projects.json.)"""
    try:
        with open(PROJECTS_FILE) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return []


@app.route("/curate/projects", methods=["POST"])
def curate_projects():
    """Save the reordered/edited project list (local curate only)."""
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
    birds._atomic_write_json(PROJECTS_FILE, clean)
    return {"ok": True, "count": len(clean)}


@app.route("/curate/taglines", methods=["POST"])
def curate_taglines():
    """Save the reordered/edited hero taglines (local curate only)."""
    if not _curate_on():
        abort(404)
    data = request.get_json(silent=True) or {}
    incoming = data.get("taglines")
    if not isinstance(incoming, list):
        abort(400)
    clean = [s.strip() for s in incoming if isinstance(s, str) and s.strip()]
    birds._atomic_write_json(TAGLINES_FILE, clean)
    return {"ok": True, "count": len(clean)}


@app.route("/curate/facts", methods=["POST"])
def curate_facts():
    """Save the reordered/edited footer facts (local curate only)."""
    if not _curate_on():
        abort(404)
    data = request.get_json(silent=True) or {}
    incoming = data.get("facts")
    if not isinstance(incoming, list):
        abort(400)
    clean = [s.strip() for s in incoming if isinstance(s, str) and s.strip()]
    birds._atomic_write_json(FACTS_FILE, clean)
    return {"ok": True, "count": len(clean)}


def load_photography():
    """Curated, non-bird galleries grouped by category from a static manifest."""
    manifest = os.path.join(app.static_folder, "img", "photography", "manifest.json")
    try:
        with open(manifest) as fh:
            items = json.load(fh)
    except (OSError, ValueError):
        return []
    galleries = {}
    for item in items:
        galleries.setdefault(item.get("category", "Other"), []).append(item)
    return galleries


# ---------------------------------------------------------------------------
# Archive (the original site, preserved)
# ---------------------------------------------------------------------------
ARCHIVE_CONTEXT = {"title": "Scott's Website (archive)", "background_image": "fall.jpg"}


@app.route("/archive", methods=["GET"])
def archive():
    template = "archive/{}.html".format(random.choice(EFFECTS))
    return render_template(template, **ARCHIVE_CONTEXT)


@app.route("/archive/<effect>", methods=["GET"])
def archive_effect(effect):
    if effect not in EFFECTS:
        abort(404)
    return render_template("archive/{}.html".format(effect), **ARCHIVE_CONTEXT)


if __name__ == "__main__":
    app.run(debug=True)
