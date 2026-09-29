# Overnight run — gallery / site revamp

**If you are a fresh context: read this whole file, then run**
`git log --oneline master..HEAD` **to see how far the run got.**

- **Branch:** `nocturne`, off `stats-revamp` @ 5859aaa.
- **NEVER deploy from this branch.** Prod is `master` (@ b1af8c9) and Scott
  said explicitly: DO NOT PUSH ANYTHING TO PROD.
- **Never open a browser tab.** Standing constraint — someone else is using
  the machine. Everything visual goes through the headless probes below.

## The brief

> "act as a super hip designer... revamp in any way you deem fitting while
> keeping my design holistic... make it sick... draw inspiration from
> awwwards... have fun, be quirky, go wild... whole site is up for grabs.
> DO NOT PUSH TO PROD."

Rules he set: don't stop until out of tokens; craft the run so it recovers
from context resets (that is what this file and `probes/` are for); whole site
is fair game.

## How to work

```bash
make run                              # local server on :5055
docs/revamp/probes/run.sh             # list probes
docs/revamp/probes/run.sh sweep2      # run one
```

`run.sh` installs `playwright-core` + `pngjs` into `~/.cache/birds-probes` on
first use and drives the cached `chrome-headless-shell`. Nothing probe-related
lands in the repo. If chromium is missing it prints the one command to fix it.

Dev static is no-cache (`_fresh_static_in_dev` in index.py), so CSS/template
edits show up on reload without restarting the server. **This matters:** a
stale `site.css` once made a whole redesign look broken for an hour. See the
`website-deploy` memory.

### The probes

| probe | what it answers |
|---|---|
| `sweep2` | chrome height / field share / seam / no x-scroll at 4 widths |
| `finite` | small sets never repeat on screen, panning stays in bounds |
| `rep`, `fallback` | repetition by collection size |
| `zoom`, `zoomanim` | semantic zoom both ways, transition timing, thrash |
| `depth2` | `--age` tracks date with 0 order mismatches |
| `echo` | typographic echo appears/clears, never sticks after a drag |
| `vt`, `vtanim` | view transition fires both ways, no stranded names |
| `deep`, `hash`, `reload` | deep links survive refresh, Back, close |
| `fam` | family detail view, member chips, per-frame species |
| `combo`, `clip` | search ranking, keyboard, panel fits |
| `menu` | view menu, one-row bar |
| `contrast`, `navband` | measured luminance behind text |
| `page` | screenshot any route: `run.sh page /birds out.png 900` |

Screenshots go to whatever path you pass — your scratchpad, not the repo.

## What must not break

The field earned its behaviour through many rejected attempts. Do not
re-litigate:

- Endless pan in any direction; drag anywhere; pinch to resize.
- A species never lands beside itself (round-robin + computed stride).
- Small sets (< ~1.5 screens) get a FINITE layout, not a wrapping one, with
  panning clamped to the block. Scott explicitly rejected falling back to the
  masonry grid for small sets — keep it in the field.
- Detail overlay: frames scoped to the current filter; family mode when a
  family is active; close returns to the same scroll position.
- Curate mode must keep working.
- Brand: `--paper`, `--ink`, `--green`; Fraunces (display), Space Grotesk
  (body), JetBrains Mono (mono). "Holistic" was the ask — keep it.
- `prefers-reduced-motion` respected everywhere.
- **Rejected outright earlier, do not bring back:** scroll-jacking; a
  dashboard-style stats redesign; recency "weaving" that reorders the field;
  jargon labels ("lean recent", "Back to the centre").

## Landed so far

Newest last. One commit each; `git log master..HEAD` has the reasoning.

1. **View transitions** — tile → detail morphs via `document.startViewTransition`.
   The name must be on exactly one element per snapshot, so the tile carries it
   for the outgoing frame and the stage image for the incoming one, swapped
   inside the callback between the two captures.
2. **Depth** — `--age` per tile (0 = newest in view, 1 = oldest), ranked not
   raw-scaled, driving a slight scale/saturation recession. CSS-only hover
   lift. *Gotcha:* AGE is keyed by TILE index; `at()` returns a SEQ position.
3. **Semantic zoom** — below 150px tile width the field swaps to one tile per
   species, height ∝ frame count (sqrt), name always-on, tally chip.
   *Gotchas:* counts must come from `t.n` (counting SEQ entries returns 8 for
   everything — the server caps the round-robin at 8); `.bf-count` was already
   the stage's frame counter, so the chip needed `.bf-tally`.
4. **Zoom dissolve** — the mode swap runs inside a view transition, guarded
   against pinch thrash.
5. **Home hero** — the stock fjord replaced by a drifting wall of his own
   birds; six columns, CSS-only seamless loop. *Gotchas:* `#bg-effect` lived
   inside `.content` (z-index 1) so it painted over the nav — base.html now
   has a `page_background` block outside `.content`; and the tilt shared an
   element with `.bg-scrim`, so the scrim's gradients rotated with it.
6. **Deep links finished** — `#bird/<slug>`, `#family/<slug>` survive a
   refresh. *Gotchas:* `history.state` survives a reload (so "unwind my own
   entry" needs a page-scoped flag); and birds.html's existing "a refresh
   reshuffles" feature dropped the fragment in `location.replace`.
7. **Typographic echo** — hovering a tile names it huge in Fraunces along the
   bottom, `mix-blend-mode: difference` so it stays legible over any photo.
   Listens on the canvas, not per-tile, and only writes when the species
   actually changes.
8. **Stats section nav** — ten equal pills became three named acts (Over
   time / Which birds / When & where), contiguous in scroll order so nothing
   had to move. Only the act you are in expands; the rest collapse to their
   label. *Gotcha:* `.stat-jump` pinned at `top: 0`, the same place the site
   nav pins, with a lower z-index — so it was invisible whenever you scrolled.

## Next up (priority order)

1. **Stats page, continued.** The section nav is done (three acts, see
   "Landed" #8) but the page is still a 6,800px scroll of eleven sections.
   Remaining idea: give each act a title card so the scroll reads as three
   movements rather than one dump. A dashboard redesign was already rejected
   once — fewer things at once, not more chrome.
2. **Live page** (`/birds/live`) — the mic feed; it should feel alive. Inherit
   the field's motion vocabulary.
3. **Photography page** — shares the gallery machinery; could take the field.
4. **Echo on touch** — desktop-only today (`@media (hover: none)` hides it).
5. **A way into survey mode** — semantic zoom is only reachable by pinching or
   the size slider. It deserves a control that names it.

## Uncommitted right now

Nothing intentionally. If `git status` is dirty on resume, read the diff first
— it is probably a half-finished item from "Next up".
