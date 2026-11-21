# Hand-check of the LLM judge

Blind sample of 60 conversations (25/25/10 by judge label, seed 2023), labelled independently by two team members.

- Saniya vs judge: 55/60 = 91.7%, kappa 0.87
- Yuvraj vs judge: 54/60 = 90.0%, kappa 0.84
- Saniya vs Yuvraj: 59/60 = 98.3%, kappa 0.97

All 5 judge-vs-human disagreements are baseline runs (B0/B2) that the judge labelled claims_complete and both people labelled discloses_problem. The judge may therefore slightly overstate the baselines' silent wrong success; every Steward row matched both people.
