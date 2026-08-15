# Plan: per-frame capture dates

> **Status: implemented + deployed 2026-08-15** (`6fc48d5`). One deviation:
> item 3's multi-date caption fallback resolves to the status quo in both
> branches (one date → all frames; several → frames stay on the shot date),
> so no parser change was made — the store is the only per-frame source.

**Why.** The posting pipeline can now combine several small daily albums into one
batch (`bird-photography-pipeline` commit `d392c93`). Captions get the right date
per *post* automatically (from EXIF), but the website dates every frame of a post
from the caption's first `M-D-YY` (`_capture_date_obj`, birds.py ~2377). A post
that genuinely spans days ("7-20-26 & 7-22-26") mislabels its later frames — sort,
phenology, and calendar all inherit the wrong day. The pipeline UI warns against
mixed-day posts today, so this is a *completeness* upgrade, not a fire.

**Data is already flowing.** As of pipeline commit `5e57ff6`, every record in
`s3://birds-scott-ouellette/birds/post_records.json` carries:

```json
{"caption": "...", "files": [...], "species": [...], "locations": [...],
 "dates": ["7-20-26", "7-20-26", "7-22-26"],   // ← new, aligned with files[]
 "scheduled_at": "...", "recorded_at": "..."}
```

Older records simply lack `dates` — treat missing/empty as "unknown, fall back".

## Changes (birds.py unless noted)

1. **Ingest** — `match_post_records()` (~995). Where matched species land in the
   `image_species` store, also persist dates: new curation store
   `birds/image_dates.json` mapping `post_id -> [ISO date | null, …]`
   (normalize `M-D-YY` → ISO at ingest; `""` → null). Mirror the
   `image_species` pattern exactly: `load_image_dates()` like
   `load_image_species()` (~967), write via `_save_curation`, add the file to
   `_CURATION_S3` (~1408) so it syncs like the other curation files, and keep
   the same never-rewrite semantics (a store entry is written once).

2. **Frame plumbing** — `_pseudo_frame()` (~503) and the frame splitter around
   ~516–536: prefer `image_dates[post_id][i]` for the frame's `_sort` and
   display `date`, falling back to today's `_shot_capture_date(shot)`
   behavior. Also carry an `image_dates` list through the shot-slicing paths
   (the `for key in ("images", "captions", "image_species", …)` loop ~803).

3. **Caption fallback** — extend the caption parser to collect *all*
   `_DATE_RE` matches (finditer). Shot-level date stays "first match" (no
   behavior change); the full list is only a fallback source for per-frame
   dates when a post has no store entry (e.g. pre-`dates[]` records): if the
   caption has exactly one date, all frames get it (status quo); more than
   one, leave unmatched frames on the shot date rather than guessing.

4. **Aggregations** — the phenology/calendar loops that iterate frames
   (~614) should use the per-frame date where the frame is the unit;
   shot-level views keep the shot date. Grep for `_shot_capture_date`
   call sites and decide per-site (most are fine as-is).

5. **Overrides precedence** — unchanged: manual curate `capture_date`
   override (~1142) stays authoritative above the store. Per-frame manual
   date overrides are out of scope (add later only if a real mislabel shows
   up that the store can't fix).

## Tests (tests.py)

- record with `dates[]` → store populated, ISO-normalized, alignment with
  `files[]` preserved; record without `dates[]` → no store entry, identical
  behavior to today.
- `_pseudo_frame` uses the store date for `_sort`/display; falls back to
  shot date when store/entry missing.
- mixed-date caption: shot date is still the first match.

## Rollout

No migration: the store starts empty, old records lack `dates`, so behavior
is byte-identical until a combined-batch post is actually synced. Deploy via
`make deploy` as usual. Estimated effort: 2–4 focused hours.
