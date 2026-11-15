# Bird detail views: open fast, even for the big birds

> **Status 2026-11-15: phases 1-4 shipped** (f95c509, 2f219f6, cd434df).
> Production, phone profile: Barred Owl JSON 4.6 s -> 0.2 s warm (1.4 s right
> after a deploy); overlay photo 6.1 s -> 1.0-2.6 s (first paint ~20 ms from a
> tile); strip 57-138 thumbs -> 18-19; species page 5.8 MB / 4.9 s -> 1.1 MB /
> 2.0 s. Differences from the plan: CloudFront here is API Gateway's edge, which
> never caches, so caching is the in-process memo (keyed on manifest ETag +
> curation stamp) plus the browser; micros live at `birds/thumbs/micro/` so the
> bucket's public allow-list already covers them; the strip's thumb flood was a
> smooth scroll sweeping to the opened frame, not lazy-loading alone; the
> species page's weight was `upgradeThumbs` in base.html swapping phone cards to
> 1440px. Micro backfill run 2026-11-15 (2,139 objects, 12.7 MB): strip now
> 83-127 KB per open, full photo ~1.0-1.1 s for both big birds.

A brief for a fresh session to implement. Read all of it, then
`docs/revamp/OVERNIGHT.md` (working rules, probes). He said: "red-tailed hawk
and barred owl are so friggin slow". This plan is measurement-first: every
phase has a number to hit and a probe that proves it.

## The two views

1. **The gallery's detail overlay**: tap a tile in `/birds` (or open
   `/birds#bird/barred-owl`). `openSpecies()` in `templates/_field.html`
   (about line 2152) fetches `/birds/species/<slug>.json`, then `fill()` builds
   the filmstrip and `showFrame()` loads the stage photo. **This is the one
   that hurts.**
2. **The species page** `/birds/species/<slug>`: server-rendered, about 15
   photos.

## Measured on production (2026-11-15, phone 412px, DPR 2.6, 12 Mbps / 60 ms)

Overlay, from the hash change:

| Bird | frames | JSON arrives | stage photo shown | strip thumbs | strip bytes |
|---|---|---|---|---|---|
| Barred Owl | 213 | 5.1 s | 6.1 s | 57 | 3.2 MB |
| Red-tailed Hawk | ~180 | 3.2 s | 3.7 s | **138** | **5.1 MB** |
| Blue Jay | small | 2.5 s | 4.3 s | 30 | 1.5 MB |

`curl` of the JSON alone: Barred Owl 5.6 s, Red-tailed Hawk 3.3 s, Blue Jay
1.0 s, all `X-Cache: Miss from cloudfront`. It is only 13 KB gzipped. **The
time is spent on the server, and it grows with the number of frames.**

Species page: 4.3-7.3 s to `load`, 4-7 MB, almost all of it the 1440px web
copies (400-800 KB each) drawn at 730-940 device px. One 510 KB spectrogram
PNG.

## Where the time goes (profiled locally, `cProfile` on the JSON route)

1. **A new boto3 client per frame.** `birds.original_url()` (birds.py, about
   line 2969) calls `boto3.client("s3")` for every frame to presign its
   full-size original. Barred Owl + Red-tailed Hawk = 377 client constructions
   = 2.1 s of a 3.4 s profile locally; slower on Lambda. The signature itself
   costs well under a millisecond with a reused client.
2. **60-second memo on everything.** `birds._MEMO_TTL = 60`. Each expiry
   re-reads S3: `_load_gallery_uncached` 1.45 s, `species_index()` 1.44 s,
   `species_profile()` 1.46 s cold vs 0.23 s warm. A low-traffic site is
   almost always cold, so most visitors pay several seconds before the first
   byte.
3. **The JSON cannot be cached anywhere.** Each frame carries a presigned URL
   minted per request, so CloudFront and the browser can't reuse a response
   (it says `max-age=300` but every response differs, and the edge misses).
4. **Strip thumbnails are 5-7x too big.** `birds/thumbs/` are 400px, ~80 KB,
   drawn as 58px squares (~150 device px). And the paging (`growStrip(24)` +
   an IntersectionObserver with `rootMargin: 300px`) did not hold on Red-tailed
   Hawk: 138 thumbs loaded right after opening. Native `loading="lazy"`
   inside a horizontal scroller plus the observer chain-loading is the likely
   cause; confirm before fixing.
5. **Nothing paints until the JSON lands** when the overlay is opened by
   link (`#bird/<slug>`), because the stage photo comes from the JSON's
   frames. From a tile it shows the tile's thumb first (good).

Not a cause: the 16-24 MP originals. They load only when the loupe is used
(`hd()`, about line 3088), and the last three are cached. Leave them alone.

## Phase 1: the server answers in under 300 ms (one commit, biggest win)

- **Reuse one S3 client.** A module-level `_s3()` in `birds.py` that builds
  the client once (lazily; boto3 clients are thread-safe) and use it in
  `original_url` and the 20-odd other `boto3.client("s3")` call sites. Keep
  `ssm` separate the same way.
- **Stop signing in the JSON.** Replace each frame's `orig` with a stable
  path: new route `GET /birds/original/<post>-<idx>.jpg` that 302-redirects to
  a freshly presigned URL (`Cache-Control: private, max-age=300` on the
  redirect). The loupe's `hd()` just loads that path; `<img>` follows the
  redirect, no CORS needed. Check `hd()` aspect logic and `paintOriginal`
  still work, plus the sequence-mode copy in `fill()` that copies `orig` onto
  grid frames. The redirect must refuse keys that are not under
  `birds/originals/` and frames that are hidden (unless curating).
- **Now the JSON is cacheable.** For readers (no curate cookie): memoise the
  trimmed frames per species keyed by the gallery's generation, and send
  `Cache-Control: public, max-age=300, stale-while-revalidate=86400`.
  **Curate responses must never be cached** (they include hidden frames):
  `private, no-store` when `_curate_on()`. Check whether CloudFront's cache
  policy forwards the `curate` cookie before relying on the edge; if it does
  not, keep edge caching off (browser caching only) and note it.
- **Longer memo, explicit invalidation.** Raise the gallery/species memo
  from 60 s to something like 15 min, and bust it on every curate write
  (hide, star, re-id, capture date). Find every writer: grep for the S3 put
  calls in `birds.py`. Alternatively keep 60 s but revalidate cheaply with an
  S3 `head_object` ETag check instead of a full re-read. Pick one, test it.

Target: `curl` of `/birds/species/barred-owl.json` under **300 ms** warm and
under **1.5 s** right after a deploy, measured 5 times in a row.

Tests (`tests.py`): `original_url` builds the client once across many calls
(mock `boto3.client`); the redirect route rejects a key outside
`birds/originals/` and a hidden frame; reader JSON has no `X-Amz-Signature`
and has the public Cache-Control; curate JSON is `no-store`.

## Phase 2: paint before the data (one commit)

- **Prefetch on intent.** Start the JSON fetch on `pointerdown` /
  `touchstart` / `mouseenter` (150 ms dwell) of a gallery tile, keyed by slug,
  and let `openSpecies` reuse the in-flight promise. Free 100-300 ms per open.
- **Link opens paint at once.** For `#bird/<slug>` with no tile clicked, find
  that species' tile in the DOM (`data-species-slug`) or the species pool the
  page already embeds, and put its thumb on the stage immediately, exactly
  like a tile click.
- **Preload the next frame's web copy** once the current one is in (one
  ahead, both directions after the first swipe), so paging is instant.

Target: stage shows a picture within **300 ms** of the tap, and the full
web copy within **1.5 s** on the 12 Mbps / 60 ms profile, for Barred Owl.

## Phase 3: a filmstrip that costs what it shows (one commit, plus a backfill)

- **Micro thumbnails.** A new `birds/micro/<post>-<idx>.jpg` at 160px
  (quality ~70, expect 5-10 KB). Generate them wherever thumbs are generated
  (find the pipeline's thumb step, including the uploader in `wildlife.py` /
  `tools/`), and add a backfill tool `tools/backfill_micro.py` with a dry-run
  default. **Writing ~2,000 new objects to the bucket is an S3 change: show
  him the dry run's count and total size and get a yes before running it.**
  The strip falls back to the 400px thumb when a micro is missing
  (`onerror`), so the page ships before the backfill finishes.
- **Fix the paging.** Find why Red-tailed Hawk loaded 138 thumbs. Then load
  exactly what is visible plus one strip-width ahead: drop native
  `loading="lazy"` in the strip and set `src` from the observer, or keep lazy
  and stop the observer chain. Keep the "grow as you scroll" behaviour and
  `syncStrip` jumping to a far frame.

Target: opening Barred Owl downloads **under 400 KB** of strip thumbnails;
scrolling the whole strip stays under 2 MB.

## Phase 4: the species page (one commit)

- Serve a right-sized web copy: `srcset` with the 400px thumb and the 1440px
  web copy (and the micro for anything 100px or smaller), with `sizes` matching
  the grid. If a 960px variant would help (phones at DPR 2-3 draw about
  1,000px), add it to the Phase 3 backfill rather than a second pass; same
  approval rule.
- Everything below the first screen is `loading="lazy"` with real
  `width`/`height` so nothing shifts.
- The 510 KB spectrogram: serve it as JPEG or WebP at display size, or load
  it lazily below the fold. It comes from the sound station
  (`clips/*_v3.png`); do not change the station, just how this page uses it.

Target: species page **under 1.5 MB** and `load` under **2.5 s** on the
phone profile, for both big birds.

## Must not break

- The loupe and its full-resolution swap (`hd()`, ocrop crops, the 3-entry
  cache), including sequence mode's copy of `orig` onto grid frames.
- Curate: hidden frames visible and flagged to the curator only; star and
  re-id queue state per frame; curate responses never cached by anyone.
- Scoped strips ("N of M frames match this view"), family mode, video frames.
- `#bird/<slug>` addresses, Back closing the overlay, the "N of M" stepper.
- Signed originals stay private: the bucket policy is not loosened, and the
  redirect route signs per request.

## Probe

`docs/revamp/probes/detailspeed.js` is the script that produced the table
above; extend it as needed: phone profile with CDP throttling (12 Mbps,
60 ms), opens `#bird/barred-owl`, `#bird/red-tailed-hawk`, `#bird/blue-jay`
from `/birds` and prints JSON time, first paint on the stage, full photo time,
strip thumb count and bytes. Run it against production before and after
each phase (`PROBE_SERVER=https://www.scott-ouellette.com`) and put both
tables in the hand-off.

## How to work

- Local server: `env BIRDS_USE_S3=1 PATH="$PWD/.venv/bin:$PATH" make run`
  (port 5055); restart after template edits.
- Never open a browser window; probes go through `docs/revamp/probes/run.sh`.
- One commit per phase, `make test` first. Ship each verified phase:
  commit to master, `make deploy` (never a bare `zappa update`), push.
- Exceptions that need his yes first: the micro/960px backfill (bucket
  writes), and any CloudFront or bucket policy change (infra lives in
  `~/infra/website`, applied with `tofu`).

## Kickoff prompt

> Read `docs/revamp/DETAIL_SPEED_PLAN.md` in full. Run the `detailspeed`
> probe and record the production baseline first. Do phase 1, ship it, and
> show me before/after numbers. Then phases 2 to 4 in order, one commit and
> one deploy each. Ask me before running any bucket backfill or touching
> CloudFront.
