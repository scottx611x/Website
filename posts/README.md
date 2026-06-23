# Posts

Each `*.md` file here is one blog post. The filename (without `.md`) is the URL
slug, so `2026-06-21-hello-again.md` is served at `/blog/2026-06-21-hello-again`.

## Frontmatter

```yaml
---
title: Post title
date: 2026-06-21          # YYYY-MM-DD, used for ordering (newest first)
summary: One-line teaser shown in the post list.   # optional
cover: backgrounds/heron.jpg   # optional hero image, path relative to static/img
---
```

Everything below the closing `---` is the post body, written in Markdown
(fenced code blocks, tables, and lists are supported).

## Publishing

1. Add a new `.md` file here.
2. Commit it.
3. `zappa update production`.

That's it — no database, no admin login.
