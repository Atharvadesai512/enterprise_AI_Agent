"""Orchestrator tests (stdlib unittest).

Run from project root:  python3 test_cases/run_orchestrator_tests.py

NOTE: the Research agent and later agents are not built yet. Where a test needs a stage to run,
it injects a clearly-labelled TEST DOUBLE. Those prove the orchestrator's routing/gating logic;
they say nothing about real research quality. Tests that use the real defaults show the honest
behaviour: the run stops at the first stage that has no agent.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from orchestrator.main import AGENT_STAGES, Orchestrator  # noqa: E402

CASES = ROOT / "test_cases"


def load(name: str) -> dict:
    return json.loads((CASES / f"{name}.json").read_text(encoding="utf-8"))["input"]


def passing_double(calls=None):
    def handler(payload):
        if calls is not None:
            calls.append(payload)
        return {"stage_status": "passed"}
    return handler


class OrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

        self.db = str(Path(self.tmp.name) / "state.db")
        self.log = Path(self.tmp.name) / "orch.log.jsonl"

    def orch(self, **kw):
        kw.setdefault("sleep", lambda s: None)
        handlers = {"research": passing_double(), "qualification": passing_double(), "scoring": passing_double(), "routing": passing_double(), "strategy": passing_double(), "communication": passing_double(), "qa": None}
        handlers.update(kw.pop("handlers", {}))
        kw["handlers"] = handlers
        o = Orchestrator(db_path=self.db, log_path=self.log, **kw)
        self.addCleanup(o.close)
        return o

    # ---- routing of intake results ---------------------------------------- #
    def test_unknown_company_research_requires_human_review(self):
        o = Orchestrator(db_path=self.db, log_path=self.log)
        self.addCleanup(o.close)
        s = o.process_lead(load("normal_lead"))
        self.assertEqual(s["status"], "exception")
        self.assertEqual(s["current_stage"], "research")
        self.assertEqual(s["reason_code"], "STAGE_NEEDS_REVIEW")
        self.assertEqual([x["stage"] for x in s["stages"]], ["intake", "validation_gate", "research"])
        self.assertEqual(s["stages"][-1]["status"], "needs_review")

    def test_valid_lead_is_sent_to_research_with_intake_result(self):
        calls = []
        o = self.orch(handlers={"research": passing_double(calls)})
        s = o.process_lead(load("normal_lead"))
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["lead"]["company_name"], "Orbit Freight Services")
        self.assertEqual(s["current_stage"], "qa")  # QA agent is not implemented yet
        self.assertEqual(s["status"], "awaiting_stage")

    def test_all_stages_passing_completes_run(self):
        o = self.orch(handlers={st: passing_double() for st in AGENT_STAGES})
        s = o.process_lead(load("normal_lead"))
        self.assertEqual(s["status"], "completed")
        self.assertEqual(len(s["stages"]), 2 + len(AGENT_STAGES))

    def test_duplicate_lead_goes_to_exception_and_research_never_runs(self):
        calls = []
        o = self.orch(handlers={"research": passing_double(calls)})
        s = o.process_lead(load("duplicate_lead"))
        self.assertEqual((s["status"], s["reason_code"]), ("exception", "DUPLICATE_LEAD"))
        self.assertEqual(calls, [])

    def test_missing_data_goes_to_exception_as_invalid(self):
        calls = []
        s = self.orch(handlers={"research": passing_double(calls)}).process_lead(load("missing_data"))
        self.assertEqual((s["status"], s["reason_code"]), ("exception", "INVALID_LEAD"))
        self.assertEqual(calls, [])

    def test_conflicting_data_needs_review(self):
        calls = []
        s = self.orch(handlers={"research": passing_double(calls)}).process_lead(load("conflicting_data"))
        self.assertEqual((s["status"], s["reason_code"]), ("exception", "NEEDS_REVIEW"))
        self.assertEqual(calls, [])

    def test_incomplete_lead_goes_to_exception(self):
        s = self.orch().process_lead({"raw_text": "Please contact me at someone@acmecorp.com."})
        self.assertEqual((s["status"], s["reason_code"]), ("exception", "INCOMPLETE_LEAD"))

    def test_possible_duplicate_same_company_different_contact(self):
        text = ("My name is Tom Reed and I am the CTO at Acme Logistics. Reach me at tom.reed@acmelogistics.com. "
                "We need to automate invoice matching.")
        s = self.orch().process_lead({"raw_text": text})
        self.assertEqual((s["status"], s["reason_code"]), ("exception", "POSSIBLE_DUPLICATE"))

    def test_free_email_is_routed_to_review_not_research(self):
        text = ("My name is Asha Rao and I am the CEO at Rao Textiles. Email me at asha.rao@gmail.com. "
                "We need to automate order tracking.")
        s = self.orch().process_lead({"raw_text": text})
        self.assertEqual((s["status"], s["reason_code"]), ("exception", "NEEDS_REVIEW"))

    def test_empty_input_goes_to_exception(self):
        s = self.orch().process_lead({"raw_text": ""})
        self.assertEqual((s["status"], s["reason_code"]), ("exception", "INVALID_LEAD"))

    def test_non_dict_input_is_rejected(self):
        s = self.orch().process_lead("just a string")
        self.assertEqual((s["status"], s["reason_code"]), ("exception", "MALFORMED_INPUT"))

    # ---- gate rejects bad intake output ----------------------------------- #
    def test_malformed_intake_output_is_rejected(self):
        s = self.orch(intake=lambda lead: {"lead_name": "X"}).process_lead(load("normal_lead"))
        self.assertEqual((s["status"], s["reason_code"]), ("exception", "MALFORMED_INTAKE"))

    def test_intake_claiming_valid_without_email_is_rejected(self):
        def lying_intake(lead):
            out = {k: None for k in ["lead_name", "company_name", "email", "industry", "employee_count",
                                     "budget", "urgency"]}
            out.update(requirements=["x"], missing_fields=[], notes=[],
                       duplicate_status="not_duplicate", validation_status="valid")
            return out
        s = self.orch(intake=lying_intake).process_lead(load("normal_lead"))
        self.assertEqual((s["status"], s["reason_code"]), ("exception", "INCONSISTENT_INTAKE"))

    # ---- workflow-level duplicate protection ------------------------------ #
    def test_same_lead_submitted_twice_is_blocked(self):
        o = self.orch()
        first = o.process_lead(load("normal_lead"))
        second = o.process_lead(load("normal_lead"))
        self.assertEqual(first["status"], "awaiting_stage")
        self.assertEqual((second["status"], second["reason_code"]), ("exception", "WORKFLOW_DUPLICATE"))
        item = [e for e in o.list_exceptions() if e["run_id"] == second["run_id"]][0]
        self.assertEqual(json.loads(item["details_json"])["existing_run_id"], first["run_id"])

    def test_resubmission_allowed_after_first_run_was_rejected(self):
        o = self.orch()
        o.process_lead(load("duplicate_lead"))  # exception, not an active run
        again = o.process_lead(load("duplicate_lead"))
        self.assertEqual(again["reason_code"], "DUPLICATE_LEAD")  # blocked by CRM duplicate, not workflow

    # ---- retries and errors ------------------------------------------------ #
    def test_flaky_agent_succeeds_after_retry(self):
        n = {"calls": 0}

        def flaky(payload):
            n["calls"] += 1
            if n["calls"] < 2:
                raise RuntimeError("temporary failure")
            return {"stage_status": "passed"}
        s = self.orch(handlers={"research": flaky}).process_lead(load("normal_lead"))
        research = [x for x in s["stages"] if x["stage"] == "research"][0]
        self.assertEqual((research["status"], research["attempts"]), ("passed", 2))

    def test_agent_that_always_crashes_fails_run_after_three_attempts(self):
        n = {"calls": 0}

        def broken(payload):
            n["calls"] += 1
            raise RuntimeError("boom")
        o = self.orch(handlers={"research": broken})
        s = o.process_lead(load("normal_lead"))
        self.assertEqual((s["status"], s["reason_code"]), ("failed", "AGENT_ERROR"))
        self.assertEqual(n["calls"], 3)
        self.assertEqual(o.list_exceptions()[0]["reason_code"], "AGENT_ERROR")

    def test_backoff_delays_are_used_between_retries(self):
        delays = []

        def broken(payload):
            raise RuntimeError("boom")
        self.orch(handlers={"research": broken}, sleep=delays.append).process_lead(load("normal_lead"))
        self.assertEqual(delays, [0.5, 1.0])

    def test_intake_crash_is_retried_then_failed(self):
        def broken_intake(lead):
            raise ValueError("bad parser")
        s = self.orch(intake=broken_intake).process_lead(load("normal_lead"))
        self.assertEqual((s["status"], s["reason_code"]), ("failed", "AGENT_ERROR"))
        self.assertEqual(s["stages"][0]["attempts"], 3)

    def test_not_implemented_error_is_not_retried(self):
        n = {"calls": 0}

        def todo(payload):
            n["calls"] += 1
            raise NotImplementedError("later")
        s = self.orch(handlers={"research": todo}).process_lead(load("normal_lead"))
        self.assertEqual(n["calls"], 1)
        self.assertEqual(s["status"], "awaiting_stage")

    # ---- stage output gating ----------------------------------------------- #
    def test_output_without_stage_status_is_rejected(self):
        calls = []

        def vague(payload):
            return {"summary": "looks good"}
        o = self.orch(handlers={"research": vague, "qualification": passing_double(calls)})
        s = o.process_lead(load("normal_lead"))
        self.assertEqual((s["status"], s["reason_code"]), ("exception", "STAGE_OUTPUT_INVALID"))
        self.assertEqual(calls, [])

    def test_non_dict_output_is_rejected(self):
        s = self.orch(handlers={"research": lambda p: "ok"}).process_lead(load("normal_lead"))
        self.assertEqual(s["reason_code"], "STAGE_OUTPUT_INVALID")

    def test_failed_stage_stops_pipeline(self):
        calls = []
        o = self.orch(handlers={"research": lambda p: {"stage_status": "failed"},
                                "qualification": passing_double(calls)})
        s = o.process_lead(load("normal_lead"))
        self.assertEqual((s["status"], s["reason_code"]), ("exception", "STAGE_FAILED"))
        self.assertEqual(calls, [])

    def test_needs_review_stage_stops_pipeline(self):
        calls = []
        o = self.orch(handlers={"research": lambda p: {"stage_status": "needs_review"},
                                "qualification": passing_double(calls)})
        s = o.process_lead(load("normal_lead"))
        self.assertEqual((s["status"], s["reason_code"]), ("exception", "STAGE_NEEDS_REVIEW"))
        self.assertEqual(calls, [])

    def test_agent_cannot_mutate_stored_intake_result(self):
        seen = {}

        def mutator(payload):
            payload["lead"]["email"] = "attacker@evil.test"
            return {"stage_status": "passed"}

        def reader(payload):
            seen["email"] = payload["lead"]["email"]
            return {"stage_status": "passed"}
        self.orch(handlers={"research": mutator, "qualification": reader}).process_lead(load("normal_lead"))
        self.assertEqual(seen["email"], "rahul.mehta@orbitfreight.com")

    # ---- persistence and audit -------------------------------------------- #
    def test_state_survives_a_new_orchestrator_instance(self):
        run_id = self.orch().process_lead(load("normal_lead"))["run_id"]
        reopened = Orchestrator(db_path=self.db, log_path=self.log)
        self.addCleanup(reopened.close)
        run = reopened.get_run(run_id)
        self.assertEqual(run["status"], "awaiting_stage")
        self.assertEqual(run["lead_email"], "rahul.mehta@orbitfreight.com")
        self.assertEqual([s["stage"] for s in run["stages"]], ["intake", "validation_gate", "research", "qualification", "scoring", "routing", "strategy", "communication", "qa"])
        self.assertEqual(json.loads(run["input_json"]), load("normal_lead"))

    def test_exception_queue_and_log_are_written(self):
        o = self.orch()
        o.process_lead(load("missing_data"))
        o.process_lead(load("duplicate_lead"))
        codes = [e["reason_code"] for e in o.list_exceptions()]
        self.assertEqual(sorted(codes), ["DUPLICATE_LEAD", "INVALID_LEAD"])
        events = [json.loads(line)["event"] for line in self.log.read_text().splitlines()]
        self.assertIn("routed_to_exception", events)
        self.assertIn("run_started", events)

    def test_logging_failure_does_not_break_workflow(self):
        bad_log = Path(self.tmp.name) / "afile"
        bad_log.write_text("x")  # a file where a directory is needed -> OSError on write
        o = Orchestrator(db_path=self.db, log_path=bad_log / "orch.log", handlers={"research": passing_double(), "qualification": passing_double(), "scoring": passing_double(), "routing": passing_double(), "strategy": passing_double(), "communication": passing_double(), "qa": None})
        self.addCleanup(o.close)
        s = o.process_lead(load("normal_lead"))
        self.assertEqual(s["status"], "awaiting_stage")


if __name__ == "__main__":
    unittest.main(verbosity=2)
