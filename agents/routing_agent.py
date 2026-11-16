"""
NEXORA TECHNOLOGIES
Routing Agent - Version 1.0

Assigns qualified leads to the appropriate sales team
using company segment and lead priority.
"""


def run_routing(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return {"stage_status": "failed", "reason": "Invalid routing payload."}

    previous = payload.get("previous", {})
    if not isinstance(previous, dict):
        return {"stage_status": "failed", "reason": "Invalid previous-stage data."}

    qualification = previous.get("qualification", {})
    scoring = previous.get("scoring", {})

    if not isinstance(qualification, dict) or not isinstance(scoring, dict):
        return {"stage_status": "failed", "reason": "Qualification and scoring outputs are required."}

    if qualification.get("qualification_status") == "needs_review":
        return {"stage_status": "needs_review", "reason": "Qualification requires human review."}

    if scoring.get("stage_status") == "needs_review":
        return {"stage_status": "needs_review", "reason": "Scoring requires human review."}

    if qualification.get("qualification_status") != "qualified":
        return {"stage_status": "failed", "reason": "Only qualified leads can be routed."}

    if scoring.get("stage_status") != "passed":
        return {"stage_status": "failed", "reason": "Successful scoring is required before routing."}

    segment = qualification.get("company_size_segment")
    priority = scoring.get("lead_priority")
    score = scoring.get("lead_score")

    if not isinstance(score, (int, float)) or isinstance(score, bool) or not 0 <= score <= 100:
        return {"stage_status": "failed", "reason": "A valid lead score between 0 and 100 is required."}

    if priority not in ("high", "medium", "low"):
        return {"stage_status": "failed", "reason": "A valid lead priority is required."}

    if segment == "enterprise":
        team = "Enterprise Sales"
    elif segment == "medium_sized_business":
        team = "Mid-Market Sales"
    else:
        return {"stage_status": "needs_review", "reason": "Company segment is unavailable or unsupported."}

    if priority == "high":
        role = "Senior Account Executive"
        action = "Priority sales outreach"
        follow_up = "Within 1 business hour"
        queue = "priority_sales_queue"
    elif priority == "medium":
        role = "Account Executive"
        action = "Standard sales outreach"
        follow_up = "Within 1 business day"
        queue = "standard_sales_queue"
    else:
        role = "Sales Development Representative"
        action = "Lead nurturing"
        follow_up = "Within 3 business days"
        queue = "nurture_queue"

    return {
        "stage_status": "passed",
        "routing_decision": "assigned",
        "assigned_team": team,
        "assigned_role": role,
        "routing_queue": queue,
        "recommended_action": action,
        "follow_up_target": follow_up,
        "lead_score": score,
        "lead_priority": priority,
        "company_size_segment": segment,
        "routing_reason": [
            f"Company segment: {segment}.",
            f"Lead priority: {priority}.",
            f"Lead score: {score}/100."
        ],
        "routing_rules": {
            "routing_method": "deterministic_rule_based",
            "external_assignment_performed": False
        }
    }
