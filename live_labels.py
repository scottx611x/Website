"""The two pieces of text on the Live stage: a stamp and a line.

The stamp marks an occasion, and most birds get none. The line is one field
note about this species in this yard. Everything here is pure (no I/O) and
computed AS OF the recording: a fact only counts recordings made before it,
so the replay over past days reads what the page would have said then.

See docs/revamp/LIVE_LABELS_PLAN.md for the rules and the voice.
"""
import bisect
import collections
import datetime
import math

LAT, LON = 42.70, -71.13          # North Andover
STAGE_CONF = 0.75                 # the page's default hero threshold

_WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven",
          "eight", "nine", "ten", "eleven", "twelve"]
_ORD = ["zeroth", "first", "second", "third", "fourth", "fifth", "sixth",
        "seventh", "eighth", "ninth", "tenth", "eleventh", "twelfth"]
_IRREGULAR = {"titmouse": "titmice", "goose": "geese", "mouse": "mice"}


# ---------------------------------------------------------------- words

def num(n):
    """Numbers under thirteen are words; the rest get thousands commas."""
    return _WORDS[n] if 0 <= n < 13 else "{:,}".format(n)


def ordinal(n):
    """first..twelfth only; there is no 13th of anything on the stage."""
    return _ORD[n] if 1 <= n <= 12 else None


def common_word(display):
    """'Black-capped Chickadee' -> 'chickadee': the word people say."""
    return (display or "").split()[-1].lower() if display else ""


def plural(word):
    if word in _IRREGULAR:
        return _IRREGULAR[word]
    if word.endswith(("s", "sh", "ch", "x", "z")):
        return word + "es"
    if word.endswith("y") and word[-2:-1] not in "aeiou":
        return word[:-1] + "ies"
    return word + "s"


def a_an(word):
    return ("an " if word[:1] in "aeiou" else "a ") + word


def month_day(d, today):
    """'October 3', with the year only when it is not this year's."""
    s = "%s %d" % (d.strftime("%B"), d.day)
    return s if d.year == today.year else "%s, %d" % (s, d.year)


# ---------------------------------------------------------------- sun

def sun_times(day, lat=LAT, lon=LON):
    """(sunrise, sunset) for a date as aware UTC datetimes (NOAA's simple
    solar model, within a couple of minutes at this latitude)."""
    n = day.timetuple().tm_yday
    g = 2 * math.pi / 365 * (n - 1)
    eqt = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g)
                    - 0.014615 * math.cos(2 * g) - 0.040849 * math.sin(2 * g))
    dec = (0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g)
           - 0.006758 * math.cos(2 * g) + 0.000907 * math.sin(2 * g)
           - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g))
    la = math.radians(lat)
    ha = math.degrees(math.acos(math.cos(math.radians(90.833)) / (math.cos(la) * math.cos(dec))
                                - math.tan(la) * math.tan(dec)))
    midnight = datetime.datetime(day.year, day.month, day.day, tzinfo=datetime.timezone.utc)
    rise = midnight + datetime.timedelta(minutes=720 - 4 * (lon + ha) - eqt)
    sett = midnight + datetime.timedelta(minutes=720 - 4 * (lon - ha) - eqt)
    return rise, sett


_PARTS = ("night", "morning", "midday", "evening")
_PART_ORDER = {"morning": 0, "midday": 1, "evening": 2}
_USUAL = {"night": "after dark", "morning": "in the morning",
          "midday": "around midday", "evening": "late in the day"}


# ---------------------------------------------------------------- index

class _Rec(object):
    __slots__ = ("sp", "ts", "day", "local", "node", "conf", "part", "dark_by", "raw")


class LabelIndex(object):
    """Every recording, sorted, with the per-species lookups the notes need.
    Build once per log generation (it walks the log a few times)."""

    def __init__(self, rows, canon=None, photos=None):
        canon = canon or (lambda n: n)
        memo = {}
        self.photos = photos or {}       # display -> [capture dates], sorted
        recs, suns = [], {}
        for r in rows:
            t, raw = r.get("t") or "", r.get("common") or r.get("display") or ""
            if len(t) < 19 or not raw:
                continue
            try:
                local = datetime.datetime.fromisoformat(t)
            except ValueError:
                continue
            if local.tzinfo is None:
                continue
            if raw not in memo:
                memo[raw] = canon(raw)
            x = _Rec()
            x.sp, x.local, x.raw = memo[raw], local, r
            x.ts = local.timestamp()
            x.day = local.date()
            x.node = r.get("node") or ""
            x.conf = r.get("conf") or 0
            if x.day not in suns:
                suns[x.day] = tuple(s.timestamp() for s in sun_times(x.day))
            rise, sett = suns[x.day]
            x.dark_by = max(rise - x.ts, x.ts - sett)       # seconds outside daylight (<0: day)
            if x.dark_by > 0:
                x.part = "night"
            elif local.hour < 11:
                x.part = "morning"
            elif local.hour < 15:
                x.part = "midday"
            else:
                x.part = "evening"
            recs.append(x)
        recs.sort(key=lambda x: x.ts)
        self.recs = recs
        self.suns = suns
        by = collections.defaultdict(list)
        for x in recs:
            by[x.sp].append(x)
        self.by = by
        self.ts_by = {sp: [x.ts for x in xs] for sp, xs in by.items()}
        # Running per-part counts, so "share of its recordings before this
        # one" is two lookups, not a walk.
        self.cum = {}
        for sp, xs in by.items():
            run, c = [], dict.fromkeys(_PARTS, 0)
            for x in xs:
                c[x.part] += 1
                run.append(dict(c))
            self.cum[sp] = run
        # Per species, its days in order: where each day's recordings start in
        # by[sp], how many it made that day, and the best day before each one,
        # so facts() looks a day up instead of rescanning the bird's history.
        self.dayx = {}
        for sp, xs in by.items():
            days, start, best, top = [], [], [0], 0
            for k, x in enumerate(xs):
                if not days or x.day != days[-1]:
                    if days:
                        top = max(top, k - start[-1])
                        best.append(top)
                    days.append(x.day)
                    start.append(k)
            self.dayx[sp] = (days, start, best)
        # The day's stage opener: first stage-worthy recording after
        # sunrise - 90 min, so a lone owl at 3am is not "first bird of the day".
        self.opener = {}
        for x in recs:
            if x.conf >= STAGE_CONF and x.day not in self.opener:
                if x.ts >= suns[x.day][0] - 90 * 60 and x.local.hour < 12:
                    self.opener[x.day] = x
        # Companions: per day, how many of A's recordings had B within 60s,
        # and how many recordings each species made, so a pairing can be
        # tested against chance (busy birds overlap all day by accident).
        pairs = collections.defaultdict(collections.Counter)
        j = 0
        for i, x in enumerate(recs):
            while recs[j].ts < x.ts - 60:
                j += 1
            near = {y.sp for y in recs[j:i] if y.sp != x.sp}
            k = i + 1
            while k < len(recs) and recs[k].ts <= x.ts + 60:
                if recs[k].sp != x.sp:
                    near.add(recs[k].sp)
                k += 1
            for sp in near:
                pairs[(x.sp, sp)][x.day] += 1
        self.pairs = pairs
        self.daily = collections.defaultdict(collections.Counter)
        for x in recs:
            self.daily[x.sp][x.day] += 1
        self.by_audio = {x.raw["audio"]: x for x in recs if x.raw.get("audio")}
        self.by_t = {x.raw.get("t"): x for x in recs}

    def find(self, row):
        """The indexed record for a log row: by clip, else by time."""
        a = row.get("audio")
        if a and a in self.by_audio:
            return self.by_audio[a]
        return self.by_t.get(row.get("t"))

    # -------------------------------------------------- facts about x

    def facts(self, x):
        xs, tss = self.by[x.sp], self.ts_by[x.sp]
        i = bisect.bisect_left(tss, x.ts)
        while i < len(xs) and xs[i] is not x:
            i += 1
        days, start, best = self.dayx[x.sp]
        j = bisect.bisect_left(days, x.day)       # days[j] is x's own day
        before_today = days[:j]
        today = xs[start[j]:i + 1]
        cum = self.cum[x.sp][i - 1] if i else dict.fromkeys(_PARTS, 0)
        # streak: consecutive days up to and including today
        streak_start, d = x.day, x.day - datetime.timedelta(days=1)
        have = set(before_today)
        while d in have:
            streak_start, d = d, d - datetime.timedelta(days=1)
        return {
            "n_prior": i,
            "first_day": days[0],
            "prev_day": before_today[-1] if before_today else None,
            "visit_days": len(before_today) + 1,
            "k_today": len(today),
            "first_today": len(today) == 1,
            "first_dark_today": x.dark_by > 0 and not any(p.dark_by > 0 for p in today[:-1]),
            "best_day": best[j],
            "parts": cum,
            "streak_start": streak_start,
            "both": bool(x.node) and any(
                y.node and y.node != x.node and abs(y.ts - x.ts) < 20
                for y in xs[max(0, i - 6):i + 6]),
        }

    def companion(self, x):
        """A species that came within 60s of this one AND keeps company with
        it: over the last 28 days, together on 3+ days and at least four
        times as often as two birds calling at random would be."""
        lo, hi, best, seen = x.ts - 60, x.ts + 60, None, set()
        for sp, tss in self.ts_by.items():
            if sp != x.sp:
                i = bisect.bisect_left(tss, lo)
                if i < len(tss) and tss[i] <= hi:
                    seen.add(sp)
        start = x.day - datetime.timedelta(days=28)
        win = lambda c: sum(n for d, n in c.items() if start <= d < x.day)
        n_me = win(self.daily[x.sp])
        for sp in seen:
            c = self.pairs.get((x.sp, sp)) or {}
            days = sum(1 for d in c if start <= d < x.day)
            together = win(c)
            expect = n_me * win(self.daily[sp]) * 120.0 / (28 * 12 * 3600)
            if days >= 3 and together >= 5 and together >= 4 * max(expect, 0.25):
                lift = together / max(expect, 0.25)
                if best is None or lift > best[1]:
                    best = (sp, lift)
        return best[0] if best else None

    def last_photo(self, sp, before):
        ds = [d for d in self.photos.get(sp) or [] if d <= before]
        return ds[-1] if ds else None


# ---------------------------------------------------------------- notes

def stamp_for(x, f, idx):
    """(kind, text) for an occasion, or None. First match wins."""
    if f["n_prior"] == 0:
        return ("new", "new to the yard")
    if f["first_today"] and f["prev_day"] and (x.day - f["prev_day"]).days >= 21:
        return ("gap", "first since " + f["prev_day"].strftime("%b").lower() + " %d" % f["prev_day"].day)
    if f["first_today"] and f["visit_days"] in (2, 3):
        return ("visit", ordinal(f["visit_days"]) + " visit")
    if x.dark_by > 3600 and f["first_dark_today"] and f["n_prior"] >= 20 \
            and f["parts"]["night"] < 0.05 * f["n_prior"]:
        # Said about the bird, not the clock: the status line already says night.
        return ("night", ("early" if x.local.hour < 12 else "late") + " for " + a_an(common_word(x.sp)))
    if idx.opener.get(x.day) is x:
        return ("opener", "first bird of the day")
    if f["best_day"] >= 10 and f["k_today"] == f["best_day"] + 1:
        return ("biggest", "busiest day yet")
    return None


def line_candidates(x, f, idx, shot=False, raining=False):
    """[(kind, sentence)] for every field note that is true of x."""
    out, sp = [], x.sp
    word = common_word(sp)
    n = f["n_prior"]
    if not shot and n + 1 >= 25:
        out.append(("unshot", "Heard %s times. Never once photographed." % num(n + 1)))
    if shot:
        d = idx.last_photo(sp, x.day)
        if d:
            out.append(("photo", "Last photographed %s." % month_day(d, x.day)))
    if n >= 30:
        usual, share = max(f["parts"].items(), key=lambda kv: kv[1])
        if share >= 0.7 * n:
            if x.part == usual:
                kept = {"morning": "A morning bird, mostly heard before eleven.",
                        "midday": "Mostly heard in the middle of the day.",
                        "evening": "An evening bird, mostly heard late in the day.",
                        "night": "A night bird, mostly heard in the dark."}[usual]
                out.append(("habit", kept))
            else:
                if x.part == "night" and x.dark_by < 1800:
                    head = None                     # twilight is not "in the dark"
                elif x.part == "night":
                    head = "%s in the dark." % a_an(word).capitalize()
                elif usual == "night":
                    head = "%s by daylight." % a_an(word).capitalize()
                else:
                    early = _PART_ORDER[x.part] < _PART_ORDER[usual]
                    head = "%s for %s." % ("Early" if early else "Late", a_an(word))
                if head:
                    out.append(("offhabit", head + " It is usually heard %s." % _USUAL[usual]))
    mate = idx.companion(x)
    if mate:
        mw = common_word(mate)
        name = mate.lower() if mw == word else mw
        out.append(("company", "Came in with the %s." % plural(name)))
    if (x.day - f["streak_start"]).days >= 13:
        since = ("the mic went up" if (f["streak_start"] - idx.recs[0].day).days <= 2
                 else month_day(f["streak_start"], x.day))
        out.append(("regular", "Here every day since %s." % since))
    if f["n_prior"] and 0 < (x.day - f["first_day"]).days <= 30 \
            and (f["first_day"] - idx.recs[0].day).days > 7:    # not "since the mic went up"
        out.append(("arrival", "First heard here %s." % month_day(f["first_day"], x.day)))
    if f["both"]:
        out.append(("both", "Both mics caught this one."))
    if raining:
        out.append(("rain", "Singing in the rain."))
    return out


# A line may not repeat what the stamp already said.
_CLASH = {"new": {"arrival", "unshot"}, "gap": {"regular", "arrival"}, "visit": {"arrival"},
          "night": {"offhabit", "habit"}, "opener": set(),
          "biggest": set()}


# The most particular true thing goes first; the generic ones are what is
# left when a bird has nothing better to say today.
_RANK = ["offhabit", "company", "unshot", "arrival", "rain", "both", "habit", "regular", "photo"]


def note_for(x, idx, prev_kind=None, shot=False, raining=False, used=()):
    """{"stamp", "line", "kind"} for one recording. `used` is the kinds of
    line this species has already said today: each is said once, and a bird
    that has said everything goes quiet."""
    f = idx.facts(x)
    st = stamp_for(x, f, idx)
    cands = [c for c in line_candidates(x, f, idx, shot=shot, raining=raining)
             if (not st or c[0] not in _CLASH.get(st[0], set())) and c[0] not in used]
    fresh = [c for c in cands if c[0] != prev_kind] or cands
    fresh.sort(key=lambda c: _RANK.index(c[0]))
    line = fresh[0] if fresh else None
    return {"stamp": st[1] if st else "", "stampKind": st[0] if st else "",
            "line": line[1] if line else "", "kind": line[0] if line else ""}


def notes_for_stage(idx, xs, shot_of=lambda sp: False, raining_after=None):
    """Notes for stage-worthy recordings in time order.

    A run of the same bird is one arrival: it keeps its line (a nuthatch
    calling fifteen times must not flip between sentences) and only an
    occasion can add a stamp. A new bird never gets the previous bird's
    kind of line."""
    out, prev, prev_sp, run_note = {}, None, None, None
    said = collections.defaultdict(set)
    for x in sorted(xs, key=lambda x: x.ts):
        rain = bool(raining_after) and x.ts >= raining_after
        if (x.sp, x.day) == prev_sp and run_note is not None:
            f = idx.facts(x)
            st = stamp_for(x, f, idx)
            n = dict(run_note, stamp=st[1] if st else "", stampKind=st[0] if st else "")
            if st and n["kind"] in _CLASH.get(st[0], set()):
                n.update(line="", kind="")
            out[id(x)] = n
            continue
        n = note_for(x, idx, prev_kind=prev, shot=shot_of(x.sp), raining=rain,
                     used=said[(x.sp, x.day)])
        if n["kind"]:
            said[(x.sp, x.day)].add(n["kind"])
        out[id(x)] = n
        prev, prev_sp, run_note = (n["kind"] or prev), (x.sp, x.day), n
    return out
