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


# Curation mode (click-to-hide X buttons) is enabled locally with BIRDS_CURATE=1.
# It's off in production so the public gallery has no edit controls.
CURATE = os.environ.get("BIRDS_CURATE") == "1"


@app.route("/birds", methods=["GET"])
def birds_gallery():
    return render_template(
        "birds.html",
        title="Birds of North Andover",
        shots=birds.load_gallery(shuffle=not CURATE),
        curate=CURATE,
    )


@app.route("/curate/exclude", methods=["POST"])
def curate_exclude():
    if not CURATE:
        abort(404)
    post_id = (request.get_json(silent=True) or {}).get("id")
    if not post_id:
        abort(400)
    birds.add_exclusion(post_id)
    return {"ok": True, "excluded": len(birds.load_excluded())}


@app.route("/curate/override", methods=["POST"])
def curate_override():
    if not CURATE:
        abort(404)
    data = request.get_json(silent=True) or {}
    post_id = (data.get("id") or "").strip()
    if not post_id:
        abort(400)
    fields = {k: data[k] for k in ("species", "location", "date") if k in data}
    shot = birds.set_override(post_id, fields)
    return {"ok": True, "ambiguous": bool(shot and shot.get("ambiguous"))}


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
