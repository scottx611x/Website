#!/usr/bin/env python3
"""Side Yard store-and-forward INGEST (runs on the brain, in the birdnetlib venv).

The Zero records the mic to 30s AAC segments and rsyncs them here whenever its
flaky WiFi is up. This ingests each uploaded segment: run BirdNET on it, and for
every detection cut a clip + render the site-palette spectrogram, upload both to
S3, and append the detection (stamped with when it was actually RECORDED, from
the filename — not when it arrived) to detections.jsonl. sound_export.py merges
that file so Side Yard shows on /birds/live alongside Back Yard, correctly timed,
no matter how long the link was down.
"""
import datetime as dt
import glob
import json
import os
import re
import subprocess
import sys
from zoneinfo import ZoneInfo

INCOMING = os.path.expanduser(os.environ.get("SY_INCOMING", "~/sideyard/incoming"))
DONE = os.path.expanduser(os.environ.get("SY_DONE", "~/sideyard/done"))
OUT_JSONL = os.path.expanduser(os.environ.get("SY_DETECTIONS", "~/sideyard/detections.jsonl"))
NODE = os.environ.get("SY_NODE", "Side Yard")
TZ = ZoneInfo(os.environ.get("SY_TZ", "America/New_York"))
LAT = float(os.environ.get("SY_LAT", "42.70"))
LON = float(os.environ.get("SY_LON", "-71.13"))
MIN_CONF = float(os.environ.get("SY_MIN_CONF", "0.70"))
# Per-species overrides mirror BirdNET-Go (sirens read as screech-owl -> 0.9).
SPECIES_MIN = {"eastern screech-owl": 0.90}
KEEP_JSONL = int(os.environ.get("SY_KEEP", "4000"))

S3_BUCKET = os.environ.get("SOUND_BUCKET", "birds-scott-ouellette")
S3_CLIPS = "birds/sounds/clips/"

_SPEC_STOPS = [
    (0.00, (13, 18, 14)), (0.12, (15, 40, 27)), (0.30, (26, 84, 54)),
    (0.52, (47, 125, 79)), (0.74, (56, 224, 138)), (0.90, (150, 240, 180)),
    (1.00, (240, 250, 225)),
]


def render_spectrogram(wav_path, out_path, height=480, width=1200, max_hz=11000):
    """Site-palette spectrogram (ink->green->neon), matching sound_export.py."""
    import wave
    import numpy as np
    from PIL import Image
    with wave.open(wav_path) as w:
        rate, n = w.getframerate(), w.getnframes()
        raw = np.frombuffer(w.readframes(n), dtype=np.int16)
        if w.getnchannels() > 1:
            raw = raw.reshape(-1, w.getnchannels()).mean(axis=1)
    x = raw.astype(np.float64) / 32768.0
    if len(x) < 2100:
        x = np.pad(x, (0, 2100 - len(x)))
    nfft = 2048
    hop = max(1, (len(x) - nfft) // width)
    frames = np.lib.stride_tricks.sliding_window_view(x, nfft)[::hop] * np.hanning(nfft)
    mag = np.abs(np.fft.rfft(frames, axis=1)).T
    freqs = np.fft.rfftfreq(nfft, 1.0 / rate)
    f_hi = min(max_hz, rate / 2.0)
    log_f = np.geomspace(150.0, f_hi, height)
    mag_log = np.empty((height, mag.shape[1]))
    for t in range(mag.shape[1]):
        mag_log[:, t] = np.interp(log_f, freqs, mag[:, t])
    db = 20 * np.log10(mag_log + 1e-9)
    db -= np.median(db, axis=1, keepdims=True)
    norm = np.clip((db - 5.0) / 28.0, 0, 1) ** 0.55
    pos = np.array([p for p, _ in _SPEC_STOPS])
    rgb = np.array([c for _, c in _SPEC_STOPS], dtype=np.float64)
    img = np.stack([np.interp(norm, pos, rgb[:, i]) for i in range(3)], axis=-1)
    Image.fromarray(img[::-1].astype(np.uint8)).save(out_path, optimize=True)


def seg_start(path):
    """Recording start time from seg_YYYYMMDDTHHMMSS.aac (local wall clock)."""
    m = re.search(r"seg_(\d{8})T(\d{6})", os.path.basename(path))
    if not m:
        return None
    return dt.datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S").replace(tzinfo=TZ)


def run(cmd):
    return subprocess.run(cmd, capture_output=True).returncode == 0


def main():
    from birdnetlib import Recording
    from birdnetlib.analyzer import Analyzer
    import boto3

    os.makedirs(DONE, exist_ok=True)
    os.makedirs(os.path.dirname(OUT_JSONL), exist_ok=True)
    analyzer = Analyzer()
    s3 = boto3.client("s3")
    segs = sorted(glob.glob(os.path.join(INCOMING, "seg_*.aac")))
    if not segs:
        return
    new_rows = []
    for seg in segs:
        start = seg_start(seg)
        if not start:
            os.rename(seg, os.path.join(DONE, os.path.basename(seg)))
            continue
        try:
            rec = Recording(analyzer, seg, lat=LAT, lon=LON, date=start.date(),
                            min_conf=min(MIN_CONF, min(SPECIES_MIN.values(), default=MIN_CONF)))
            rec.analyze()
        except Exception as e:  # a corrupt/partial segment shouldn't stall the queue
            print("analyze failed %s: %s" % (seg, e), file=sys.stderr)
            os.rename(seg, os.path.join(DONE, os.path.basename(seg)))
            continue
        for d in rec.detections:
            conf = d["confidence"]
            common = d["common_name"]
            floor = SPECIES_MIN.get(common.lower(), MIN_CONF)
            if conf < floor:
                continue
            t = start + dt.timedelta(seconds=float(d["start_time"]))
            base = "%s_%dp_%s" % (re.sub(r"[^a-z0-9]+", "_", d["scientific_name"].lower()).strip("_"),
                                  round(conf * 100), t.astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
            m4a, png = base + ".m4a", base + "_v3.png"
            cs = max(0.0, float(d["start_time"]) - 1.5)  # ~9s window around the call
            wavp = "/tmp/%s.wav" % base
            m4ap = "/tmp/" + m4a
            pngp = "/tmp/" + png
            ok = run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-ss", "%.2f" % cs,
                      "-t", "9", "-i", seg, "-ac", "1", "-ar", "48000", wavp])
            if not ok:
                continue
            try:
                render_spectrogram(wavp, pngp)
            except Exception as e:
                print("spec failed %s: %s" % (base, e), file=sys.stderr)
                continue
            # Tame the Side Yard USB mic's poor SNR. loudnorm (content-aware) was
            # wrong here: it normalizes INTEGRATED loudness, so on a low-SNR mic it
            # pumps even the broadband hiss up to target — noise-only clips came out
            # at ~-28 dB, audibly "gainy". Instead: high-pass (rumble), afftdn
            # (knock down the broadband hiss), a FIXED moderate +22 dB (so quiet/
            # noisy clips STAY quiet rather than being normalized up), and a limiter
            # to catch loud calls. Measured: noise floor ~-38 dB — ~10 dB quieter
            # than loudnorm, while calls stay audible.
            run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", wavp,
                 "-af", ("highpass=f=250,afftdn=nr=20:nf=-50,"
                         "volume=22dB,alimiter=limit=0.9:attack=5:release=60"),
                 "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", m4ap])
            try:
                s3.upload_file(m4ap, S3_BUCKET, S3_CLIPS + m4a,
                               ExtraArgs={"ContentType": "audio/mp4"})
                s3.upload_file(pngp, S3_BUCKET, S3_CLIPS + png,
                               ExtraArgs={"ContentType": "image/png"})
            except Exception as e:
                print("s3 upload failed %s: %s" % (base, e), file=sys.stderr)
                continue
            finally:
                for f in (wavp, m4ap, pngp):
                    try:
                        os.remove(f)
                    except OSError:
                        pass
            new_rows.append({"common": common, "sci": d["scientific_name"],
                             "conf": round(conf, 3), "t": t.isoformat(timespec="seconds"),
                             "node": NODE, "audio": m4a, "spec": png})
        os.rename(seg, os.path.join(DONE, os.path.basename(seg)))

    if new_rows:
        with open(OUT_JSONL, "a") as fh:
            for r in new_rows:
                fh.write(json.dumps(r) + "\n")
        # trim the jsonl so it can't grow forever
        try:
            lines = open(OUT_JSONL).read().splitlines()
            if len(lines) > KEEP_JSONL:
                open(OUT_JSONL, "w").write("\n".join(lines[-KEEP_JSONL:]) + "\n")
        except OSError:
            pass
    # keep the "done" dir bounded (segments already analyzed + uploaded)
    old = sorted(glob.glob(os.path.join(DONE, "seg_*.aac")))[:-200]
    for f in old:
        try:
            os.remove(f)
        except OSError:
            pass
    print("ingested %d segments, %d new detections" % (len(segs), len(new_rows)))


if __name__ == "__main__":
    main()
