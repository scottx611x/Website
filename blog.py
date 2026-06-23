"""Markdown blog backend.

Posts are plain Markdown files in ``posts/`` with YAML frontmatter, e.g.::

    ---
    title: First Light
    date: 2026-06-21
    summary: A short teaser shown in the post list.
    cover: backgrounds/heron.jpg   # optional, relative to static/img
    ---

    # Markdown body goes here.

The filename (minus extension) is the URL slug, so
``posts/2026-06-21-first-light.md`` is served at ``/blog/2026-06-21-first-light``.
Add a file, commit, deploy -- that's the whole publishing flow.
"""

import datetime
import os

import frontmatter
import markdown

POSTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "posts")

# Markdown extensions: fenced code blocks, tables, and auto-linked bare URLs.
_MD_EXTENSIONS = ["fenced_code", "tables", "sane_lists"]


def _coerce_date(value):
    """Frontmatter dates may parse as date/datetime or arrive as a string."""
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    if value:
        try:
            return datetime.datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
        except ValueError:
            pass
    return datetime.date.min


def _load(path):
    post = frontmatter.load(path)
    slug = os.path.splitext(os.path.basename(path))[0]
    meta = post.metadata or {}
    return {
        "slug": slug,
        "title": meta.get("title", slug.replace("-", " ").title()),
        "date": _coerce_date(meta.get("date")),
        "summary": meta.get("summary", ""),
        "cover": meta.get("cover"),
        "html": markdown.markdown(post.content, extensions=_MD_EXTENSIONS),
        "raw": post.content,
    }


def list_posts():
    """Return all posts, newest first."""
    if not os.path.isdir(POSTS_DIR):
        return []
    posts = [
        _load(os.path.join(POSTS_DIR, name))
        for name in os.listdir(POSTS_DIR)
        if name.endswith(".md")
    ]
    return sorted(posts, key=lambda p: p["date"], reverse=True)


def get_post(slug):
    """Return a single post by slug, or ``None`` if it doesn't exist."""
    path = os.path.join(POSTS_DIR, "{}.md".format(slug))
    # Guard against path traversal via a crafted slug.
    if os.path.dirname(os.path.abspath(path)) != POSTS_DIR or not os.path.isfile(path):
        return None
    return _load(path)
