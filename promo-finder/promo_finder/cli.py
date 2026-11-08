"""python -m promo_finder --input <folder or .zip> --out outputs [--llm gemini] [--top 25]"""
from __future__ import annotations

import argparse
import os
import tempfile
import time
import zipfile
from pathlib import Path

from .parse import load_dir
from .candidates import generate
from .evaluate import qc_flags, recall, cliff_detector_check
from .rank import finalize
from .report import write_all
from . import llm as L


def run(input_path: str, out: str, llm: str = "none", top: int = 25, llm_top_k: int = 40,
        reference: str | None = None, model: str | None = None) -> dict:
    t0 = time.time()
    src = Path(input_path)
    tmp = None
    if src.suffix.lower() == ".zip":
        tmp = tempfile.mkdtemp()
        with zipfile.ZipFile(src) as z:
            z.extractall(tmp)
        src = Path(tmp)
    episodes = load_dir(src)
    if not episodes:
        raise SystemExit(f"No screenplay .txt files found in {input_path}")
    eps = {e.ep: e for e in episodes}
    title = episodes[0].title or src.name
    promos = generate(episodes, title)
    usage = None
    for p in promos:
        p.flags = qc_flags(p, eps)
    ranked = finalize(promos, max(eps))           # diverse rule-based order
    if llm and llm != "none":
        # the LLM reviews the top of the *diverse* order, not 40 cuts of one scene
        promos, usage = L.rerank(ranked, eps, title, llm, top_k=llm_top_k, model=model)
        for p in promos:
            p.flags = qc_flags(p, eps)
        ranked = finalize(promos, max(eps))
    evals = {"cliff": cliff_detector_check(episodes)}
    if reference and Path(reference).exists():
        evals["recall"] = recall(ranked, reference)
    meta = {"title": title, "episodes": len(episodes), "candidates": len(promos),
            "mode": "rules" if llm in (None, "none") else f"rules+llm({llm})",
            "llm_usage": usage, "runtime_sec": round(time.time() - t0, 1)}
    shortlist = write_all(Path(out), ranked, eps, meta, evals, top)
    return {"meta": meta, "shortlist": shortlist, "ranked": ranked, "evals": evals, "eps": eps}


def main():
    ap = argparse.ArgumentParser(description="Find promo clips in microdrama screenplays")
    ap.add_argument("--input", required=True, help="folder of episode .txt files, or a .zip of them")
    ap.add_argument("--out", default="outputs")
    ap.add_argument("--llm", default=os.getenv("PROMO_LLM", "none"),
                    help="none | gemini | groq | openrouter | openai | ollama | openai_compat | anthropic | mock")
    ap.add_argument("--model", default=None, help="override the provider's default model id")
    ap.add_argument("--top", type=int, default=25, help="promos in the shortlist")
    ap.add_argument("--llm-top-k", type=int, default=40, help="how many rule-ranked candidates the LLM reviews")
    ap.add_argument("--reference", default=None, help="optional hand-picked reference json for recall")
    a = ap.parse_args()
    r = run(a.input, a.out, a.llm, a.top, a.llm_top_k, a.reference, a.model)
    m = r["meta"]
    print(f"{m['title']}: {m['episodes']} episodes, {m['candidates']} candidates, mode={m['mode']}, {m['runtime_sec']}s")
    if m["llm_usage"]:
        print("LLM usage:", m["llm_usage"])
    for p in r["shortlist"][:10]:
        segs = " + ".join(f"Ep{s.ep} {s.start:.1f}-{s.end:.1f}s" for s in p.segments)
        print(f"  {p.rank:>2}. [{p.final_score:5.1f}] {p.kind:12s} {p.duration:4.0f}s  {segs}")
    print(f"Wrote {a.out}/promos.json, promos.csv, report.md, qc_report.md, candidates_all.json")


if __name__ == "__main__":
    main()
