"""Make the filmstrip's micro copies (birds/thumbs/micro/<id>.jpg) for every
archived frame that has a thumb but no micro yet.

    BIRDS_USE_S3=1 .venv/bin/python tools/backfill_micro.py            # dry run
    BIRDS_USE_S3=1 .venv/bin/python tools/backfill_micro.py --write    # do it

The daily sync runs the same fill (birds.fill_missing_micros), so this is for
doing it now. The dry run only lists what is missing.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import birds  # noqa: E402


def main(argv):
    if "--write" not in argv:
        _, missing = birds.fill_missing_micros(limit=0)
        print("missing %d micros; dry run, nothing written (pass --write)" % missing)
        return
    made, missing = birds.fill_missing_micros()
    print("made %d of %d missing micros" % (made, missing))


if __name__ == "__main__":
    main(sys.argv[1:])
