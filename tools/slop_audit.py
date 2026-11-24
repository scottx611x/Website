#!/usr/bin/env python3
"""Count the stylistic habits that make the site read as machine-made.

Each line is a pattern and how often it appears in the templates and the site
stylesheet. Run it before and after a cleanup; the numbers should only go down.

    python tools/slop_audit.py            # totals
    python tools/slop_audit.py -v PATTERN # every hit for one row, by file:line
"""
import glob
import re
import sys

FILES = sorted(glob.glob("templates/*.html")) + ["static/css/site.css"]

CHECKS = {
    "backdrop blur": r"backdrop-filter",
    "box-shadow": r"box-shadow",
    "text-shadow": r"text-shadow",
    "gradients": r"(linear|radial)-gradient",
    "keyframes": r"@keyframes",
    "pill radius": r"border-radius:\s*(999|9999)px",
    "uppercase labels": r"text-transform:\s*uppercase",
    "tracked letters": r"letter-spacing:\s*\.?[0-9.]*[1-9][0-9.]*em",
    "mono family": r"var\(--mono\)",
    "hover lift/zoom": r"translateY\(-|scale\(1\.0[2-9]",
    "link arrows": r"→|&rarr;|↗|↓ ?<",
    "emoji": r"[\U0001F300-\U0001FAFF]",
    "banner comments": r"(/\*|<!--|//)\s*[=\-—]{4,}",
    "history comments": r"\b(replaces? the old|used to|no longer|is gone|was a|were a)\b",
}


def main(argv):
    verbose = argv[1:3] if len(argv) > 2 and argv[1] == "-v" else None
    texts = {f: open(f, encoding="utf-8").read() for f in FILES}
    for name, pat in CHECKS.items():
        if verbose and verbose[1] != name:
            continue
        rx = re.compile(pat, re.I)
        n = sum(len(rx.findall(t)) for t in texts.values())
        print(f"{name:<18}{n:>5}")
        if verbose:
            for f, t in texts.items():
                for i, line in enumerate(t.splitlines(), 1):
                    if rx.search(line):
                        print(f"  {f}:{i}: {line.strip()[:110]}")


if __name__ == "__main__":
    main(sys.argv)
