# Technical Documentation

Covers what is built so far: the Intake Agent and the Orchestrator. Other components are placeholders.

## Design principles

- AI-style extraction is isolated in agents; **scoring, validation, routing and permissions are deterministic Python**.
- Agents never get write access. The orchestrator performs no external actions.
- Nothing is hardcoded to look successful: a stage with no agent is recorded as `not_implemented`.
- Every decision is persisted and logged.

## Intake Agent (`agents/intake_agent.py`)

`run_intake({"raw_text": str, ...}) -> dict` with exactly these keys: `lead_name, company_name, email, industry, employee_count, requirements, budget, urgency, missing_fields, duplicate_status, validation_status, notes`.

- `validation_status`: `valid | incomplete | needs_review | invalid`
- `duplicate_status`: `not_duplicate | possible_duplicate | duplicate | unknown`
- Conflicting values are nulled and flagged. Notes are tagged `FACT`, `ASSUMPTION` or `FLAG`.
- CRM access is a read-only lookup (`crm_lookup`) against `database/mock_crm.json`.
- Current implementation is rule-based so it runs offline; an LLM-backed version can keep the same contract.

## Orchestrator (`orchestrator/main.py`)

### Flow

```
raw lead
  -> intake (retry on crash)           stage_results: intake
  -> validation gate (deterministic)   stage_results: validation_gate
        reject -> exception_queue + run status "exception"
  -> research -> qualification -> scoring -> routing -> strategy -> communication -> qa
        each stage runs only if the previous returned stage_status "passed"
        no agent for the stage -> status "awaiting_stage" (STAGE_NOT_IMPLEMENTED)
        all passed             -> status "completed"
```

### Gate rules (`validate_intake_result`)

In order: schema match, enum values, list types, consistency (a `valid` lead must have name, company, email, requirements), then `validation_status` (`invalid`, `incomplete`, `needs_review` all rejected), then `duplicate_status` (`duplicate`, `possible_duplicate`, `unknown` all rejected). Then a workflow-level check blocks a lead whose email already has a `running`, `awaiting_stage` or `completed` run (`WORKFLOW_DUPLICATE`).

### Agent contract (stages after intake)

`agents/<stage>_agent.py::run_<stage>(payload) -> dict`, payload = `{"run_id", "lead", "previous"}`. Output must be a JSON-serialisable dict with `stage_status` in `passed | failed | needs_review`; otherwise `STAGE_OUTPUT_INVALID`. Agents receive a deep copy, so they cannot alter stored state.

### Error handling

- Agent exceptions: up to 2 retries (3 attempts) with 0.5s then 1.0s backoff; then run status `failed` and an `AGENT_ERROR` exception item.
- `NotImplementedError` is not retried.
- Log-file write errors are swallowed; the database remains the source of truth.

### State (`database/schema.sql`, SQLite)

- `workflow_runs`: run status, current stage, lead email/company, original input, final reason.
- `stage_results`: per stage status, attempts, output JSON, error, timestamps.
- `exception_queue`: stage, reason code, message, details, open/resolved.

### Not built yet

Resolving exception-queue items, human approval for external actions, concurrent-run locking (the duplicate check is not race-safe if two runs for one email start simultaneously), and any agent after Intake.
