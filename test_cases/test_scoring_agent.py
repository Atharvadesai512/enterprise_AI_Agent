from agents.scoring_agent import run_scoring


def valid_payload():
    return {
        "lead": {
            "lead_name": "Rahul Sharma",
            "company_name": "ABC Manufacturing Pvt Ltd",
            "email": "rahul@abcmanufacturing.com",
            "requirements": ["Finance automation", "HR automation"],
            "urgency": "high",
            "budget": "₹10 lakh"
        },
        "previous": {
            "research": {
                "stage_status": "passed",
                "research_confidence": "high"
            },
            "qualification": {
                "stage_status": "passed",
                "qualification_status": "qualified",
                "company_size_segment": "medium_sized_business"
            }
        }
    }


def test_high_fit_lead_gets_expected_score():
    result = run_scoring(valid_payload())
    assert result["stage_status"] == "passed"
    assert result["lead_score"] == 94
    assert result["lead_priority"] == "high"


def test_missing_budget_reduces_score():
    payload = valid_payload()
    payload["lead"]["budget"] = None
    result = run_scoring(payload)
    assert result["stage_status"] == "passed"
    assert result["lead_score"] == 84


def test_research_needs_review_stops_scoring():
    payload = valid_payload()
    payload["previous"]["research"]["stage_status"] = "needs_review"
    result = run_scoring(payload)
    assert result["stage_status"] == "needs_review"


def test_unqualified_lead_cannot_be_scored():
    payload = valid_payload()
    payload["previous"]["qualification"]["qualification_status"] = "not_qualified"
    result = run_scoring(payload)
    assert result["stage_status"] == "failed"


def test_enterprise_lead_gets_enterprise_fit_points():
    payload = valid_payload()
    payload["previous"]["qualification"]["company_size_segment"] = "enterprise"
    result = run_scoring(payload)
    assert result["stage_status"] == "passed"
    assert result["score_breakdown"]["company_fit"]["points"] == 30
