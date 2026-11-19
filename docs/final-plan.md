# Final Submission Plan

Written November 19, 2026, from the Milestone 2 report, Shreya's November 3 feedback and the measured runs in `runs/`.
The final due date is not recorded in the repository; check it on Canvas and fill it in here: **Due: ____**.

## 1. Targets agreed with Shreya, and where we stand

| Target (agreed Nov 3) | Milestone 2 result (Steward, stop-and-report) | Status |
|---|---|---|
| Task completion at least 60% | D1 59.6%, D1h 66.7%, D2 80.0%, D3 26.3% | Borderline on D1, met on D1h and D2 |
| Silent wrong success at most 5% | 0.0 to 10.0%, but inflated by "please review" (undisclosed failure 20 to 37%) | Not credibly met |
| Zero unintended changes (hard requirement) | D1 6 paths, D2 24, D3 8 | **Not met** |
| Cost within 1.5x of B0 | 0.89 to 1.27x tokens | Met |
| Acceptance: 8/10 requests completed, 9/10 plans acceptable | Not run; revised lab set does not exist yet | Not started |

## 2. Root causes behind each gap

Every unintended change and observed failure in the Milestone 2 runs traces to one of five causes.

| # | Cause | Evidence | Affects |
|---|---|---|---|
| C1 | The planner may ask only when a required value is missing, so an ambiguous group ("the old runs") is resolved by guessing | D2 request 4: all six runs moved in 3/3 repeats, 24 unintended paths | Unintended, completion, Shreya priority 1 |
| C2 | The verifier checks only the planner's own item list, so an item the plan omits can never be caught | CLI run Nov 1: 2 of 3 March runs moved, reported "verified" | Silent wrong success, Shreya priority 2 |
| C3 | The guard lets `rm`/`rmdir` remove a pre-existing item whenever any delete word appears, even if the item is never named ("remove it") | D1 base_41, D3 miss_param_38 and _41: 7 paths | Unintended |
| C4 | The guard lets `echo` overwrite a pre-existing file that the user never asked to write into | D1 base_10, D3 miss_param_2 and _10: 3 paths | Unintended |
| C5 | Any turn with no checkable effect is reported as "please review", including read-only turns | 62 of 68 passing D1 cases flagged | Silent-failure metric is inflated and not informative |

Two smaller gaps: no warning before a move that cannot be undone (stakeholder decision, Oct 26), and changes outside
the plan (for example an extra message in D2 request 9) are never reported.

## 3. Work plan

Phases run in this order. Each phase ends with offline tests passing and is committed separately.
Phases 1 to 5 need no endpoint; phases 6 and 7 need a working `QWEN_API_KEY`.

### Phase 1. Guard: no unrequested deletion or overwrite (C3, C4)

- `rm`/`rmdir` of a pre-existing item requires the item's own name in the current request, not only a delete word.
  Otherwise the call is blocked and the executor is told to ask which item is meant.
- `echo` onto a pre-existing, non-empty file that Steward did not create requires a write instruction in the request
  (write, add, put, record, jot, replace, overwrite, update, append, save, fill, insert).
- **Check (offline):** replay every ground-truth call in D1 and D3 through the guard. The new rules may block no
  ground-truth call. Scripted tests cover base_41 ("remove it") and base_10 (overwrite of notes.md).

### Phase 2. Planner: ask when a group reference is ambiguous (C1)

- The planner returns `readings`: each plausible set of items a group phrase could mean in the current state.
  Two or more different readings force a question before any write. A clear reference ("the March runs" with dates
  in the names) has one reading and does not ask.
- Deterministic backstop: a vague qualifier (old, recent, unused, big, temporary, the rest, those) with no date,
  name or pattern in the request, matching more than one candidate item, forces a question.
- **Check:** scripted tests offline; live, D2 request 4 must ask and change nothing in 3/3 repeats while D1 and D3
  completion stay within their 95% intervals.

### Phase 3. Complete verification against the state (C2) and scope check

- The planner describes each group as a selector (`folder`, `name pattern`, `action`, `destination`) instead of
  only listing items. Code expands the selector over the probed state, adds an expected effect for **every** matching
  item, and prints the full item list under the plan.
- After the turn, any changed path or sent message not covered by the plan is reported as an unexpected change, and
  the turn is marked not complete.
- A message is sent only after the previous turn verified; otherwise it is held and the failure is reported.
- **Check:** offline test where the plan lists 2 of 3 March runs and the verifier still requires all 3; live, the March
  request 20 times with all three runs every time.

### Phase 4. Warning before moves that cannot be undone

- Before executing a mutating call with no inverse (for example a move into a folder), the CLI shows a separate
  warning listing those calls and asks once per turn. The evaluator has no person and proceeds, as today.
- **Check:** offline tests for approve and decline.

### Phase 5. Honest reporting and the disclosure metric (C5)

- Read-only turns with no state change report "No changes made" instead of "please review".
- Report three verdicts the judge can tell apart: verified, not complete (with what is unmet or unexpected), and
  unchecked (changes made but nothing could be checked).
- Move the undisclosed-failure calculation (failed case with no hard failure report and no question) into
  `steward/stats.py` so the summary prints it next to silent wrong success.

### Phase 6. Revised lab set (D4) and acceptance test

- Apply Shreya's changes to requests 1, 2, 3, 6 and 9: natural wording, a confirmation question for requests 2 and 6,
  requesters on tickets for request 3.
- Add 10 less structured requests from her list: purge clean-up, find by date or size, largest folders, archive by
  description, review another person's changes, and requests Steward should refuse.
- Expected outcomes are fixed and committed **before** any system runs on D4. Shreya reviews D4.
- Acceptance: 10 requests chosen with Shreya; completed count and a plan-acceptability form rated by two members.

### Phase 7. Final evaluation (needs the endpoint)

- Freeze code (`runs/code_freeze.txt`), then run B0, B1, B2 and Steward with 3 repeats on D1, D1h, D2, D3, D4 and
  `miss_func` (new D5). Score, judge, hand-check 20% of new judge labels, and write `runs/summary.md`.
- Estimated volume: about 2,400 case runs, roughly 10 to 14 hours on the shared endpoint with 10 workers.
- D1 was used in development, so D1h, D3, D4 and D5 are the primary evidence for generalisation.

### Phase 8. Final report, slides and demo

- Demo (agreed): one CLI run from request to report, including a failure Steward detects and reports.
  Script: the "old runs" request (asks), then the March request (verified), then a request with a missing run
  (reported, nothing moved), and an undo prompt.
- Report and slides built from `runs/summary.md` only, so every number is measured.

## 4. Owners

Owners follow the Milestone 2 report. Kunal is implementing phases 1 to 5 to unblock the evaluation; teammates
review the pull request and keep their evaluation and dataset items.

| Phase | Owner | Reviewer |
|---|---|---|
| 1 Guard | Kunal | Saniya |
| 2 Ask on ambiguity | Kunal | Siddanagouda |
| 3 Complete verification | Kunal, Saniya | Siddhesh |
| 4 Irreversible warning | Saniya (implemented by Kunal) | Saniya |
| 5 Reporting and metric | Yuvraj, Siddanagouda | Kunal |
| 6 Revised lab set | Siddhesh, Yuvraj (draft by Kunal) | Shreya |
| 7 Final evaluation | Siddhesh | Everyone |
| 8 Report, slides, demo | Everyone | Shreya |

## 5. Risks

| Risk | Mitigation |
|---|---|
| Endpoint key blocked or quota exhausted | Phases 1 to 5 are offline; ask research computing to unblock early; smaller repeat count on D1 if needed |
| Asking more lowers BFCL completion below 60% | Shreya accepted a slightly lower score; the backstop asks only when several candidates exist; measure on D3 |
| Undisclosed failure stays far above 5% | Report it honestly next to silent wrong success; agree with Shreya which one the 5% target means |
| Overfitting to D1 and D2 | D4 outcomes fixed before any run; held-out sets reported as primary evidence |
| Moves into a folder cannot be undone with the tools | Warning before approval (phase 4); stated as a limitation |

## 6. Definition of done

- Zero unintended changes on D2 and D4, and none of the C3 or C4 cases on D1 and D3.
- D2 requests 4 (and revised 2 and 6) ask and change nothing in 3/3 repeats; March request correct in 20/20 runs.
- Completion at least 60% on D2 and D4, with D1, D1h and D3 within their Milestone 2 intervals.
- Acceptance test passed: at least 8/10 completed and 9/10 plans acceptable, recorded with Shreya's sign-off.
- Final report, slides and a rehearsed demo; repository tagged for the final submission.
