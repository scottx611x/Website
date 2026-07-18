# Photography galleries (`/photography` → "Wildlife")

Non-bird photography (mammals, reptiles, insects, macro, landscapes). Unlike the
birds gallery (which syncs from Instagram), these are published straight from raw
files, and the images live on **S3** — not in this repo — so the Lambda deploy
stays small. Only this small `manifest.json` is committed.

## Adding photos

1. Drop images into `wildlife_incoming/<Category>/` at the repo root — the folder
   name becomes the on-page category (e.g. `Mammals`, `Reptiles`, `Insects`).
   Name each file for its subject (`Red Fox.jpg`, `red-fox-ipswich.jpg`); that
   becomes the caption (editable later).
2. Run `make wildlife` (or `python wildlife.py <dir>`). It re-encodes each photo
   **with EXIF stripped** (no leaked GPS), resizes it, uploads a full + thumbnail
   copy to `s3://birds-scott-ouellette/wildlife/…`, and appends an entry here.
3. Review this `manifest.json` (tweak any `title`/`category`), commit it, deploy.

Re-runs are idempotent (same file = same content hash → skipped), and they never
overwrite a manifest entry you've hand-edited.

## Manifest entry

```json
{
  "id": "9f1c2a…",                 // content hash (do not edit)
  "image": "https://…/wildlife/images/9f1c2a….jpg",
  "thumb": "https://…/wildlife/thumbs/9f1c2a….jpg",
  "title": "Red Fox",              // caption (edit freely)
  "category": "Mammals",           // section heading (edit freely)
  "date": "2026-06-14",
  "w": 2048, "h": 1365
}
```

## One-time setup

The `wildlife/images/*` and `wildlife/thumbs/*` prefixes must be public-read in the
`birds-scott-ouellette` bucket policy (same scoping as the birds media). See
`RELEASE.md`.
