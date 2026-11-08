# Promo Finder — find ad clips in microdrama screenplays

Reads a folder (or .zip) of timestamped episode screenplays and returns ranked **20–60 s promos**: episode and
start/end of every segment, the hook, the cliffhanger, one line on why it works, why it is ranked where it is,
and QC flags. Rules run free and offline; an optional LLM re-ranks the shortlist. You swap the model with one flag.

## Run it

```bash
pip install -r requirements.txt          # streamlit + pandas for the UI; the CLI itself is stdlib-only (Python 3.10+)

# rules only (free, ~4 s for 50 episodes)
python -m promo_finder --input path/to/scripts.zip --out outputs/rules_only

# + LLM re-rank of the top 40 (free Gemini key from aistudio.google.com)
export GEMINI_API_KEY=...
python -m promo_finder --input path/to/scripts.zip --out outputs/gemini --llm gemini

# any other model: groq | openrouter | openai | anthropic | ollama | openai_compat
python -m promo_finder --input scripts.zip --llm anthropic --model claude-haiku-5-5
PROMO_LLM_BASE_URL=http://my-gateway/v1 python -m promo_finder --input scripts.zip --llm openai_compat --model my-model

# UI
streamlit run app.py
```

Optional: `--reference eval/handpicked.json` adds recall against hand-picked moments to `qc_report.md`.
`--top N` sets the shortlist size; `--llm-top-k K` sets how many candidates the LLM reviews.

## Outputs (`--out`)
| file | what |
|---|---|
| `promos.csv` / `promos.json` | ranked shortlist: segments, hook, cliffhanger, why it works, why this rank, flags, alternate cuts |
| `report.md` | the same, readable, with the script inside each cut |
| `qc_report.md` | flag counts, recall vs reference, cliffhanger-detector check |
| `candidates_all.json` | every candidate scored (unfiltered) |
| `run_meta.json` | settings, runtime, LLM token usage |

## How it works
1. **Parse** (`parse.py`): each block (CAMERA/ACTION/SOUND FX/character line with delivery tags) becomes a timestamped event. Camera blocks give the shot cuts.
2. **Generate** (`candidates.py`): four shapes are generated:
   - *single*: one continuous 20–60 s stretch
   - *jumpcut*: two stretches of one episode, skipping the slow middle
   - *continuation*: episode N's cliffhanger plus N+1's payoff and its new cliffhanger
   - *premise*: 3 beats that sell the show title (setup → title phrase → twist)

   Every cut snaps to a shot boundary and never splits a line.
3. **Score** (`features.py`): hook = strongest beat in the first 3 s (delivery tags, violence/danger/betrayal/reveal words, short punchy lines); cliffhanger = the last ~5 s (open question, threat, arrival, blow about to land, cruel line nobody has answered, writer's own cliffhanger cue, minus resolution words); standalone = no context-dependent opener, at most 4 speakers, relationships named on screen; plus peak intensity and dead air.
4. **LLM re-rank (optional)** (`llm.py`): the model scores hook/cliffhanger/standalone and may tighten the cut, but it can only return **event IDs from the script it was shown**. IDs are validated, cuts re-snapped and kept within 20–60 s; anything malformed falls back to the rule result. It can't invent timestamps or quotes. Responses are cached on disk.
5. **Rank** (`rank.py`): score − QC penalties + funnel bonus (early-episode promos first: the ad viewer starts at Ep 1). Greedy diversity ordering; cuts overlapping a higher-ranked promo become its *alternate cuts*.
6. **QC** (`evaluate.py`): flags per promo, recall vs a hand-picked list, and a check of the dialogue-only cliffhanger detector against the writers' own cliffhanger notes.

## Tests
`PROMO_INPUT=path/to/unzipped/scripts python -m pytest -q`: parser, "no cut splits a line, all clips 20–60 s",
and the LLM HTTP path plus guardrail against a local stub server (invented IDs are rejected).

## Confidentiality
The input pack is Kuku's content. `data/` and `outputs/` are git-ignored: don't commit them to a public repo.
Share raw outputs through a link-shared Drive folder instead.
