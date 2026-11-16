-- Workflow state store (SQLite). Applied by orchestrator/main.py on startup.
-- Every orchestrator decision is persisted so a run can be audited or resumed after a restart.

CREATE TABLE IF NOT EXISTS workflow_runs (
    run_id         TEXT PRIMARY KEY,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL,
    status         TEXT NOT NULL CHECK (status IN
                       ('running', 'awaiting_stage', 'completed', 'exception', 'failed')),
    current_stage  TEXT NOT NULL,
    lead_email     TEXT,                -- lower-cased; NULL when intake found no usable email
    lead_company   TEXT,
    input_json     TEXT NOT NULL,       -- raw lead exactly as received
    final_reason   TEXT                 -- reason code when status is exception / failed / awaiting_stage
);

CREATE INDEX IF NOT EXISTS idx_runs_email ON workflow_runs (lead_email);

CREATE TABLE IF NOT EXISTS stage_results (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id       TEXT NOT NULL REFERENCES workflow_runs (run_id),
    stage        TEXT NOT NULL,
    status       TEXT NOT NULL,         -- passed | routed_to_exception | failed | not_implemented | needs_review
    attempts     INTEGER NOT NULL DEFAULT 1,
    output_json  TEXT,                  -- agent output (JSON), NULL if the agent never returned one
    error        TEXT,                  -- last error message, if any
    started_at   TEXT NOT NULL,
    finished_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_stage_run ON stage_results (run_id);

CREATE TABLE IF NOT EXISTS exception_queue (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id        TEXT NOT NULL REFERENCES workflow_runs (run_id),
    stage         TEXT NOT NULL,
    reason_code   TEXT NOT NULL,
    message       TEXT NOT NULL,
    details_json  TEXT,
    status        TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'resolved')),
    created_at    TEXT NOT NULL,
    resolved_at   TEXT
);

CREATE INDEX IF NOT EXISTS idx_exc_status ON exception_queue (status);
