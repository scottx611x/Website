"""The Kindle sleep screen: starred birds, drawn for e-ink.

When it has Wi-Fi, the jailbroken Paperwhite reads /birds/kindle.json (the
latest POOL starred birds, newest first), downloads the ones it lacks from
/birds/kindle.png?frame=<key>, and shows a random one each time it sleeps. All the image work happens here, so the device only saves
files. The screen is 1072x1448 at 300ppi, shows 16 grays, and is portrait.
"""
import io

from PIL import Image, ImageDraw, ImageFont, ImageOps

import birds

WIDTH, HEIGHT = 1072, 1448
MARGIN = 56
GRAYS = 16  # the Paperwhite 3 panel shows 16 levels


POOL = 60  # birds the device holds at once; it shows a random one per sleep


def starred_frames(shots, starred):
    """Every starred still as (key, shot, index), newest post first.

    Frames of one post keep their carousel order. Videos are skipped because a
    still from a clip rarely makes a good wallpaper."""
    out = []
    for shot in shots:
        images = shot.get("images") or []
        videos = shot.get("image_videos") or []
        for i in range(len(images)):
            if i < len(videos) and videos[i]:
                continue
            key = birds.frame_star_key(shot, i)
            if key in starred:
                out.append((shot.get("timestamp") or "", -i, key, shot, i))
    out.sort(key=lambda t: t[:3], reverse=True)
    return [(key, shot, i) for _, _, key, shot, i in out]


def latest_keys(shots, starred):
    """Star keys of the pool, newest first: what the device should hold."""
    return [key for key, _, _ in starred_frames(shots, starred)[:POOL]]


def frame_for_key(shots, starred, key):
    """The _pseudo_frame for one starred key, or None if it is not starred
    (or is a video)."""
    for k, shot, i in starred_frames(shots, starred):
        if k == key:
            return birds._pseudo_frame(shot, i)[0]
    return None


def pick_frame(shots, starred, slot=0):
    """The ``slot``-th newest starred bird (0..POOL-1), so the device's pool is
    always the latest POOL stars. With fewer stars than that, slots wrap.
    Returns a _pseudo_frame dict, or None when nothing is starred."""
    frames = starred_frames(shots, starred)
    if not frames:
        return None
    _, shot, i = frames[slot % len(frames)]
    frame, _ = birds._pseudo_frame(shot, i)
    return frame


def _font(size):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow without FreeType sizing
        return ImageFont.load_default()


def _quantize(img):
    """Dither to the panel's 16 grays so gradients (sky, water) don't band."""
    palette = []
    for g in range(GRAYS):
        v = round(g * 255 / (GRAYS - 1))
        palette += [v, v, v]
    pal = Image.new("P", (1, 1))
    pal.putpalette(palette + [0, 0, 0] * (256 - GRAYS))
    return img.convert("RGB").quantize(palette=pal, dither=Image.Dither.FLOYDSTEINBERG).convert("L")


def _full_bleed_box(w, h, focus):
    """The crop box (l, t, r, b) that fills the screen around the bird, or None
    when the bird is too wide for a portrait slice of this photo.

    ``focus`` is birds.focus_point(): [fx, fy, aspect] plus, on newer entries,
    the bird's box size [bw, bh], all as fractions of the frame. Without it
    the crop is centred."""
    fx, fy = (focus[0], focus[1]) if focus else (0.5, 0.45)
    bw = focus[3] if focus and len(focus) >= 5 else 0
    ratio = WIDTH / HEIGHT
    if w / h > ratio:  # wider than the screen: slide a full-height slice across
        cw = h * ratio
        if bw * w > cw * 0.9:
            return None
        left = min(max(fx * w - cw / 2, 0), w - cw)
        return (left, 0, left + cw, h)
    ch = w / ratio  # taller: slide a full-width slice down
    top = min(max(fy * h - ch / 2, 0), h - ch)
    return (0, top, w, top + ch)


def render(photo_bytes, species="", date="", location="", focus=None):
    """PNG bytes for the sleep screen.

    The photo fills the screen, cropped around the bird, with the caption set
    over its foot in black with a white outline so it reads on any photo. When
    the bird is too wide to survive a portrait crop (a soaring hawk), the whole
    photo runs the full width with the caption underneath instead."""
    photo = ImageOps.exif_transpose(Image.open(io.BytesIO(photo_bytes))).convert("L")
    photo = ImageOps.autocontrast(photo, cutoff=0.5)
    canvas = Image.new("L", (WIDTH, HEIGHT), 255)
    draw = ImageDraw.Draw(canvas)

    title = species or ""
    sub = " · ".join(x for x in (location, date) if x)
    title_font, sub_font, handle_font = _font(56), _font(34), _font(26)

    box = _full_bleed_box(photo.width, photo.height, focus)
    if box:
        canvas.paste(photo.crop(tuple(round(v) for v in box))
                     .resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS), (0, 0))
        y = HEIGHT - 190
        ink, sub_ink, handle_ink, stroke = 0, 0, 40, 4
    else:
        scaled = ImageOps.contain(photo, (WIDTH, HEIGHT - 360))
        top = (HEIGHT - 300 - scaled.height) // 2
        canvas.paste(scaled, ((WIDTH - scaled.width) // 2, top))
        y = top + scaled.height + 60
        ink, sub_ink, handle_ink, stroke = 0, 80, 120, 0

    halo = dict(stroke_width=stroke, stroke_fill=255) if stroke else {}
    if title:
        draw.text((MARGIN, y), title, font=title_font, fill=ink, **halo)
        y += 74
    if sub:
        draw.text((MARGIN, y), sub, font=sub_font, fill=sub_ink, **halo)
    draw.text((WIDTH - MARGIN, HEIGHT - 28), "@birdsofnorthandover",
              font=handle_font, fill=handle_ink, anchor="rs",
              **(dict(stroke_width=3, stroke_fill=255) if stroke else {}))

    out = io.BytesIO()
    _quantize(canvas).save(out, "PNG", optimize=True)
    return out.getvalue()
