from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import mm

OUT = "/home/claude/Kuku_Problem1_Promo_Finder.pdf"
doc = SimpleDocTemplate(OUT, pagesize=A4, leftMargin=14*mm, rightMargin=14*mm, topMargin=11*mm, bottomMargin=10*mm,
                        title="Kuku AI Generalist - Problem 1: Find the Promos")
ss = getSampleStyleSheet()
B = ParagraphStyle("b", parent=ss["Normal"], fontName="Helvetica", fontSize=9.1, leading=11.4, spaceAfter=2)
S = ParagraphStyle("s", parent=B, fontSize=7.4, leading=9)
H = ParagraphStyle("h", parent=B, fontName="Helvetica-Bold", fontSize=10.2, leading=12.2, spaceBefore=6, spaceAfter=2,
                   textColor=colors.HexColor("#1f3a5f"))
T = ParagraphStyle("t", parent=B, fontName="Helvetica-Bold", fontSize=13, leading=15.5, spaceAfter=1)
BL = ParagraphStyle("bl", parent=B, leftIndent=8, bulletIndent=0)


def p(t, st=B): return Paragraph(t, st)
def bl(items): return [Paragraph(i, BL, bulletText="•") for i in items]


def table(rows, widths, head=True, font=7.9):
    st = ParagraphStyle("c", parent=B, fontSize=font, leading=font + 1.6, spaceAfter=0)
    sth = ParagraphStyle("ch", parent=st, fontName="Helvetica-Bold")
    data = [[Paragraph(str(c), sth if (head and i == 0) else st) for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=[w*mm for w in widths], repeatRows=1)
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#b8c2cc")),
                           ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef4") if head else colors.white),
                           ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 3),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 3), ("TOPPADDING", (0, 0), (-1, -1), 1.5),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5)]))
    return t


s = []
s.append(p("Problem 1: Find the Promos. A screenplay-to-promo finder", T))
s.append(p("[Name] · [Roll no.] · [Branch] · Prototype: [repo link] · Raw outputs: [Drive link] · Video: [optional]", S))

s.append(p("Why this problem", H))
s.append(p("It is the one with a real input pack and a checkable output: every promo is a set of timestamps an editor can "
           "open and judge in seconds. The pain is volume. An editor watches every episode of every weekly show, but the "
           "screenplays already hold most of what that editor looks for (who is cruel to whom, which line is shouted, where "
           "the writer put the cliffhanger sting). So the tool reads the script, not the video, and hands the editor a ranked "
           "shortlist to check rather than 50 episodes to watch."))

s.append(p("Assumptions (the brief was silent)", H))
s += bl([
    "Timestamps are <b>episode-relative</b> and the script timings match the final cut closely enough to pick cut points; "
    "the editor trims frames. Script ≠ footage: a beat that reads big may play small.",
    "<b>Hook = a beat that starts in the first 3 s of the clip</b>; cliffhanger = the last ~5 s is unresolved. Clips are "
    "20–60 s in total; 25–50 s is preferred. A promo may join up to 3 segments, always in story order.",
    "An ad viewer who taps lands on <b>Ep 1</b>. Promos from early episodes therefore convert and spoil less, so they post "
    "first. Late-twist promos go to retargeting. The show title already gives away \"He was a Duke\".",
    "Same script format for every show (CAMERA / ACTION / SOUND FX / CHARACTER (tags) + Start/End). New formats need only a new parser.",
])

s.append(p("How it works: code does the searching, AI does the taste, a human signs off", H))
s.append(table([
    ["Step", "Who does it", "What happens"],
    ["1 Parse", "Code", "3,727 timestamped events from 50 episodes; CAMERA blocks give the shot cuts."],
    ["2 Generate", "Code", "Every 20–60 s window plus jump cuts within an episode, Ep N cliffhanger + Ep N+1 payoff, and a 3-beat "
     "<i>premise montage</i> built from the title (setup → \"married\" → \"Duke\"). Cuts snap to shot boundaries and never split a line."],
    ["3 Score", "Rules (free)", "Hook 35%, cliffhanger 30%, standalone 15%, peak intensity 10%, pace 10%. Signals: writer's delivery tags "
     "(furious, gloating…), violence/danger/betrayal/reveal words, open questions, threats, arrivals, a blow about to land, "
     "an unanswered cruel line, the writer's cliffhanger cue; penalties for resolution words, context openers, >4 speakers, dead air."],
    ["4 Re-rank", "LLM (optional)", "Reviews the top 40 and may tighten the cut, but can only answer with <b>event IDs it was shown</b>. IDs are "
     "validated, re-snapped and kept within 20–60 s, else it falls back to the rule result. It cannot invent timestamps or quotes. "
     "Model is one flag: <font face='Courier'>--llm gemini | groq | openai | anthropic | ollama | openai_compat</font>; responses are cached."],
    ["5 Rank + QC", "Code", "Score − QC penalties + funnel bonus; diversity ordering; near-duplicate cuts become \"alternate cuts\". "
     "Flags per promo: weak hook/cliffhanger, may resolve, needs context, dead air, spoiler risk."],
    ["6 Approve", "Editor", "Picks from the shortlist in a Streamlit UI or CSV, watches the footage, trims frames."],
], [19, 20, 143]))

s.append(p("What it found (rules only, full pack, 3.7 s, 260 candidates → 25-promo shortlist)", H))
s.append(table([
    ["#", "Segments", "Hook (first 3 s)", "Cliffhanger (cut on)"],
    ["9", "Ep3 00:58.20–01:28.10", "\"Guards! Remove her!\" She is dragged from the church", "Stranger drops a guard → \"He's only one man!\""],
    ["4", "Ep12 00:26.80–01:09.50", "\"You planted it!\"", "\"Fail, or refuse, and your husband hangs from the gallows.\""],
    ["1", "Ep24 00:32.80–01:10.50", "Riding-crop strike", "\"Do you want the same punishment?\""],
    ["3", "Ep32 00:52.50–01:22.50 + 02:14.80–02:32.00", "\"You are lying!\"", "Red-hot iron stops millimetres from her eye"],
    ["10", "Ep36 02:25.80–03:17.10", "\"What wedding?\"", "\"…their dead Duke is coming home.\""],
    ["13", "Ep26 01:50.80–02:00.88 + Ep27 00:44.20–01:20.80", "\"Where did you get this ring?\"", "Doors burst open; she is framed"],
    ["20", "Ep1 00:39.00–00:50.40 + Ep12 01:05.20–01:14.00 + Ep45 00:16.90–00:24.50", "\"Because he is marrying me.\"", "\"You're the Duke?\" (premise montage)"],
], [7, 56, 55, 64]))
s.append(p("<b>Post first:</b> Ep3, then Ep1 and Ep12. They are early (the viewer lands where the promo happens), play cold (sister, husband "
           "and gallows are named on screen) and end mid-threat. Then Ep24, the Ep26→27 ring reveal and the premise montage. Hold Ep45 and the "
           "Ep44→45 reveal for viewers already watching. The tool's own order puts Ep24 first (#1), which is fine. In my review below, Ep3 (#9) is the better opener.", B))

s.append(p("How I know it's good, and where it picks badly", H))
s += bl([
    "<b>Recall vs a reference list.</b> Before seeing any output I hand-picked 17 promo moments from the scripts. The tool ranks "
    "<b>7/17 in its top 10, 10/17 in the top 20, 12/17 in the top 40</b>, and all 17 appear somewhere in the 260 candidates.",
    "<b>Cliffhanger detector vs the writers.</b> 38 episode endings have a clear writer cue (\"cliffhanger sting\" vs \"warm fade-out\"). "
    "Using dialogue only (SFX hidden, as on a script without music notes), the detector gets <b>precision 0.94, recall 0.53</b>. "
    "When it says cliffhanger it is almost always right, but it misses visual ones (Ep1 ends on her face hardening).",
    "<b>Manual review of the top 20</b> (from the script text, not footage): <b>10 post-ready, 7 right moment with a wrong cut, 3 reject</b>. Failure patterns:",
])
s.append(table([
    ["Where it picks badly", "Example", "Why / fix"],
    ["Loud beats beat meaningful ones", "Ep1 starts 7 s after the real hook \"Because he is marrying me.\"", "Tags and \"!\" drive the hook score → LLM judge"],
    ["Exposition reads as stakes", "Ep43: \"Arrest him!\" then a Crown official reads records (rejected)", "No exposition penalty → LLM \"needs backstory\" check"],
    ["60 s cap cuts before the payoff", "Ep11 cuts on \"Happy?\", 25 s before the planted watch is found", "Should jump-cut to the payoff"],
    ["Visual spectacle under-ranked", "Fire (Ep18), ledger thrown in mud (Ep5), explosion (Ep41), proposal (Ep3): ranks 51–79", "Text can't see scale → LLM / video signals"],
    ["Same scene twice", "3 Ep32 promos in top 20; 2 share an ending", "Raise episode-diversity penalty"],
    ["Word-list labels", "\"You have thrown yourself away!\" labelled a threat", "Labels are hints; the LLM rewrites them"],
], [44, 82, 56]))
s.append(p("<b>Honest limits.</b> The rules were tuned on this one show, so these numbers are optimistic; the real test is the new show in "
           "the interview. The reference list and the review are one person's judgement, not editors' or ad performance. The LLM layer "
           "is built and tested (stub HTTP server; invented IDs are rejected) but <b>not yet measured</b>: the build machine could not reach "
           "any model API. I will run it with a free Gemini key and compare its top 20 against the same review.", B))

s.append(p("Scale and cost", H))
s += bl([
    "Rules: ~4 s and $0 per 50-episode show on a laptop, deterministic, no limits. Parsing is the only show-specific part.",
    "LLM pass: 40 reviews × ~1.1k tokens ≈ 46k input + 7k output per show → about <b>$0.03/show</b> on Gemini 2.5 Flash "
    "($0.30/$2.50 per M), $0.007 on Flash-Lite, ~$0.18 on a pro-class model. At 5 shows a week that is under $50 a year even on the top tier. "
    "The free tier's rate limit is handled by backoff and an on-disk cache.",
    "Real-world loop: log which shortlisted promos editors actually post and their CTR / cost per install, then re-weight the five scores "
    "(or few-shot the LLM with winners). That replaces my judgement with Kuku's data. The same pipeline works per language when scripts are localised.",
])

s.append(p("AI tools used, and where they got it wrong", H))
s.append(p("Claude (via Claude Code) helped me read all 50 scripts, write the parser/scorer/UI and draft this doc. The decisions above are mine: weights, "
           "funnel-first ranking, ID-only LLM answers, the evaluation design. Where it got it wrong: (1) its first LLM integration blended "
           "LLM-reviewed and unreviewed promos on different score scales, so the reviewed ones sank. A mock-model run caught it, and reviewed "
           "promos are now ranked as their own tier. (2) Its violence word list tagged figurative speech (\"thrown yourself away\") as physical violence. "
           "Violent words in dialogue now count as threats, but the labels remain approximate.", B))
doc.build(s)
print(OUT)
