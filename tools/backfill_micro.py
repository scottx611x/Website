"""Make the filmstrip's micro copies (birds/thumbs/micro/<id>.jpg) for every
archived frame that has a thumb but no micro yet.

    BIRDS_USE_S3=1 .venv/bin/python tools/backfill_micro.py            # dry run
    BIRDS_USE_S3=1 .venv/bin/python tools/backfill_micro.py --write    # do it

The dry run lists what is missing and encodes a sample to estimate the total
size; nothing is written without --write. Each micro is made from the 640px
thumb (short side 160px, so the strip's square crop is never upscaled).
Idempotent: a rerun only fills what is still missing.
"""
import concurrent.futures
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import birds  # noqa: E402


def _names(s3, prefix):
    out = set()
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=birds.S3_BUCKET, Prefix=prefix):
        for o in page.get("Contents") or []:
            rest = o["Key"][len(prefix):]
            if "/" not in rest and rest.endswith(".jpg"):
                out.add(rest)
    return out


def main(argv):
    write = "--write" in argv
    s3 = birds._s3()
    thumbs = _names(s3, "%s/thumbs/" % birds.S3_PREFIX)
    micros = _names(s3, "%s/thumbs/micro/" % birds.S3_PREFIX)
    todo = sorted(thumbs - micros)
    print("thumbs %d, micros %d, missing %d" % (len(thumbs), len(micros), len(todo)))
    if not todo:
        return

    def make(name):
        data = s3.get_object(Bucket=birds.S3_BUCKET,
                             Key="%s/thumbs/%s" % (birds.S3_PREFIX, name))["Body"].read()
        return name, len(data), birds._make_micro(data)

    if not write:
        sample = todo[:: max(1, len(todo) // 25)][:25]
        with concurrent.futures.ThreadPoolExecutor(8) as ex:
            got = list(ex.map(make, sample))
        avg_in = sum(g[1] for g in got) / len(got)
        avg_out = sum(len(g[2]) for g in got) / len(got)
        print("sample of %d: thumb %.0f KB -> micro %.1f KB" % (len(got), avg_in / 1024, avg_out / 1024))
        print("would write %d objects, about %.1f MB, to s3://%s/%s/thumbs/micro/"
              % (len(todo), len(todo) * avg_out / 1048576, birds.S3_BUCKET, birds.S3_PREFIX))
        print("dry run: nothing written (pass --write)")
        return

    done = 0
    total = 0

    def put(name):
        _, _, body = make(name)
        s3.put_object(Bucket=birds.S3_BUCKET, Key="%s/thumbs/micro/%s" % (birds.S3_PREFIX, name),
                      Body=body, ContentType="image/jpeg",
                      CacheControl="public, max-age=31536000, immutable")
        return len(body)

    with concurrent.futures.ThreadPoolExecutor(8) as ex:
        for n in ex.map(put, todo):
            done += 1
            total += n
            if done % 200 == 0:
                print("  %d / %d" % (done, len(todo)))
    print("wrote %d micros, %.1f MB" % (done, total / 1048576))


if __name__ == "__main__":
    main(sys.argv[1:])
