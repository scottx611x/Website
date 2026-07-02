---
title: How this blog works
date: 2026-06-14
summary: Writing a post is one Markdown file and a git commit.
---

No CMS, no database, no login screen. A post is a single Markdown file in the
`posts/` directory. To publish:

1. Create `posts/YYYY-MM-DD-some-slug.md`.
2. Add a little frontmatter at the top:

   ```yaml
   ---
   title: Your title
   date: 2026-06-21
   summary: One line shown in the post list.
   cover: backgrounds/heron.jpg   # optional hero image, relative to static/img
   ---
   ```

3. Write the body in Markdown below the frontmatter.
4. Commit and deploy (`zappa update production`).

The filename becomes the URL — this post lives at
`/blog/2026-06-14-how-this-blog-works`. That's the whole system.
