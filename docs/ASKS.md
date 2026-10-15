# Open asks — live site

Status: A1, A3, A7 shipped to master in 497c032 (NOT yet deployed).

Persisted at Scott's request (2026-10-10): *"record and persist all asks in this
chat and do not miss anything."* Tick items only when verified on the LIVE site.

## Overnight run protocol (authorised 2026-10-10)

> *"work through the other asks autonomously overnight"*

Order: **A8 → A2 → A4 → A6 → A5.** A8 and A2 are small and concrete; A4 is
large but mechanical; the two facelifts are last because they are subjective
and have the worst track record.

**Deploy policy — deliberately split, because these differ in risk:**

- **Ship as you go**: bug fixes and behaviour changes that a probe can prove
  (A8, A2, A4). Every one gets `make test` + the relevant probe + a live
  check before and after `make deploy`.
- **Build but DO NOT deploy**: the stats and live facelifts (A5, A6). Scott has
  rejected four design attempts — acts, the Chorus, the life list, the
  plate-blue palette. Shipping unreviewed design to prod is how that becomes
  five. Build on master, screenshot, leave deployed prod on the last good
  commit, and show him the renders.

Never open a browser tab. `make deploy` only. After each deploy, verify the
actual behaviour live, not just a 200.

## A. Live-site fixes (do these FIRST, before the Lightroom work)

- [x] **A1. Ordered modes leave the field entirely.** Superseded 2026-10-10 by
      Scott: *"shuffled can be full gallery pan magic, but newest/oldest should
      revert to the old gallery style."* So Shuffle keeps the endless field and
      the ordered modes render the CLASSIC GRID. The bounded top-left-anchored
      block built earlier still backs an explicit `?view=field&sort=…`.
- [x] **A9. BUG: filtered field views clipped under the header.** A species or
      family view takes the finite path, but the clamp used PAD=40 as its top
      stop while the header is 172–334px once a chip row appears — so the first
      row sat under the chrome. All bounded layouts now clear it.
- [~] **A2. Cut non-essential copy.** *(view menu + home subtitle done; site-wide pass still to do.)* Scott: *"anything non-essential. you have
      a habit of being wordy."* Covers the view-menu descriptors ("a new
      arrangement each time", "when it went up", "when the bird was seen",
      "from the beginning"), the home subtitle ("A rotating selection of my
      favorite shots from around my hometown."), **and a general pass for
      wordiness site-wide.** Treat terseness as the default everywhere.
- [x] **A3. Remove the "North Andover only" link.** `templates/birds.html:28` —
      the `area=local` link ("123 species here"). Keep the `area=elsewhere`
      ("outside North Andover ⚠") link; that one flags travel birds and earns
      its place. *(Confirmed 2026-10-10.)*
- [ ] **A4. Photography gets the same gallery.** Same sorting + viewing
      controls as /birds. **Bigger than it looks:** templates/photography.html
      is a standalone 249-line grid with tag chips and its own lightbox — it
      does not use _field.html at all. Needs the field + view menu ported, and
      the field's data shape adapted (photos carry title/species/date/tags,
      not species/family/post id).
- [ ] **A5. Facelift /birds/stats.** Long-standing: Scott has rejected several
      attempts (act cards, dashboard). See docs/revamp/OVERNIGHT.md "Rejected
      outright" before starting.
- [ ] **A6. Facelift /birds/live.** Same history — "The Chorus" was rejected.
- [x] **A8. The home mosaic's SHAPE must survive the click into the gallery.**
      Done 2026-10-11. A `?start=` arrival now lands in the GRID (the field's
      canvas is fixed to the viewport and cannot carry an opening block) with
      the five frames in the same 2x2-lead composition, the masonry continuing
      beneath. Measured: lead is 2.04x wide / 2.07x tall at 1440, collapsing to
      a full-width banner under 700px, same order, 1,886 frames below. Probe:
      `mosaic`. Original wording follows.

      The home strip is a deliberate arrangement — one large lead tile plus
      four smaller ones. Clicking through currently preserves only the *set*
      (`/birds?start=…` pins those frames to the head of the sequence); the
      field then re-lays them out in its own uniform masonry, so the
      composition is lost. The first screen of the gallery should land in that
      same mosaic. *(Raised 2026-10-10.)*
- [x] **A7. BUG: home → gallery flies off-screen.** Clicking "See all photos →"
      on the home page lands on /birds with the birds drifted to the top-left,
      out of view.

## B. Lightroom originals recovery — LARGELY DONE

**Coverage 90.7% (1,732 / 1,909). 177 missing**, of which 52 are manual-post
frames whose sources left the disk years ago. The historical note below is kept
because every line of it was learned the hard way.

**The mistake to avoid repeating:** Scott already has working Lightroom
automation in `~/bird-photography-pipeline` — `lr_auto.py`, `lr_denoise.py`,
`lr_host.py` (HTTP bridge), `lr_verify.py` (screenshot fingerprinting to prove
an action landed), plus an auto-nudge that re-triggers a wedged render. A
concurrent session drives it successfully. Build on THAT, not on raw cliclick.

**Facts established the hard way — all verified, none of them guesses:**

- `Cmd+F` focuses the search box reliably; clicking it by coordinate does not.
  A missed click turns the typed filename into keyboard SHORTCUTS (this set
  star ratings on photos via a stray "November 2025").
- Searching a FILENAME filters; searching a DATE does not ("2025-11-29" and
  "November 2025" both no-op).
- Search terms become TOKEN CHIPS that accumulate and AND together. Neither
  `Cmd+A` nor backspace clears them (backspace edits the last chip's text).
  Only the field's clear button works — find it at the right edge of the
  accent-blue focus outline.
- Filtering does NOT change the selection, and Export acts on the SELECTION.
  Without `Edit > Select All` you re-export whatever was selected last.
- But `Edit > Select All` on an unfiltered view selects all 5,534 and Export
  then raises a modal **"AI Update Required"**. These STACK, one per attempt,
  and block everything silently.
- Dismiss that modal by locating `window "AI Update Required"` via System
  Events and clicking its frame + (325, 321). This works first try.
- **The Lightroom window moves between calls** and was on a SECOND DISPLAY
  (origin x=-1018) for part of the session. Never use absolute screen
  coordinates; always re-read the window frame.
- `cliclick` drops the shift on the first character of a `t:` string
  ("DSC_" -> "dSC_"). Search is case-insensitive, so send lowercase.
- Lightroom names each export after its SOURCE photo, so comparing the
  exported filename to the requested one is cheap, certain proof the search
  took. Use it; pixel heuristics are not needed and mislead.
- Previews are content-addressed with NO link back to a catalog asset, so a
  frame cannot be mapped to one filename. Per-DAY candidates + content hash.
- `tools/lr_backfill.py` is the failed attempt, kept for its findings. It is
  SAFE (refuses to ship a mismatch) but unreliable. 3,453 candidates would
  cover the 631 frames.

**Recommended path (split so each half is reliable):** Scott selects a month in
Lightroom (click first, shift-click last) and hits `File > Export with
Previous`; the agent handles the AI modal, then matches, uploads to Glacier,
verifies and deletes locals. ~9 selections covers 2025-11 .. 2026-07.
The collection half is proven: 1,275 originals shipped, 7 mis-keyed files
caught, 12/12 byte-verified before deleting 20 GB.

- [x] **B1. FULL SWEEP COMPLETE (2026-10-13).** Every month of 2026, all of
      2025 and 2010 exported and collected. August needed three retries: it
      selects and exports fine, but the script was clicking it while a modal
      from the previous month was still up, so the click was swallowed.
      Coverage 1,310 -> **1,417 of 1,904 (74.4%)**, missing 594 -> **487**.
      ~4,650 exports for ~107 frames.

      Per bucket (exported -> frames): Apr 563->8, Feb 735->1, Mar 651->3,
      Jan 335->11, Jun 318->13, Jul 593->8, Sep 297->7, **2025 507->55**,
      Aug 647->9. 2025 yielded 11%, roughly 8x any 2026 month -- the old posts
      are the unarchived ones and their shoots are still intact.

      **The library is now exhausted.** What remains is not findable this way.
- [ ] **B2.** Sweep yields so far (exports -> frames): May 25 32->14,
      May 9/17/26 159->13, May 8-16 185->2, May rest 241->3, Apr 563->8,
      Feb 735->1, Mar 651->3, Jan 335->11, Jun 318->13. Roughly 3,200 exports
      for 68 frames. Yield is lumpy, not uniformly low: when a post's shoot is
      intact in Lightroom the whole post returns at once (Jan gave 9 of its 11
      from a single post).
- [ ] **B2.** Batch the rest. 554 frames across 144 shoot days;
      `~/Desktop/lightroom-reexport.html` is the worksheet. Export into
      `~/Desktop/birbs`, then `BIRDS_USE_S3=1 tools/match_originals.py` and
      `tools/upload_originals.py`.
      Disk: 111 GB free; a full ~5,987-asset export would be 60–90 GB, so work
      day-by-day rather than Select All.
- [ ] **B3.** Selection by capture day through the UI is still unsolved.

## C. Carried over, still open

- [x] **C0. Export destination reconciled (2026-10-14).** Rather than fight
      Lightroom's export dialog, `~/Documents/birbs` is now a SYMLINK to
      `~/Desktop/birbs`, so both paths are one folder: whichever Lightroom
      writes to, the pipeline's `/birds` mount sees it. Verified both show
      the same 2,658 files. Original note follows.

      ~~PUT LIGHTROOM'S EXPORT DESTINATION BACK TO ~/Desktop/birbs.~~
      On 2026-10-13 it was re-pointed to ~/Documents/birbs to dodge a TCC
      problem (this process kept losing read access to Desktop). That BREAKS
      the posting pipeline's archiving: `archive_originals()` reads `/birds`,
      mounted from `~/Desktop/birbs`, so a batch exported to Documents is
      invisible to it and its full-size originals never reach Glacier.
      `BIRDS_DIR` is used in 23 places in server.py (thumbs, previews,
      .excluded, the posting UI) -- it is the pipeline's whole working folder,
      so do NOT split it. One folder, and it must be Desktop/birbs.
      Fix the access problem the other way: give iTerm **Full Disk Access**
      and RESTART iTerm (TCC changes do not apply to a running app).
      Re-point via File > Export… once; Export with Previous then reuses it.

- [x] **C1. DONE (2026-10-12).** Rebuilt; `archive_originals` verified present
      in the running image (was 0, now 1), state intact, batch resumed.
      ~~**REBUILD** (not restart) the bird-pipeline container~~ so
      `archive_originals()` (committed `085b7ae`) takes effect. The Dockerfile
      `COPY`s server.py at build time — it is NOT bind-mounted — so a restart
      alone changes nothing. Verified: `grep -c "def archive_originals"` is 1
      on disk, **0 in the running container**.

          cd ~/bird-photography-pipeline && docker compose up -d --build

      Not done unprompted: the active batch is parked at `proc_step: posting`
      and a browser session was polling the UI. Interrupting a posting step is
      the one failure mode that could double-post to Buffer.
- [x] **C2. DONE (2026-10-15).** `wildlife.py` now archives each untouched
      source to `wildlife/originals/<id>.jpg` as GLACIER_IR (the web copy is
      capped at 2048px, so the full-res file existed only on the import drive),
      and its closing note says plainly that committing + deploying is NOT
      enough — production reads the S3 curation store, which wins over the
      deployed repo copy.
- [ ] **C3.** ~38 GB of unposted `birbs` files are still unarchived (3,036 on
      disk vs 1,264 uploaded) if Scott wants the whole folder safe.
- [x] **C4. DONE (2026-10-15).** OVERNIGHT.md marked as shipped history.
- [x] **C5. DONE (2026-10-15).** Kept. It was a one-line `log_level: INFO` in
      zappa_settings.json that never landed — Zappa defaults to DEBUG, which
      floods CloudWatch and costs money for nothing. Applied and committed;
      the stash is gone.

## Standing constraints

- **Never open a browser tab** — someone else uses this laptop. Visual checks go
  through `docs/revamp/probes/run.sh`.
- **Deploy only with `make deploy`** — never bare `zappa update`.
- **Photography changes need the S3 curation write**; a deploy alone does not
  publish them.
