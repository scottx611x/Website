# scott-ouellette.com

[![CI](https://github.com/scottx611x/Website/actions/workflows/ci.yml/badge.svg)](https://github.com/scottx611x/Website/actions/workflows/ci.yml)

Personal site: a blog, photography, an auto-updating bird gallery, and the
original animated-background site preserved in an archive. Flask, deployed to AWS
Lambda with [Zappa](https://github.com/zappa/Zappa).

## Structure

| Path | What |
|------|------|
| `/` | Home, rendered over a live rotating animated background (collision / tilt-shift / voronoi) |
| `/blog`, `/blog/<slug>` | Markdown blog — posts live in `posts/` (see `posts/README.md`) |
| `/birds` | Top bird shots from [@birdsofnorthandover](https://www.instagram.com/birdsofnorthandover/), ranked by likes |
| `/photography` | Other curated galleries (see `static/img/photography/README.md`) |
| `/projects` | Highlighted builds + link to GitHub (see `static/PROJECTS.md`) |
| `/archive`, `/archive/<effect>` | The original site, untouched |

Also served at **`birds.scott-ouellette.com`** via host-based routing.

### Key files

- `index.py` — routes, swappable backgrounds, birds-subdomain routing
- `blog.py` — Markdown + frontmatter post loading
- `birds.py` — Instagram sync + gallery manifest (`birds/README.md` for setup)
- `templates/` — `base.html` + per-page templates; `templates/archive/` is the old site
- `static/css/site.css` — theme

## Local development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest tests.py          # tests
python -m flask --app index run    # http://127.0.0.1:5000
```

The bird gallery reads the committed `birds/manifest.json` fallback locally, so no
Instagram credentials are needed to run.

## Adding content

- **Blog post:** add a Markdown file to `posts/` and commit (`posts/README.md`).
- **Background photo:** drop it in `static/img/backgrounds/` and list it in that
  folder's `manifest.json`.
- **Photography:** add to `static/img/photography/` + its `manifest.json`.
- **Project highlight:** edit `static/projects.json`.

## Deploy

```bash
zappa update production
# one-time, for the birds subdomain:
zappa certify production   # + a Route 53 record for birds.scott-ouellette.com
```

The bird gallery refreshes daily via the scheduled `birds.instagram_sync` event
in `zappa_settings.json` (requires `INSTAGRAM_ACCESS_TOKEN`; see `birds/README.md`).
