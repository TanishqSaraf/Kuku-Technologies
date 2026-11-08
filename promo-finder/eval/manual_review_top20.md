# Manual review of the rules-only top 20

Reviewer read the script inside each cut (report.md) and judged it as a promo editor would.
Verdicts: **POST** = usable as is · **FIX** = right moment, wrong cut or weak element · **REJECT** = shouldn't be posted.
This is a script-only judgement; nobody has watched the rendered video. Re-check it against footage.

| # | Cut | Verdict | Note |
|---|---|---|---|
| 1 | Ep24 00:32.8–01:10.5 | POST | Riding-crop strike in the first 0.3 s; ends on a threat to Prudence. 48–57 s (walking to the hearth) is slow. |
| 2 | Ep45 00:53.8–01:28.4 | POST (later) | "You poisoned my mother. You tortured my wife." → bishop bursts in. Spoils the Duke reveal, so it goes after the early promos. |
| 3 | Ep32 jump cut | FIX | Great ending (iron millimetres from her eye) but opens on a speech about Gerald. The alternate cut (Ep32 01:59.5–02:32) is the better promo. |
| 4 | Ep12 00:26.8–01:09.5 | POST | "…your husband hangs from the gallows." Opening "You planted it!" lacks context (planted what?) and QC did not flag it. |
| 5 | Ep1 00:46.8–01:21.4 | FIX | Right scene, starts 7 s late. Misses the real hook "Why are you holding her hand?" / "Because he is marrying me." The rules reward the loud accusation over the line that carries the twist. |
| 6 | Ep43 jump cut | REJECT | 8 s of "Arrest him!" then a Crown official reading records. Exposition-heavy, needs the whole backstory, ends on a door-creak SFX. |
| 7 | Ep11 00:29.0–01:16.8 | FIX | Good build (cottage ransacked), but cuts on "Happy?" ~25 s before the payoff (planted watch found). The 60 s cap with this start can't reach it. |
| 8 | Ep4 01:54.8–02:14.8 | FIX | "You are disowned!" works, but it is the 20 s minimum and needs context. Hook mislabelled "life-or-death threat" ("thrown yourself away"). |
| 9 | Ep3 00:58.2–01:28.1 | POST (first) | Dragged out of church → "Take your hands off her" → punch → "He's only one man!" Best early-funnel promo. |
| 10 | Ep36 02:25.8–03:17.1 | POST | "…their dead Duke is coming home." The title already gives the twist away, so the spoiler costs little. |
| 11 | Ep29 00:56.6–01:36.1 | POST | Catherine's taunts, thrown into a cell, door slams. The "Mother…" cut is soft but holds. |
| 12 | Ep2 00:04.6–00:51.5 | FIX | Same betrayal as Ep1 at lower intensity; 47 s is long. Backup only. |
| 13 | Ep26 → Ep27 | POST | Duchess sees the ring → "What is your husband's name?" → doors burst → accusation. The cross-episode join works. |
| 14 | Ep28 01:47.8–02:14.5 | POST | "The bride who married a penniless war veteran…" → gallows threat. Restates the premise. |
| 15 | Ep21 00:03.6–00:35.8 | FIX | Dying-child plea. Emotional but generic, and the payoff (a cure) is soft. Weak as an ad. |
| 16 | Ep32 01:11.2–02:02.8 | REJECT | A 52 s argument ending "Why?!". Talky, nothing visual, and the third Ep32 cut in the top 20. |
| 17 | Ep22 00:19.0–00:46.0 | FIX | Disguised as a maid, "Who is this?" Mild stakes. |
| 18 | Ep44 → Ep45 | POST (later) | Catherine begs → "You're the Duke?" Strong, late spoiler. |
| 19 | Ep32 jump cut | REJECT | Same ending as #3. Redundant (dedupe threshold 0.4 IoU let it through). |
| 20 | Premise montage | FIX | Right idea (altar betrayal → husband to hang → "You're the Duke?") but choppy 8–11 s beats, and the middle beat should be Ep11 "You married a beggar!". |

**Tally:** 10 POST · 7 FIX · 3 REJECT → 50% post-ready, 85% at least the right moment.

## Patterns behind the failures
1. **Loud beats beat meaningful beats** (#5, #16). Emotion tags and "!" drive the hook score, so an accusation outranks the quieter line that carries the twist.
2. **Exposition isn't penalised** (#6). Legal or official dialogue reads as "high stakes" to the lexicon.
3. **Fixed 60 s window vs the payoff** (#7). When the build-up is long, the tool cuts before the reveal instead of jump-cutting to it.
4. **Visual spectacle is under-ranked.** Fire (Ep18), ledger thrown in the mud (Ep5), cathedral explosion (Ep41) and the proposal on one knee (Ep3) rank 51–79. Text rules can't see how big a moment looks.
5. **Diversity across the same episode is too soft** (#3, #16, #19 are all Ep32).
6. **Hook/cliff labels come from word lists** and are sometimes wrong (#8).

These are exactly what the LLM re-ranker is asked to judge (it sees the full script around the cut and can move the start/end). Its effect has not been measured yet: no free API was reachable from the build machine.
