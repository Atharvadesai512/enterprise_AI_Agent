
import pytest
from copy import deepcopy

from agents.research_agent import ResearchAgent
from test_cases.mock_research_data import MOCK_RESEARCH_DATABASE


@pytest.fixture
def agent():
    return ResearchAgent(MOCK_RESEARCH_DATABASE)


@pytest.fixture
def valid_lead():
    return {
        "lead_name": "Sam Smith",
        "company_name": "ABC Manufacturing Pvt Ltd",
        "email": "sam@abcmanufacturing.com",
        "validation_status": "valid",
        "requirements": ["Finance automation", "HR automation"]
    }


def test_successful_research(agent, valid_lead):

    result = agent.run(valid_lead)

    assert result["stage_status"] == "passed"

    assert (
        result["company_profile"]["industry"]["value"]
        == "Manufacturing"
    )

    assert len(result["verified_facts"]) > 0


def test_unknown_company(agent, valid_lead):

    valid_lead["company_name"] = "Unknown Company XYZ"

    result = agent.run(valid_lead)

    assert result["stage_status"] == "passed"
    assert result["research_confidence"] == "low"

    assert result["verified_facts"] == []
    assert result["research_sources"] == []

    assert "prospect_provided" in result
    assert result["prospect_provided"]["requirements"] == valid_lead["requirements"]

    assert len(result["assumptions"]) > 0


def test_invalid_lead_rejected(agent, valid_lead):

    valid_lead["validation_status"] = "incomplete"

    with pytest.raises(ValueError):

        agent.run(valid_lead)


def test_missing_company_name(agent, valid_lead):

    valid_lead["company_name"] = ""

    with pytest.raises(ValueError):

        agent.run(valid_lead)


def test_original_input_not_modified(agent, valid_lead):

    original = deepcopy(valid_lead)

    agent.run(valid_lead)

    assert valid_lead == original


def test_no_fabricated_sources(agent, valid_lead):

    result = agent.run(valid_lead)

    for source in result["research_sources"]:

        assert source["url"].startswith("https://")


def test_unverified_company_size(agent, valid_lead):

    database = deepcopy(MOCK_RESEARCH_DATABASE)

    del database["abc manufacturing pvt ltd"]["company_size"]

    agent_without_size = ResearchAgent(database)

    result = agent_without_size.run(valid_lead)

    assert result["company_profile"]["company_size"] is None

    assert (
        "company_size"
        in result["unverified_information"]
    )


def test_research_source_missing(agent, valid_lead):

    database = deepcopy(MOCK_RESEARCH_DATABASE)

    database["abc manufacturing pvt ltd"]["research_sources"] = []

    agent_without_sources = ResearchAgent(database)

    result = agent_without_sources.run(valid_lead)

    assert result["stage_status"] == "needs_review"


def test_conflicting_sources(agent, valid_lead):

    database = deepcopy(MOCK_RESEARCH_DATABASE)

    database["abc manufacturing pvt ltd"]["source_conflict"] = True

    agent_with_conflict = ResearchAgent(database)

    result = agent_with_conflict.run(valid_lead)

    assert result["stage_status"] == "needs_review"


def test_invalid_source_does_not_support_fact(agent, valid_lead):

    database = deepcopy(MOCK_RESEARCH_DATABASE)

    database["abc manufacturing pvt ltd"]["research_sources"] = [
        {
            "source_id": "SRC-001",
            "source_name": "Invalid source",
            "url": "not-a-valid-url"
        }
    ]

    agent_with_invalid_source = ResearchAgent(database)

    result = agent_with_invalid_source.run(valid_lead)

    assert result["stage_status"] == "needs_review"

    assert result["verified_facts"] == []
