# Photography galleries

Curated, non-bird photography for `/photography`. Add image files to this folder
and list them in `manifest.json`. Entries are grouped on the page by `category`.

```json
[
  { "image": "mountains.jpg", "title": "Franconia Ridge", "category": "Landscapes", "date": "2026-05-01" },
  { "image": "dew.jpg",       "title": "Morning dew",      "category": "Macro",      "date": "2026-04-12" }
]
```

- `image` — filename in this folder (`static/img/photography/`)
- `title` — caption shown under the photo (optional)
- `category` — section heading; photos with the same category are grouped
- `date` — optional, for your own reference
