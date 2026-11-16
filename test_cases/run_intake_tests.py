"""Run the Intake Agent on every test case and compare to each case's "expected" block.

Usage (from project root):  python3 test_cases/run_intake_tests.py
Exit code 0 = all pass, 1 = at least one mismatch.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents.intake_agent import run_intake  # noqa: E402

SCHEMA_KEYS = ["lead_name", "company_name", "email", "industry", "employee_count", "requirements",
               "budget", "urgency", "missing_fields", "duplicate_status", "validation_status", "notes"]


def main() -> int:
    failures = 0
    for path in sorted((ROOT / "test_cases").glob("*.json")):
        case = json.loads(path.read_text(encoding="utf-8"))
        out = run_intake(case["input"])
        problems = []
        if list(out.keys()) != SCHEMA_KEYS:
            problems.append(f"schema keys differ: {list(out.keys())}")
        for key, want in case["expected"].items():
            if out.get(key) != want:
                problems.append(f"{key}: expected {want!r}, got {out.get(key)!r}")
        status = "PASS" if not problems else "FAIL"
        failures += bool(problems)
        print(f"[{status}] {case['case_id']}: {case['description']}")
        for p in problems:
            print(f"        - {p}")
    print(f"\n{len(list((ROOT / 'test_cases').glob('*.json'))) - failures} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
