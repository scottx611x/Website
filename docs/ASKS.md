# Open asks — live site

Status: A1, A3, A7 shipped to master in 497c032 (NOT yet deployed).

Persisted at Scott's request (2026-10-10): *"record and persist all asks in this
chat and do not miss anything."* Tick items only when verified on the LIVE site.

## A. Live-site fixes (do these FIRST, before the Lightroom work)

- [x] **A1. Ordered modes constrain the field.** Newest post / Newest sighting /
      Oldest should NOT pan infinitely in every direction. Bounded grid
      **anchored top-left** (newest at top-left, reading order), travel down +
      right only. Shuffle keeps the endless field. *(Confirmed 2026-10-10.)*
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

- [ ] **C1.** Restart the bird-pipeline Docker container so `archive_originals()`
      (committed `085b7ae`) takes effect. Until then new posts need manual
      reconciliation.
- [ ] **C2.** `wildlife.py` tells you to "commit it, and deploy" — wrong now that
      the S3 curation store is seeded. Make it write through to S3, or at least
      warn. See the `live-curation` memory.
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
