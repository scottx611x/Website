"""Replay the Live stage's stamp and line over past days.

    BIRDS_USE_S3=1 .venv/bin/python tools/label_replay.py [days=14] [YYYY-MM-DD ...]

Runs live_labels over every recording that would have taken the stage
(confidence >= 0.75, in time order) for the last `days` days, and prints:
how often each stamp and line kind appears, the stamp rate per day, and the
full sequence for two days (the busiest and the quietest, or the dates given).
The acceptance test for any change to the copy: read the sequences.
"""
import collections
import datetime
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import index  # noqa: E402
import live_labels  # noqa: E402


def main(argv):
    days = int(argv[0]) if argv and argv[0].isdigit() else 14
    pick = [datetime.date.fromisoformat(a) for a in argv if "-" in a]
    t0 = time.time()
    idx = index._label_index()
    built = time.time() - t0
    shots = index._photo_dates(index.birds.load_gallery(shuffle=False))
    last = idx.recs[-1].day
    start = last - datetime.timedelta(days=days - 1)
    stage = [x for x in idx.recs if x.conf >= live_labels.STAGE_CONF and start <= x.day <= last]
    t1 = time.time()
    notes = live_labels.notes_for_stage(idx, stage, shot_of=lambda sp: sp in shots)
    took = time.time() - t1

    n = len(stage)
    stamps = collections.Counter(notes[id(x)]["stamp"] for x in stage)
    kinds = collections.Counter(notes[id(x)]["kind"] or "(none)" for x in stage)
    print("%d stage recordings, %s to %s  (index %.1fs, notes %.1fs)\n" % (n, start, last, built, took))
    print("STAMPS  %d of %d arrivals stamped (%.0f%%)" % (n - stamps[""], n, 100.0 * (n - stamps[""]) / max(n, 1)))
    for s, c in stamps.most_common():
        if s:
            print("  %-22s %5d  %4.1f%%" % (s.upper(), c, 100.0 * c / n))
    print("\nLINES")
    for k, c in kinds.most_common():
        print("  %-22s %5d  %4.1f%%" % (k, c, 100.0 * c / n))
    by_day = collections.defaultdict(list)
    for x in stage:
        by_day[x.day].append(x)
    print("\nPER DAY  (arrivals, stamped)")
    for d in sorted(by_day):
        xs = by_day[d]
        st = sum(1 for x in xs if notes[id(x)]["stamp"])
        print("  %s  %4d  %3d  %4.1f%%" % (d, len(xs), st, 100.0 * st / len(xs)))
    full = [d for d in sorted(by_day) if d != last] or sorted(by_day)
    if not pick:
        pick = [max(full, key=lambda d: len(by_day[d])), min(full, key=lambda d: len(by_day[d]))]
    for d in pick:
        xs = by_day.get(d) or []
        print("\n== %s  (%d arrivals)" % (d, len(xs)))
        # One row per arrival: a run of the same bird with the same words
        # is one thing on screen, so it prints once with its length.
        rows = []
        for x in xs:
            nt = notes[id(x)]
            key = (x.sp, nt["stamp"], nt["line"])
            if rows and rows[-1][1] == key:
                rows[-1][2] += 1
            else:
                rows.append([x, key, 1])
        for x, (sp, st, ln), c in rows:
            print("  %s  %-26s %-4s %-18s %s" % (x.local.strftime("%H:%M"), sp[:26],
                                                 ("x%d" % c) if c > 1 else "", st.upper(), ln))


if __name__ == "__main__":
    main(sys.argv[1:])
