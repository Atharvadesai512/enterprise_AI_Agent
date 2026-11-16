"""
NEXORA TECHNOLOGIES
Communication Agent - Version 1.0

Creates personalised sales communication drafts.
Never sends external messages.
"""


def run_communication(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return {"stage_status": "failed", "reason": "Invalid communication payload."}

    lead = payload.get("lead", {})
    previous = payload.get("previous", {})

    if not isinstance(lead, dict) or not isinstance(previous, dict):
        return {"stage_status": "failed", "reason": "Invalid lead or previous-stage data."}

    strategy = previous.get("strategy", {})
    routing = previous.get("routing", {})

    if not isinstance(strategy, dict) or not isinstance(routing, dict):
        return {"stage_status": "failed", "reason": "Strategy and routing outputs are required."}

    if strategy.get("stage_status") == "needs_review":
        return {"stage_status": "needs_review", "reason": "Sales strategy requires human review."}

    if strategy.get("stage_status") != "passed":
        return {"stage_status": "failed", "reason": "A successful sales strategy is required."}

    if routing.get("stage_status") != "passed":
        return {"stage_status": "failed", "reason": "Successful lead routing is required."}

    email = lead.get("email")
    if not isinstance(email, str) or "@" not in email:
        return {"stage_status": "needs_review", "reason": "A valid lead email address is required."}

    lead_name = lead.get("lead_name")
    company_name = lead.get("company_name")

    if not isinstance(lead_name, str) or not lead_name.strip():
        lead_name = "there"

    if not isinstance(company_name, str) or not company_name.strip():
        company_name = "your organisation"

    priority = strategy.get("lead_priority")
    if priority not in ("high", "medium", "low"):
        return {"stage_status": "failed", "reason": "A valid lead priority is required."}

    value_propositions = strategy.get("value_propositions", [])
    discovery_questions = strategy.get("discovery_questions", [])

    if not isinstance(value_propositions, list) or not isinstance(discovery_questions, list):
        return {"stage_status": "failed", "reason": "Invalid strategy recommendations."}

    value_propositions = [
        item.strip() for item in value_propositions
        if isinstance(item, str) and item.strip()
    ]

    discovery_questions = [
        item.strip() for item in discovery_questions
        if isinstance(item, str) and item.strip()
    ]

    if not value_propositions:
        return {"stage_status": "needs_review", "reason": "No value propositions are available."}

    # Select communication tone based on lead priority.
    if priority == "high":
        tone = "consultative and personalised"
        subject = f"Exploring automation opportunities at {company_name}"
        opening = (
            f"I would welcome the opportunity to understand your business priorities "
            f"and explore where automation could make a meaningful difference."
        )
    elif priority == "medium":
        tone = "professional and needs-focused"
        subject = f"Workflow automation possibilities for {company_name}"
        opening = (
            f"I wanted to introduce how workflow automation may help address "
            f"some of the operational requirements at your organisation."
        )
    else:
        tone = "informative and educational"
        subject = f"An introduction to business workflow automation"
        opening = (
            f"I wanted to share a few ideas about how businesses can use "
            f"workflow automation to simplify repetitive work."
        )

    benefits_text = "\n".join(
        f"- {item}" for item in value_propositions[:4]
    )

    questions_text = "\n".join(
        f"- {item}" for item in discovery_questions[:3]
    )

    email_body = (
        f"Hello {lead_name},\n\n"
        f"{opening}\n\n"
        f"Based on the requirements shared by {company_name}, "
        f"here are a few areas worth exploring:\n\n"
        f"{benefits_text}\n\n"
        f"To better understand your needs, I would be interested in discussing:\n\n"
        f"{questions_text}\n\n"
        f"Would you be available for a short conversation "
        f"to explore these opportunities?\n\n"
        f"Best regards,\n"
        f"Nexora Technologies\n"
        f"Sales Team"
    )

    follow_up_message = (
        f"Hello {lead_name}, I wanted to follow up on my previous message "
        f"about workflow automation opportunities at {company_name}. "
        f"Would you be open to a brief discussion?"
    )

    return {
        "stage_status": "passed",
        "communication_status": "drafted",
        "channel": "email",
        "recipient": email,
        "subject": subject,
        "email_body": email_body,
        "follow_up_message": follow_up_message,
        "communication_tone": tone,
        "lead_priority": priority,
        "assigned_team": routing.get("assigned_team"),
        "assigned_role": routing.get("assigned_role"),
        "human_approval_required": True,
        "external_message_sent": False,
        "communication_rules": {
            "communication_method": "deterministic_template_based",
            "uses_verified_lead_information": True,
            "external_action_performed": False
        }
    }
