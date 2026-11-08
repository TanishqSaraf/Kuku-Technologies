"""Generate and score promo candidates.

Four shapes:
  single      one continuous 20-60 s stretch of one episode
  jumpcut     two stretches of the same episode (skip the slow middle)
  continuation tail of episode N (its cliffhanger) + head of N+1 (payoff + new cliffhanger)
  premise     3 short beats across the series that sell the show's title premise
All cut points snap to shot boundaries and never split a line of dialogue.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from .parse import Episode, Event, fmt
from . import features as F

MIN_DUR, MAX_DUR = 20.0, 60.0
HOOK_MIN = 2.5          # beat intensity needed to be considered as an opening


@dataclass
class Segment:
    ep: int
    start: float
    end: float

    @property
    def dur(self):
        return self.end - self.start

    def to_dict(self):
        return {"episode": self.ep, "start": fmt(self.start), "end": fmt(self.end),
                "start_sec": round(self.start, 2), "end_sec": round(self.end, 2),
                "duration_sec": round(self.dur, 2)}


@dataclass
class Promo:
    kind: str
    segments: list[Segment]
    scores: dict = field(default_factory=dict)
    hook_event: Event | None = None
    cliff_event: Event | None = None
    why: str = ""
    hook_type: str = ""
    cliff_type: str = ""
    flags: list[str] = field(default_factory=list)
    rule_score: float = 0.0
    llm: dict | None = None
    final_score: float = 0.0
    rank: int = 0
    id: str = ""

    @property
    def duration(self):
        return sum(s.dur for s in self.segments)

    @property
    def episodes(self):
        return sorted({s.ep for s in self.segments})


# ------------------------------------------------------------------ snapping --
def _speech_at(ep: Episode, t: float) -> Event | None:
    for e in ep.events:
        if e.kind == "dialogue" and e.start < t - 0.05 and e.end > t + 0.05:
            return e
    return None


def snap_start(ep: Episode, t: float) -> float:
    cuts = [c for c in ep.cuts if t - 1.2 <= c <= t + 0.01]
    s = max(cuts) if cuts else max(0.0, t - 0.2)
    d = _speech_at(ep, s)
    if d is not None:                       # never open mid-sentence
        s = d.end if d.end <= t + 0.01 else d.start
    return round(max(0.0, s), 2)


def snap_end(ep: Episode, t: float) -> float:
    cuts = [c for c in ep.cuts if t - 0.01 <= c <= t + 1.5]
    e = min(cuts) if cuts else min(ep.duration, t + 0.3)
    d = _speech_at(ep, e)
    if d is not None:                       # never cut a line in half
        e = d.start if d.start >= t - 0.01 else d.end
    return round(min(ep.duration, e), 2)


# ------------------------------------------------------------------ labels ----
HOOK_NAMES = {"violence": "physical violence", "danger": "a life-or-death threat",
              "betrayal": "a betrayal", "reveal": "an identity reveal",
              "humiliation": "public humiliation", "romance": "a shock proposal or declaration"}
CLIFF_NAMES = [("action_in_progress", "a blow that is about to land"),
               ("arrival", "someone bursting in"),
               ("open_question", "an unanswered question"),
               ("villain_taunt", "a cruel line nobody has answered yet"),
               ("unfinished", "a line cut off mid-sentence"),
               ("stakes_line", "a reveal left hanging"),
               ("threat_or_promise", "a threat or vow not yet paid off"),
               ("shock_reaction", "a shocked reaction with no answer"),
               ("writer_marked", "the script's own cliffhanger beat")]


def hook_type_of(e: Event | None) -> str:
    if e is None:
        return "a slow open"
    _, why = F.event_intensity(e)
    lex = why.get("lex", {})
    if lex:
        return HOOK_NAMES[max(lex, key=lex.get)]
    if why.get("confront"):
        return "a direct confrontation"
    if why.get("sfx_impact"):
        return "a sudden impact"
    return "an emotional outburst"


def cliff_type_of(why: dict) -> str:
    for k, name in CLIFF_NAMES:
        if why.get(k):
            return name
    return "a tense beat"


def quote(e: Event | None, n: int = 70) -> str:
    if e is None:
        return ""
    t = e.text if len(e.text) <= n else e.text[: n - 1].rsplit(" ", 1)[0] + "…"
    return f"{e.speaker.title()}: \"{t}\"" if e.kind == "dialogue" else f"[{t}]"


# ------------------------------------------------------------------ scoring ---
def _clamp(x):
    return max(0.0, min(1.0, x))


def score_segments(eps: dict[int, Episode], segs: list[Segment], kind: str) -> Promo:
    first, last = segs[0], segs[-1]
    ev_first, ev_last = eps[first.ep].events, eps[last.ep].events
    h, h_e = F.hook_score(ev_first, first.start)
    c, c_why, c_e = F.cliff_score(ev_last, last.end)
    st_parts, pace_parts, body = [], [], []
    for s in segs:
        st, st_why = F.standalone_score(eps[s.ep].events, s.start, s.end)
        st_parts.append((st, st_why))
        p, gap = F.pace_score(eps[s.ep].events, s.start, s.end)
        pace_parts.append((p, gap))
        body += [F.event_intensity(e)[0] for e in F.window(eps[s.ep].events, s.start, s.end)]
    st = st_parts[0][0] if len(segs) == 1 else (st_parts[0][0] + sum(x[0] for x in st_parts[1:]) * 0.5) / (1 + 0.5 * (len(segs) - 1))
    pace = sum(p * s.dur for (p, _), s in zip(pace_parts, segs)) / max(sum(s.dur for s in segs), 1)
    top = sorted(body, reverse=True)[:3]
    bod = sum(top) / max(len(top), 1)
    dur = sum(s.dur for s in segs)

    parts = {"hook": _clamp(h / 8), "cliff": _clamp(c / 8), "standalone": _clamp((st - 2) / 5),
             "body": _clamp(bod / 9), "pace": _clamp((pace + 1) / 4)}
    w = {"hook": .35, "cliff": .30, "standalone": .15, "body": .10, "pace": .10}
    total = sum(parts[k] * w[k] for k in w) * 100
    if dur < 25 or dur > 50:
        total -= 2.0                                    # sweet spot is ~25-50 s
    total -= {"single": 0, "jumpcut": 4, "continuation": 3, "premise": 5}[kind]  # each cut costs a bit
    pr = Promo(kind=kind, segments=segs, hook_event=h_e, cliff_event=c_e,
               scores={k: round(v, 3) for k, v in parts.items()} |
                      {"raw_hook": round(h, 2), "raw_cliff": round(c, 2), "raw_standalone": round(st, 2),
                       "max_silence_sec": round(max(g for _, g in pace_parts), 1),
                       "cliff_signals": c_why, "standalone_signals": st_parts[0][1]})
    pr.rule_score = round(total, 2)
    pr.hook_type, pr.cliff_type = hook_type_of(h_e), cliff_type_of(c_why)
    pr.why = make_why(pr, st_parts[0][1])
    return pr


def make_why(p: Promo, st_why: dict) -> str:
    cold = ("relationships are spelled out on screen, so it plays cold"
            if st_why.get("stakes_words", 0) >= 2 else "needs a little context to land")
    shape = {"single": "", "jumpcut": " Jump cut skips the slow middle.",
             "continuation": " Pairs one episode's cliffhanger with the next episode's payoff.",
             "premise": " Sells the show's title premise in three beats."}[p.kind]
    return f"Opens on {p.hook_type} and cuts on {p.cliff_type}; {cold}.{shape}"


# ------------------------------------------------------------------ generators -
def _openers(ep: Episode, lo=0.0, hi=None) -> list[Event]:
    hi = ep.duration if hi is None else hi
    return [e for e in ep.events if e.kind != "camera" and lo <= e.start <= hi
            and F.event_intensity(e)[0] >= HOOK_MIN and not _continues(e)]


def _continues(e: Event) -> bool:
    """A line that finishes someone's previous sentence can't open a promo."""
    t = e.text.strip()
    return e.kind == "dialogue" and (t.startswith(("...", "…", "-", "—")) or (t[:1].islower()))


def _closers(ep: Episode, lo=0.0, hi=None) -> list[Event]:
    hi = ep.duration if hi is None else hi
    return [e for e in ep.events if e.kind != "camera" and lo <= e.end <= hi + 0.01]


def iou(a: Promo, b: Promo) -> float:
    inter = uni = 0.0
    for sa in a.segments:
        for sb in b.segments:
            if sa.ep == sb.ep:
                inter += max(0.0, min(sa.end, sb.end) - max(sa.start, sb.start))
    uni = a.duration + b.duration - inter
    return inter / uni if uni else 0.0


def nms(cands: list[Promo], keep: int, thr: float = 0.3) -> list[Promo]:
    out: list[Promo] = []
    for c in sorted(cands, key=lambda p: -p.rule_score):
        if all(iou(c, o) < thr for o in out):
            out.append(c)
        if len(out) >= keep:
            break
    return out


def singles(eps: dict[int, Episode], ep: Episode, keep=4) -> list[Promo]:
    cands, seen = [], set()
    for o in _openers(ep):
        s = snap_start(ep, o.start)
        for cl in _closers(ep, lo=o.start + MIN_DUR - 2, hi=o.start + MAX_DUR + 1):
            e = snap_end(ep, cl.end)
            if not (MIN_DUR <= e - s <= MAX_DUR) or (s, e) in seen:
                continue
            seen.add((s, e))
            cands.append(score_segments(eps, [Segment(ep.ep, s, e)], "single"))
    return nms(cands, keep)


def _beats_A(ep: Episode, lo=0.0, hi=None, min_d=6, max_d=30, top=12):
    """Opening segments: start on a hook, end right after an intense line."""
    out = []
    for o in _openers(ep, lo, hi):
        s = snap_start(ep, o.start)
        h, _ = F.hook_score(ep.events, s)
        for cl in ep.events:
            if cl.kind != "dialogue" or not (s + min_d <= cl.end <= s + max_d):
                continue
            e = snap_end(ep, cl.end)
            out.append((h + 0.4 * F.event_intensity(cl)[0], Segment(ep.ep, s, e)))
    out.sort(key=lambda x: -x[0])
    return [seg for _, seg in out[:top]]


def _beats_B(ep: Episode, lo=0.0, hi=None, min_d=6, max_d=35, top=12):
    """Closing segments: start on a strong beat, end on a cliffhanger."""
    out = []
    for o in _openers(ep, lo, hi):
        s = snap_start(ep, o.start)
        for cl in _closers(ep, lo=s + min_d, hi=s + max_d):
            e = snap_end(ep, cl.end)
            c, _, _ = F.cliff_score(ep.events, e)
            out.append((c + 0.3 * F.event_intensity(o)[0], Segment(ep.ep, s, e)))
    out.sort(key=lambda x: -x[0])
    return [seg for _, seg in out[:top]]


def jumpcuts(eps, ep: Episode, keep=2) -> list[Promo]:
    cands = []
    A, B = _beats_A(ep), _beats_B(ep)
    for a in A:
        for b in B:
            if b.start < a.end + 10:              # must actually skip something
                continue
            if not (MIN_DUR <= a.dur + b.dur <= MAX_DUR):
                continue
            cands.append(score_segments(eps, [a, b], "jumpcut"))
    return nms(cands, keep)


CONT_RX = re.compile(r"(picks up|directly follows|immediately|continu)", re.I)


def continuations(eps, ep: Episode, nxt: Episode, keep=1) -> list[Promo]:
    if not (CONT_RX.search(nxt.continuity) or any("CONTINUOUS" in e.heading.upper() for e in nxt.events[:3])):
        return []
    cands = []
    tail_A = []
    end_n = snap_end(ep, ep.duration)
    for o in _openers(ep, lo=ep.duration - 32, hi=ep.duration - 8):
        s = snap_start(ep, o.start)
        tail_A.append(Segment(ep.ep, s, end_n))
    for a in tail_A:
        for b in _beats_B(nxt, lo=0, hi=45, min_d=8, max_d=40):
            if MIN_DUR <= a.dur + b.dur <= MAX_DUR:
                p = score_segments(eps, [a, b], "continuation")
                # episode N+1 often re-plays N's last beat - don't show it twice
                ta = {e.text.lower() for e in F.window(ep.events, a.start, a.end) if e.kind == "dialogue"}
                tb = {e.text.lower() for e in F.window(nxt.events, b.start, b.end) if e.kind == "dialogue"}
                if ta & tb:
                    p.rule_score -= 8; p.flags.append("REPEATED_LINE")
                cands.append(p)
    return nms(cands, keep)


# --- premise montage ------------------------------------------------------------
SYNONYMS = {
    "married": ["marry", "married", "marrying", "wedding", "wed", "husband", "wife", "vow", "bride", "accept my hand", "ring"],
    "marry": ["marry", "married", "wedding", "husband", "wife", "bride"],
    "wife": ["wife", "married", "husband", "wedding"],
    "soldier": ["soldier", "veteran", "war", "scarred", "beggar", "sergeant", "penniless"],
    "broken": ["scar", "scarred", "beggar", "penniless", "nobody", "wounded"],
    "duke": ["duke", "your grace", "duchess", "heir", "title"],
    "ceo": ["ceo", "billionaire", "company", "boss"], "billionaire": ["billionaire", "rich", "fortune"],
    "king": ["king", "majesty", "throne", "crown"], "prince": ["prince", "highness", "royal"],
    "alpha": ["alpha", "pack", "wolf"], "luna": ["luna", "mate", "pack"], "heir": ["heir", "inherit", "fortune"],
    "revenge": ["revenge", "pay", "destroy", "vengeance"], "secret": ["secret", "hidden", "truth", "who are you"],
}
STOP = set("i a an the he she was is my his her of to and in on at for with by from it was were be".split())


def premise_terms(title: str) -> list[tuple[str, list[str]]]:
    """[(stem of the title word, synonyms), ...] in title order."""
    words = [w for w in re.findall(r"[a-z]+", title.lower()) if w not in STOP]
    groups = []
    for w in words:
        if w in SYNONYMS:
            groups.append((w[:max(4, len(w) - 3)], SYNONYMS[w]))
    return groups


def premise_montage(eps: dict[int, Episode], title: str, keep=2) -> list[Promo]:
    """Three beats that sell the title premise, in story order:
    setup (Ep 1-2) -> first title phrase (first third of the series) -> last title phrase, the twist
    (back half), with the twist beat ENDING on the line that says it. 4-16 s per beat, <= 60 s."""
    groups = premise_terms(title)
    if len(groups) < 2:
        return []
    first_g, last_g = groups[0], groups[-1]
    order = sorted(eps)
    n = len(order)

    def lines_of(epn, terms, stem, bonus=4):
        out = []
        for e in eps[epn].events:
            if e.kind != "dialogue" or _continues(e):
                continue
            tl = e.text.lower()
            if terms and not any(re.search(rf"\b{re.escape(t)}\b", tl) for t in terms):
                continue
            sc = F.event_intensity(e)[0]
            if stem and re.search(rf"\b{re.escape(stem)}\w*", tl):
                sc += bonus      # the show saying its own title word = the premise, stated
            out.append((sc, e))
        return out

    def opening_beat(e: Event, lines=2) -> Segment:   # starts on the line, runs a line or two on
        ep = eps[e.ep]
        s0 = snap_start(ep, e.start)
        ds = [x for x in ep.events if x.kind == "dialogue" and x.start >= e.start][:lines]
        end = min(max(x.end for x in ds), s0 + 14)
        return Segment(e.ep, s0, snap_end(ep, end))

    def closing_beat(e: Event) -> Segment:        # 1-2 lines of lead-in, ends on the line
        ep = eps[e.ep]
        prev = [x for x in ep.events if x.kind == "dialogue" and x.end <= e.start + 0.05][-2:]
        s0 = prev[0].start if prev and e.end - prev[0].start <= 14 else e.start
        return Segment(e.ep, snap_start(ep, s0), snap_end(ep, e.end))

    def top(cands, k=2):
        return [e for _, e in sorted(cands, key=lambda x: -x[0])[:k]]

    setups = top([c for epn in order[:2] for c in lines_of(epn, [], first_g[0])])
    mids = top([c for epn in order[2: max(4, n // 3)] for c in lines_of(epn, first_g[1], first_g[0], bonus=8)], 4)
    lasts = []
    for epn in order[n // 2:]:
        for sc, e in lines_of(epn, last_g[1], last_g[0]):
            if "?" in e.text or "!" in e.text:
                sc += 2
            lasts.append((sc, e))
    lasts = top(lasts, 3)
    out = []
    for a in setups:
        for b in mids:
            for c in lasts:
                if not ((a.ep, a.start) < (b.ep, b.start) < (c.ep, c.start)) or a.ep == b.ep:
                    continue
                segs = [opening_beat(a, 3), opening_beat(b), closing_beat(c)]
                if MIN_DUR <= sum(x.dur for x in segs) <= MAX_DUR:
                    out.append(score_segments(eps, segs, "premise"))
    return nms(out, keep, thr=0.5)


def generate(episodes: list[Episode], title: str = "") -> list[Promo]:
    eps = {e.ep: e for e in episodes}
    allp: list[Promo] = []
    order = sorted(eps)
    for i, n in enumerate(order):
        ep = eps[n]
        allp += singles(eps, ep)
        allp += jumpcuts(eps, ep)
        if i + 1 < len(order) and order[i + 1] == n + 1:
            allp += continuations(eps, ep, eps[n + 1])
    allp += premise_montage(eps, title or episodes[0].title)
    return allp
