from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from orchestrator.main import DEFAULT_DB, SCHEMA_FILE

DB_PATH = Path(DEFAULT_DB)

APPROVAL_SCHEMA = """
CREATE TABLE IF NOT EXISTS human_approvals (
    run_id TEXT PRIMARY KEY REFERENCES workflow_runs(run_id),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected')),
    reviewer TEXT,
    comments TEXT,
    decided_at TEXT,
    created_at TEXT NOT NULL
);
"""


def connect(db_path=DB_PATH):
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))
    conn.executescript(APPROVAL_SCHEMA)
    conn.commit()
    return conn


def _load_outputs(conn, run_id):
    rows = conn.execute(
        "SELECT stage, status, output_json FROM stage_results WHERE run_id=?",
        (run_id,),
    ).fetchall()
    outputs = {}
    statuses = {}
    for row in rows:
        statuses[row["stage"]] = row["status"]
        if row["output_json"]:
            try:
                outputs[row["stage"]] = json.loads(row["output_json"])
            except (TypeError, json.JSONDecodeError):
                outputs[row["stage"]] = {}
    return outputs, statuses


def _eligible(run, outputs, statuses):
    qa = outputs.get("qa", {})
    communication = outputs.get("communication", {})
    return (
        run["status"] == "completed"
        and statuses.get("qa") == "passed"
        and qa.get("stage_status") == "passed"
        and qa.get("qa_status") == "passed_pending_human_approval"
        and qa.get("human_approval_required") is True
        and qa.get("external_action_performed") is False
        and statuses.get("communication") == "passed"
        and communication.get("communication_status") == "drafted"
        and communication.get("human_approval_required") is True
        and communication.get("external_message_sent") is False
    )


def _ensure_pending(conn, run_id):
    row = conn.execute(
        "SELECT * FROM workflow_runs WHERE run_id=?", (run_id,)
    ).fetchone()
    if not row:
        raise ValueError("Workflow run not found.")

    outputs, statuses = _load_outputs(conn, run_id)
    if not _eligible(dict(row), outputs, statuses):
        return

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT OR IGNORE INTO human_approvals (run_id, status, created_at)
        VALUES (?, 'pending', ?)
        """,
        (run_id, now),
    )
    conn.commit()


def get_review(run_id, db_path=DB_PATH):
    conn = connect(db_path)
    try:
        _ensure_pending(conn, run_id)
        run = conn.execute(
            "SELECT * FROM workflow_runs WHERE run_id=?", (run_id,)
        ).fetchone()
        if not run:
            return None

        outputs, statuses = _load_outputs(conn, run_id)
        approval = conn.execute(
            "SELECT * FROM human_approvals WHERE run_id=?", (run_id,)
        ).fetchone()

        result = dict(run)
        result["outputs"] = outputs
        result["stage_statuses"] = statuses
        result["approval"] = dict(approval) if approval else None
        result["eligible_for_approval"] = _eligible(result, outputs, statuses)
        return result
    finally:
        conn.close()


def list_reviews(db_path=DB_PATH):
    conn = connect(db_path)
    try:
        runs = conn.execute(
            "SELECT run_id FROM workflow_runs ORDER BY created_at DESC"
        ).fetchall()
        run_ids = [r["run_id"] for r in runs]
    finally:
        conn.close()

    results = []
    for run_id in run_ids:
        review = get_review(run_id, db_path)
        if review:
            results.append(review)
    return results


def record_decision(run_id, decision, reviewer, comments="", db_path=DB_PATH):
    if decision not in {"approved", "rejected"}:
        raise ValueError("Decision must be approved or rejected.")
    reviewer = (reviewer or "").strip()
    comments = (comments or "").strip()
    if not reviewer:
        raise ValueError("Reviewer name is required.")
    if decision == "rejected" and not comments:
        raise ValueError("A rejection reason is required.")

    conn = connect(db_path)
    try:
        _ensure_pending(conn, run_id)

        review = get_review(run_id, db_path)
        if not review or not review["eligible_for_approval"]:
            raise ValueError("This workflow has not passed QA and cannot be decided.")

        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        cursor = conn.execute(
            """
            UPDATE human_approvals
            SET status=?, reviewer=?, comments=?, decided_at=?
            WHERE run_id=? AND status='pending'
            """,
            (decision, reviewer, comments, now, run_id),
        )
        conn.commit()
        if cursor.rowcount != 1:
            raise ValueError("This item has already been reviewed.")
    finally:
        conn.close()

    return get_review(run_id, db_path)
