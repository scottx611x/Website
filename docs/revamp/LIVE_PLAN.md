# /birds/live: make it feel live

> **Status 2026-11-13:** phases 1-3 shipped, plus phase 4's sentences (not
> the wall-chip playback). Probe: `run.sh livefeel`. The 220px hero target was
> not met: the shared bird-page header alone is ~330px, and it is shared with
> the gallery, so it was left alone. Hero sits at ~475px (was ~575px).

A brief for a fresh session. Read all of it before touching anything, then read
`docs/revamp/OVERNIGHT.md` (working rules, probes, the rejected-design record).

## The problem, in one look

Screenshot the page first (`docs/revamp/probes/run.sh page /birds/live out.png 900`,
and again at 412 wide) and look at it as a visitor would.

- It is a report about a microphone. Seven stat cards, three bar charts and
  two ranked lists; "13 species today" appears twice within one scroll.
- Nothing on it moves. "Live" is a 6px green dot. A new bird arrives silently
  on a 60s poll, by swapping a row.
- The one thing nobody else has, a bird that sang in this yard a minute ago
  with its photo and its voice, starts 400px down, under four counters and a
  search box.
- The lower half (soundtrack, most vocal, history) shows the same counts three
  ways. On a phone the page is 4,800px tall.
- At 2 AM with nothing singing it looks the same as at the dawn chorus.

## What has already been tried and reverted

Three bigger ideas were built, shown and thrown out. Do not rebuild them under
another name.

| Idea | Commit | Verdict |
|---|---|---|
| "Listen to today": the page as a radio station with a queue | 4bcf945 | reverted the same day |
| "Name that bird" quiz | 70f011a | reverted the same day |
| The Chorus: a scrubbable 24h ribbon with the sky as a clock | 0cf6fa4 | "not wowed by the live page updates at all" |

Also rejected elsewhere on the site: scroll-jacking, dashboard grids, chapter
cards, jargon labels.

The pattern in every one: a **new structure was added**. What has worked on
this site is removing things and making what remains feel good under the hand
(the gallery went from eleven controls to one row). So this plan adds no new
section. It cuts, then spends the effort on feel.

## Direction

**The page is one bird at a time, arriving.** Everything else is quieter than
that or gone. Fun comes from timing, sound and small true sentences, not from
widgets.

## Phases

Each phase is one commit, shippable and revertable alone. Do them in order.

### 1. Cut (no new UI)

- Replace the four top stat cards with one mono sentence under the title:
  `13 species · 131 recordings today · 95 species all-time`. Counts tick up
  when a poll changes them.
- Drop the three "heard today vs shot" cards. The wall already says it: a
  heard-but-never-photographed species renders as a ghost chip, and the kicker
  becomes `Heard today · 13, all photographed` or `· 2 never photographed`.
- Fold "Most vocal today" into the soundtrack: rows sort by count, each row
  gets its count and a play button for its clearest clip. One section, not two.
- Move History off the page: it belongs on `/birds/stats`. Leave one link.
  Check whether Stats already covers it before porting anything.
- Search moves into the collapsed header row beside the page pills.

Done when: the hero's top edge is within 220px of the top at 1440x900 and
within 200px at 412 wide; page height is under 2,200px desktop and 2,800px
mobile with a 13-species day; no number appears twice.

### 2. The arrival

This is the phase that matters. Spend most of the time here.

- **Stagger what a poll brings.** A poll can return several new detections at
  once. Queue them and release one at a time, spaced over the following
  seconds in their real order, so the page reads as continuous rather than
  jumping every 60s. Never interrupt a clip that is playing.
- **A bird arriving is an event.** The hero cross-fades to the new portrait
  (View Transitions where supported, a plain fade otherwise), the name sets
  itself in Fraunces, the previous bird slides to the top of the feed, and the
  bird's mark lands on the soundtrack row at the same moment. One motion, three
  places, about 600ms.
- **The hero uses a real photo.** It currently stretches the `thumbs/` copy.
  Use the web copy and a slow drift (a few px over 20s) so it is never frozen.
- **Liveness you can see between arrivals:** the "1m ago" counts up live, and
  the status line names the gap honestly (`quiet for 14 min`).
- First-of-the-day and new-to-the-yard (`rec.new`) arrivals get one extra beat:
  a small stamp on the hero, in ink, that stays for that bird only.

Done when: a probe that injects three new detections into one poll shows three
separate hero changes at least 2s apart, playback is not cut, and with
`prefers-reduced-motion` the same content appears with no animation.

### 3. The page knows what time it is

Copy and state only. No sky gradient, no clock graphic (that was the Chorus).

- **Night / quiet:** when nothing has been heard for a while after sunset, the
  hero becomes the last bird of the day with `Last heard 4:51 PM`, and one line
  uses `hoursHist` to say when the yard usually wakes
  (`First song is usually around 6:30`).
- **Dawn chorus:** when the rate over the last 20 minutes is well above the
  typical hour, say so in the status line.
- **Weather** is already in the payload (`weather.condition`, `raining`):
  `Raining · quiet morning` is a truer status than `listening`.
- **Station stale:** keep the existing honest offline state exactly.

Done when: a probe that fakes the clock and payload shows the four states at
1440 and 412, each with one sentence that is true for that data.

### 4. Small true sentences (only if 1 to 3 landed well)

One line under the hero, picked from facts computed from `daily` and
`dayrecs`, changing with the bird on stage. No LLM, no invented colour.

- `Carolina Wren has sung every day for 41 days.`
- `First Dark-eyed Junco since April.`
- `Both mics heard this one.` (same species on Back Yard and Side Yard within
  a few seconds)
- `Loudest hour so far: 9 AM, 38 recordings.`

Also: hovering or tapping a wall chip plays that species' clearest clip of the
day, with the chip's border as the progress ring.

## Must not break

- Spectrogram player: scrub, slow-mo, full-screen viewer, share link.
- Mic filter (all / Back Yard / Side Yard), confidence slider and its
  "lower confidence" note, the hour strip with the typical-day ghost and sun
  marks, tapping an hour to list its recordings.
- Soundtrack day stepping (today / yesterday / last 7 days / any day).
- Curate mode (hide a clip, suppress a species) and its toasts.
- `/birds/heard`, `/birds/live/log`, and the `live.json` shape other pages use.
- Brand: paper `#f4f1e9`, ink, green; Fraunces, Space Grotesk, JetBrains Mono.

## Things that will bite

- `LIVE` is a local of the page's IIFE in `templates/birds_live.html`;
  `window.LIVE` is undefined. A guard on it once blanked a whole section.
- The page is 1,844 lines of template with inline CSS and JS. The 60s poll
  re-renders the hero, feed, wall and counts; find every render path before
  adding animation, or the next poll will undo it.
- Record times (`t`) are local ISO with an offset. Do not re-derive times
  from clip filenames: the two stations name them differently
  (`sound_index._instant`).
- Data for the view is built in `index.py` `_live_view()`. Prefer computing
  new facts there, with tests in `tests.py`, over doing it in the browser.
- Dev static is no-cache, so template edits show on reload.

## How to work

- Branch `live-feel` off `master`. Check `git status` first: if `master` has
  uncommitted work, stop and ask, do not carry it onto the branch.
- Local server: `env BIRDS_USE_S3=1 PATH="$PWD/.venv/bin:$PATH" make run` (port 5055).
- **Never open a browser window.** Everything visual goes through
  `docs/revamp/probes/run.sh`. Add a probe per phase next to the others.
- `make test` must pass before each commit.
- **Do not deploy and do not push.** When asked to, deploy is `make deploy`,
  never a bare `zappa update`.
- **Stop after phase 2** and show before/after screenshots at 1440 and 412
  plus a short screen recording or frame sequence of an arrival. Scott has
  rejected three finished redesigns of this page; he sees this one half-built.

## Kickoff prompt

> Read `docs/revamp/LIVE_PLAN.md` and `docs/revamp/OVERNIGHT.md` in full, then
> screenshot `/birds/live` at 1440 and 412 wide before changing anything. Do
> phases 1 and 2 on a `live-feel` branch, one commit each, with a headless
> probe for each phase's "done when". Do not deploy or push. Stop after phase 2
> and show me before/after screenshots and the arrival frames.
