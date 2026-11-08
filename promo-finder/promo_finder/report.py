from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

from .parse import Episode, fmt
from .candidates import Promo
from . import features as F


def post_note(p: Promo, n_eps: int) -> str:
    e = min(p.episodes)
    tier = "Top-tier score" if p.final_score >= 80 else "Strong score" if p.final_score >= 70 else "Solid backup"
    if e <= max(5, n_eps // 10):
        where = f"from Ep {e}, so a new viewer lands right where the promo happens"
    elif e <= n_eps // 2:
        where = f"from Ep {e}; good mid-funnel promo once the opening promos are live"
    else:
        where = f"from Ep {e}; spoils later twists, so post after the early-episode promos"
    return f"{tier}; {where}."


def promo_dict(p: Promo, n_eps: int) -> dict:
    he, ce = p.hook_event, p.cliff_event
    return {
        "rank": p.rank, "id": p.id, "type": p.kind, "duration_sec": round(p.duration, 1),
        "segments": [s.to_dict() for s in p.segments],
        "hook": {"at": f"Ep{he.ep} {fmt(he.start)}" if he else None, "beat": he.text if he else None,
                 "speaker": he.speaker if he else None, "type": p.hook_type},
        "cliffhanger": {"at": f"Ep{ce.ep} {fmt(ce.start)}" if ce else None, "beat": ce.text if ce else None,
                        "speaker": ce.speaker if ce else None, "type": p.cliff_type},
        "why_it_works": p.why, "why_this_rank": post_note(p, n_eps),
        "score": p.final_score, "rule_score": p.rule_score, "post_priority": p.scores.get("post_priority"),
        "score_parts": {k: p.scores[k] for k in ("hook", "cliff", "standalone", "body", "pace")},
        "qc_flags": p.flags, "alternate_of": p.scores.get("alternate_of"), "llm": p.llm,
    }


def seg_str(p: Promo) -> str:
    return " | ".join(f"Ep{s.ep} {fmt(s.start)}-{fmt(s.end)}" for s in p.segments)


def write_all(out: Path, ranked: list[Promo], eps: dict[int, Episode], meta: dict, evals: dict, top_n: int):
    out.mkdir(parents=True, exist_ok=True)
    n_eps = max(eps)
    blocking = {"DURATION_OUT_OF_RANGE", "MID_LINE_CUT", "NO_HOOK_IN_FIRST_3S"}
    shortlist = [p for p in ranked if not (set(p.flags) & blocking) and "alternate_of" not in p.scores][:top_n]
    alts: dict[str, list[str]] = {}
    for p in ranked:
        if "alternate_of" in p.scores:
            alts.setdefault(p.scores["alternate_of"], []).append(seg_str(p))
    dicts = [promo_dict(p, n_eps) | {"alternate_cuts": alts.get(p.id, [])[:3]} for p in shortlist]
    (out / "promos.json").write_text(json.dumps(dicts, indent=2, ensure_ascii=False))
    (out / "candidates_all.json").write_text(json.dumps([promo_dict(p, n_eps) for p in ranked], indent=1, ensure_ascii=False))

    with open(out / "promos.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["rank", "id", "type", "duration_sec", "segments", "hook", "cliffhanger", "why_it_works",
                    "why_this_rank", "score", "qc_flags"])
        for p, d in zip(shortlist, dicts):
            w.writerow([p.rank, p.id, p.kind, d["duration_sec"], seg_str(p),
                        f'{d["hook"]["at"]}: {d["hook"]["beat"]}', f'{d["cliffhanger"]["at"]}: {d["cliffhanger"]["beat"]}',
                        p.why, d["why_this_rank"], p.final_score, ";".join(p.flags)])

    # human-readable report
    L = [f"# Promo picks — {meta['title']}", "",
         f"{meta['episodes']} episodes · {meta['candidates']} candidates scored · mode: `{meta['mode']}` · "
         f"runtime {meta['runtime_sec']}s", "",
         "Posting order = score + funnel bonus (early-episode promos first) with diversity "
         "(no back-to-back cuts of the same scene). Timestamps are episode-relative MM:SS.ss.", ""]
    for p, d in zip(shortlist, dicts):
        L += [f"## {p.rank}. {p.id} · {p.kind} · {p.duration:.0f}s · score {p.final_score}",
              f"**Segments:** {seg_str(p)}  ",
              f"**Hook ({p.hook_type}):** {d['hook']['at']} — {d['hook']['beat']}  ",
              f"**Cliffhanger ({p.cliff_type}):** {d['cliffhanger']['at']} — {d['cliffhanger']['beat']}  ",
              f"**Why it works:** {p.why}  ",
              f"**Why this rank:** {d['why_this_rank']}  ",
              f"**QC flags:** {', '.join(p.flags) or 'none'}  ",
              f"**Alternate cuts of this scene:** {'; '.join(alts.get(p.id, [])[:3]) or 'none'}", "", "<details><summary>Script inside the cut</summary>", "", "```"]
        for s in p.segments:
            L.append(f"--- Ep{s.ep} {fmt(s.start)}-{fmt(s.end)}")
            for e in F.window(eps[s.ep].events, s.start, s.end):
                if e.kind == "dialogue":
                    L.append(f"{fmt(e.start)} {e.speaker}: {e.text}")
                elif e.kind in ("action", "sfx"):
                    L.append(f"{fmt(e.start)} [{e.text[:110]}]")
        L += ["```", "</details>", ""]
    (out / "report.md").write_text("\n".join(L), encoding="utf-8")

    # QC report
    fc = Counter(f for p in shortlist for f in p.flags)
    fa = Counter(f for p in ranked for f in p.flags)
    Q = ["# Quality check", "", "## Flags on the shortlist", "",
         "| flag | shortlist | all candidates |", "|---|---|---|"]
    for f in sorted(set(fa) | set(fc)):
        Q.append(f"| {f} | {fc.get(f, 0)} | {fa.get(f, 0)} |")
    Q += ["", "## Shape mix", ""] + [f"- {k}: {v} shortlisted / {sum(1 for p in ranked if p.kind == k)} generated"
                                     for k, v in Counter(p.kind for p in shortlist).most_common()]
    Q += ["", f"Episodes covered by shortlist: {sorted({e for p in shortlist for e in p.episodes})}"]
    if "recall" in evals:
        Q += ["", "## Recall vs hand-picked reference moments", "", json.dumps(evals["recall"]["summary"]), "",
              "| ref | first matching rank | moment |", "|---|---|---|"]
        for k, v in evals["recall"]["detail"].items():
            Q.append(f"| {k} | {v['first_matching_rank']} | {v['label']} |")
    if "cliff" in evals:
        c = evals["cliff"]
        Q += ["", "## Cliffhanger detector vs writers' own marks (dialogue only, SFX hidden)", "",
              f"{c['labelled_endings']} labelled episode endings · precision {c['precision']} · recall {c['recall']} "
              f"(tp {c['tp']}, fp {c['fp']}, fn {c['fn']}, tn {c['tn']})", "",
              "Missed cliffhangers (writer marked, detector said no):", ""]
        for r in c["rows"]:
            if r["writer_says_cliffhanger"] and not r["predicted"]:
                Q.append(f"- Ep{r['episode']} score {r['dialogue_only_score']}: \"{r['last_line']}\"")
    (out / "qc_report.md").write_text("\n".join(Q), encoding="utf-8")
    (out / "run_meta.json").write_text(json.dumps(meta | {"evals_summary": {
        "recall": evals.get("recall", {}).get("summary"),
        "cliff": {k: v for k, v in evals.get("cliff", {}).items() if k != "rows"}}}, indent=2))
    return shortlist
