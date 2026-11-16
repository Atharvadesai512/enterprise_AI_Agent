"""
NEXORA TECHNOLOGIES
Scoring Agent - Version 1.0

Calculates a transparent 0-100 lead score using
intake, verified research, and qualification results.
"""


def run_scoring(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return {
            "stage_status": "failed",
            "reason": "Invalid scoring payload."
        }

    lead = payload.get("lead", {})
    previous = payload.get("previous", {})

    if not isinstance(lead, dict) or not isinstance(previous, dict):
        return {
            "stage_status": "failed",
            "reason": "Invalid lead or previous-stage data."
        }

    research = previous.get("research", {})
    qualification = previous.get("qualification", {})

    if not isinstance(research, dict) or not isinstance(qualification, dict):
        return {
            "stage_status": "failed",
            "reason": "Research and qualification outputs are required."
        }

    if research.get("stage_status") == "needs_review":
        return {
            "stage_status": "needs_review",
            "reason": "Research requires human review."
        }

    if qualification.get("qualification_status") == "needs_review":
        return {
            "stage_status": "needs_review",
            "reason": "Qualification requires human review."
        }

    if research.get("stage_status") != "passed":
        return {
            "stage_status": "failed",
            "reason": "Successful research is required before scoring."
        }

    if qualification.get("qualification_status") != "qualified":
        return {
            "stage_status": "failed",
            "reason": "Only qualified leads can proceed to scoring."
        }

    score = 0
    breakdown = {}
    reasons = []

    # 1. Company size fit: maximum 30 points
    segment = qualification.get("company_size_segment")

    if segment == "enterprise":
        points = 30
        reasons.append("Enterprise company profile.")
    elif segment == "medium_sized_business":
        points = 24
        reasons.append("Medium-sized business fits the target profile.")
    else:
        points = 0

    breakdown["company_fit"] = {
        "points": points,
        "maximum": 30
    }
    score += points

    # 2. Research confidence: maximum 20 points
    confidence = research.get("research_confidence")

    confidence_points = {
        "high": 20,
        "medium": 12,
        "low": 5
    }.get(confidence, 0)

    breakdown["research_confidence"] = {
        "points": confidence_points,
        "maximum": 20
    }
    score += confidence_points

    if confidence == "high":
        reasons.append("Company research has high confidence.")

    # 3. Stated automation requirements: maximum 20 points
    requirements = lead.get("requirements", [])

    valid_requirements = [
        item for item in requirements
        if isinstance(item, str) and item.strip()
    ] if isinstance(requirements, list) else []

    requirement_points = min(len(valid_requirements) * 10, 20)

    breakdown["automation_requirements"] = {
        "points": requirement_points,
        "maximum": 20
    }
    score += requirement_points

    if requirement_points:
        reasons.append("Lead has stated automation requirements.")

    # 4. Urgency: maximum 15 points
    urgency = lead.get("urgency")

    urgency_points = {
        "high": 15,
        "medium": 10,
        "low": 5
    }.get(
        urgency.strip().lower() if isinstance(urgency, str) else "",
        0
    )

    breakdown["urgency"] = {
        "points": urgency_points,
        "maximum": 15
    }
    score += urgency_points

    if urgency_points:
        reasons.append(f"Lead urgency recorded as {urgency}.")

    # 5. Budget information: maximum 10 points
    budget_provided = bool(lead.get("budget"))

    budget_points = 10 if budget_provided else 0

    breakdown["budget_information"] = {
        "points": budget_points,
        "maximum": 10
    }
    score += budget_points

    if budget_provided:
        reasons.append("Budget information has been provided.")

    # 6. Contact completeness: maximum 5 points
    contact_points = 0

    if lead.get("lead_name"):
        contact_points += 2

    if lead.get("company_name"):
        contact_points += 1

    if lead.get("email"):
        contact_points += 2

    breakdown["contact_completeness"] = {
        "points": contact_points,
        "maximum": 5
    }
    score += contact_points

    # Lead priority classification
    if score >= 75:
        priority = "high"
    elif score >= 50:
        priority = "medium"
    else:
        priority = "low"

    return {
        "stage_status": "passed",
        "lead_score": score,
        "lead_priority": priority,
        "score_breakdown": breakdown,
        "reasons": reasons,
        "scoring_rules": {
            "maximum_score": 100,
            "high_priority_minimum": 75,
            "medium_priority_minimum": 50,
            "scoring_method": "deterministic_rule_based"
        }
    }
