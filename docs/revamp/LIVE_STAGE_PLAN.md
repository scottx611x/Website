# /birds/live: the stage

> **Status 2026-11-14:** phases 1-2 shipped (5e562c5, 2009da2, d71288a) and
> made the default on Scott's "ship it". `?stage=0` keeps the old paper page
> until 2026-11-21; then delete its markup in its own commit. Deviations: on
> wide screens the photo sits right of centre with a blurred copy behind the
> words (full-bleed shading failed contrast on bright daytime photos); the
> meta line is paper, not green. Phase 3 shipped 0f85f7f (probe
> `livevoice`); phase 4 shipped after it (`livefeel` checks reel head + tab
> title). The reel now orders by each bird's newest released recording.
> Phase 5 ("sound on") shipped to everyone on Scott's "no flag just rip it"
> (probe `livesound`). Left: 3b (needs bucket CORS in the infra repo, ask).

A design brief for a fresh session to implement. Read all of it, then
`docs/revamp/OVERNIGHT.md` (working rules, probes, rejected designs) and
`docs/revamp/LIVE_PLAN.md` (what is on the page today and why).

Look at the mocks before reading further:

- `docs/revamp/mocks/live-stage-photo-1440.jpg` (a photographed bird)
- `docs/revamp/mocks/live-stage-ghost-1440.jpg` (a bird heard but never photographed)
- `docs/revamp/mocks/live-stage-photo-412.jpg` (phone)
- `docs/revamp/mocks/live-stage-*.html` (the static HTML/CSS they were shot from)

The mocks are one frame of real data (real photo, real spectrogram, real
names). They are the target for the look. They do not move; the motion is
described below.

## Why another plan

`LIVE_PLAN.md` shipped on 2026-11-13 (82861dc): cut to one sentence, arrivals
queued one at a time, time-aware status line. Scott's verdict: "the live page
is still underwhelming", and he asked for a redesign "with some cool factor".

Screenshot the page first (`docs/revamp/probes/run.sh livefeel <outdir>`) and
read it as a visitor. What is wrong is visible in one look:

- It is paper-coloured lists and small charts. The bird on stage is a 650px
  card sharing the row with a feed. Nothing on the page is big.
- When the latest bird has no photo (tonight: Common Goldeneye), the hero is
  an empty beige box with a silhouette. That is the first thing a visitor sees.
- The one asset no other site has, the yard's real sound, is a 110px strip
  under the card.
- The site's best-liked surface is the gallery's dark detail view: one
  photograph, full stage. Live looks nothing like it.

The earlier recipe (cut, add nothing, polish) has now been tried and was not
enough. This plan changes the page's first screen outright. That is a
deliberate departure, and it is why this ships behind a flag first (see "How
to ship").

## Already rejected: do not rebuild under another name

| Idea | Commit | Verdict |
|---|---|---|
| "Listen to today": the page as a radio station with a queue | 4bcf945 | reverted the same day |
| "Name that bird" quiz | 70f011a | reverted the same day |
| The Chorus: a scrubbable 24h ribbon with the sky as a clock | 0cf6fa4 | "not wowed by the live page updates at all" |
| Cut + polish (current page) | 82861dc | "still underwhelming" |

Also rejected site-wide: scroll-jacking, dashboard grids, chapter cards,
jargon labels. So: **no playback queue, no auto-advancing playlist, no game,
no day timeline as the main control, no sky/clock graphic.**

## Direction

**The first screen is a dark stage, and the bird that just sang owns all of
it.** Full-bleed photograph, its name at poster size, its call as a glowing
voiceprint, and today's other birds as a film reel along the bottom edge.
Everything the page has today (feed, hour strip, mic filter, soundtrack)
stays, unchanged, below the stage on paper.

Three things carry the cool factor, in order of importance:

1. **Scale.** One bird, the whole viewport, name set at ~150px.
2. **Sound you can see.** The call is drawn in light, and moves when it plays.
3. **A reel you can throw.** Today's birds in one horizontal strip; pick one
   and the stage becomes that bird.

## The stage, piece by piece

Top to bottom, matching the mock:

| Piece | What it is |
|---|---|
| Backdrop | The bird's web copy (`/birds/images/`, via `webPhoto()`), `object-fit: cover`, thumbnail underneath while it loads, slow drift (reuse `.lv-ph`). A bottom-heavy ink gradient keeps text legible. |
| Backdrop, no photo | **The spectrogram is the picture**: the clip's own spectrogram PNG stretched full-bleed, brightened, slightly blurred. No silhouette box, ever. |
| Top line | Site nav and the Gallery / Stats / Live / Map pills, in paper-on-dark, over the photo. Then the live line: green dot, place, today's species count. This line is `moodLine()`'s output: it already says "quiet for 14 min", "Raining", "dawn chorus". |
| Meta | Mono, green: time, relative time (ticking), mic, confidence. Or "HEARD, NEVER PHOTOGRAPHED". |
| Name | Fraunces 400, `clamp(54px, 9.4vw, 150px)`, paper colour. It is the page's `h1`; the "Live from the yard" title is not shown on this page. |
| Fact | The existing one true sentence (`_yard_rhythm`), Fraunces italic. |
| Voiceprint | Play button (existing neon) and the spectrogram at ~74px tall, full width. Existing scrub, slow-mo and full-screen viewer all still work on it. |
| Reel | Today's species, one frame each, most recently heard first. |

Height: `100svh` (not `100vh`: phone toolbars). The paper page starts
immediately below; a small "the log ↓" cue at the bottom-right of the stage is
the only hint needed.

Stamps (`first today`, `new to the yard`) stay, restyled as paper ink on dark,
above the meta line.

## Phases

One commit each. Do them in order. Each has a "done when" a probe can check;
add `docs/revamp/probes/livestage.js` in phase 1 and extend it per phase.

### 1. The stage, standing still

Build the stage at `?stage=1` (see "How to ship") with the pieces above,
rendered from the same `LIVE` payload and the same `renderHero` data. No new
motion yet beyond the existing drift and arrival cross-fade.

- The stage replaces the header title block, the tally sentence, the "Just
  heard" card and the wall of chips. The tally's three numbers move into the
  live line (`22 species today`) and the log section's heading; the search box
  moves to the top of the log.
- The feed column, hour strip, mic filter, confidence slider, soundtrack and
  the Stats link stay exactly as they are, below the stage.
- Stale / offline station: the existing honest state, shown on the stage
  (dimmed backdrop, the same sentence).
- Night: the stage holds the last bird of the day, backdrop dimmed ~35%, and
  the live line carries the existing night sentence ("First song is usually
  around 6:12").

Done when, at 1440x900 and 412x860: the stage is exactly one viewport tall;
the name is ≥ 96px desktop / ≥ 44px phone and never wraps past two lines
(test the longest name heard: "Black-throated Green Warbler"); a no-photo
bird shows the spectrogram backdrop; measured text contrast over the photo
(use the `contrast` probe's method) is ≥ 4.5:1 for name, meta and fact on
three different birds; no horizontal scroll; no page errors; without the flag
the page is byte-for-byte today's.

### 2. The reel

- One horizontal row, native scrolling with `scroll-snap-type: x proximity`
  and momentum (no JS scroll physics, no scroll-jacking: vertical wheel still
  scrolls the page; horizontal wheel, drag and swipe move the reel). Left and
  right arrow keys step it when the stage has focus.
- **Picking a frame puts that bird on the stage**: backdrop cross-fades, name
  re-sets, meta/fact/voiceprint switch to that species' clearest clip of
  today. Nothing plays until the play button is pressed.
- While a picked bird is on stage, a "● back to live" chip sits beside the
  live line. Clicking it, or pressing Escape, returns to the latest bird.
  New arrivals do not take the stage from a bird the visitor picked; they
  land in the reel (next phase) and the chip shows "● 2 new".
- Heard-never-photographed birds are frames too: their spectrogram as the
  frame image, dashed outline (today's ghost chip, same meaning).
- The frame's name is a link to the species page on a fine pointer (same
  rule as the Stats pin: on touch the whole frame picks, and the stage's name
  is the link).

Done when: clicking the 5th frame changes the stage name to that bird and
`scrollY` does not move; Escape returns to the latest; a simulated poll with
a new bird while one is picked does not change the stage; the reel scrolls
horizontally by wheel and by touch drag while a vertical wheel over it still
scrolls the page; keyboard reachable.

### 3. Sound you can see

When a clip plays on the stage:

- **The voiceprint scrolls under a fixed needle** (the needle sits at 38% and
  the spectrogram moves through it) instead of a needle crossing a still
  image. Drive it from the existing `--p` progress var; `playhead.js` already
  updates it at 60fps. Scrubbing still works: drag the print, not the needle.
- The part already played stays bright; the part to come is at 45%.
- The needle has a soft green bloom, and the play button's glow tightens
  while playing.
- On a no-photo bird the full-bleed spectrogram backdrop scrolls with it, so
  the whole screen moves with the call.

**3b, needs Scott's OK first: the photo breathes with the call.** A 1-2%
scale and brightness pulse on the backdrop driven by the clip's loudness
(`AnalyserNode`). This needs the audio to be CORS-readable, and **the bucket
has no CORS configuration today** (`aws s3api get-bucket-cors` returns
NoSuchCORSConfiguration). Adding a GET rule for the site's origins is a bucket
config change: ask before making it, and check whether the `infra` OpenTofu
monorepo owns that bucket. Do not set `crossorigin` on the `<audio>` element
before the rule exists: without the header the clip will not play at all.

Done when: during playback the needle's x position is constant and the
spectrogram's transform changes every frame; pausing freezes it; seeking by
click lands within 100ms of the clicked time; with `prefers-reduced-motion`
the old moving needle is used and nothing else animates.

### 4. The arrival, at stage scale

The queue from 82861dc stays (`scheduleRelease`, `releaseNext`, `arrive`):
one bird at a time, never interrupting a playing clip. What changes is what
an arrival looks like when the visitor is on live:

- The new photo wipes in from the reel side (a `clip-path` sweep, ~700ms),
  the old name drops, the new name sets word by word (reuse `lvWord`).
- At the same moment the bird's frame slides into the head of the reel and
  the others shift right.
- `document.title` becomes `● Carolina Wren · Live` for that bird, so a
  background tab shows the yard is doing something.
- First-of-the-day and new-to-the-yard arrivals get their ink stamp, as now.

Done when: the existing arrivals check in `livefeel.js` still passes against
the stage (three injected birds, three stage changes ≥ 2s apart, in order);
the reel's first frame matches the stage after each; the tab title updates;
reduced motion shows the same content with no animation.

### 5. Optional, show first: hear the yard

A single "sound on" switch on the stage. While it is on, each **new arrival**
plays its clip once as it takes the stage. This is not the rejected radio:
there is no queue, no playlist, nothing plays unless a bird actually just
sang. It is still close enough to a rejected idea that it must not ship
unasked: build it behind `?stage=1&sound=1`, record a 30-second capture, and
let Scott decide.

## Must not break

Everything in `LIVE_PLAN.md`'s list, which in short is:

- Spectrogram player: scrub, slow-mo, full-screen viewer, share link.
- Mic filter, confidence slider and its "lower confidence" note, the hour
  strip with its typical-day ghost and sun marks, tapping an hour.
- Soundtrack day stepping, its per-row play buttons and "+N more".
- Curate mode (hide a clip, suppress a species) and its toasts. The floating
  Curate button must stay reachable over the stage.
- `/birds/heard`, `/birds/live/log`, and the `live.json` shape.
- The honest offline state, and the arrivals queue's "never cut a playing
  clip" rule.
- Brand: paper `#f4f1e9`, ink `#0d120e`, green, the neon play button;
  Fraunces, Space Grotesk, JetBrains Mono. The stage's dark is the gallery
  detail view's dark, not a new colour.

## Things that will bite

- `templates/birds_live.html` is ~1,900 lines of inline CSS and JS. `LIVE` is
  a local of the page's IIFE; `window.LIVE` is undefined.
- The 60s poll re-renders hero, feed, wall and counts through `apply()`.
  Find every render path before adding stage state, or the next poll will
  put the latest bird back on a stage the visitor picked.
- The header on this page collapses (`data-collapse`), and a shrinking sticky
  header is what caused the scroll flicker fixed in fba77d8. On the stage the
  header should not be the collapsing kind: nav sits over the photo and
  scrolls away with it. Re-run the `collapse` probe on the gallery after
  touching `base.html`.
- Portrait photos on a landscape stage and landscape photos on a phone both
  crop hard under `cover`. Use `object-position: 50% 30%` as a start and check
  ten birds at both sizes; if a bird's head is routinely lost, cap the crop
  with a blurred copy of the same photo behind a `contain` copy rather than
  inventing focal-point data.
- Web copies are 2.4MP: fine at 1440, soft on a 4K display. Do not use the
  presigned originals here.
- Jinja templates are cached by the dev server: restart it after template
  edits (`lsof -ti tcp:5055 | xargs kill`, then `make run`).
- Record times are local ISO with an offset; never re-derive them from clip
  filenames.
- Autoplay: browsers block sound before a gesture. Nothing in phases 1-4
  plays without a click.

## How to work

- Local server: `env BIRDS_USE_S3=1 PATH="$PWD/.venv/bin:$PATH" make run` (port 5055).
- **Never open a browser window.** Everything visual goes through
  `docs/revamp/probes/run.sh`.
- `make test` before each commit. New server-side facts get tests in `tests.py`.

## How to ship

Three finished redesigns of this page have been thrown out, so this one
reaches Scott's own phone before it replaces anything:

- Build everything behind `?stage=1`. Without the flag, `/birds/live` is
  unchanged.
- Each verified phase is committed to `master`, deployed with `make deploy`
  (never a bare `zappa update`) and pushed, without asking, **behind the
  flag**. After phase 2, tell Scott to open
  `https://www.scott-ouellette.com/birds/live?stage=1` and send the 1440 and
  412 captures.
- **Making the stage the default is Scott's call.** Do not flip it unasked.
  When he says yes: the flag flips, `?stage=0` keeps the old page for a week,
  then the old markup is deleted in its own commit.

## Kickoff prompt

> Read `docs/revamp/LIVE_STAGE_PLAN.md`, `docs/revamp/LIVE_PLAN.md` and
> `docs/revamp/OVERNIGHT.md` in full, and look at the three mock images in
> `docs/revamp/mocks/`. Capture `/birds/live` at 1440 and 412 before changing
> anything. Implement phases 1 to 4 behind `?stage=1`, one commit each, with
> the `livestage` probe. Ship each verified phase behind the flag (commit,
> `make deploy`, push). After phase 2, stop and show me captures at both
> sizes and the flagged URL. Do not make the stage the default, do not change
> the bucket's CORS, and do not build phase 5, without asking me.
