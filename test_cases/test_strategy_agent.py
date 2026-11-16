from agents.strategy_agent import run_strategy


def valid_payload(priority="high"):
    return {
        "lead": {
            "requirements": ["Finance automation", "HR automation"]
        },
        "previous": {
            "qualification": {
                "stage_status": "passed",
                "qualification_status": "qualified"
            },
            "scoring": {
                "stage_status": "passed",
                "lead_score": 90,
                "lead_priority": priority
            },
            "routing": {
                "stage_status": "passed",
                "assigned_team": "Mid-Market Sales",
                "assigned_role": "Senior Account Executive"
            }
        }
    }


def test_creates_strategy_for_qualified_lead():
    result = run_strategy(valid_payload())
    assert result["stage_status"] == "passed"
    assert result["strategy_status"] == "created"


def test_high_priority_gets_consultative_approach():
    result = run_strategy(valid_payload("high"))
    assert result["sales_approach"] == "Consultative priority outreach"


def test_medium_priority_gets_needs_focused_approach():
    result = run_strategy(valid_payload("medium"))
    assert result["sales_approach"] == "Needs-focused sales outreach"


def test_low_priority_gets_nurturing_approach():
    result = run_strategy(valid_payload("low"))
    assert result["sales_approach"] == "Educational lead nurturing"


def test_generates_discovery_questions():
    result = run_strategy(valid_payload())
    assert len(result["discovery_questions"]) == 2
    assert any("finance" in q.lower() for q in result["discovery_questions"])


def test_unqualified_lead_is_rejected():
    payload = valid_payload()
    payload["previous"]["qualification"]["qualification_status"] = "not_qualified"
    result = run_strategy(payload)
    assert result["stage_status"] == "failed"


def test_previous_review_stops_strategy():
    payload = valid_payload()
    payload["previous"]["scoring"]["stage_status"] = "needs_review"
    result = run_strategy(payload)
    assert result["stage_status"] == "needs_review"


def test_missing_requirements_needs_review():
    payload = valid_payload()
    payload["lead"]["requirements"] = []
    result = run_strategy(payload)
    assert result["stage_status"] == "needs_review"


def test_strategy_does_not_perform_external_actions():
    result = run_strategy(valid_payload())
    assert result["strategy_rules"]["external_action_performed"] is False
    assert result["human_review_required_before_external_action"] is True
