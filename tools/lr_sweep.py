"""Unattended sweep of Lightroom's date sidebar: export every shoot day.

    BIRDS_USE_S3=1 .venv/bin/python tools/lr_sweep.py [--rows N] [--limit N]

Why a sweep and not targeting: the site's per-frame capture date is unreliable
(every frame in a multi-image post inherits one date), so "this day owes N
frames" does not survive contact with reality — sweeping all of May recovered
~32 frames against a predicted 99. Coverage terminates; targeting does not.

How it navigates, and why this way:

  * Clicking a day in the LEFT SIDEBAR scopes the grid to that day, which is
    what makes `Edit > Select All` safe. Without it Select All grabs all 5,534
    photos and Lightroom raises a modal that silently stacks.
  * Sidebar rows are a constant 28 logical px apart.
  * Arrow keys do NOT move the sidebar selection (they move the photo
    selection), so paging is done with real scroll-wheel events via Quartz.
  * Two dialogs can interrupt an export and BOTH are confirmations, not
    errors: "AI Update Required" and "Choose Export Location" (the latter
    appears when Export with Previous loses its destination). Confirming the
    location picker also re-establishes the destination.

Correctness does not depend on knowing which day was clicked: everything is
matched afterwards by content hash against the frames that still lack an
original, so an imprecise click costs time, never accuracy.
"""
import argparse
import os
import subprocess
import sys
import time

sys.path.insert(0, "/Users/scott/Website")

BIRBS = os.environ.get("BIRBS_DIR") or os.path.expanduser("~/Desktop/birbs")
SIDEBAR_X = 142
ROW_H = 28
TOP_ROW_Y = 180          # first day row under the sticky header
ROWS_PER_SCREEN = 21


def osa(script):
    return subprocess.run(["osascript", "-e", script],
                          capture_output=True, text=True)


def activate():
    osa('tell application "Adobe Lightroom" to activate')
    time.sleep(1.0)


def click(x, y):
    subprocess.run(["cliclick", "c:%d,%d" % (x, y)], capture_output=True)


def scroll(clicks, x=SIDEBAR_X, y=500):
    """Scroll the sidebar. Negative = down the list."""
    import Quartz
    subprocess.run(["cliclick", "m:%d,%d" % (x, y)], capture_output=True)
    time.sleep(0.2)
    for _ in range(abs(clicks)):
        ev = Quartz.CGEventCreateScrollWheelEvent(
            None, Quartz.kCGScrollEventUnitLine, 1, -3 if clicks > 0 else 3)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
        time.sleep(0.05)
    time.sleep(0.8)


def window_pos(name):
    r = osa('tell application "System Events" to tell process "Adobe Lightroom" '
            'to get position of window "%s"' % name)
    if r.returncode or not r.stdout.strip():
        return None
    try:
        x, y = [int(v.strip()) for v in r.stdout.strip().split(",")[:2]]
        return x, y
    except ValueError:
        return None


def dialogs():
    """Confirm anything blocking. Both dialogs mean 'yes, export'."""
    hit = False
    p = window_pos("AI Update Required")
    if p:
        click(p[0] + 405, p[1] + 321)
        hit = True
        time.sleep(1.5)
    p = window_pos("Choose Export Location")
    if p:
        click(p[0] + 743, p[1] + 417)
        hit = True
        time.sleep(1.5)
    return hit


def menu(bar, item):
    return osa('tell application "System Events" to tell process "Adobe Lightroom" '
               'to click menu item "%s" of menu 1 of menu bar item "%s" '
               'of menu bar 1' % (item, bar)).returncode == 0


def count():
    try:
        return len(os.listdir(BIRBS))
    except OSError:
        return -1


def export_row(y, idle_limit=90):
    activate()
    click(SIDEBAR_X, y)
    time.sleep(2.5)
    menu("Edit", "Select All")
    time.sleep(1.2)
    before = count()
    menu("File", "Export with Previous...")

    stable, last = 0, before
    for _ in range(idle_limit):
        time.sleep(10)
        dialogs()
        now = count()
        stable = stable + 1 if now == last else 0
        last = now
        if stable >= 3 and now > before:
            break
        if stable >= 6:
            break
    return last - before


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=ROWS_PER_SCREEN)
    ap.add_argument("--screens", type=int, default=1)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    total = 0
    done = 0
    for screen in range(args.screens):
        for i in range(args.rows):
            y = TOP_ROW_Y + i * ROW_H
            n = export_row(y)
            total += n
            done += 1
            print("  screen %d row %2d (y=%d): %d files   [running total %d]"
                  % (screen + 1, i + 1, y, n, total), flush=True)
            if args.limit and done >= args.limit:
                print("  limit reached")
                return
        scroll(-args.rows)      # page down one screenful of rows
        print("  --- scrolled to next screen ---", flush=True)


if __name__ == "__main__":
    main()
