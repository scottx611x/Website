# Projects manifest (`projects.json`)

Hand-picked highlights shown on `/projects`, above the link to your full GitHub
profile. Add entries like:

```json
[
  {
    "name": "Birds of North Andover",
    "url": "https://github.com/scottx611x/Website",
    "tech": "Flask · Zappa · Instagram API",
    "description": "This site, plus the auto-updating bird gallery."
  }
]
```

- `name` — project title
- `url` — link (GitHub repo, live demo, etc.)
- `tech` — short stack line (optional)
- `description` — one or two sentences (optional)

Future enhancement: auto-populate from the GitHub API (pinned/most-starred repos)
the same way the bird gallery pulls from Instagram — see `../birds.py` for the
pattern.
