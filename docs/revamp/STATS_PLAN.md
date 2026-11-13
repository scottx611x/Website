# /birds/stats: pick a bird, the page answers

> **Status 2026-11-13:** phases 1-3 shipped (c13959a, 0ec8ca6, 2caa622).
> Probes: `statpin`, `statarrive`. Height 7,364 -> 5,867px desktop and
> 8,415 -> 6,353px phone: short of the 4,800 / 5,800 targets, because the
> sections kept as-is (30-row rhythm, map, river) are most of what is left.
> Deviation: on touch the whole row pins (the bar is hidden on phones and
> the name fills the row); the pin chip's name links to the profile there.
> Phase 4 (river palette) not started: show both versions first.

A design brief for a fresh session to implement. Read all of it, then
`docs/revamp/OVERNIGHT.md` (working rules, probes, rejected designs) and
`docs/revamp/LIVE_PLAN.md` (the same recipe, already shipped on Live).

## The page today

Screenshot it first at 1440 and 412 wide (`docs/revamp/probes/run.sh page
/birds/stats out.png 900`, or a full-page capture) and read it as a visitor.

- 7,364px tall on desktop, 8,415px on a phone. Ten sections, each in its own
  bordered card, under four stat cards and a ten-pill jump bar.
- It says the same thing more than once. The header's "95 species" and
  "32,907 recordings" are repeated as cards inside "Heard from the yard".
  "Around the yard" (19 rows) lists the same birds with the same counts as the
  Heard list above it, and its bars are almost all one colour.
- The charts do not know about each other. Find the Barred Owl in "Most
  photographed" and you still have to hunt for it in the year grid, the
  rhythm ridges and the river by eye. The only way to follow one bird is
  `?bird=`, which reloads the page.
- Nothing moves. Every chart is fully drawn before you reach it.
- Weak pieces: the life-list chart reads as a flat line with a label (it has
  been rebuilt three times); the family treemap has unlabelled cells and an
  empty strip under it; "The year, in birds" ends in a stray grey bar that
  repeats "134 species".
- The good pieces, which stay as they are: the life-list photo and ticket,
  the wall of lifers, the year grid, the shooting-days punchcard, the daily
  rhythm ridgeline, the places map, the river.

## Already tried and rejected here

Do not rebuild these under another name.

| Idea | Commit | Verdict |
|---|---|---|
| Dense dashboard mockup (2026-09-25) | not merged | "this isn't great" |
| Ten pills grouped into three acts, with chapter cards | a0ce274, 2b5702a | "Stats edits are trash", reverted |
| The life list as a ledger | 7f6f187 | "wtf this is trash", reverted |
| Scrubbing the life-list chart by date | cf1296d, 84012a0 | unusable: 71% of lifers sit in 8% of the axis |

He has also cut copy from this page twice ("Cut the wordy copy", "Cut the
non-essential copy"). Do not add sentences.

What worked on Live, and is the recipe here: **cut first, add no new section,
then spend the effort on one felt interaction.**

## Direction

**Pick a bird anywhere and every chart on the page answers for that bird.**
The charts are the same charts; they become one instrument instead of ten
posters. Everything else on the page gets quieter or goes.

## Phase 1: cut (no new UI)

One commit. Target: under 4,800px desktop, under 5,800px phone, no number
shown twice.

**Header.** Replace the four stat cards and the date line with one sentence,
in the same style as Live's tally (move `.lv-tally` / `.lv-bar` from
`birds_live.html` into `site.css` as a shared `.tally` and use it on both):

    134 species photographed · 2,064 photos · 95 heard · 32,907 recordings · since Jul 2014

Each number links where its card linked. In `?bird=` / `?family=` focus the
same sentence carries the focus numbers (photos, months active, places,
recordings).

**Section chrome.** Remove the bordered cards. Sections sit on the paper,
separated by a hairline, each opened by its existing Fraunces `h2`. The
subtitle line under each `h2` stays only where it carries a number that is
not elsewhere in the section.

**Jump bar.** Keep it (sticky, scroll-spied; the `top` fix from 65b3a84
stays). It drops to seven links to match the sections below.

**Section by section:**

| Section | Change |
|---|---|
| The life list | Keep photo, ticket, wall. **Delete the chart.** In its place, beside the photo under the ticket, a short year list (see wireframe). |
| The year, in birds | Keep. Delete the stray grey "134 species" bar at the bottom. |
| Shooting days | Keep as is. |
| Most photographed + By family | **One section, "Most photographed"**, with a two-way switch: by species (today's list, top 12) / by family (same row design: name, species count, bar, photo count). The treemap goes. |
| Heard from the yard | Keep the list and the per-day strip. **Delete the four cards** (they repeat the header). Each row's bar becomes the two-mic split bar from "Around the yard". |
| Around the yard | **Delete.** Its one piece of information (which mic hears each bird) now lives in the Heard rows; the mic legend moves there. |
| The daily rhythm | Keep as is. |
| Where I find them | Keep as is. |
| The river | Keep as is (see phase 4 for colour). |

Life list wireframe, desktop (phone stacks: photo, ticket, years, wall):

    +------------------------------------+  +---------------------+
    |                                    |  | NO. 134             |
    |            lifer photo             |  | Merlin              |
    |          (web copy, 3:2)           |  | Sep 7, 2026 Falcons |
    |                                    |  | 2 photos ->         |
    |                                    |  +---------------------+
    |                                    |   2026  ############ 72
    |                                    |   2025  #####        30
    |                                    |   2024  ###          14
    |                                    |   ...   (one row per year)
    +------------------------------------+
    2026  72 species ----------------------------------------------
    [wall of thumbnails, newest first, grouped by year, as today]

The year rows are the crescendo the chart was trying to draw, at a size where
every row can be clicked: a click scrolls the wall (inside the section, not
the page) to that year and selects its first bird. This reuses the year
click that 3bd947d added to the ribbon; nothing about the wall changes.

The photo uses the gallery's web copy (`/birds/images/`), not the thumbnail,
with the thumbnail layered underneath while it loads (same as Live's hero).

## Phase 2: the page answers

The phase that matters. One commit.

**Hover is local, click pins.**

- Hovering a bird in any section highlights it in that section only (as
  today). No other section reacts to hover: reacting off-screen is invisible,
  and reacting on-screen while the pointer travels is noise.
- **Clicking (or tapping) a bird's row, tile, ridge or stream pins it.** The
  page does not scroll and does not reload. A pinned bird is marked in every
  section at once:

| Section | Pinned bird |
|---|---|
| Life list | Its tile is ringed; the photo and ticket switch to it. |
| The year, in birds | Its row is lit and brought into view inside the grid's own scroll area; other rows dim to 35%. |
| Shooting days | Days with that bird keep full ink; other days drop to outlines. |
| Most photographed | Its row is lit. If it is outside the top 12, it is appended as a 13th row with its true rank. |
| Heard from the yard | Its row is lit (appended with its rank if outside the list); if never heard, the section says "not heard from the yard" in the row's place. |
| The daily rhythm | Its ridge at full colour, the rest at 25%. |
| Where I find them | Only its places keep their pins; the top-spots list re-counts for it. |
| The river | Its stream at full colour, the rest at 20%. |

- **The pin lives in the jump bar**: the bird's thumbnail, its name, a link
  to its profile, and a clear button, at the right end of the sticky bar
  (on a phone: a second row of the bar). Escape clears. Clicking the pinned
  bird again clears.
- The URL becomes `#bird=<slug>` (replaceState, no history spam) so a pinned
  view can be shared. `?bird=` keeps working exactly as today as the
  server-rendered deep link; it is not replaced.
- Links stay links: the bird's *name* still goes to its profile. The pin
  target is the rest of the row (bar, avatar, ridge, tile). On the wall, a
  tile click already selects that lifer; it now pins too.

Data: every section already renders from JSON embedded in the page. Add one
`data-slug` per bird element (`slug` filter / `slugify` as on Live) and drive
the pin with a single `setPin(slug)` that toggles classes and calls each
section's existing re-render. Shooting days and places need per-bird data the
page may not embed yet: check `birds.stats_series` and the places payload
first, and add it server-side (with tests in `tests.py`) rather than fetching.

Done when a probe (`docs/revamp/probes/statpin.js`) shows: clicking a bird in
Most photographed marks the same slug in all eight sections; `scrollY` is
unchanged by the click; Escape clears all eight; `#bird=` on load pins the
same way; a tap on a phone viewport does the same; no page errors.

## Phase 3: charts arrive once

Small, one commit, only after phase 2 is solid.

Each chart draws itself the first time it scrolls into view, once, in
400-700ms, then never again (IntersectionObserver, no scroll-jacking, no
parallax):

- tally numbers count up (reuse Live's `countTo`);
- punchcard dots appear in date order, left to right;
- bars grow from zero; year rows in the life list grow top to bottom;
- rhythm ridges rise from their baselines, staggered 15ms a row;
- the river wipes in left to right.

`prefers-reduced-motion`: everything is simply drawn.

## Phase 4: optional, show before/after first

The river is the only thing on the site outside the palette (a full rainbow).
Recolour its streams by family with the five validated series hues plus the
neutral (`--s-forest`, `--s-cardinal`, `--s-jay`, `--s-goldfinch`,
`--s-grackle`, `--s-other`), the same rule as Live's soundtrack. This is a
visible change to a piece he has not complained about: build it behind a
query flag, screenshot both, and let him choose. Do not ship it unasked.

## Must not break

- `?bird=` and `?family=` server-rendered focus, and the shared subnav chip.
- The year grid's filter box and its four sorts; "show all 134 species".
- Shooting days: the whole cell is the tap target (42cb6b6).
- Heard: its sorts (most heard / recently heard) and filters (all /
  photographed / not yet), and the "all 95 species" link.
- The places map (pan, zoom, pin clusters) and the "full map" link.
- The river's "full history" link and its avatar bubbles.
- Curate mode.
- Brand: paper `#f4f1e9`, ink, green; Fraunces, Space Grotesk, JetBrains Mono.

## Things that will bite

- `templates/stats.html` is 1,931 lines with inline CSS and JS; data is built
  in `index.py` `birds_stats()` from `birds.gallery_stats`,
  `birds.stats_series` and `birds.activity_river`. Find every render path
  before adding pin classes, or a sort/filter click will wipe them.
- Stats' header is not the collapsing one (no `data-collapse`); the jump bar
  is the sticky element. Changing section heights under a sticky bar is how
  Live's title flicker happened (fba77d8): after the cut, re-check that
  scroll-spy lights the right link at three depths.
- Jinja templates are cached by the dev server: restart it after template
  edits (`lsof -ti tcp:5055 | xargs kill`, then `make run`). Static files are
  not cached.
- Slugs: use the same rule everywhere (`slug` filter server-side, `slugify`
  client-side). The heard list uses sound names; map them through
  `birds._canon_species` as `_live_view` does.

## How to work

- Local server: `env BIRDS_USE_S3=1 PATH="$PWD/.venv/bin:$PATH" make run` (port 5055).
- **Never open a browser window.** Everything visual goes through
  `docs/revamp/probes/run.sh`; add `statpin.js` beside the others.
- One commit per phase. `make test` before each.
- Shipping: finished and verified phases are committed to `master`, deployed
  with `make deploy` (never a bare `zappa update`) and pushed, without asking.
  Verify the live page after each deploy. Phase 4 is the exception: show it
  first.

## Kickoff prompt

> Read `docs/revamp/STATS_PLAN.md` and `docs/revamp/OVERNIGHT.md` in full,
> then capture `/birds/stats` at 1440 and 412 wide before changing anything.
> Implement phases 1 to 3 in order, one commit each, with the `statpin` probe
> for phase 2. Ship each phase when it is verified (commit, `make deploy`,
> push) and tell me what changed with before/after heights. Do not do phase 4
> without showing me both versions first.
