# Quality check

## Flags on the shortlist

| flag | shortlist | all candidates |
|---|---|---|
| DEAD_AIR | 0 | 38 |
| ENDING_MAY_RESOLVE | 0 | 19 |
| LATE_SERIES_SPOILER_RISK | 7 | 52 |
| MANY_CHARACTERS | 1 | 8 |
| NEEDS_CONTEXT | 1 | 31 |
| REPEATED_LINE | 0 | 1 |
| WEAK_CLIFFHANGER | 0 | 27 |
| WEAK_HOOK | 0 | 38 |

## Shape mix

- single: 17 shortlisted / 165 generated
- continuation: 4 shortlisted / 25 generated
- jumpcut: 3 shortlisted / 68 generated
- premise: 1 shortlisted / 2 generated

Episodes covered by shortlist: [1, 2, 3, 4, 11, 12, 13, 21, 22, 24, 25, 26, 27, 28, 29, 32, 36, 43, 44, 45, 46, 47]

## Recall vs hand-picked reference moments

{"recall@10": "7/17", "recall@20": "10/17", "recall@40": "12/17", "recall@all": "17/17"}

| ref | first matching rank | moment |
|---|---|---|
| H01 | 5 | Ep1 altar betrayal: 'Why are you holding her hand?' / 'Because he is marrying me.' |
| H02 | 9 | Ep3 guards drag her out, scarred stranger drops a guard |
| H03 | 70 | Ep3 stranger kneels: 'Lady Juliana... accept my hand.' |
| H04 | 79 | Ep5 stepmother throws mother's ledger into the mud |
| H05 | 52 | Ep11 constable pulls the planted watch from his coat |
| H06 | 4 | Ep12 Clarissa's ultimatum: thorns barehanded or husband hangs |
| H07 | 21 | Ep13 Juliana crawls into the blackthorn briars |
| H08 | 36 | Ep16 catches the club, 'Who sent you?' - 'Gerald Harrington paid us!' |
| H09 | 77 | Ep18 cottage fire, runs back for the ledger, beam crashes |
| H10 | 1 | Ep24 noblewoman strikes her with a riding crop |
| H11 | 13 | Ep26-27 Duchess recognises the ring: 'Where did you get this ring?' |
| H12 | 14 | Ep28 Catherine unmasks 'Lady Juliana Ashcroft', threatens gallows |
| H13 | 3 | Ep31-32 Catherine with the red-hot iron |
| H14 | 10 | Ep36 'their dead Duke is coming home' |
| H15 | 51 | Ep41-42 cathedral doors explode, 'Who are you?' - 'You already know.' |
| H16 | 18 | Ep44 Catherine begs Alexander, ends 'Her?!' |
| H17 | 2 | Ep45 'You're the Duke?' / 'Duchess of Ashburton!' / 'Juliana?!' |

## Cliffhanger detector vs writers' own marks (dialogue only, SFX hidden)

38 labelled episode endings · precision 0.94 · recall 0.53 (tp 16, fp 1, fn 14, tn 7)

Missed cliffhangers (writer marked, detector said no):

- Ep1 score 0.0: "...when Clarissa is the true jewel of the county."
- Ep3 score 1.5: "Lady Juliana... accept my hand."
- Ep4 score -1.5: "Come, Lady Juliana."
- Ep12 score 0.0: "Tell me where the garden is."
- Ep13 score 1.5: "Please, ring... you have to be here."
- Ep14 score 1.5: "No one will ever hurt you for protecting me again."
- Ep16 score -1.5: "No."
- Ep21 score 1.0: "Inside that massive house with all their wealth, she is fading to nothing, and n"
- Ep38 score -2.5: "Alexander..."
- Ep40 score 0.5: "And you look better in silk than you ever did as an ignored cousin."
- Ep42 score 1.5: "And now, Rupert... we settle what you stole."
- Ep47 score 1.5: "I accept, Your Grace."
- Ep49 score 0.0: "We always have."
- Ep50 score 1.5: "Or perhaps discretion isn't the only thing you've developed a taste for."