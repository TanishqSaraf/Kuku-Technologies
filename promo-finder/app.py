"""Streamlit UI:  streamlit run app.py"""
import os
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from promo_finder.cli import run
from promo_finder.parse import fmt
from promo_finder import features as F

st.set_page_config(page_title="Promo Finder", layout="wide")
st.title("Promo Finder — find ad clips in microdrama screenplays")
st.caption("Upload a .zip of episode screenplays (timestamped .txt). The tool returns ranked 20-60 s promos "
           "with segment timestamps, hook, cliffhanger and QC flags. Nothing is stored after the session.")

with st.sidebar:
    up = st.file_uploader("Screenplays (.zip)", type=["zip"])
    provider = st.selectbox("LLM re-ranker", ["none (rules only, free)", "gemini", "groq", "openrouter",
                                              "openai", "anthropic", "ollama"])
    key = st.text_input("API key (only if an LLM is selected)", type="password")
    model = st.text_input("Model override (optional)")
    top = st.slider("Promos in shortlist", 5, 50, 25)
    k = st.slider("Candidates the LLM reviews", 5, 80, 40)
    go = st.button("Find promos", type="primary", disabled=up is None)

if go and up:
    prov = provider.split(" ")[0]
    if key:
        os.environ["PROMO_LLM_API_KEY"] = key
    with tempfile.TemporaryDirectory() as td:
        zp = Path(td) / "in.zip"
        zp.write_bytes(up.getvalue())
        with st.spinner("Reading scripts and scoring every 20-60 s window..."):
            res = run(str(zp), str(Path(td) / "out"), llm=prov, top=top, llm_top_k=k, model=model or None)
        files = {n: (Path(td) / "out" / n).read_bytes() for n in ("promos.csv", "promos.json", "report.md", "qc_report.md")}
    st.session_state["res"], st.session_state["files"] = res, files

if "res" in st.session_state:
    res, files = st.session_state["res"], st.session_state["files"]
    m = res["meta"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Episodes", m["episodes"]); c2.metric("Candidates scored", m["candidates"])
    c3.metric("Mode", m["mode"]); c4.metric("Runtime (s)", m["runtime_sec"])
    if m.get("llm_usage") and m["llm_usage"].get("errors"):
        st.warning(f"LLM errors on {m['llm_usage']['errors']} calls — those promos fell back to rule scores.")
    rows = []
    for p in res["shortlist"]:
        rows.append({"rank": p.rank, "type": p.kind, "sec": round(p.duration),
                     "segments": " | ".join(f"Ep{s.ep} {fmt(s.start)}-{fmt(s.end)}" for s in p.segments),
                     "hook": p.hook_event.text if p.hook_event else "",
                     "cliffhanger": p.cliff_event.text if p.cliff_event else "",
                     "why": p.why, "score": p.final_score, "flags": ", ".join(p.flags)})
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    d1, d2, d3, d4 = st.columns(4)
    d1.download_button("promos.csv", files["promos.csv"], "promos.csv")
    d2.download_button("promos.json", files["promos.json"], "promos.json")
    d3.download_button("report.md", files["report.md"], "report.md")
    d4.download_button("qc_report.md", files["qc_report.md"], "qc_report.md")
    st.subheader("Inspect a promo")
    pick = st.selectbox("Promo", [f"{p.rank}. {p.kind} {p.duration:.0f}s — {p.hook_event.text[:60] if p.hook_event else ''}"
                                  for p in res["shortlist"]])
    p = res["shortlist"][int(pick.split(".")[0]) - 1]
    st.write(f"**Why it works:** {p.why}  \n**QC flags:** {', '.join(p.flags) or 'none'}")
    for s in p.segments:
        st.markdown(f"**Episode {s.ep}  {fmt(s.start)} → {fmt(s.end)}**")
        lines = []
        for e in F.window(res["eps"][s.ep].events, s.start, s.end):
            if e.kind == "dialogue":
                lines.append(f"{fmt(e.start)}  {e.speaker}: {e.text}")
            elif e.kind in ("action", "sfx"):
                lines.append(f"{fmt(e.start)}  [{e.text}]")
        st.code("\n".join(lines), language=None)
    with st.expander("Quality report"):
        st.markdown(files["qc_report.md"].decode())
