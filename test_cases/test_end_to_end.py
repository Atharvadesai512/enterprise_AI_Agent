import json

from agents.intake_agent import run_intake
from orchestrator.main import AGENT_STAGES, Orchestrator


def test_complete_sales_workflow_with_real_agents(tmp_path):
    raw_lead = {
        "raw_text": (
            "My name is Rahul Sharma. "
            "I am the Operations Director at ABC Manufacturing Pvt Ltd. "
            "My email is rahul.integration@abcmanufacturing.com. "
            "Industry: Manufacturing. "
            "We have 450 employees. "
            "We need to automate finance workflows. "
            "We need to automate HR processes. "
            "We need a solution within the next 2 weeks."
        )
    }

    # Isolate the CRM lookup so this test is independent of existing CRM data.
    def isolated_intake(lead):
        return run_intake(
            lead,
            lookup=lambda email, company, name: []
        )

    db_path = tmp_path / "integration_test.sqlite3"
    log_path = tmp_path / "integration_test.log.jsonl"

    orchestrator = Orchestrator(
        db_path=db_path,
        log_path=log_path,
        intake=isolated_intake,
        max_retries=0,
    )

    try:
        summary = orchestrator.process_lead(raw_lead)

        assert summary["status"] == "completed", summary
        assert summary["reason_code"] is None

        stage_names = {stage["stage"] for stage in summary["stages"]}
        assert "intake" in stage_names
        assert set(AGENT_STAGES).issubset(stage_names)

        for stage in summary["stages"]:
            assert stage["status"] == "passed", stage

        # Read the actual persisted outputs from SQLite.
        rows = orchestrator.conn.execute(
            """
            SELECT stage, output_json
            FROM stage_results
            WHERE run_id = ?
            ORDER BY id
            """,
            (summary["run_id"],),
        ).fetchall()

        outputs = {
            row["stage"]: json.loads(row["output_json"])
            for row in rows
            if row["output_json"]
        }

        intake = outputs["intake"]
        assert intake["lead_name"] == "Rahul Sharma"
        assert intake["company_name"] == "ABC Manufacturing Pvt Ltd"
        assert intake["employee_count"] == 450
        assert intake["validation_status"] == "valid"
        assert len(intake["requirements"]) >= 2

        research = outputs["research"]
        assert research["stage_status"] == "passed"

        qualification = outputs["qualification"]
        assert qualification["qualification_status"] == "qualified"

        scoring = outputs["scoring"]
        assert scoring["stage_status"] == "passed"
        assert 0 <= scoring["lead_score"] <= 100

        routing = outputs["routing"]
        assert routing["stage_status"] == "passed"

        strategy = outputs["strategy"]
        assert strategy["strategy_status"] == "created"

        communication = outputs["communication"]
        assert communication["stage_status"] == "passed"
        assert communication["communication_status"] == "drafted"
        assert communication["recipient"] == "rahul.integration@abcmanufacturing.com"
        assert communication["email_body"]
        assert communication["human_approval_required"] is True
        assert communication["external_message_sent"] is False

        qa = outputs["qa"]
        assert qa["stage_status"] == "passed"
        assert qa["qa_status"] == "passed_pending_human_approval"
        assert qa["passed_checks"] == 8
        assert qa["failed_checks"] == 0
        assert qa["human_approval_required"] is True
        assert qa["external_action_performed"] is False

    finally:
        orchestrator.close()
