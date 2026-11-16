"""
NEXORA TECHNOLOGIES
Qualification Agent - Version 1.0

Evaluates whether a researched lead fits Nexora's target customer profile.
Rules are provisional demo assumptions.
"""


def run_qualification(payload: dict) -> dict:
    lead = payload.get("lead", {})
    previous = payload.get("previous", {})
    research = previous.get("research", {})

    if not isinstance(lead, dict) or not isinstance(research, dict):
        return {
            "stage_status": "failed",
            "reason": "Invalid lead or research input."
        }

    if research.get("stage_status") == "needs_review":
        return {
            "stage_status": "needs_review",
            "qualification_status": "needs_review",
            "reasons": ["Research requires human review."]
        }

    if research.get("stage_status") != "passed":
        return {
            "stage_status": "failed",
            "reason": "Successful company research is required."
        }

    profile = research.get("company_profile", {})
    verified_facts = research.get("verified_facts", [])

    employee_count = None

    for fact in verified_facts:
        if (
            fact.get("field") == "company_size"
            and fact.get("classification") == "FACT"
            and isinstance(fact.get("value"), int)
            and not isinstance(fact.get("value"), bool)
        ):
            employee_count = fact["value"]
            break

    employee_count_source = "verified_research"

    if employee_count is None:
        prospect_data = research.get("prospect_provided", {})
        supplied_count = prospect_data.get("company_size")

        if (
            isinstance(supplied_count, int)
            and not isinstance(supplied_count, bool)
            and supplied_count >= 0
        ):
            employee_count = supplied_count
            employee_count_source = "prospect_provided"

    if employee_count is None or employee_count < 0:
        return {
            "stage_status": "needs_review",
            "qualification_status": "needs_review",
            "reasons": ["Employee count is unavailable."]
        }

    requirements = lead.get("requirements")

    if not isinstance(requirements, list) or not any(
        isinstance(item, str) and item.strip() for item in requirements
    ):
        return {
            "stage_status": "needs_review",
            "qualification_status": "needs_review",
            "reasons": ["A clear automation requirement is unavailable."]
        }

    if employee_count < 50:
        return {
            "stage_status": "passed",
            "qualification_status": "not_qualified",
            "company_size_segment": "small_business",
            "employee_count": employee_count,
            "employee_count_source": employee_count_source,
            "reasons": [
                "Company has fewer than 50 employees.",
                "Outside Nexora's provisional target customer profile."
            ]
        }

    if employee_count >= 1000:
        segment = "enterprise"
    else:
        segment = "medium_sized_business"

    return {
        "stage_status": "passed",
        "qualification_status": "qualified",
        "company_size_segment": segment,
        "employee_count": employee_count,
            "employee_count_source": employee_count_source,
        "requirements": requirements,
        "budget_status": (
            "provided" if lead.get("budget") else "not_provided"
        ),
        "reasons": [
            "Company meets the provisional employee-count criteria.",
            "Lead has stated automation requirements."
        ],
        "qualification_rules": {
            "minimum_employees": 50,
            "enterprise_threshold": 1000,
            "budget_required": False
        }
    }
