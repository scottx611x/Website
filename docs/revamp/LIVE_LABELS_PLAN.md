# /birds/live: the stamp and the line under the name

> **Status 2026-11-15: shipped** (live_labels.py, 26241df, e345f06). Changes
> from this plan after reading the replay: BOTH MICS is a line, not a stamp
> (two mics made it routine); the "Fourth time this morning" lines are cut
> (tally voice); company must beat chance by 4x; a run of one bird keeps one
> line; each line kind is said once per bird per day, most particular first.
> Replay: `BIRDS_USE_S3=1 .venv/bin/python tools/label_replay.py 14`.

A brief for a fresh session to implement. Read all of it, then
`docs/revamp/OVERNIGHT.md` (working rules, probes) and skim
`docs/revamp/LIVE_STAGE_PLAN.md` (the stage these labels sit on).

## What exists, and why it fails

Each bird on the stage can carry two pieces of text:

- **the stamp**: the tilted rubber stamp above the name (`.lv-stamp`);
- **the line**: one italic serif sentence under the name (`.lv-fact`).

Both come from `heroNotes()` in `templates/birds_live.html` (about line 1652).
Its history: the stamp said "first of the day" on nearly every arrival, he
said it "gets old easily", and the fix (e13bc7c) was a pool of a dozen
phrases picked by hash. That fix missed the complaint. What is on the page
now:

    120 DAYS STRAIGHT      UNMISTAKABLE        6TH CALL TODAY
    MOST HEARD TODAY       CHECKING IN         FIRST CALL TODAY

His verdict: "there's little taste". The reasons, so they are not repeated:

1. **A stamp on every bird is wallpaper.** The problem with "first of the
   day" was never the wording; it was that a stamp appeared at all. Twelve
   synonyms for nothing-much is the same wallpaper with more patterns.
2. **It reads like a sports ticker.** Counts, streaks and rankings
   ("6th", "120 days", "most heard") are dashboard facts. The memory note
   for this revamp says he wants cinematic, not a dashboard.
3. **The words judge.** "Unmistakable" restates the confidence bar beside
   it; "checking in" is filler invented to have something to say.
4. **The two slots say the same kind of thing.** Stamp "8 days straight",
   line "Heard here 13 days running": two statistics, no voice.
5. **Nothing is about the bird.** Every fact is about today's tally. None
   says what this species does here: when it sings, when it left, who it
   travels with, whether he has ever got a picture of it.

## Direction

**The stamp marks an occasion. The line is a field note. Most birds get no
stamp, and that is the design.**

Think of a naturalist's notebook: the stamp is the inked mark made a few
times a week ("NEW"), the line is the pencilled margin note in a consistent
hand. No new UI, no new slots, no added sentences: one stamp at most, one
line at most, and fewer of both than today.

## The stamp: occasions only

A stamp appears only when one of these is true. First match wins. Nothing
else may ever be stamped; if none holds, there is no stamp.

| Occasion | Stamp | Rule |
|---|---|---|
| The mic has never heard it | `NEW TO THE YARD` | `r.new` (today's rule) |
| Back after a real absence | `FIRST SINCE OCT 3` | last heard 21+ days before today; the date, never "after N days" |
| Almost never here | `SECOND VISIT` / `THIRD VISIT` | heard on 2 or 3 distinct **days** ever (not recordings) |
| A day bird at night, or the reverse | `NIGHT VOICE` | recorded more than an hour outside sunrise..sunset, **and** under 5% of this species' recordings fall in darkness. An owl at night is not an occasion. |
| The day's opener | `FIRST VOICE` | the first recording of the yard's waking burst (the same burst rule `_yard_rhythm` uses for `firstSong`), so a lone 3am swan does not take it. Once per day. |
| Both mics at once | `BOTH MICS` | today's rule (other node within 20s) |
| Its biggest day here | `ITS BIGGEST DAY` | today's count for this species just passed its previous best day, and that best was at least 10. Once per species per day. |

Targets, to be checked by the replay below, not assumed:

- a stamp on **at most one arrival in five** over a normal week;
- no single stamp on more than **8%** of arrivals;
- `FIRST VOICE` exactly once on any day with a waking burst.

If the replay shows more, raise thresholds; do not add softer stamps to fill
quiet days. A whole afternoon with no stamp is correct.

## The line: one field note, in one voice

One sentence, or none. It is about this species in this yard. Candidates,
each with the rule that makes it true:

| Kind | Example | Rule |
|---|---|---|
| Never photographed | *Heard 412 times. Never once photographed.* | `shot` false and 25+ recordings. This is the site's own tension (heard vs shot); use it. |
| Photographed | *Last photographed September 7.* | `shot` true; date of its newest gallery photo |
| Habit, kept | *A morning bird: mostly heard before nine.* | 70%+ of its recordings fall in one of four day-parts and this one does too |
| Habit, broken | *Late for a nuthatch. It is usually done by noon.* | 70%+ in one day-part and this one is outside it. Never together with `NIGHT VOICE`. |
| Company | *Came in with the chickadees.* | another species recorded within 60s, on 3+ separate days in the last 28 that pair co-occurred. A habit, not a coincidence. |
| Regular | *Here every day since July 18.* | streak reaches back 14+ days; the start **date**, never the count |
| Arrival | *First heard here October 20.* | first-ever day is within the last 30 days and it is not `NEW` today |
| Weather | *Singing in the rain.* | `weather.raining` |
| Today | *Fourth time this morning.* | 3rd to 12th recording of it today; spelled out; morning / afternoon / evening / tonight |

Choosing: drop any candidate that repeats the stamp's fact, then pick by a
hash of species + station date + kind list, skipping the kind the previous
bird on stage used. So one bird keeps one note through a day's polls, says
something else tomorrow, and two birds in a row never get the same shape of
sentence. `Today` is the fallback, used only when nothing else holds; with
nothing true, no line.

## Voice rules (the test of taste; enforce in code and tests)

- Stamp: 1 to 3 words, a noun phrase, never a sentence, never a judgement.
- Line: one sentence, 9 words or fewer where possible, at most one number.
- Dates over durations: "since July 18", not "120 days".
- Numbers under thirteen are words. No ordinals above twelfth anywhere.
- No adjectives of praise or certainty (unmistakable, clear, loud, rare).
  Confidence already has a bar; do not narrate it.
- Plural species names in running text are lower case with a plain plural
  ("the chickadees", "a nuthatch"): add a tiny helper with tests for the
  irregulars the yard has (titmouse/titmice, goose/geese, a/an).
- Nothing invented: every phrase maps to one rule above. If a phrase needs
  a new fact, add the fact server-side first.
- **Banned outright:** checking in, unmistakable, most heard today, clear as
  a bell, N days straight, Nth call today (as a stamp), first call today,
  first of the day, up before the sun, after dark, dawn chorus.

## How to build it

**Move the logic to the server.** `heroNotes()` is 50 lines of untestable
closure in a template; that is how filler shipped. Compute the notes in
Python and send them with each record.

1. `index.py`: extend `_yard_rhythm` (it already walks the full merged log
   once, memoised) to return per species: distinct days heard, first day,
   previous day heard, streak start date, best single-day count, share of
   recordings in darkness, share per day-part, and the co-occurrence pairs
   for the last 28 days. Add newest-photo date per species from the gallery
   (`birds.species_groups` / `species_covers` are already loaded in
   `_live_view`).
2. New pure function `_hero_note(rec, ctx) -> {"stamp", "line", "kinds"}` in
   `index.py`; no I/O, so it is unit-testable. `_live_view` attaches `note`
   to every row of `dayrecs` and `recent`. The "previous bird's kind" rule
   needs arrival order: process `dayrecs` oldest first.
3. `templates/birds_live.html`: `renderHero` reads `r.note`; delete
   `heroNotes`, `lastStampKind`, `hashStr`, `nth`, `WORDNTH`. A bird picked
   from the reel shows the note of its newest recording.
4. Darkness needs sunrise and sunset for past days. Today's come from
   `weather`; for history use a fixed-latitude solar calculation (North
   Andover, 42.70 N, 71.13 W) in a small helper with a test, not a network
   call.

**Tests (`tests.py`):** one case per stamp and per line kind with a minimal
log; the precedence order; "an owl at night gets no `NIGHT VOICE`"; stamp
and line never share a fact; every banned phrase absent from the module
source; number-word and plural helpers.

**The replay, which is the real acceptance test.** Add
`tools/label_replay.py`: run `_hero_note` over every recording of the last
14 days that would have taken the stage (confidence at or above 0.75, in
time order) and print:

- a frequency table: each stamp and each line kind, count and share;
- the stamp rate per day;
- the full sequence for two contrasting days (a busy morning, a quiet one),
  one arrival per row: time, bird, stamp, line.

Tune thresholds until the targets above hold and the two day-sequences read
well top to bottom. **Paste both sequences and the table in the hand-off
message before deploying.** This change is copy he has already rejected
twice; he reads the sequences first, then it ships.

**Probe:** extend `docs/revamp/probes/livefixes.js`: on the live page, every
visible stamp is in the allowed list, no banned phrase appears anywhere in
`#lv-stage`, and stamp and line are never both present with the same kind.

## Must not break

- `NEW TO THE YARD` keeps its exact wording and its arrival animation.
- The status line, the "heard, not photographed" tag in the time row, the
  confidence bar, and the old page (`?stage=0`) keep working; the old page
  may simply render `r.note` too.
- Curate mode: hiding a clip must not leave a `FIRST VOICE` on a clip that
  is no longer first (notes are computed over the curated log, so this
  holds if step 2 uses `_sound_log_merged`; test it).
- Polls must not change the note of the bird already on stage.

## How to work

- Local server: `env BIRDS_USE_S3=1 PATH="$PWD/.venv/bin:$PATH" make run`
  (port 5055); restart it after template edits.
- Never open a browser window; use `docs/revamp/probes/run.sh`.
- One commit for the server facts and `_hero_note` with tests, one for the
  template switch and probe. `make deploy` (never a bare `zappa update`),
  then push, after he has seen the replay.

## Kickoff prompt

> Read `docs/revamp/LIVE_LABELS_PLAN.md` in full. Build the server-side
> facts and `_hero_note` with tests, then `tools/label_replay.py`. Show me
> the frequency table and the two day-sequences from the replay before
> touching the template or deploying. After I approve the copy, switch the
> template to `r.note`, extend the `livefixes` probe, deploy and push.
