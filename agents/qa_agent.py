"""
NEXORA TECHNOLOGIES
QA Agent - Version 1.0

Performs deterministic quality checks on sales communication drafts.
Does not approve or send external messages.
"""

import re


def run_qa(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return {"stage_status": "failed", "reason": "Invalid QA payload."}

    lead = payload.get("lead", {})
    previous = payload.get("previous", {})

    if not isinstance(lead, dict) or not isinstance(previous, dict):
        return {"stage_status": "failed", "reason": "Invalid lead or previous-stage data."}

    research = previous.get("research", {})
    strategy = previous.get("strategy", {})
    communication = previous.get("communication", {})

    if not all(isinstance(item, dict) for item in (research, strategy, communication)):
        return {
            "stage_status": "failed",
            "reason": "Research, strategy, and communication outputs are required."
        }

    if any(item.get("stage_status") == "needs_review"
           for item in (research, strategy, communication)):
        return {
            "stage_status": "needs_review",
            "reason": "A previous stage requires human review."
        }

    if research.get("stage_status") != "passed":
        return {"stage_status": "failed", "reason": "Successful research is required."}

    if strategy.get("stage_status") != "passed":
        return {"stage_status": "failed", "reason": "Successful strategy is required."}

    if communication.get("stage_status") != "passed":
        return {"stage_status": "failed", "reason": "Successful communication draft is required."}

    checks = []

    def check(name, passed, message):
        checks.append({
            "check": name,
            "status": "passed" if passed else "failed",
            "message": message
        })

    # 1. Recipient validation
    expected_email = lead.get("email")
    actual_email = communication.get("recipient")

    recipient_ok = (
        isinstance(expected_email, str)
        and bool(expected_email.strip())
        and actual_email == expected_email
        and "@" in actual_email
    )
    check("recipient_validation", recipient_ok,
          "Draft recipient matches the lead email." if recipient_ok
          else "Draft recipient is missing or does not match the lead email.")

    # 2. Subject and message validation
    subject = communication.get("subject")
    body = communication.get("email_body")

    content_ok = (
        isinstance(subject, str) and bool(subject.strip())
        and isinstance(body, str) and len(body.strip()) >= 40
    )
    check("content_validation", content_ok,
          "Email subject and body are present." if content_ok
          else "Email subject or body is missing or too short.")

    if not content_ok:
        return {
            "stage_status": "needs_review",
            "qa_status": "review_required",
            "checks": checks,
            "reason": "Communication content is incomplete."
        }

    # 3. Personalisation validation
    lead_name = lead.get("lead_name")
    company_name = lead.get("company_name")

    personalisation_ok = (
        isinstance(lead_name, str) and bool(lead_name.strip())
        and lead_name.strip() in body
        and isinstance(company_name, str) and bool(company_name.strip())
        and company_name.strip() in body
    )
    check("personalisation", personalisation_ok,
          "Email includes the lead and company names." if personalisation_ok
          else "Email is missing lead or company personalisation.")

    # 4. Requirement alignment
    requirements = lead.get("requirements", [])
    addressed = strategy.get("requirements_addressed", [])

    if not isinstance(requirements, list) or not isinstance(addressed, list):
        requirements_ok = False
    else:
        clean_requirements = [
            item.strip().casefold() for item in requirements
            if isinstance(item, str) and item.strip()
        ]
        clean_addressed = [
            item.strip().casefold() for item in addressed
            if isinstance(item, str) and item.strip()
        ]
        requirements_ok = (
            bool(clean_requirements)
            and all(item in clean_addressed for item in clean_requirements)
        )

    check("requirement_alignment", requirements_ok,
          "Strategy addresses the lead's stated requirements."
          if requirements_ok else
          "One or more lead requirements are not addressed by the strategy.")

    # 5. Verify strategy content appears in the email
    propositions = strategy.get("value_propositions", [])
    questions = strategy.get("discovery_questions", [])

    if not isinstance(propositions, list) or not isinstance(questions, list):
        strategy_content_ok = False
    else:
        strategy_content_ok = (
            bool(propositions)
            and all(
                isinstance(item, str) and item.strip() and item.strip() in body
                for item in propositions
            )
            and all(
                isinstance(item, str) and item.strip() and item.strip() in body
                for item in questions
            )
        )

    check("strategy_alignment", strategy_content_ok,
          "Email reflects the approved strategy recommendations."
          if strategy_content_ok else
          "Email does not fully reflect the strategy recommendations.")

    # 6. Flag unsupported numerical promises and absolute guarantees
    risky_patterns = [
        r"\bguarantee(?:d|s)?\b",
        r"\b100\s*%\s*(?:success|increase|improvement|savings)\b",
        r"\b(?:save|increase|reduce|improve)\s+(?:by\s+)?\d+(?:\.\d+)?\s*%",
        r"\b\d+(?:\.\d+)?\s*%\s*(?:increase|reduction|improvement|savings)\b",
        r"\b(?:guaranteed|assured)\s+(?:results|roi|savings|success)\b"
    ]

    unsupported_claims = [
        pattern for pattern in risky_patterns
        if re.search(pattern, body, flags=re.IGNORECASE)
    ]

    claims_ok = not unsupported_claims
    check("unsupported_claims", claims_ok,
          "No obvious unsupported numerical promises or guarantees detected."
          if claims_ok else
          "Potential unsupported promises or guarantees require human review.")

    # 7. Human approval safeguard
    approval_ok = communication.get("human_approval_required") is True
    check("human_approval", approval_ok,
          "Human approval is required before external use."
          if approval_ok else
          "Human approval safeguard is missing.")

    # 8. External action safeguard
    rules = communication.get("communication_rules", {})
    if not isinstance(rules, dict):
        rules = {}

    external_action_ok = (
        communication.get("external_message_sent") is False
        and rules.get("external_action_performed") is False
    )
    check("external_action_safeguard", external_action_ok,
          "No external message was sent or action performed."
          if external_action_ok else
          "External action detected or cannot be ruled out.")

    failed_checks = [
        item for item in checks if item["status"] == "failed"
    ]

    if failed_checks:
        return {
            "stage_status": "needs_review",
            "qa_status": "review_required",
            "checks": checks,
            "passed_checks": len(checks) - len(failed_checks),
            "failed_checks": len(failed_checks),
            "human_approval_required": True,
            "external_action_performed": False,
            "reason": "One or more quality checks require human review."
        }

    return {
        "stage_status": "passed",
        "qa_status": "passed_pending_human_approval",
        "checks": checks,
        "passed_checks": len(checks),
        "failed_checks": 0,
        "human_approval_required": True,
        "external_action_performed": False,
        "qa_method": "deterministic_rule_based"
    }
