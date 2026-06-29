import json
import os
import random

from flask import Flask, abort, redirect, render_template, request

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


def _home_context():
    shots = birds.load_gallery()
    return {
        "title": TITLE,
        "effect": random.choice(EFFECTS),
        "background_image": random.choice(load_backgrounds()),
        "posts": blog.list_posts()[:3],
        "shots": shots,
        "projects": load_projects(),
        "species": birds.ticker_species(shots),
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
    return render_template("home.html", **context)


@app.route("/blog", methods=["GET"])
def blog_index():
    return render_template("blog_list.html", title="Blog", posts=blog.list_posts())


@app.route("/blog/<slug>", methods=["GET"])
def blog_post(slug):
    post = blog.get_post(slug)
    if post is None:
        abort(404)
    return render_template("blog_post.html", title=post["title"], post=post)


@app.route("/photography", methods=["GET"])
def photography():
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
    resp = redirect(request.referrer or "/birds")
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
    media = "video" if request.args.get("media") == "video" else ""
    # Curate-only review/rating facets.
    review = (request.args.get("review") or "") if curate else ""
    if review not in ("reclassified", "reid", "hidden"):
        review = ""
    rating = (request.args.get("rating") or "") if curate else ""
    if rating not in ("unrated", "1", "2", "3", "4", "5"):
        rating = ""
    reid_posts = {k.rsplit("-", 1)[0] for k in birds.reid_keys()} if curate else set()
    hidden_posts = ({pid for pid, v in birds.load_overrides().items() if v.get("exclude_images")}
                    if curate else set())
    review_counts = {
        "reclassified": sum(1 for s in all_shots if s.get("reclassified")),
        "reid": sum(1 for s in all_shots if s.get("id") in reid_posts),
        "hidden": sum(1 for s in all_shots if s.get("id") in hidden_posts),
    } if curate else {}
    if review == "reclassified":
        shots = [s for s in all_shots if s.get("reclassified")]
    elif review == "reid":
        shots = [s for s in all_shots if s.get("id") in reid_posts]
    elif review == "hidden":
        shots = [s for s in all_shots if s.get("id") in hidden_posts]
    elif bird or family or area or media or rating:
        shots = birds.images_filtered(all_shots, bird, family, area, out_of_area,
                                      media=media, rating=rating)
    else:
        shots = all_shots
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
        active_review=review,
        active_rating=rating,
        review_counts=review_counts,
        has_videos=birds.has_videos(all_shots),
        bird_family=bird_family,
        curate=curate,
        local=_is_local(),
        reid_queued=sorted(birds.reid_keys()) if curate else [],
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


@app.route("/curate/rate", methods=["POST"])
def curate_rate():
    if not _curate_on():
        abort(404)
    data = request.get_json(silent=True) or {}
    post_id = (data.get("id") or "").strip()
    if not post_id or data.get("index") is None:
        abort(400)
    rating = birds.set_rating(post_id, data["index"], data.get("rating", 0))
    return {"ok": True, "rating": rating}


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
    )


def load_projects():
    """Curated things I've built, from a static manifest. (See projects.json.)"""
    manifest = os.path.join(app.static_folder, "projects.json")
    try:
        with open(manifest) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return []


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
