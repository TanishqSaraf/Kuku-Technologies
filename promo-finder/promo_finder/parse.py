"""Parse Kuku-style timestamped microdrama screenplays into flat event lists.

Each block in the script looks like:
    **SPEAKER (Emotion, Emotion):**      or  **CAMERA:** / **ACTION:** / **SOUND FX:**
    Start: (MM:SS.ss) | End: (MM:SS.ss)
    text...
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from pathlib import Path

TS = r"(\d+):(\d+(?:\.\d+)?)"
HEADER_RE = re.compile(r"^\*\*(.+?):\*\*\s*$")
TIME_RE = re.compile(rf"Start:\s*\({TS}\)\s*\|\s*End:\s*\({TS}\)")
SCENE_RE = re.compile(r"^SCENE\s+(\d+)", re.I)
HEADING_RE = re.compile(r"^Scene heading:\s*(.+)$", re.I)
EP_RE = re.compile(r"^EPISODE NUMBER:\s*Episode\s*(\d+)", re.I)
LOGLINE_RE = re.compile(r"^EPISODE LOGLINE:\s*(.+)$", re.I)
CONT_RE = re.compile(r"^CONTINUITY NOTES:\s*(.+)$", re.I)

NON_DIALOGUE = {"CAMERA": "camera", "ACTION": "action", "SOUND FX": "sfx", "SFX": "sfx",
                "MUSIC": "sfx", "TEXT ON SCREEN": "action", "VO": "dialogue"}


def to_sec(m: str, s: str) -> float:
    return int(m) * 60 + float(s)


def fmt(t: float) -> str:
    m, s = divmod(max(t, 0.0), 60)
    return f"{int(m):02d}:{s:05.2f}"


@dataclass
class Event:
    id: str            # e.g. "E07-0042"
    ep: int
    idx: int
    kind: str          # camera | action | sfx | dialogue
    speaker: str       # "" for non-dialogue
    tags: list[str]    # emotion / delivery tags from the parenthetical
    text: str
    start: float
    end: float
    scene: int = 1
    heading: str = ""

    def to_dict(self):
        d = asdict(self)
        d["start_ts"], d["end_ts"] = fmt(self.start), fmt(self.end)
        return d


@dataclass
class Episode:
    ep: int
    title: str
    logline: str
    continuity: str
    events: list[Event] = field(default_factory=list)

    @property
    def duration(self) -> float:
        return max((e.end for e in self.events), default=0.0)

    @property
    def cuts(self) -> list[float]:
        """Shot boundaries (camera block starts/ends) = natural edit points."""
        pts = {0.0, self.duration}
        for e in self.events:
            if e.kind == "camera":
                pts.add(round(e.start, 2)); pts.add(round(e.end, 2))
        return sorted(pts)


def _split_header(h: str) -> tuple[str, str, list[str]]:
    """'LADY JULIANA (O.S.) (Trembling, Pleading)' -> (dialogue, 'LADY JULIANA', [...])."""
    base = h.split("(")[0].strip().upper()
    if base in NON_DIALOGUE:
        return NON_DIALOGUE[base], "", []
    parens = re.findall(r"\(([^)]*)\)", h)
    tags: list[str] = []
    for p in parens:
        if p.strip().upper() in {"O.S.", "V.O.", "OFF-SCREEN", "CONT'D", "O.S", "V.O"}:
            continue
        tags += [t.strip().lower() for t in re.split(r"[,/]", p) if t.strip()]
    return "dialogue", base, tags


def parse_text(raw: str, fallback_ep: int = 0, title: str = "") -> Episode:
    lines = raw.replace("\r\n", "\n").split("\n")
    ep_no, logline, cont = fallback_ep, "", ""
    scene, heading = 1, ""
    events: list[Event] = []
    i = 0
    while i < len(lines):
        ln = lines[i].strip()
        if (m := EP_RE.match(ln)):
            ep_no = int(m.group(1))
        elif (m := LOGLINE_RE.match(ln)):
            logline = m.group(1).strip()
        elif (m := CONT_RE.match(ln)):
            cont = m.group(1).strip()
        elif (m := SCENE_RE.match(ln)):
            scene = int(m.group(1))
        elif (m := HEADING_RE.match(ln)):
            heading = m.group(1).strip()
        elif (m := HEADER_RE.match(ln)):
            kind, speaker, tags = _split_header(m.group(1))
            # find timing line
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            tm = TIME_RE.search(lines[j]) if j < len(lines) else None
            if tm:
                start, end = to_sec(tm.group(1), tm.group(2)), to_sec(tm.group(3), tm.group(4))
                k, body = j + 1, []
                while k < len(lines) and lines[k].strip() and not HEADER_RE.match(lines[k].strip()) \
                        and not lines[k].startswith("---") and not SCENE_RE.match(lines[k].strip()):
                    body.append(lines[k].strip())
                    k += 1
                text = " ".join(body).strip().strip('"').strip("“”")
                events.append(Event(id="", ep=ep_no, idx=len(events), kind=kind, speaker=speaker,
                                    tags=tags, text=text, start=start, end=max(end, start),
                                    scene=scene, heading=heading))
                i = k
                continue
        i += 1
    events.sort(key=lambda e: (e.start, e.end))
    for n, e in enumerate(events):
        e.idx, e.ep, e.id = n, ep_no, f"E{ep_no:02d}-{n:04d}"
    return Episode(ep=ep_no, title=title, logline=logline, continuity=cont, events=events)


def load_dir(path: str | Path) -> list[Episode]:
    path = Path(path)
    files = sorted(p for p in path.rglob("*.txt"))
    eps = []
    for n, f in enumerate(files, 1):
        ep = parse_text(f.read_text(encoding="utf-8", errors="replace"), fallback_ep=n,
                        title=f.parent.name)
        if ep.events:
            eps.append(ep)
    eps.sort(key=lambda e: e.ep)
    return eps
