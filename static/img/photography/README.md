# Photography gallery (`/photography`)

General, non-bird photography (wildlife, landscapes, macro, …), published from raw
files rather than Instagram. Images live on **S3** — not in this repo — so the
Lambda deploy stays small; only this small `manifest.json` is committed (it's an
S3-backed curation store, like the birds overrides).

Each photo carries: `title`, optional `species`, optional `location`, `date`
(auto from EXIF), and `tags` (the page is one stream filterable by tag).

## Adding photos

1. Drop images into `wildlife_incoming/<tag>/` at the repo root — a subfolder
   name seeds a starting tag (e.g. `Mammals/` → `mammals`), loose files start
   untagged. Name each file for its subject (`Red Fox.jpg`) → the title.
2. `make wildlife` — re-encodes each photo **EXIF-stripped** (no leaked GPS),
   resizes, uploads full + thumbnail to `s3://…/wildlife/`, and appends a stub
   entry here (title + date + seed tag). Idempotent; never clobbers your edits.
3. `make push-curations` seeds the manifest to S3, then deploy.

## Editing metadata (species / location / tags)

On the live site, unlock curate (the same secret cookie as the birds gallery) and
the `/photography` cards show inline fields — set title, species, location, date,
and tags per photo; edits save straight to S3. Run `make pull-curations` to fold
those live edits back into this committed copy. (Or just hand-edit this JSON.)

## Manifest entry

```json
{
  "id": "9f1c2a…",                 // content hash (do not edit)
  "image": "https://…/wildlife/images/9f1c2a….jpg",
  "thumb": "https://…/wildlife/thumbs/9f1c2a….jpg",
  "title": "Red Fox at dawn",
  "species": "Red Fox",            // optional
  "location": "Weir Hill",         // optional
  "date": "2026-06-14",
  "tags": ["wildlife", "mammal"]
}
```

One-time: `wildlife/images/*` and `wildlife/thumbs/*` must be public-read in the
`birds-scott-ouellette` bucket policy (same scoping as the birds media).
