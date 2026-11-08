"""Cheap, explainable signals computed from the screenplay text.

Everything here is plain rules (no model), so it is free, deterministic and
fast enough to scan every possible window of every episode. The LLM stage
(llm.py) only re-ranks the shortlist this produces.
"""
from __future__ import annotations

import re
from .parse import Event

# --- delivery tags written by the screenwriter in the parenthetical -------------
HOT_TAGS = {
    "screaming": 3, "shrieking": 3, "roaring": 3, "hysterical": 3, "enraged": 3, "furious": 2.5,
    "outraged": 2.5, "horrified": 2.5, "shocked": 2.5, "terrified": 2.5, "panicked": 2.5,
    "frantic": 2.5, "devastated": 2, "betrayed": 2, "desperate": 2, "shouting": 2, "booming": 2,
    "thunderous": 2.5, "venomous": 2, "vicious": 2, "cruel": 2, "sadistic": 2.5, "menacing": 2,
    "threatening": 2, "sinister": 2, "chilling": 2, "deadly": 2, "lethal": 2, "dangerous": 2,
    "gloating": 1.5, "mocking": 1.5, "taunting": 1.5, "smug": 1, "scornful": 1.5,
    "contemptuous": 1.5, "accusing": 1.5, "accusatory": 1.5, "imperious": 1.5, "defiant": 1.2,
    "gasping": 2, "sobbing": 1.5, "weeping": 1.2, "heartbroken": 1.5, "stunned": 2,
    "incredulous": 1.5, "breathless": 1, "disbelieving": 1.5, "agonized": 2.5, "anguished": 2,
    "fierce": 1.2, "triumphant": 1.2, "unhinged": 3, "livid": 2.5, "derisive": 1.5,
    "vindictive": 1.5, "spiteful": 1.5, "callous": 1.5, "ruthless": 1.5, "cold": 0.8,
    "shaken": 1.5, "trembling": 1.0, "intense": 1.5, "demanding": 1.0, "urgent": 1.0, "alarmed": 1.5,
}
COOL_TAGS = {"gentle", "soft", "tender", "warm", "playful", "teasing", "amused", "reflective",
             "peaceful", "content", "fond", "sweet", "loving", "comforted", "relieved",
             "lighthearted", "smiling", "grateful", "humble", "polite", "nostalgic", "dry"}

# --- text lexicons (lowercase regex) -------------------------------------------
HOOK_LEX = {
    "violence": (3.0, r"\b(slap\w*|strik\w*|struck|punch\w*|whip\w*|riding crop|crop|shov\w*|drag\w*|"
                      r"seiz\w*|throat|tackl\w*|kick\w*|club|fling\w*|flung|throw\w*|thrown|hurl\w*|snatch\w*|"
                      r"yank\w*|smash\w*|trampl\w*|crush\w*|rip\w*|slam\w*|lung\w*|collaps\w*|blood\w*|bleed\w*|wound\w*|lacerat\w*|"
                      r"burn\w*|fire|flame\w*|inferno|blaze|explo\w*|detonat\w*|shatter\w*|"
                      r"branding|red-hot|searing|iron rod|knife|blade|sword|rifle|gun|shot)\b"),
    "danger": (2.5, r"\b(gallows|hang\w*|noose|execut\w*|kill\w*|die|dead|death|dying|poison\w*|"
                    r"arsenic|dungeon|chains?|chained|shackl\w*|arrest\w*|guards?|witch\w*)\b"),
    "betrayal": (2.0, r"\b(marrying|marry|married|wedding|altar|bride|groom|husband|wife|sister|"
                      r"fianc\w*|betray\w*|cheat\w*|abandon\w*|disown\w*|stole|steal|planted|lie|lying|liar)\b"),
    "reveal": (2.5, r"\b(duke|duchess|your grace|alive|imposter|traitor|who are you|"
                    r"you already know|it'?s you|his name|this ring|crest|heir|title)\b"),
    "romance": (2.0, r"\b(one knee|propos\w*|accept my hand|be my wife|kiss\w*|i love you|"
                     r"i loved you|my lawful wife|offering it back|ring)\b"),
    "humiliation": (1.5, r"\b(beggar|worthless|plain|nobody|gutter|rat|servant|maid|crawl|kneel|"
                         r"bow|disgrace\w*|humiliat\w*|discarded|penniless|place)\b"),
}
CLIFF_SFX = r"(cliffhanger|cut\w* to black|abrupt|ominous|sting|into silence|freez\w*|suspense|" \
            r"heart-stopping|crescendo|unresolved|holds? on|stops mere|millimeters)"
ARRIVAL = r"\b(door\w*|latch|bursts?|burst open|footsteps|someone is coming|creak\w*|knock\w*|pounding|"\
          r"emerg\w*|silhouett\w*|storm\w* in|steps through|enters|strides)\b"
THREAT_FUTURE = r"\b(will|shall|tomorrow|tonight|two days|before|hang\w*|die|execut\w*|coming|next|" \
                r"or|unless|until|if you|now|pay|settle|regret|destroy|revenge|vengeance|never)\b"
RESOLUTION = r"\b(embrac\w*|peaceful\w*|sleep\w*|relief|relieved|smil\w*|warm\w*|tender\w*|laugh\w*|" \
             r"fade[sd]?|fading|fade-out|hand-in-hand|safe|thank you|together|kiss\w*|rest\w*|" \
             r"comfort\w*|content|gentle|softly)\b"
VILLAIN_TAGS = {"cruel", "smug", "mocking", "gloating", "taunting", "sneering", "venomous", "vicious",
                "sadistic", "scornful", "derisive", "spiteful", "menacing", "threatening", "sinister", "malicious"}
CONTEXT_OPENERS = r"^(\.\.\.|…|and\b|but\b|so\b|then\b|he\b|she\b|it\b|that\b|they\b|this\b|" \
                  r"again\b|still\b|yes\b|no\b(?!\w))"
CONTEXT_REFS = r"\b(again|the other day|last time|remember|as i said|earlier)\b"
STAKES_WORDS = r"\b(sister|husband|wife|father|mother|son|daughter|fianc\w*|marry\w*|married|" \
               r"wedding|duke|duchess|family|maid|lady|soldier|veteran|beggar|witch)\b"


def _lex_hits(text: str) -> dict[str, float]:
    t = text.lower()
    out = {}
    for cat, (w, rx) in HOOK_LEX.items():
        n = len(re.findall(rx, t))
        if n:
            out[cat] = w * min(n, 2)
    return out


def event_intensity(e: Event) -> tuple[float, dict]:
    """How much a single beat grabs attention (0..~10) + why."""
    why: dict = {}
    s = 0.0
    if e.kind == "camera":
        return 0.0, why            # shot descriptions repeat the action; don't double count
    hits = _lex_hits(e.text)
    if e.kind == "dialogue" and "violence" in hits:
        # in speech, violent words are usually threats or figures of speech ("thrown yourself away")
        hits["danger"] = max(hits.get("danger", 0), hits.pop("violence"))
    if hits:
        why["lex"] = hits
        s += sum(hits.values())
    if e.kind == "dialogue":
        tag_score = sum(HOT_TAGS.get(t, 0) for t in e.tags)
        cool = sum(1 for t in e.tags if t in COOL_TAGS)
        s += min(tag_score, 5) - 1.5 * cool
        if tag_score:
            why["tags"] = [t for t in e.tags if t in HOT_TAGS]
        if "!" in e.text:
            s += 1.0
        if "?" in e.text:
            s += 0.5
        words = len(e.text.split())
        if 0 < words <= 7:
            s += 0.7                # short punchy lines read fast on a phone
        if re.match(r"^you\b", e.text.lower()) and ("!" in e.text or "?" in e.text):
            s += 1.0; why["confront"] = True
    elif e.kind == "sfx":
        if re.search(r"(slap|crack|crash|explo|scream|gasp|punch|thud|slam|bang|shatter)", e.text.lower()):
            s += 2.0; why["sfx_impact"] = True
    return max(s, 0.0), why


def window(events: list[Event], t0: float, t1: float) -> list[Event]:
    return [e for e in events if e.end > t0 + 1e-6 and e.start < t1 - 1e-6]


def hook_score(events: list[Event], t0: float, span: float = 3.0) -> tuple[float, Event | None]:
    """Strongest beat that starts inside the first `span` seconds of the clip."""
    best, best_e = 0.0, None
    for e in events:
        if e.kind == "camera" or e.start < t0 - 0.05 or e.start > t0 + span:
            continue
        sc, _ = event_intensity(e)
        sc *= 1.0 - 0.12 * max(0.0, e.start - t0)   # earlier is better
        if sc > best:
            best, best_e = sc, e
    return best, best_e


def last_line(events: list[Event], t1: float) -> Event | None:
    ds = [e for e in events if e.kind == "dialogue" and e.end <= t1 + 0.05]
    return ds[-1] if ds else None


def cliff_score(events: list[Event], t1: float, use_sfx: bool = True) -> tuple[float, dict, Event | None]:
    """Is the clip cut at an unresolved moment? Looks at the last ~5 s."""
    tail = [e for e in events if e.start >= t1 - 5.0 and e.start < t1 and e.kind != "camera"]
    why: dict = {}
    s = 0.0
    ll = last_line(events, t1)
    final_beat = tail[-1] if tail else ll
    if ll is not None and ll.end >= t1 - 6.0:
        t = ll.text.strip()
        tl = t.lower()
        if "?" in t[-60:]:
            s += 3.0; why["open_question"] = True
        if t.endswith("...") or t.endswith("—") or t.endswith("-"):
            s += 2.0; why["unfinished"] = True
        if re.search(THREAT_FUTURE, tl):
            s += 1.5; why["threat_or_promise"] = True
        if len(t.split()) <= 3 and ("?" in t or "!" in t or any(x in HOT_TAGS for x in ll.tags)):
            s += 1.5; why["shock_reaction"] = True
        hits = _lex_hits(t)
        if hits.get("reveal") or hits.get("danger") or hits.get("romance") or hits.get("violence"):
            s += 1.5; why["stakes_line"] = list(hits)
        s += min(sum(HOT_TAGS.get(x, 0) for x in ll.tags), 3) * 0.5
        if set(ll.tags) & VILLAIN_TAGS and not t.endswith("?"):
            s += 1.5; why["villain_taunt"] = True     # cut on the cruel line, before anyone answers it
    for e in tail:
        tl = e.text.lower()
        if e.kind in ("sfx", "action") and use_sfx and re.search(CLIFF_SFX, tl):
            s += 3.0; why["writer_marked"] = True
        if e.kind in ("sfx", "action") and re.search(ARRIVAL, tl):
            s += 1.5; why["arrival"] = True
        if e.kind == "action" and re.search(r"(raises|hoists|lunges|thrusts|grabs|drags|lifts .* (rod|club|crop))", tl):
            s += 1.5; why["action_in_progress"] = True
    res = 0
    for e in tail:
        if e.kind == "dialogue" and not any(t in HOT_TAGS for t in e.tags):
            res += len(re.findall(RESOLUTION, e.text.lower())) + sum(1 for t in e.tags if t in COOL_TAGS)
        elif e.kind != "dialogue":
            res += len(re.findall(RESOLUTION, e.text.lower()))
    if res:
        s -= 1.5 * min(res, 3); why["resolution_penalty"] = res
    return s, why, final_beat


def standalone_score(events: list[Event], t0: float, t1: float) -> tuple[float, dict]:
    ws = window(events, t0, t1)
    ds = [e for e in ws if e.kind == "dialogue"]
    why: dict = {}
    s = 5.0
    if ds:
        first = ds[0].text.strip().lower()
        if re.match(CONTEXT_OPENERS, first):
            s -= 2.0; why["context_opener"] = ds[0].text[:40]
        if re.search(CONTEXT_REFS, " ".join(d.text.lower() for d in ds[:3])):
            s -= 1.0; why["back_reference"] = True
    speakers = {d.speaker for d in ds}
    if len(speakers) > 4:
        s -= 0.8 * (len(speakers) - 4); why["many_speakers"] = len(speakers)
    stakes = len(set(re.findall(STAKES_WORDS, " ".join(d.text.lower() for d in ds))))
    s += min(stakes, 4) * 0.6
    why["stakes_words"] = stakes
    return s, why


def pace_score(events: list[Event], t0: float, t1: float) -> tuple[float, float]:
    """Penalise dead air: longest stretch without dialogue or impact SFX."""
    pts = sorted([(e.start, e.end) for e in window(events, t0, t1)
                  if e.kind == "dialogue" or (e.kind in ("sfx", "action") and event_intensity(e)[0] > 0)])
    gap, cur = 0.0, t0
    for a, b in pts:
        gap = max(gap, a - cur)
        cur = max(cur, b)
    gap = max(gap, t1 - cur)
    dur = max(t1 - t0, 1)
    talk = sum(min(b, t1) - max(a, t0) for a, b in pts) / dur
    s = 3.0 * min(talk, 0.8) / 0.8 - max(0.0, gap - 4.0) * 0.6
    return s, gap
