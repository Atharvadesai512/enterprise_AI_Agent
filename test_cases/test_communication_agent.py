import unittest
from agents.communication_agent import run_communication


def valid_payload():
    return {
        "lead": {
            "lead_name": "Rahul Sharma",
            "company_name": "ABC Manufacturing Pvt Ltd",
            "email": "rahul@abcmanufacturing.com",
            "requirements": ["Finance automation"]
        },
        "previous": {
            "routing": {
                "stage_status": "passed",
                "assigned_team": "Mid-Market Sales",
                "assigned_role": "Account Executive"
            },
            "strategy": {
                "stage_status": "passed",
                "lead_priority": "high",
                "value_propositions": [
                    "Explore opportunities to reduce repetitive finance work."
                ],
                "discovery_questions": [
                    "Which finance processes require the most manual effort?"
                ]
            }
        }
    }


class CommunicationAgentTests(unittest.TestCase):

    def test_generates_email_draft(self):
        result = run_communication(valid_payload())
        self.assertEqual(result["stage_status"], "passed")
        self.assertEqual(result["communication_status"], "drafted")
        self.assertIn("finance", result["email_body"].lower())

    def test_uses_correct_recipient(self):
        result = run_communication(valid_payload())
        self.assertEqual(result["recipient"], "rahul@abcmanufacturing.com")

    def test_personalises_email(self):
        result = run_communication(valid_payload())
        self.assertIn("Rahul Sharma", result["email_body"])
        self.assertIn("ABC Manufacturing Pvt Ltd", result["email_body"])

    def test_generates_subject_and_follow_up(self):
        result = run_communication(valid_payload())
        self.assertTrue(result["subject"])
        self.assertTrue(result["follow_up_message"])

    def test_requires_human_approval(self):
        result = run_communication(valid_payload())
        self.assertTrue(result["human_approval_required"])

    def test_never_sends_external_message(self):
        result = run_communication(valid_payload())
        self.assertFalse(result["external_message_sent"])

    def test_missing_email_requires_review(self):
        payload = valid_payload()
        payload["lead"]["email"] = ""
        result = run_communication(payload)
        self.assertEqual(result["stage_status"], "needs_review")

    def test_strategy_needs_review_stops_communication(self):
        payload = valid_payload()
        payload["previous"]["strategy"]["stage_status"] = "needs_review"
        result = run_communication(payload)
        self.assertEqual(result["stage_status"], "needs_review")

    def test_invalid_priority_is_rejected(self):
        payload = valid_payload()
        payload["previous"]["strategy"]["lead_priority"] = "urgent"
        result = run_communication(payload)
        self.assertEqual(result["stage_status"], "failed")

    def test_invalid_payload_is_rejected(self):
        result = run_communication("invalid")
        self.assertEqual(result["stage_status"], "failed")


if __name__ == "__main__":
    unittest.main()
