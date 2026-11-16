from agents.qualification_agent import run_qualification


def make_payload(size=450, requirements=None):
    requirements = ["Finance automation", "HR automation"] if requirements is None else requirements

    return {
        "lead": {
            "company_name": "ABC Manufacturing Pvt Ltd",
            "requirements": requirements,
            "budget": None
        },
        "previous": {
            "research": {
                "stage_status": "passed",
                "company_profile": {"company_size": size},
                "verified_facts": [
                    {
                        "field": "company_size",
                        "value": size,
                        "classification": "FACT",
                        "source_ids": ["SRC-002"]
                    }
                ]
            }
        }
    }


def test_medium_business_qualifies():
    result = run_qualification(make_payload(450))
    assert result["qualification_status"] == "qualified"
    assert result["company_size_segment"] == "medium_sized_business"


def test_enterprise_qualifies():
    result = run_qualification(make_payload(1500))
    assert result["qualification_status"] == "qualified"
    assert result["company_size_segment"] == "enterprise"


def test_small_business_not_qualified():
    result = run_qualification(make_payload(20))
    assert result["qualification_status"] == "not_qualified"


def test_missing_employee_count_needs_review():
    result = run_qualification(make_payload(None))
    assert result["qualification_status"] == "needs_review"


def test_missing_requirements_needs_review():
    result = run_qualification(make_payload(450, []))
    assert result["qualification_status"] == "needs_review"


def test_missing_budget_does_not_disqualify():
    result = run_qualification(make_payload(450))
    assert result["qualification_status"] == "qualified"
    assert result["budget_status"] == "not_provided"
