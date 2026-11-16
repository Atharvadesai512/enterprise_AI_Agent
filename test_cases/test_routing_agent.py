from agents.routing_agent import run_routing


def valid_payload(segment="medium_sized_business", priority="high"):
    return {
        "previous": {
            "qualification": {
                "qualification_status": "qualified",
                "company_size_segment": segment
            },
            "scoring": {
                "stage_status": "passed",
                "lead_score": 90,
                "lead_priority": priority
            }
        }
    }


def test_enterprise_routes_to_enterprise_sales():
    result = run_routing(valid_payload("enterprise"))
    assert result["assigned_team"] == "Enterprise Sales"


def test_medium_business_routes_to_mid_market():
    result = run_routing(valid_payload())
    assert result["assigned_team"] == "Mid-Market Sales"


def test_high_priority_gets_senior_account_executive():
    result = run_routing(valid_payload(priority="high"))
    assert result["assigned_role"] == "Senior Account Executive"
    assert result["follow_up_target"] == "Within 1 business hour"


def test_low_priority_goes_to_nurture_queue():
    result = run_routing(valid_payload(priority="low"))
    assert result["routing_queue"] == "nurture_queue"


def test_needs_review_stops_routing():
    payload = valid_payload()
    payload["previous"]["qualification"]["qualification_status"] = "needs_review"
    result = run_routing(payload)
    assert result["stage_status"] == "needs_review"


def test_invalid_score_is_rejected():
    payload = valid_payload()
    payload["previous"]["scoring"]["lead_score"] = 150
    result = run_routing(payload)
    assert result["stage_status"] == "failed"
