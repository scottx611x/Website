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
- [ ] **A8. The home mosaic's SHAPE must survive the click into the gallery.**
      The home strip is a deliberate arrangement — one large lead tile plus
      four smaller ones. Clicking through currently preserves only the *set*
      (`/birds?start=…` pins those frames to the head of the sequence); the
      field then re-lays them out in its own uniform masonry, so the
      composition is lost. The first screen of the gallery should land in that
      same mosaic. *(Raised 2026-10-10.)*
- [x] **A7. BUG: home → gallery flies off-screen.** Clicking "See all photos →"
      on the home page lands on /birds with the birds drifted to the top-left,
      out of view.

## B. Lightroom originals recovery (after A)

Scott granted both unblocks on 2026-10-10: Screen Recording permission and
`cliclick`. Verify both, then resume.

- [ ] **B1.** Locate the Export button (now that screenshots work) and drive
      `File > Export…` to completion for one shoot day as a dry run.
- [ ] **B2.** Batch the rest. 554 frames across 144 shoot days;
      `~/Desktop/lightroom-reexport.html` is the worksheet. Export into
      `~/Desktop/birbs`, then `BIRDS_USE_S3=1 tools/match_originals.py` and
      `tools/upload_originals.py`.
      Disk: 111 GB free; a full ~5,987-asset export would be 60–90 GB, so work
      day-by-day rather than Select All.
- [ ] **B3.** Selection by capture day through the UI is still unsolved.

## C. Carried over, still open

- [ ] **C1.** **REBUILD** (not restart) the bird-pipeline container so
      `archive_originals()` (committed `085b7ae`) takes effect. The Dockerfile
      `COPY`s server.py at build time — it is NOT bind-mounted — so a restart
      alone changes nothing. Verified: `grep -c "def archive_originals"` is 1
      on disk, **0 in the running container**.

          cd ~/bird-photography-pipeline && docker compose up -d --build

      Not done unprompted: the active batch is parked at `proc_step: posting`
      and a browser session was polling the UI. Interrupting a posting step is
      the one failure mode that could double-post to Buffer.
- [ ] **C2.** `wildlife.py` tells you to "commit it, and deploy" — wrong now that
      the S3 curation store is seeded. Make it write through to S3, or at least
      warn. See the `live-curation` memory. It also does not archive originals
      for /photography, the same gap birds_manual.py had until 2026-10-11.
- [ ] **C3.** ~38 GB of unposted `birbs` files are still unarchived (3,036 on
      disk vs 1,264 uploaded) if Scott wants the whole folder safe.
- [ ] **C4.** `docs/revamp/OVERNIGHT.md` still describes the branch as
      undeployed; it has shipped. Tidy.
- [ ] **C5.** Stash `stash@{0}: On search-and-video: log_level INFO` — unrelated
      to the deploys; decide whether to keep or drop.

## Standing constraints

- **Never open a browser tab** — someone else uses this laptop. Visual checks go
  through `docs/revamp/probes/run.sh`.
- **Deploy only with `make deploy`** — never bare `zappa update`.
- **Photography changes need the S3 curation write**; a deploy alone does not
  publish them.
