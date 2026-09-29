# Overnight run — gallery / site revamp

**Branch:** `nocturne` (off `stats-revamp` @ 5859aaa). **NEVER deploy from here.**
Prod is `master` @ b1af8c9 and must stay that way.

Read this first after any context reset, then `git log --oneline master..HEAD`
to see how far the run got.

## The brief

Scott: "act as a super hip designer... revamp in any way you deem fitting while
keeping my design holistic... make it sick... draw inspiration from awwwards...
have fun, be quirky, go wild... whole site is up for grabs. DO NOT PUSH TO PROD."

Standing constraint from earlier in the session: **never open a browser tab** —
his wife is using the laptop. All visual checks go through the headless probe
(see Tooling).

## What must not break

The field earned its behaviour through a lot of rejected attempts. Do not
re-litigate these:

- Endless pan in any direction, drag anywhere, pinch to resize.
- A species never lands beside itself (round-robin + computed stride).
- Small sets get a FINITE layout, not a wrapping one (< ~1.5 screens of tiles).
- Detail overlay: frames scoped to the current filter, family mode when a
  family is active, close returns you to the same scroll position.
- Curate mode must keep working.
- Brand: warm paper `--paper`, `--ink`, green `--green`, Fraunces (display),
  Space Grotesk (body), JetBrains Mono (mono). Keep it. "Holistic" was the ask.
- `prefers-reduced-motion` respected everywhere.

## Design direction (chosen)

Working title: **Nocturne** — the field as a living plane you fly over.

1. **Shared-element transitions** (View Transitions API) tile → detail, so
   opening a bird is a continuous move rather than a modal appearing.
2. **Depth**: tiles parallax in layers; the layer comes from data (frequency /
   recency), so the depth *means* something.
3. **Semantic zoom**: pinch out past a threshold and the field resolves into
   species clusters; pinch in and it becomes photos again.
4. **Kinetic type**: species names as a typographic layer that reacts to pan.
5. **Cohesion**: home, stats and live inherit the same motion vocabulary.

## Tooling (headless, no tabs)

Probes live in the scratchpad, driven by `playwright-core` + the cached
`chrome-headless-shell`. Pattern:

    SP=<scratchpad>
    SP=$SP node $SP/<probe>.js

Existing probes worth reusing: `sweep2.js` (viewport sweep), `finite.js`
(repetition), `fam.js` (family detail), `combo.js` (search), `deep.js`
(deep links), `menu.js` (view menu).

Local server: `make run` on :5055. Dev static is no-cache (see
`_fresh_static_in_dev`), so CSS edits show up without a restart.

## Log

Append one line per landed change. Newest last.

- setup: branch created, brief written.
- **view transitions**: tile -> detail morphs via `document.startViewTransition`.
  The name lives on the tile for the outgoing snapshot and the stage image for
  the incoming one, swapped inside the callback between captures (two elements
  holding one name is an error). Verified: group animates 520ms with the custom
  easing, root cross-fades 300ms, no stranded `view-transition-name`, works in
  both directions.
- **depth**: `--age` per tile, 0 = newest frame in view, 1 = oldest; drives a
  slight scale/saturation recession so the archive sits further back. Ranked,
  not raw-date-scaled. Pointer lift on hover (CSS only, no per-frame JS).
  Gotcha: AGE is keyed by TILE index, `at()` returns a SEQ position — looking
  up the wrong one gave plausible-but-scrambled depth. Verified 0 order
  mismatches across 70 tiles; 84-103 frames rendered during a 1s drag.
- **semantic zoom**: below 150px tile width the field swaps representation —
  one tile per species (newest frame), height encoding the species' frame
  count (sqrt-scaled), name always-on in Fraunces, tally chip. `setOverview()`
  swaps SEQ between SEQ_PHOTOS/SEQ_SPECIES and reseats. Gotchas: counting SEQ
  occurrences reports 8 for everything (the server caps the round-robin at 8)
  — use `t.n`; and `.bf-count` was already the stage's frame counter, so the
  chip needed its own class (`.bf-tally`).
- **home hero**: the stock fjord is replaced by a wall of Scott's own birds —
  six columns, one frame per species, drifting at prime-ish durations in
  alternating directions, each column holding its list twice and translating
  -50% for a seamless CSS-only loop. Three gotchas, all found by measuring:
  (1) `#bg-effect` lived INSIDE `.content` (z-index:1) while the nav is
  z-index:0, so the wall painted over the nav — base.html now has a
  `page_background` block outside `.content`; (2) the tilt was on the same
  element as `.bg-scrim`, so the scrim's gradients rotated with it and the
  nav band ran off at an angle — tilt moved to `.wall-tilt`; (3) nav ink is
  dark by default and vanished on the dark wall. Nav-strip backdrop went from
  peak luminance 117 to 52.
- **deep links finished**: `#bird/<slug>` and `#family/<slug>` now survive a
  refresh. Two separate causes, both non-obvious: (1) `history.state` SURVIVES
  a reload, so closeOver's "unwind my own entry" saw a stale marker and called
  `history.back()` into the pre-redirect `/birds` — now gated on a
  `pushedHere` flag scoped to this page load; (2) birds.html already had a
  deliberate "a refresh reshuffles" feature whose `location.replace()` dropped
  the fragment, so the two features fought and the reshuffle always won. It
  carries `location.hash` through now — you get both.
