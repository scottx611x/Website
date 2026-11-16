"""Find where the bird is in every gallery frame, so the Live stage can crop
around it (birds.focus_point, templates/birds_live.html aim()).

    .venv/bin/python tools/bird_focus.py                    # dry run: count what is new
    .venv/bin/python tools/bird_focus.py --sheet out.jpg    # also draw a contact sheet
    .venv/bin/python tools/bird_focus.py --write            # detect and save to S3

Runs here, not on the Lambda: it needs OpenCV (pip install opencv-python-headless
numpy) and a COCO object detector, YOLOv5s as ONNX, fetched once into
~/.cache/birds/. COCO's "bird" class is preferred; any other animal class is
taken when no bird is found (a hawk read as a cat still marks where it is).

Output: birds/focus.json, {media id: [fx, fy, aspect, score] or null}. fx, fy
are fractions of the frame: the box's centre across, and 40% of the way down
the box (heads are near the top). null = looked, found nothing; it is not
retried. Only frames not already in the file are processed, so re-running is
cheap; --redo processes everything again.
"""
import io
import json
import os
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.environ.setdefault("BIRDS_USE_S3", "1")

import birds  # noqa: E402

MODEL_URL = "https://github.com/ultralytics/yolov5/releases/download/v7.0/yolov5s.onnx"
MODEL = os.path.expanduser("~/.cache/birds/yolov5s.onnx")
BIRD, ANIMALS = 14, set(range(14, 24))
_NET = None


def _net():
    global _NET
    if _NET is None:
        import cv2
        if not os.path.exists(MODEL):
            os.makedirs(os.path.dirname(MODEL), exist_ok=True)
            urllib.request.urlretrieve(MODEL_URL, MODEL + ".part")
            os.replace(MODEL + ".part", MODEL)
        _NET = cv2.dnn.readNetFromONNX(MODEL)
    return _NET


def detect(data):
    """JPEG bytes -> [fx, fy, aspect, score], or None when no animal is found."""
    import cv2
    import numpy as np
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return None
    h, w = img.shape[:2]
    s = 640 / max(h, w)
    nh, nw = int(h * s), int(w * s)
    canvas = np.full((640, 640, 3), 114, np.uint8)
    canvas[:nh, :nw] = cv2.resize(img, (nw, nh))
    net = _net()
    net.setInput(cv2.dnn.blobFromImage(canvas, 1 / 255, (640, 640), swapRB=True))
    out = net.forward()[0]
    cls = out[:, 5:].argmax(1)
    conf = out[:, 4] * out[np.arange(len(out)), 5 + cls]
    for pref in ({BIRD}, ANIMALS):
        m = np.isin(cls, list(pref)) & (conf > .25)
        if not m.any():
            continue
        boxes = [[float(x - bw / 2), float(y - bh / 2), float(bw), float(bh)]
                 for x, y, bw, bh in out[m, :4]]
        sc = conf[m].astype(float).tolist()
        keep = np.array(cv2.dnn.NMSBoxes(boxes, sc, .25, .45)).flatten()
        dets = sorted(((sc[i], boxes[i]) for i in keep), reverse=True)
        # The main bird: the biggest of the confident ones. A far bird in
        # the corner of a portrait is scenery.
        top = dets[0][0]
        c, (x, y, bw, bh) = max((d for d in dets if d[0] >= top * .6),
                                key=lambda d: d[1][2] * d[1][3])
        fx = min(1, max(0, (x + bw / 2) / s / w))
        fy = min(1, max(0, (y + bh * .4) / s / h))
        return [round(fx, 3), round(fy, 3), round(w / h, 4), round(c, 2)]
    return None


def _thumb_ids(s3):
    out = []
    pg = s3.get_paginator("list_objects_v2")
    for page in pg.paginate(Bucket=birds.S3_BUCKET, Prefix="{}/thumbs/".format(birds.S3_PREFIX),
                            Delimiter="/"):
        for o in page.get("Contents") or []:
            name = o["Key"].rsplit("/", 1)[-1]
            if name.endswith(".jpg"):
                out.append(name[:-4])
    return out


def _sheet(path, items):
    from PIL import Image, ImageDraw
    W, cols = 200, 8
    rows = (len(items) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * W, rows * W), "white")
    for k, (mid, data, pt) in enumerate(items):
        im = Image.open(io.BytesIO(data)).convert("RGB")
        im.thumbnail((W, W))
        d = ImageDraw.Draw(im)
        w, h = im.size
        vw = min(1, (412 / 915) * h / w) * w          # a phone stage's slice
        d.rectangle([(w - vw) / 2, 0, (w + vw) / 2, h - 1], outline=(255, 0, 0), width=2)
        if pt:
            cx = min(max(pt[0] * w, vw / 2), w - vw / 2)
            d.rectangle([cx - vw / 2, 0, cx + vw / 2, h - 1], outline=(0, 255, 0), width=2)
            d.ellipse([pt[0] * w - 5, pt[1] * h - 5, pt[0] * w + 5, pt[1] * h + 5],
                      fill=(255, 255, 0), outline=(0, 0, 0))
            d.text((4, 4), str(pt[3]), fill=(255, 255, 0))
        else:
            d.text((4, 4), "none", fill=(255, 0, 255))
        sheet.paste(im, ((k % cols) * W, (k // cols) * W))
    sheet.save(path, quality=85)


def main(argv):
    write, redo = "--write" in argv, "--redo" in argv
    sheet = argv[argv.index("--sheet") + 1] if "--sheet" in argv else None
    limit = int(argv[argv.index("--limit") + 1]) if "--limit" in argv else None
    s3 = birds._s3()
    table = {} if redo else dict(birds.focus_table(force=True))
    todo = [m for m in _thumb_ids(s3) if m not in table]
    print("%d frames, %d already done, %d to detect" % (len(todo) + len(table), len(table), len(todo)))
    if limit is not None:
        todo = todo[:limit]
    if not todo:
        return
    if not write and not sheet:
        print("dry run, nothing written (pass --write, or --sheet out.jpg to look)")
        return

    def fetch(mid):
        key = "{}/thumbs/{}.jpg".format(birds.S3_PREFIX, mid)
        return mid, s3.get_object(Bucket=birds.S3_BUCKET, Key=key)["Body"].read()

    found, seen, shown = 0, 0, []
    with ThreadPoolExecutor(8) as ex:
        for mid, data in ex.map(fetch, todo):
            pt = detect(data)
            table[mid] = pt
            seen += 1
            found += bool(pt and pt[3] >= birds.FOCUS_MIN_SCORE)
            if sheet and len(shown) < 96:
                shown.append((mid, data, pt))
            if seen % 200 == 0:
                print("  %d / %d" % (seen, len(todo)))
    print("found a bird in %d of %d" % (found, seen))
    if sheet:
        _sheet(sheet, shown)
        print("contact sheet: %s (red = middle crop, green = aimed crop)" % sheet)
    if write:
        s3.put_object(Bucket=birds.S3_BUCKET,
                      Key="{}/{}".format(birds.S3_PREFIX, birds.FOCUS_KEY),
                      Body=json.dumps(table, separators=(",", ":")).encode(),
                      ContentType="application/json", CacheControl="no-cache")
        print("wrote %s/%s (%d entries)" % (birds.S3_PREFIX, birds.FOCUS_KEY, len(table)))


if __name__ == "__main__":
    main(sys.argv[1:])
