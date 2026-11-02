# Development findings (D1 dev slice only)

## Smoke run, first version: rollback on a planner typo (multi_turn_base_2)

Turn 4 asked for TeamNotes.txt to be copied to Archived as IdeasArchive.txt. The executor did this correctly.
The planner's expected effect was `exists /simona/documents/Archived/ideasArchive.txt` (lower-case i).
The case-sensitive verifier reported the effect unmet. The executor replied that the file existed and the
request was complete, but the single repair was then spent, so rollback undid the correct work:
`mv(IdeasArchive.txt -> TeamNotes.txt), cd .., cd Archived, rm(TeamNotes.txt), cd ..`.
In turn 5 the executor had to rebuild the file. The trace of this smoke run was not kept; this note is the record.

Observed: a correct state was undone. Cause: the planner's copy of a user-supplied name differed from the actual name.

## Dev rounds on D1 (kept apart from reported results, in dev_runs/)

| Round | System | Pass | Change before the round |
|---|---|---|---|
| 100 | guard only | 20/38 | none |
| 100 | steward | 19/38 | case-sensitive verifier as first written |
| 101 | steward | 21/38 | effects grounded in the request or state; planner sees earlier tool results and must list every matching item |

Round 100 false alarms included invented names and placeholders such as `<byte_count>.pdf` and `IconsArchive.txt`,
and needless questions on cases answerable from earlier results. Differences between rounds are within run-to-run noise.
Tuning stopped after round 101 because further changes could not be told apart from noise on 38 cases.
