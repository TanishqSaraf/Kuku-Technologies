"""Turn scored candidates into a posting order."""
from __future__ import annotations

from .candidates import Promo, iou

SERIOUS = {"WEAK_HOOK": 4, "NO_HOOK_IN_FIRST_3S": 6, "WEAK_CLIFFHANGER": 4, "ENDING_MAY_RESOLVE": 3,
           "NEEDS_CONTEXT": 3, "DEAD_AIR": 2, "MID_LINE_CUT": 8, "DURATION_OUT_OF_RANGE": 10,
           "REPEATED_LINE": 4, "MANY_CHARACTERS": 1}


def funnel_bonus(p: Promo, n_eps: int) -> float:
    """A viewer who taps an ad starts at episode 1. Promos drawn from early
    episodes promise what they'll see soon and spoil less."""
    e = min(p.episodes)
    if e <= max(5, n_eps // 10):
        return 6.0
    if e <= n_eps // 2:
        return 3.0
    if "LATE_SERIES_SPOILER_RISK" in p.flags:
        return -3.0
    return 0.0


def finalize(promos: list[Promo], n_eps: int, llm_weight: float = 0.5) -> list[Promo]:
    for p in promos:
        base = p.rule_score
        if p.llm and p.llm.get("ok"):
            base = (1 - llm_weight) * p.rule_score + llm_weight * p.llm["score"]
        pen = sum(SERIOUS.get(f, 0) for f in p.flags)
        p.final_score = round(base - pen, 2)
        p.scores["post_priority"] = round(p.final_score + funnel_bonus(p, n_eps), 2)
    # when an LLM reviewed the shortlist, reviewed promos rank ahead of unreviewed ones
    # (different score scales; unreviewed ones were below the shortlist cut anyway)
    if any(p.llm and p.llm.get("ok") for p in promos):
        for p in promos:
            if not (p.llm and p.llm.get("ok")):
                p.scores["post_priority"] -= 1000
    # greedy diverse ordering: avoid posting five cuts of the same scene back to back
    pool = sorted(promos, key=lambda p: -p.scores["post_priority"])
    chosen: list[Promo] = []
    alternates: list[Promo] = []
    while pool:
        best, best_v = None, -1e9
        for p in pool[:80]:
            v = p.scores["post_priority"]
            for c in chosen[-15:]:
                if set(p.episodes) & set(c.episodes):
                    v -= 5.0
                v -= 25.0 * iou(p, c)
            if v > best_v:
                best, best_v = p, v
        pool.remove(best)
        parent = next((c for c in chosen if iou(best, c) >= 0.4), None)
        if parent is not None:                 # same scene, different cut -> alternate, not a new promo
            best.scores["alternate_of"] = parent
            alternates.append(best)
        else:
            chosen.append(best)
    # make sure the shortlist shows every shape: lift the best premise montage into the top 20
    prem = [p for p in chosen if p.kind == "premise"]
    if prem and chosen.index(prem[0]) >= 20:
        chosen.remove(prem[0]); chosen.insert(19, prem[0])
    for i, p in enumerate(chosen + alternates, 1):
        p.rank = i
        p.id = f"P{i:03d}"
    for p in alternates:
        p.scores["alternate_of"] = p.scores["alternate_of"].id
    return chosen + alternates
