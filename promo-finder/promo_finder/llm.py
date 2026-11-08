"""Optional LLM re-ranking. Swap the model with environment variables only.

    PROMO_LLM=gemini|groq|openrouter|openai|ollama|openai_compat|anthropic|mock|none
    PROMO_LLM_MODEL=<model id>            (optional, preset default otherwise)
    PROMO_LLM_API_KEY=<key>               (or GEMINI_API_KEY / GROQ_API_KEY / OPENAI_API_KEY / ...)
    PROMO_LLM_BASE_URL=<url>              (only for openai_compat)

Guardrail: the model never types timestamps or quotes. It only returns IDs of
script events it was shown; we validate the IDs, re-snap the cut points with
the same rules as the rule engine, and fall back to the rule result if the
answer is malformed or the clip would leave 20-60 s.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .parse import Episode, fmt
from .candidates import Promo, Segment, snap_start, snap_end, score_segments, MIN_DUR, MAX_DUR

PRESETS = {
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "gemini-2.5-flash", "GEMINI_API_KEY"),
    "groq": ("https://api.groq.com/openai/v1", "llama-3.3-70b-versatile", "GROQ_API_KEY"),
    "openrouter": ("https://openrouter.ai/api/v1", "meta-llama/llama-3.3-70b-instruct:free", "OPENROUTER_API_KEY"),
    "openai": ("https://api.openai.com/v1", "gpt-4o-mini", "OPENAI_API_KEY"),
    "ollama": ("http://localhost:11434/v1", "llama3.1", ""),
    "openai_compat": (os.getenv("PROMO_LLM_BASE_URL", ""), "", ""),
    "anthropic": ("https://api.anthropic.com/v1", "claude-haiku-5-5", "ANTHROPIC_API_KEY"),
}

SYSTEM = """You are a senior promo editor for vertical microdrama ads (ReelShort / DramaBox style).
You judge whether a 20-60 second clip, cut straight from the show, will stop a stranger scrolling
TikTok/Instagram and make them need the next episode. A great promo:
- HOOK: something in the first 3 seconds that stops the scroll (slap, reveal, shocking line).
- CLIFFHANGER: it cuts at an unresolved moment, before the answer/blow/reveal lands.
- STANDALONE: a viewer who never saw the show understands who is wronging whom.
You are strict: most clips are a 4-6. Reserve 9-10 for clips you would post first.
Reply with JSON only."""

USER_TMPL = """SHOW: {title}
EPISODE CONTEXT: {loglines}

CANDIDATE PROMO ({kind}, {dur:.0f}s). Segments in play order:
{segs}

SCRIPT AROUND THE CANDIDATE (each beat has an ID; lines marked >> are inside the current cut):
{script}

Tasks:
1. Score hook, cliffhanger, standalone and overall from 0-10.
2. You MAY tighten the cut: choose start_id (first beat to show, from segment 1's script) and end_id
   (last beat to show, from the last segment's script). Only use IDs listed above. Keep the total 20-60 s.
3. hook_id = the beat that hooks in the first 3 s; cliff_id = the unresolved beat we cut on.
4. why = one line (max 25 words) on why it works, in plain English.
5. problems = list of short strings for anything that would make an editor reject it (or []).

JSON schema:
{{"hook":0-10,"cliffhanger":0-10,"standalone":0-10,"overall":0-10,
 "start_id":"E..-....","end_id":"E..-....","hook_id":"E..-....","cliff_id":"E..-....",
 "why":"...","problems":["..."]}}"""


def _line(e, inside: bool) -> str:
    who = f"{e.speaker} ({', '.join(e.tags)})" if e.kind == "dialogue" else e.kind.upper()
    mark = ">>" if inside else "  "
    return f"{mark} [{e.id}] {fmt(e.start)}-{fmt(e.end)} {who}: {e.text}"


def build_prompt(p: Promo, eps: dict[int, Episode], title: str) -> tuple[str, set[str], set[str]]:
    script, first_ids, last_ids = [], set(), set()
    for i, s in enumerate(p.segments):
        ep = eps[s.ep]
        script.append(f"--- Episode {s.ep} ---")
        for e in ep.events:
            if e.kind == "camera" or e.end < s.start - 12 or e.start > s.end + 8:
                continue
            script.append(_line(e, s.start - 0.05 <= e.start < s.end))
            if i == 0 and e.start < s.start + 20:
                first_ids.add(e.id)
            if i == len(p.segments) - 1 and e.end > s.end - 20:
                last_ids.add(e.id)
    segs = "\n".join(f"  {k+1}. Episode {s.ep} {fmt(s.start)}-{fmt(s.end)} ({s.dur:.0f}s)" for k, s in enumerate(p.segments))
    logl = " | ".join(f"Ep{n}: {eps[n].logline}" for n in p.episodes)
    return USER_TMPL.format(title=title, loglines=logl, kind=p.kind, dur=p.duration, segs=segs,
                            script="\n".join(script)), first_ids, last_ids


# ------------------------------------------------------------------ providers -
class Client:
    def __init__(self, provider: str, model: str | None = None, cache_dir: str = ".llm_cache"):
        self.provider = provider
        base, default_model, key_env = PRESETS.get(provider, ("", "", ""))
        self.base = (os.getenv("PROMO_LLM_BASE_URL") or base).rstrip("/")
        self.model = model or os.getenv("PROMO_LLM_MODEL") or default_model
        self.key = os.getenv("PROMO_LLM_API_KEY") or (os.getenv(key_env) if key_env else "") or ""
        self.cache = Path(cache_dir); self.cache.mkdir(exist_ok=True)
        self.usage = {"calls": 0, "cached": 0, "in_tokens": 0, "out_tokens": 0, "errors": 0}

    def _post(self, url, body, headers):
        req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.loads(r.read().decode())

    def chat(self, system: str, user: str) -> str:
        h = hashlib.sha256(f"{self.provider}|{self.model}|{system}|{user}".encode()).hexdigest()[:24]
        cp = self.cache / f"{h}.json"
        if cp.exists():
            self.usage["cached"] += 1
            return json.loads(cp.read_text())["text"]
        if self.provider == "mock":
            self.usage["calls"] += 1
            text = _mock_answer(user)
        else:
            text = self._call_with_retry(system, user)
        cp.write_text(json.dumps({"text": text}))
        return text

    def _call_with_retry(self, system, user, tries=4):
        for k in range(tries):
            try:
                return self._call(system, user)
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 502, 503) and k < tries - 1:
                    time.sleep(2 ** k * 3); continue       # free tiers rate-limit; back off
                raise

    def _call(self, system, user) -> str:
        self.usage["calls"] += 1
        if self.provider == "anthropic":
            r = self._post(f"{self.base}/messages",
                           {"model": self.model, "max_tokens": 600, "system": system,
                            "messages": [{"role": "user", "content": user}], "temperature": 0.2},
                           {"x-api-key": self.key, "anthropic-version": "2023-06-01",
                            "content-type": "application/json"})
            u = r.get("usage", {})
            self.usage["in_tokens"] += u.get("input_tokens", 0); self.usage["out_tokens"] += u.get("output_tokens", 0)
            return "".join(b.get("text", "") for b in r.get("content", []))
        headers = {"Content-Type": "application/json"}
        if self.key:
            headers["Authorization"] = f"Bearer {self.key}"
        body = {"model": self.model, "temperature": 0.2,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        r = self._post(f"{self.base}/chat/completions", body, headers)
        u = r.get("usage", {}) or {}
        self.usage["in_tokens"] += u.get("prompt_tokens", 0); self.usage["out_tokens"] += u.get("completion_tokens", 0)
        return r["choices"][0]["message"]["content"] or ""


def _mock_answer(user: str) -> str:
    """Deterministic fake editor used for offline tests of the plumbing. NOT a quality signal."""
    ids = re.findall(r">> \[(E\d+-\d+)\]", user)
    return json.dumps({"hook": 6, "cliffhanger": 6, "standalone": 6, "overall": 6,
                       "start_id": ids[0] if ids else "", "end_id": ids[-1] if ids else "",
                       "hook_id": ids[0] if ids else "", "cliff_id": ids[-1] if ids else "",
                       "why": "mock answer", "problems": []})


def parse_json(text: str) -> dict | None:
    text = re.sub(r"^```(json)?|```$", "", text.strip(), flags=re.M)
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


# ------------------------------------------------------------------ rerank ----
def review(client: Client, p: Promo, eps: dict[int, Episode], title: str) -> Promo:
    prompt, first_ids, last_ids = build_prompt(p, eps, title)
    try:
        ans = parse_json(client.chat(SYSTEM, prompt))
    except Exception as ex:                                  # network / auth / quota
        client.usage["errors"] += 1
        p.llm = {"ok": False, "error": str(ex)[:200]}
        return p
    if not ans:
        p.llm = {"ok": False, "error": "unparseable"}
        return p
    by_id = {e.id: e for n in p.episodes for e in eps[n].events}
    newp = p
    sid, eid = ans.get("start_id"), ans.get("end_id")
    if sid in first_ids and eid in last_ids and sid in by_id and eid in by_id:
        segs = [Segment(s.ep, s.start, s.end) for s in p.segments]
        segs[0].start = snap_start(eps[segs[0].ep], by_id[sid].start)
        segs[-1].end = snap_end(eps[segs[-1].ep], by_id[eid].end)
        if all(s.end - s.start >= 4 for s in segs) and MIN_DUR <= sum(s.dur for s in segs) <= MAX_DUR:
            if (segs[0].start, segs[-1].end) != (p.segments[0].start, p.segments[-1].end):
                newp = score_segments(eps, segs, p.kind)
                newp.flags = list(p.flags)
    overall = _num(ans.get("overall"))
    newp.llm = {"ok": overall is not None, "score": (overall or 0) * 10,
                "hook": _num(ans.get("hook")), "cliffhanger": _num(ans.get("cliffhanger")),
                "standalone": _num(ans.get("standalone")),
                "why": str(ans.get("why", ""))[:200], "problems": [str(x)[:80] for x in (ans.get("problems") or [])][:5],
                "adjusted_cut": newp is not p, "model": f"{client.provider}:{client.model}"}
    if ans.get("hook_id") in by_id:
        newp.hook_event = by_id[ans["hook_id"]]
    if ans.get("cliff_id") in by_id:
        newp.cliff_event = by_id[ans["cliff_id"]]
    if newp.llm["why"]:
        newp.why = newp.llm["why"]
    return newp


def _num(x):
    try:
        return max(0.0, min(10.0, float(x)))
    except (TypeError, ValueError):
        return None


def rerank(promos: list[Promo], eps: dict[int, Episode], title: str, provider: str,
           top_k: int = 40, workers: int = 4, model: str | None = None) -> tuple[list[Promo], dict]:
    client = Client(provider, model)
    shortlist = promos[:top_k]                 # caller passes promos already in rule order
    rest = [p for p in promos if p not in shortlist]
    with ThreadPoolExecutor(max_workers=1 if provider in ("gemini", "groq", "openrouter") else workers) as ex:
        reviewed = list(ex.map(lambda p: review(client, p, eps, title), shortlist))
    return reviewed + rest, client.usage | {"provider": provider, "model": client.model, "reviewed": len(shortlist)}
