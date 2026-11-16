"""
NEXORA TECHNOLOGIES
Strategy Agent - Version 1.0

Creates a practical sales strategy from verified workflow outputs.
"""


def run_strategy(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return {"stage_status": "failed", "reason": "Invalid strategy payload."}

    lead = payload.get("lead", {})
    previous = payload.get("previous", {})

    if not isinstance(lead, dict) or not isinstance(previous, dict):
        return {"stage_status": "failed", "reason": "Invalid lead or previous-stage data."}

    qualification = previous.get("qualification", {})
    scoring = previous.get("scoring", {})
    routing = previous.get("routing", {})

    if not all(isinstance(item, dict) for item in (qualification, scoring, routing)):
        return {"stage_status": "failed", "reason": "Qualification, scoring, and routing outputs are required."}

    if any(item.get("stage_status") == "needs_review" for item in (qualification, scoring, routing)):
        return {"stage_status": "needs_review", "reason": "A previous stage requires human review."}

    if qualification.get("qualification_status") != "qualified":
        return {"stage_status": "failed", "reason": "Only qualified leads can receive a sales strategy."}

    if scoring.get("stage_status") != "passed":
        return {"stage_status": "failed", "reason": "Successful scoring is required."}

    if routing.get("stage_status") != "passed":
        return {"stage_status": "failed", "reason": "Successful routing is required."}

    requirements = lead.get("requirements", [])
    if not isinstance(requirements, list):
        return {"stage_status": "needs_review", "reason": "Lead requirements are unavailable."}

    requirements = [
        item.strip() for item in requirements
        if isinstance(item, str) and item.strip()
    ]

    if not requirements:
        return {"stage_status": "needs_review", "reason": "Clear automation requirements are needed."}

    # Build value propositions from the lead's stated requirements.
    value_propositions = []
    discovery_questions = []

    requirement_topics = {
        "finance": (
            "Explore opportunities to reduce repetitive finance work and improve process efficiency.",
            "Which finance processes currently require the most manual effort?"
        ),
        "hr": (
            "Explore opportunities to streamline HR workflows and reduce administrative workload.",
            "Which HR activities would benefit most from automation?"
        ),
        "sales": (
            "Explore opportunities to improve sales workflow efficiency and lead management.",
            "Where do delays or manual tasks occur in your current sales process?"
        ),
        "customer": (
            "Explore opportunities to automate customer-facing workflows and improve response efficiency.",
            "Which customer interactions or support processes should be prioritised?"
        ),
        "inventory": (
            "Explore opportunities to streamline inventory processes and reduce manual tracking.",
            "What inventory tasks currently require repetitive manual work?"
        ),
        "operations": (
            "Explore opportunities to improve operational efficiency through workflow automation.",
            "Which operational processes create the biggest bottlenecks?"
        )
    }

    for requirement in requirements:
        matched = False
        for keyword, (value, question) in requirement_topics.items():
            if keyword in requirement.lower():
                value_propositions.append(value)
                discovery_questions.append(question)
                matched = True
                break

        if not matched:
            value_propositions.append(
                f"Assess how automation could improve the stated requirement: {requirement}."
            )
            discovery_questions.append(
                f"What outcome would you like to achieve by automating {requirement}?"
            )

    priority = scoring.get("lead_priority")
    score = scoring.get("lead_score")

    if priority not in ("high", "medium", "low"):
        return {"stage_status": "failed", "reason": "A valid lead priority is required."}

    if not isinstance(score, (int, float)) or isinstance(score, bool) or not 0 <= score <= 100:
        return {"stage_status": "failed", "reason": "A valid lead score is required."}

    if priority == "high":
        approach = "Consultative priority outreach"
        objective = "Arrange a discovery meeting and identify a suitable automation opportunity."
        next_steps = [
            "Contact the lead with a personalised introduction.",
            "Arrange a discovery meeting.",
            "Understand business impact, stakeholders, and expected outcomes.",
            "Prepare a tailored solution proposal."
        ]
    elif priority == "medium":
        approach = "Needs-focused sales outreach"
        objective = "Understand the lead's requirements and assess solution fit."
        next_steps = [
            "Send a relevant introductory message.",
            "Ask discovery questions about current workflows.",
            "Identify decision-makers and expected outcomes.",
            "Schedule a follow-up discussion."
        ]
    else:
        approach = "Educational lead nurturing"
        objective = "Build interest and learn more about the lead's automation needs."
        next_steps = [
            "Share relevant information about workflow automation.",
            "Understand the lead's current challenges.",
            "Identify potential future opportunities.",
            "Schedule a follow-up when appropriate."
        ]

    return {
        "stage_status": "passed",
        "strategy_status": "created",
        "sales_approach": approach,
        "primary_objective": objective,
        "value_propositions": value_propositions,
        "discovery_questions": discovery_questions,
        "recommended_next_steps": next_steps,
        "assigned_team": routing.get("assigned_team"),
        "assigned_role": routing.get("assigned_role"),
        "lead_priority": priority,
        "lead_score": score,
        "requirements_addressed": requirements,
        "human_review_required_before_external_action": True,
        "strategy_rules": {
            "strategy_method": "deterministic_rule_based",
            "external_action_performed": False
        }
    }
