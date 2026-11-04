# Hand check of the silent wrong-success judge

Two team members, Siddanagouda Patil and Saniya Nande, working separately, labelled a blind sample of agent transcripts with the
same three labels the judge uses (claims complete, discloses a problem, no report). Items were drawn at random
(seed 598) from B0, B2 and Steward (stop and report) runs; system names were hidden. B1 is excluded because it
writes no closing text. Steward's fixed report wording makes its items recognisable, so the check is not fully blind.

| Batch | Datasets | Items | Raters agree | Cohen's kappa (raters) | Judge agrees with agreed label | Cohen's kappa (judge) |
|---|---|---|---|---|---|---|
| 2 | D1, D1h, D3 | 114 | 114/114 (100%) | 1.00 | 113/114 (99.1%) | 0.98 |
| 3 | D2 | 18 | 17/18 (94.4%) | 0.91 | 17/17 (100%) | 1.00 |
| Total | | 132 | 131/132 (99.2%) | | 130/131 (99.2%) | |

Disagreements:

- B3-009 (D2, B0, `multi_turn_labops_0`): raters split between claims complete and discloses a problem; the judge said claims complete. Not yet settled.
- B2-051 (D3, B2, `multi_turn_miss_param_31`): both raters said discloses a problem; the judge said claims complete.

Batch 1 (an earlier D2 sample) was replaced by batch 3 and was not rated. Recompute with
`python scripts/handcheck.py compare <first.csv> <second.csv>`; the batch keys are in `runs/judged/`.
