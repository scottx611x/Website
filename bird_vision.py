"""Per-image species assignment by actually LOOKING at the photos.

A caption naming N species for a post of M>N images can't say which image is
which bird — the info isn't in the text, so any caption-only heuristic guesses
(and drops species). This classifies each image against the caption's species
list using Claude vision on AWS Bedrock (the existing AWS creds — no separate
key). It's a CONSTRAINED classification: the model may only return species the
caption named (enforced by a tool schema enum), so no bird is invented and none
named vanishes. Results are cached per post; the curate editor still overrides.
"""
import io
import json
import os
import urllib.request

MODEL = os.environ.get("BIRD_VISION_MODEL", "us.anthropic.claude-sonnet-4-5-20250929-v1:0")
REGION = os.environ.get("AWS_REGION", "us-east-1")
_MAXPX = 512


def _load_jpeg(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    raw = urllib.request.urlopen(req, timeout=30).read()
    from PIL import Image
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    im.thumbnail((_MAXPX, _MAXPX))
    b = io.BytesIO(); im.save(b, "JPEG", quality=80)
    return b.getvalue()


def classify(image_urls, species, client=None):
    """Assign each image to one of `species`. Returns a list the same length as
    image_urls (each an item of `species`), or None on any failure — callers then
    fall back to the caption heuristic, so a Bedrock hiccup never breaks a sync."""
    species = [s for s in dict.fromkeys(species) if s]
    if len(image_urls) < 2 or len(species) < 2:
        return None  # unambiguous — nothing for vision to resolve
    try:
        import boto3
        br = client or boto3.client("bedrock-runtime", region_name=REGION)
        content = [{"text":
            "This is one Instagram carousel from a bird photographer. Its caption "
            "names exactly these species (order not guaranteed to match the "
            "images):\n- " + "\n- ".join(species) +
            f"\n\nThere are {len(image_urls)} images, given in order below. For "
            "EACH image, identify which of those species is the bird actually "
            "visible in it, and call the assign_species tool with one species per "
            "image, in image order. Only use species from the list above."}]
        for i, u in enumerate(image_urls):
            content.append({"text": f"Image {i}:"})
            content.append({"image": {"format": "jpeg", "source": {"bytes": _load_jpeg(u)}}})
        tool = {"toolSpec": {
            "name": "assign_species",
            "description": "Record the species visible in each image, in image order.",
            "inputSchema": {"json": {
                "type": "object",
                "properties": {"species": {
                    "type": "array",
                    "items": {"type": "string", "enum": species},
                    "minItems": len(image_urls), "maxItems": len(image_urls),
                }},
                "required": ["species"],
            }},
        }}
        resp = br.converse(
            modelId=MODEL,
            messages=[{"role": "user", "content": content}],
            inferenceConfig={"maxTokens": 600, "temperature": 0},
            toolConfig={"tools": [tool], "toolChoice": {"tool": {"name": "assign_species"}}},
        )
        for block in resp["output"]["message"]["content"]:
            if "toolUse" in block:
                out = block["toolUse"]["input"].get("species") or []
                if len(out) == len(image_urls) and all(s in species for s in out):
                    return out
        return None
    except Exception as e:  # noqa: BLE001 - never let vision break the pipeline
        print("bird_vision: classify failed:", e)
        return None


def needs_vision(shot, species):
    """A post worth classifying: 2+ images and 2+ distinct caption species (order
    and grouping across images is otherwise unknowable from the caption)."""
    return len(shot.get("images") or []) >= 2 and len({s for s in species if s}) >= 2


def backfill(shots, store, caption_species, force=False, limit=None, log=print):
    """Populate `store` (post_id -> per-image species list) for ambiguous posts
    that don't already have a cached result. Returns the number newly classified."""
    import boto3
    br = boto3.client("bedrock-runtime", region_name=REGION)
    done = 0
    for shot in shots:
        pid = shot.get("id")
        if not pid or (pid in store and not force):
            continue
        species = caption_species(shot.get("caption") or "")
        if not needs_vision(shot, species):
            continue
        result = classify(shot.get("images") or [], species, client=br)
        if result:
            store[pid] = result
            done += 1
            log("  vision %s: %s" % (pid, result))
        else:
            log("  vision %s: (unresolved — keeps caption heuristic)" % pid)
        if limit and done >= limit:
            break
    return done
