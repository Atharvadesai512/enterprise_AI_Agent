# Test Report

## Intake Agent (Step 1)

Run with: `python3 test_cases/run_intake_tests.py`

### Results

| Case | Scenario | Result |
|------|----------|--------|
| TC-01-normal | Complete, valid, new lead | PASS |
| TC-02-duplicate | Email matches CRM record CRM-1001 | PASS |
| TC-03-missing-data | No email, company or numbers | PASS |
| TC-04-conflicting | Two headcounts, two budgets, urgent vs no rush, two emails | PASS |

**4 passed, 0 failed.**

### Behaviour verified

- Output contains exactly the 12 schema fields, in order.
- Unavailable fields are `null`; nothing is invented (e.g. a first-name-only sign-off does not produce a `lead_name`).
- Duplicate detection returns `duplicate`, `not_duplicate` or `unknown` correctly for the three relevant cases.
- Leads without a usable email are marked `invalid`; conflicting data is marked `needs_review`.
- Conflicting values are nulled and flagged instead of guessed; the sender's `From` address is used when several emails appear.
- Inferred values are labelled `ASSUMPTION` in `notes`; stated values are labelled `FACT`.
- The agent only reads the mock CRM; no records are created and no email is sent.

### Limitations

- Extraction is rule-based (regex), tuned to these four cases. It has not been tested on large or varied real inquiries; an LLM-backed version is expected to be more robust.
- `possible_duplicate` (same company, different contact) and the free-mail flag are only exercised indirectly, through the orchestrator tests; disposable-domain and spam-phrase flags have no test yet.
- Budgets are returned as written (for example `$60,000`), not normalised to a currency and number.

## Orchestrator (Step 4)

Run with: `python3 test_cases/run_orchestrator_tests.py`

**28 tests, all passing.** Each test uses a temporary database.

| Area | What is checked |
|------|-----------------|
| Routing | Valid lead reaches research; duplicate, invalid, incomplete, needs-review, possible-duplicate and free-email leads go to the exception queue and research is never called |
| Gate | Malformed intake output and a lead falsely marked valid (no email) are rejected |
| Workflow duplicates | Same email submitted twice is blocked; resubmission after a rejected run is not blocked by this rule |
| Retries | Flaky agent succeeds on attempt 2; always-crashing agent fails after 3 attempts with backoff 0.5s, 1.0s; `NotImplementedError` is not retried; intake crashes are retried |
| Stage gating | Output without `stage_status`, non-dict output, `failed` and `needs_review` all stop the pipeline; later stages are not called |
| Safety | An agent mutating its input does not change what later stages see |
| Persistence | A new orchestrator instance reads the same run, stages and original input; exception queue and event log are written; a log-write failure does not break the run |

**Sanity check on the tests themselves:** disabling the gate's duplicate check in a scratch copy made 4 tests fail, so the suite does detect that regression.

### Limitations

- Research and later agents do not exist. Tests that need them use clearly-labelled test doubles, which prove routing and gating logic only, not research quality. With the real defaults, a valid lead stops at `research` (`awaiting_stage`).
- Only synthetic leads have been tested. This is not evidence of production readiness.
- The workflow-duplicate check is not safe against two simultaneous runs for the same email.
