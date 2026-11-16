import unittest
from agents.qa_agent import run_qa


def valid_payload():
    lead_name = "Rahul Sharma"
    company_name = "ABC Manufacturing Pvt Ltd"
    proposition = "Explore opportunities to reduce repetitive finance work."
    question = "Which finance processes require the most manual effort?"

    body = (
        f"Hello {lead_name},\n\n"
        f"We would like to explore automation opportunities at {company_name}.\n\n"
        f"{proposition}\n\n"
        f"{question}\n\n"
        "Would you be available for a short discussion?\n\n"
        "Best regards,\nNexora Technologies"
    )

    return {
        "lead": {
            "lead_name": lead_name,
            "company_name": company_name,
            "email": "rahul@abcmanufacturing.com",
            "requirements": ["Finance automation"]
        },
        "previous": {
            "research": {"stage_status": "passed"},
            "strategy": {
                "stage_status": "passed",
                "requirements_addressed": ["Finance automation"],
                "value_propositions": [proposition],
                "discovery_questions": [question]
            },
            "communication": {
                "stage_status": "passed",
                "recipient": "rahul@abcmanufacturing.com",
                "subject": "Exploring automation opportunities",
                "email_body": body,
                "human_approval_required": True,
                "external_message_sent": False,
                "communication_rules": {
                    "external_action_performed": False
                }
            }
        }
    }


class QAAgentTests(unittest.TestCase):

    def test_valid_draft_passes_qa(self):
        result = run_qa(valid_payload())
        self.assertEqual(result["stage_status"], "passed")
        self.assertEqual(result["failed_checks"], 0)

    def test_all_eight_checks_pass(self):
        result = run_qa(valid_payload())
        self.assertEqual(result["passed_checks"], 8)

    def test_wrong_recipient_requires_review(self):
        payload = valid_payload()
        payload["previous"]["communication"]["recipient"] = "wrong@example.com"
        result = run_qa(payload)
        self.assertEqual(result["stage_status"], "needs_review")

    def test_missing_subject_requires_review(self):
        payload = valid_payload()
        payload["previous"]["communication"]["subject"] = ""
        result = run_qa(payload)
        self.assertEqual(result["stage_status"], "needs_review")

    def test_missing_personalisation_requires_review(self):
        payload = valid_payload()
        payload["previous"]["communication"]["email_body"] = (
            "Hello, we would like to discuss workflow automation opportunities."
        )
        result = run_qa(payload)
        self.assertEqual(result["stage_status"], "needs_review")

    def test_unaddressed_requirement_requires_review(self):
        payload = valid_payload()
        payload["previous"]["strategy"]["requirements_addressed"] = []
        result = run_qa(payload)
        self.assertEqual(result["stage_status"], "needs_review")

    def test_unsupported_guarantee_requires_review(self):
        payload = valid_payload()
        payload["previous"]["communication"]["email_body"] += (
            "\nWe guarantee 100% success."
        )
        result = run_qa(payload)
        self.assertEqual(result["stage_status"], "needs_review")

    def test_missing_human_approval_requires_review(self):
        payload = valid_payload()
        payload["previous"]["communication"]["human_approval_required"] = False
        result = run_qa(payload)
        self.assertEqual(result["stage_status"], "needs_review")

    def test_external_message_detected_requires_review(self):
        payload = valid_payload()
        payload["previous"]["communication"]["external_message_sent"] = True
        result = run_qa(payload)
        self.assertEqual(result["stage_status"], "needs_review")

    def test_invalid_payload_is_rejected(self):
        result = run_qa("invalid")
        self.assertEqual(result["stage_status"], "failed")


if __name__ == "__main__":
    unittest.main()
