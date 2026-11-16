import json
import sqlite3

import pytest

from dashboard.approval_service import (
    connect,
    get_review,
    record_decision,
)


def create_eligible_run(db_path):
    conn = connect(db_path)
    conn.execute(
        """
        INSERT INTO workflow_runs
        (run_id, created_at, updated_at, status, current_stage,
         lead_email, lead_company, input_json)
        VALUES ('run-test', '2026-11-16', '2026-11-16', 'completed',
                'qa', 'rahul@example.com', 'ABC Manufacturing', '{}')
        """
    )

    outputs = {
        "intake": {"lead_name": "Rahul", "company_name": "ABC Manufacturing",
                   "email": "rahul@example.com", "industry": "Manufacturing",
                   "employee_count": 450},
        "communication": {
            "stage_status": "passed", "communication_status": "drafted",
            "recipient": "rahul@example.com", "subject": "Hello",
            "email_body": "Draft email", "human_approval_required": True,
            "external_message_sent": False,
        },
        "qa": {
            "stage_status": "passed",
            "qa_status": "passed_pending_human_approval",
            "human_approval_required": True,
            "external_action_performed": False,
            "passed_checks": 8, "failed_checks": 0,
            "checks": [],
        },
        "scoring": {"lead_score": 80, "lead_priority": "high"},
        "routing": {"assigned_team": "Enterprise Sales",
                    "assigned_role": "Senior Account Executive"},
    }

    for stage, output in outputs.items():
        conn.execute(
            """
            INSERT INTO stage_results
            (run_id, stage, status, attempts, output_json, started_at, finished_at)
            VALUES (?, ?, 'passed', 1, ?, '2026-11-16', '2026-11-16')
            """,
            ("run-test", stage, json.dumps(output)),
        )
    conn.commit()
    conn.close()


def test_qa_passed_run_can_be_approved(tmp_path):
    db = tmp_path / "approval.sqlite3"
    create_eligible_run(db)

    review = get_review("run-test", db)
    assert review["eligible_for_approval"] is True
    assert review["approval"]["status"] == "pending"

    result = record_decision("run-test", "approved", "Test Reviewer",
                             "Looks good", db)
    assert result["approval"]["status"] == "approved"
    assert result["approval"]["reviewer"] == "Test Reviewer"
    assert result["approval"]["comments"] == "Looks good"


def test_decision_cannot_be_overwritten(tmp_path):
    db = tmp_path / "approval.sqlite3"
    create_eligible_run(db)

    record_decision("run-test", "approved", "Reviewer", db_path=db)
    with pytest.raises(ValueError):
        record_decision("run-test", "rejected", "Another Reviewer", db_path=db)


def test_non_qa_passed_run_cannot_be_approved(tmp_path):
    db = tmp_path / "approval.sqlite3"
    create_eligible_run(db)

    conn = sqlite3.connect(db)
    conn.execute(
        "UPDATE stage_results SET output_json=? WHERE run_id='run-test' AND stage='qa'",
        (json.dumps({"stage_status": "needs_review"}),),
    )
    conn.commit()
    conn.close()

    with pytest.raises(ValueError):
        record_decision("run-test", "approved", "Reviewer", db_path=db)


def test_reviewer_name_is_required(tmp_path):
    db = tmp_path / "approval.sqlite3"
    create_eligible_run(db)

    with pytest.raises(ValueError):
        record_decision("run-test", "approved", "", db_path=db)


def test_rejection_requires_a_reason(tmp_path):
    db = tmp_path / "approval.sqlite3"
    create_eligible_run(db)

    with pytest.raises(ValueError, match="rejection reason"):
        record_decision("run-test", "rejected", "Test Reviewer", db_path=db)

    result = record_decision(
        "run-test",
        "rejected",
        "Test Reviewer",
        "The lead does not meet our qualification criteria.",
        db,
    )
    assert result["approval"]["status"] == "rejected"
    assert result["approval"]["reviewer"] == "Test Reviewer"
    assert result["approval"]["comments"] == (
        "The lead does not meet our qualification criteria."
    )
