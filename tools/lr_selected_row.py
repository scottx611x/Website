"""Which sidebar row is highlighted, in logical screen y.

A click on a month row is silently dropped while Lightroom is still finishing
the previous export. The selection then stays put and the next Select All +
Export re-exports the SAME month -- which is how September, July, 2025 and
August each "exported 318 files", June's exact count.

The selected row draws a lighter plate than its neighbours, so find the
brightest run of rows in the sidebar column.
"""
import subprocess
import sys

from PIL import Image

SHOT = "/tmp/lrsel.png"
X0, X1 = 150, 430          # sidebar column, capture px (retina 2x)


def selected_row_y():
    subprocess.run(["screencapture", "-x", "-o", SHOT], capture_output=True)
    im = Image.open(SHOT).convert("L")
    rows = []
    for y in range(300, 1700, 2):
        band = [im.getpixel((x, y)) for x in range(X0, X1, 6)]
        rows.append((sum(band) / len(band), y))
    rows.sort(reverse=True)
    top = [y for _, y in rows[:14]]        # ~1 row tall at 2px sampling
    top.sort()
    runs, cur = [], [top[0]]
    for y in top[1:]:
        if y - cur[-1] <= 6:
            cur.append(y)
        else:
            runs.append(cur); cur = [y]
    runs.append(cur)
    best = max(runs, key=len)
    return ((best[0] + best[-1]) // 2) // 2


if __name__ == "__main__":
    print(selected_row_y())
