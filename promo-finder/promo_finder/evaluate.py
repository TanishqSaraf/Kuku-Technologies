"""Quality checks.

1. Automated QC flags on every promo (duration, hook timing, resolved ending,
   context-dependent opening, mid-line cuts, dead air, cast size).
2. Recall against a hand-picked reference list (eval/handpicked.json).
3. Cliffhanger-detector check against the writers' own marks: the SOUND FX /
   ACTION text at each episode's end says whether the writer meant a
   cliffhanger. We score endings with dialogue-only features (SFX hidden) and
   see if the detector agrees - this tells us how it will do on scripts
   that don't annotate music cues.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from .parse import Episode
from . import features as F
from .candidates import Promo, snap_end, _speech_at


def qc_flags(p: Promo, eps: dict[int, Episode]) -> list[str]:
    fl = list(dict.fromkeys(p.flags))
    if not (20 <= p.duration <= 60):
        fl.append("DURATION_OUT_OF_RANGE")
    first, last = p.segments[0], p.segments[-1]
    ev = eps[first.ep].events
    if p.hook_event is None:
        fl.append("NO_HOOK_IN_FIRST_3S")
    elif p.scores.get("raw_hook", 0) < 3:
        fl.append("WEAK_HOOK")
    beats = [e for e in F.window(ev, first.start, first.start + 3) if e.kind != "camera"]
    if not beats:
        fl.append("SILENT_OPEN")
    sig = p.scores.get("cliff_signals", {})
    if sig.get("resolution_penalty"):
        fl.append("ENDING_MAY_RESOLVE")
    if p.scores.get("raw_cliff", 0) < 2:
        fl.append("WEAK_CLIFFHANGER")
    st = p.scores.get("standalone_signals", {})
    if st.get("context_opener") or st.get("back_reference"):
        fl.append("NEEDS_CONTEXT")
    if st.get("many_speakers"):
        fl.append("MANY_CHARACTERS")
    if p.scores.get("max_silence_sec", 0) > 7:
        fl.append("DEAD_AIR")
    for s in p.segments:
        ep = eps[s.ep]
        if _speech_at(ep, s.start) or _speech_at(ep, s.end):
            fl.append("MID_LINE_CUT")
    # late-series promos give away the main twist
    if max(p.episodes) > 0.8 * max(eps):
        fl.append("LATE_SERIES_SPOILER_RISK")
    return list(dict.fromkeys(fl))


def _overlap(seg, ref):
    ep, a, b = ref
    if seg.ep != ep:
        return 0.0
    return max(0.0, min(seg.end, b) - max(seg.start, a))


def recall(promos: list[Promo], ref_path: str | Path, ks=(10, 20, 40, None)) -> dict:
    ref = json.loads(Path(ref_path).read_text())["items"]
    ranked = sorted(promos, key=lambda p: p.rank or 1e9)
    res, detail = {}, {}
    for item in ref:
        hit_rank = None
        for p in ranked:
            ok = any(_overlap(s, r) >= min(8.0, 0.4 * (r[2] - r[1])) for s in p.segments for r in item["segments"])
            if ok:
                hit_rank = p.rank
                break
        detail[item["id"]] = {"label": item["label"], "first_matching_rank": hit_rank}
    for k in ks:
        n = sum(1 for d in detail.values() if d["first_matching_rank"] is not None
                and (k is None or d["first_matching_rank"] <= k))
        res[f"recall@{k or 'all'}"] = f"{n}/{len(ref)}"
    return {"summary": res, "detail": detail}


WRITER_CLIFF = re.compile(r"(cliffhanger|ominous|cut\w* to black|abrupt|sting|suspense|heart-stopping|"
                          r"crescendo|into silence|unresolved|tension)", re.I)
WRITER_SOFT = re.compile(r"(warm|tender|gentle|peaceful|fades? out|fade-out|fading|melancholic|soft)", re.I)


def cliff_detector_check(episodes: list[Episode], threshold: float = 2.0) -> dict:
    rows = []
    for ep in episodes:
        tail = [e for e in ep.events if e.kind in ("sfx", "action", "camera") and e.start >= ep.duration - 8]
        txt = " ".join(e.text for e in tail)
        if WRITER_CLIFF.search(txt):
            label = 1
        elif WRITER_SOFT.search(txt):
            label = 0
        else:
            continue                       # writer gave no clear signal; skip
        # judge the episode's final spoken line, as if the script had no music/SFX notes
        ds = [e for e in ep.events if e.kind == "dialogue"]
        if not ds:
            continue
        end = snap_end(ep, ds[-1].end)
        sc, why, _ = F.cliff_score(ep.events, end, use_sfx=False)
        rows.append({"episode": ep.ep, "writer_says_cliffhanger": bool(label),
                     "dialogue_only_score": round(sc, 2), "predicted": sc >= threshold,
                     "signals": list(why), "last_line": ds[-1].text[:80]})
    tp = sum(r["predicted"] and r["writer_says_cliffhanger"] for r in rows)
    fp = sum(r["predicted"] and not r["writer_says_cliffhanger"] for r in rows)
    fn = sum((not r["predicted"]) and r["writer_says_cliffhanger"] for r in rows)
    tn = sum((not r["predicted"]) and not r["writer_says_cliffhanger"] for r in rows)
    return {"labelled_endings": len(rows), "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": round(tp / max(tp + fp, 1), 2), "recall": round(tp / max(tp + fn, 1), 2),
            "rows": rows}
