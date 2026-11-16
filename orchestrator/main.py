"""Orchestrator — Nexora Agentic Sales System (Step 4).

Responsibilities
  * Receive a raw lead, run the Intake Agent, and persist every step.
  * Run a deterministic validation gate on the intake result (plain Python, no AI).
  * Send valid leads on to the Research stage; send everything else to the exception queue.
  * Continue to a stage only when the previous stage explicitly passed.
  * Track attempts, errors and outputs of each agent; retry agent crashes with backoff.

What it deliberately does NOT do
  * It gives agents no write access to anything. It performs no external actions (email, CRM
    writes). Those will need a separate human-approval step before they are ever added.
  * It does not fake results. A stage whose agent is not built yet is recorded as
    `not_implemented` and the run stops there with status `awaiting_stage`.

Agent contract (stages after intake)
  Each agent is `agents/<stage>_agent.py::run_<stage>(payload: dict) -> dict`, where payload is
  {"run_id", "lead": <intake result>, "previous": {<stage>: <output>, ...}}.
  The returned dict MUST contain `"stage_status"`: "passed" | "failed" | "needs_review".
  Anything else is rejected (STAGE_OUTPUT_INVALID) so a malformed agent cannot silently advance.

Usage:
    python3 orchestrator/main.py test_cases/normal_lead.json
    python3 orchestrator/main.py --all
    python3 orchestrator/main.py --all --db /tmp/demo.db
"""

from __future__ import annotations

import copy
import importlib
import json
import sqlite3
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents.intake_agent import run_intake  # noqa: E402

DEFAULT_DB = ROOT / "database" / "workflow_state.db"
SCHEMA_FILE = ROOT / "database" / "schema.sql"
DEFAULT_LOG = ROOT / "logs" / "orchestrator.log.jsonl"

# Stages after the gate, in order. A stage only runs if every earlier stage passed.
AGENT_STAGES = ["research", "qualification", "scoring", "routing", "strategy", "communication", "qa"]

INTAKE_KEYS = [
    "lead_name", "company_name", "email", "industry", "employee_count", "requirements",
    "budget", "urgency", "missing_fields", "duplicate_status", "validation_status", "notes",
]
VALIDATION_STATUSES = {"valid", "incomplete", "needs_review", "invalid"}
DUPLICATE_STATUSES = {"not_duplicate", "possible_duplicate", "duplicate", "unknown"}
STAGE_STATUSES = {"passed", "failed", "needs_review"}

# Runs in these states hold the lead's email, so a second submission is blocked.
ACTIVE_RUN_STATUSES = ("running", "awaiting_stage", "completed")


class Rejection(Exception):
    """A lead the gate refuses to pass on. Carries the exception-queue reason."""

    def __init__(self, code: str, message: str, details: Optional[dict] = None):
        super().__init__(message)
        self.code, self.message, self.details = code, message, details or {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# Deterministic validation gate (no AI involved)
# --------------------------------------------------------------------------- #
def validate_intake_result(result) -> None:
    """Raise Rejection if the intake result must not proceed to research."""
    if not isinstance(result, dict):
        raise Rejection("MALFORMED_INTAKE", f"Intake returned {type(result).__name__}, expected a JSON object.")
    if set(result.keys()) != set(INTAKE_KEYS):
        missing = sorted(set(INTAKE_KEYS) - set(result))
        extra = sorted(set(result) - set(INTAKE_KEYS))
        raise Rejection("MALFORMED_INTAKE", "Intake result does not match the schema.",
                        {"missing_keys": missing, "unexpected_keys": extra})
    if result["validation_status"] not in VALIDATION_STATUSES:
        raise Rejection("MALFORMED_INTAKE", f"Unknown validation_status {result['validation_status']!r}.")
    if result["duplicate_status"] not in DUPLICATE_STATUSES:
        raise Rejection("MALFORMED_INTAKE", f"Unknown duplicate_status {result['duplicate_status']!r}.")
    for key in ("requirements", "missing_fields", "notes"):
        if not isinstance(result[key], list):
            raise Rejection("MALFORMED_INTAKE", f"Field '{key}' must be a list.")

    # A lead cannot claim to be valid while lacking what research needs.
    if result["validation_status"] == "valid":
        absent = [k for k in ("lead_name", "company_name", "email", "requirements") if not result[k]]
        if absent:
            raise Rejection("INCONSISTENT_INTAKE",
                            "Intake marked the lead valid but required fields are empty.",
                            {"empty_fields": absent})

    context = {"validation_status": result["validation_status"],
               "duplicate_status": result["duplicate_status"],
               "missing_fields": result["missing_fields"], "notes": result["notes"]}
    by_validation = {
        "invalid": ("INVALID_LEAD", "Lead is invalid (e.g. no usable email)."),
        "incomplete": ("INCOMPLETE_LEAD", "Lead is missing core information."),
        "needs_review": ("NEEDS_REVIEW", "Lead has conflicting or suspicious data and needs a human."),
    }
    if result["validation_status"] in by_validation:
        code, msg = by_validation[result["validation_status"]]
        raise Rejection(code, msg, context)

    by_duplicate = {
        "duplicate": ("DUPLICATE_LEAD", "Lead already exists in the CRM; no new record may be created."),
        "possible_duplicate": ("POSSIBLE_DUPLICATE", "Lead may already exist in the CRM; a human must confirm."),
        "unknown": ("DUPLICATE_CHECK_UNKNOWN", "Duplicate check could not be completed."),
    }
    if result["duplicate_status"] in by_duplicate:
        code, msg = by_duplicate[result["duplicate_status"]]
        raise Rejection(code, msg, context)


def validate_stage_output(output) -> None:
    """Raise Rejection if an agent's output may not be trusted to advance the workflow."""
    if not isinstance(output, dict):
        raise Rejection("STAGE_OUTPUT_INVALID", f"Agent returned {type(output).__name__}, expected a dict.")
    if output.get("stage_status") not in STAGE_STATUSES:
        raise Rejection("STAGE_OUTPUT_INVALID",
                        "Agent output must contain 'stage_status' of passed | failed | needs_review.",
                        {"got": output.get("stage_status")})
    try:
        json.dumps(output)
    except (TypeError, ValueError) as exc:
        raise Rejection("STAGE_OUTPUT_INVALID", f"Agent output is not JSON-serialisable: {exc}")


# --------------------------------------------------------------------------- #
# Orchestrator
# --------------------------------------------------------------------------- #
class Orchestrator:
    def __init__(self, db_path=None, handlers: Optional[dict[str, Callable]] = None,
                 intake: Callable = run_intake, max_retries: int = 2,
                 sleep: Callable[[float], None] = time.sleep, log_path=None):
        """
        handlers   — optional {stage: callable} overrides (used by tests as test doubles).
                     Stages without one fall back to agents/<stage>_agent.py::run_<stage>.
        max_retries — retries after the first attempt when an agent raises (so 3 attempts total).
        """
        self.handlers = handlers or {}
        self.intake = intake
        self.max_retries = max_retries
        self.sleep = sleep
        self.log_path = Path(log_path) if log_path else DEFAULT_LOG
        self.db_path = str(db_path or DEFAULT_DB)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # ---- public API ------------------------------------------------------- #
    def process_lead(self, raw_lead) -> dict:
        run_id = uuid.uuid4().hex[:12]
        self._create_run(run_id, raw_lead)
        self._event(run_id, "run_started", {})

        if not isinstance(raw_lead, dict):
            return self._reject(run_id, "intake", Rejection(
                "MALFORMED_INPUT", f"Lead must be a JSON object, got {type(raw_lead).__name__}."))

        # Stage 1: intake (agent call, retried on crash)
        started = _now()
        attempts, intake_result, error = self._call_with_retry(self.intake, raw_lead)
        if error is not None:
            self._record_stage(run_id, "intake", "failed", attempts, None, error, started)
            return self._fail(run_id, "intake", "AGENT_ERROR",
                              f"Intake agent crashed after {attempts} attempt(s): {error}")
        self._record_stage(run_id, "intake", "passed", attempts, intake_result, None, started)

        # Stage 2: validation gate (deterministic)
        started = _now()
        try:
            validate_intake_result(intake_result)
            self._check_workflow_duplicate(run_id, intake_result)
        except Rejection as rej:
            self._record_stage(run_id, "validation_gate", "routed_to_exception", 1,
                               {"code": rej.code, "message": rej.message}, None, started)
            self._store_lead_identity(run_id, intake_result)
            return self._reject(run_id, "validation_gate", rej)
        self._record_stage(run_id, "validation_gate", "passed", 1, {"code": "OK"}, None, started)
        self._store_lead_identity(run_id, intake_result)

        # Stages 3+: each runs only if every earlier stage passed
        previous: dict[str, dict] = {}
        for stage in AGENT_STAGES:
            self._set_run(run_id, status="running", current_stage=stage)
            handler = self._resolve_handler(stage)
            started = _now()
            if handler is None:
                self._record_stage(run_id, stage, "not_implemented", 0, None,
                                   f"No agent registered for stage '{stage}'.", started)
                self._set_run(run_id, status="awaiting_stage", current_stage=stage,
                              final_reason="STAGE_NOT_IMPLEMENTED")
                self._event(run_id, "awaiting_stage", {"stage": stage})
                return self._summary(run_id)

            payload = {"run_id": run_id, "lead": intake_result, "previous": previous}
            attempts, output, error = self._call_with_retry(handler, payload)
            if isinstance(error, NotImplementedError):
                self._record_stage(run_id, stage, "not_implemented", attempts, None, str(error), started)
                self._set_run(run_id, status="awaiting_stage", current_stage=stage,
                              final_reason="STAGE_NOT_IMPLEMENTED")
                return self._summary(run_id)
            if error is not None:
                self._record_stage(run_id, stage, "failed", attempts, None, error, started)
                return self._fail(run_id, stage, "AGENT_ERROR",
                                  f"{stage} agent crashed after {attempts} attempt(s): {error}")
            try:
                validate_stage_output(output)
            except Rejection as rej:
                self._record_stage(run_id, stage, "failed", attempts, None, rej.message, started)
                return self._reject(run_id, stage, rej)

            self._record_stage(run_id, stage, output["stage_status"], attempts, output, None, started)
            if output["stage_status"] == "failed":
                return self._reject(run_id, stage, Rejection(
                    "STAGE_FAILED", f"{stage} agent reported failure.", {"output": output}))
            if output["stage_status"] == "needs_review":
                return self._reject(run_id, stage, Rejection(
                    "STAGE_NEEDS_REVIEW", f"{stage} agent asked for human review.", {"output": output}))
            if (
                stage == "qualification"
                and output.get("qualification_status") == "not_qualified"
            ):
                return self._reject(
                    run_id,
                    stage,
                    Rejection(
                        "LEAD_NOT_QUALIFIED",
                        "Lead does not meet Nexora's target customer criteria.",
                        {"output": output}
                    )
                )

            previous[stage] = output

        self._set_run(run_id, status="completed", current_stage=AGENT_STAGES[-1])
        self._event(run_id, "run_completed", {})
        return self._summary(run_id)

    def get_run(self, run_id: str) -> Optional[dict]:
        row = self.conn.execute("SELECT * FROM workflow_runs WHERE run_id=?", (run_id,)).fetchone()
        if not row:
            return None
        run = dict(row)
        run["stages"] = [dict(r) for r in self.conn.execute(
            "SELECT stage, status, attempts, error, started_at, finished_at FROM stage_results "
            "WHERE run_id=? ORDER BY id", (run_id,))]
        run["exceptions"] = [dict(r) for r in self.conn.execute(
            "SELECT * FROM exception_queue WHERE run_id=? ORDER BY id", (run_id,))]
        return run

    def list_exceptions(self, status: str = "open") -> list[dict]:
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM exception_queue WHERE status=? ORDER BY id", (status,))]

    # ---- internals ---------------------------------------------------------- #
    def _resolve_handler(self, stage: str) -> Optional[Callable]:
        if stage in self.handlers:
            return self.handlers[stage]
        try:
            module = importlib.import_module(f"agents.{stage}_agent")
        except ImportError:
            return None
        return getattr(module, f"run_{stage}", None)

    def _call_with_retry(self, fn: Callable, payload):
        """Return (attempts, output, error). error is the exception object, or None on success.
        Deterministic NotImplementedError is never retried."""
        attempts, last = 0, None
        while attempts <= self.max_retries:
            attempts += 1
            try:
                return attempts, fn(copy.deepcopy(payload)), None
            except NotImplementedError as exc:
                return attempts, None, exc
            except Exception as exc:  # agent crashed: retry with exponential backoff
                last = exc
                if attempts <= self.max_retries:
                    self.sleep(0.5 * 2 ** (attempts - 1))
        return attempts, None, last

    def _check_workflow_duplicate(self, run_id: str, intake_result: dict) -> None:
        email = (intake_result.get("email") or "").lower()
        if not email:
            return
        marks = ",".join("?" * len(ACTIVE_RUN_STATUSES))
        row = self.conn.execute(
            f"SELECT run_id, status FROM workflow_runs WHERE lead_email=? AND run_id<>? "
            f"AND status IN ({marks}) ORDER BY created_at LIMIT 1",
            (email, run_id, *ACTIVE_RUN_STATUSES)).fetchone()
        if row:
            raise Rejection("WORKFLOW_DUPLICATE",
                            "This lead is already being processed or was already processed.",
                            {"existing_run_id": row["run_id"], "existing_status": row["status"]})

    def _create_run(self, run_id: str, raw_lead) -> None:
        now = _now()
        try:
            payload = json.dumps(raw_lead, ensure_ascii=False)
        except (TypeError, ValueError):
            payload = json.dumps({"unserialisable_input": repr(raw_lead)})
        with self.conn:
            self.conn.execute(
                "INSERT INTO workflow_runs (run_id, created_at, updated_at, status, current_stage, input_json) "
                "VALUES (?,?,?,?,?,?)", (run_id, now, now, "running", "intake", payload))

    def _store_lead_identity(self, run_id: str, intake_result) -> None:
        if not isinstance(intake_result, dict):
            return
        email = intake_result.get("email")
        with self.conn:
            self.conn.execute("UPDATE workflow_runs SET lead_email=?, lead_company=? WHERE run_id=?",
                              (email.lower() if isinstance(email, str) else None,
                               intake_result.get("company_name"), run_id))

    def _set_run(self, run_id: str, **fields) -> None:
        fields["updated_at"] = _now()
        cols = ", ".join(f"{k}=?" for k in fields)
        with self.conn:
            self.conn.execute(f"UPDATE workflow_runs SET {cols} WHERE run_id=?", (*fields.values(), run_id))

    def _record_stage(self, run_id, stage, status, attempts, output, error, started) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO stage_results (run_id, stage, status, attempts, output_json, error, started_at, finished_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (run_id, stage, status, attempts,
                 json.dumps(output, ensure_ascii=False, default=str) if output is not None else None,
                 str(error) if error is not None else None, started, _now()))
        self._event(run_id, "stage_finished", {"stage": stage, "status": status, "attempts": attempts})

    def _reject(self, run_id: str, stage: str, rej: Rejection) -> dict:
        with self.conn:
            self.conn.execute(
                "INSERT INTO exception_queue (run_id, stage, reason_code, message, details_json, created_at) "
                "VALUES (?,?,?,?,?,?)",
                (run_id, stage, rej.code, rej.message,
                 json.dumps(rej.details, ensure_ascii=False, default=str), _now()))
        self._set_run(run_id, status="exception", current_stage=stage, final_reason=rej.code)
        self._event(run_id, "routed_to_exception", {"stage": stage, "reason": rej.code})
        return self._summary(run_id)

    def _fail(self, run_id: str, stage: str, code: str, message: str) -> dict:
        with self.conn:
            self.conn.execute(
                "INSERT INTO exception_queue (run_id, stage, reason_code, message, details_json, created_at) "
                "VALUES (?,?,?,?,?,?)", (run_id, stage, code, message, "{}", _now()))
        self._set_run(run_id, status="failed", current_stage=stage, final_reason=code)
        self._event(run_id, "run_failed", {"stage": stage, "reason": code})
        return self._summary(run_id)

    def _summary(self, run_id: str) -> dict:
        run = self.get_run(run_id)
        return {
            "run_id": run_id,
            "status": run["status"],
            "current_stage": run["current_stage"],
            "reason_code": run["final_reason"],
            "stages": [{"stage": s["stage"], "status": s["status"], "attempts": s["attempts"]}
                       for s in run["stages"]],
        }

    def _event(self, run_id: str, event: str, data: dict) -> None:
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"timestamp": _now(), "run_id": run_id, "event": event, **data}) + "\n")
        except OSError:
            pass  # logging must never break the workflow; state is already in the database


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv: list[str]) -> int:
    db = None
    if "--db" in argv:
        i = argv.index("--db")
        db = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    if not argv:
        print(__doc__)
        return 1
    paths = sorted((ROOT / "test_cases").glob("*.json")) if argv[0] == "--all" else [Path(a) for a in argv]
    orch = Orchestrator(db_path=db)
    for p in paths:
        case = json.loads(p.read_text(encoding="utf-8"))
        summary = orch.process_lead(case["input"])
        print(f"=== {p.name} ===")
        print(json.dumps(summary, indent=2))
    queue = orch.list_exceptions()
    print(f"\nException queue: {len(queue)} open item(s)")
    for item in queue:
        print(f"  - run {item['run_id']} | {item['stage']} | {item['reason_code']}: {item['message']}")
    orch.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
