
"""
NEXORA TECHNOLOGIES
Research Agent - Version 1.0

Purpose:
Research and enrich a validated sales lead.

Current mode:
Rule-based research using explicitly supplied research records.

Important:
This version does NOT perform live internet research.
Only supplied records are treated as evidence.
"""

from copy import deepcopy
from typing import Any
from urllib.parse import urlparse


class ResearchAgentError(Exception):
    """Raised when research execution fails."""


class ResearchAgent:

    REQUIRED_INPUT_FIELDS = [
        "company_name",
        "email",
        "validation_status"
    ]

    ALLOWED_STATUSES = {
        "passed",
        "needs_review",
        "failed"
    }

    def __init__(self, research_database=None):

        # Mock research database.
        # Replace this with a real research provider later.

        self.research_database = research_database or {}

    # --------------------------------------------------
    # 1. INPUT VALIDATION
    # --------------------------------------------------

    def validate_input(self, lead):

        if not isinstance(lead, dict):
            raise ValueError("Lead input must be a dictionary.")

        missing = [
            field for field in self.REQUIRED_INPUT_FIELDS
            if field not in lead
        ]

        if missing:
            raise ValueError(
                f"Missing required input fields: {missing}"
            )

        if not isinstance(lead["company_name"], str):
            raise ValueError("Invalid company name.")

        if not lead["company_name"].strip():
            raise ValueError("Company name cannot be empty.")

        if lead["validation_status"] != "valid":
            raise ValueError(
                "Research cannot run on an unvalidated lead."
            )

    # --------------------------------------------------
    # 2. SOURCE VALIDATION
    # --------------------------------------------------

    def validate_source(self, source):

        if not isinstance(source, dict):
            return False

        url = source.get("url")

        if not isinstance(url, str):
            return False

        parsed = urlparse(url)

        return (
            parsed.scheme in {"http", "https"}
            and bool(parsed.netloc)
        )

    # --------------------------------------------------
    # 3. FACT CREATION
    # --------------------------------------------------

    def make_fact(self, field, value, source_id):

        return {
            "field": field,
            "value": value,
            "classification": "FACT",
            "source_ids": [source_id]
        }

    # --------------------------------------------------
    # 4. COMPANY RESEARCH
    # --------------------------------------------------

    def research_company(self, lead):

        company_name = lead["company_name"].strip()

        record = self.research_database.get(
            company_name.lower()
        )

        if not record:
            return self.empty_research_result(
                company_name,
                "No external research record available; using prospect-provided information.",
                lead
            )

        record = deepcopy(record)

        sources = record.get("research_sources", [])

        valid_sources = [
            source for source in sources
            if self.validate_source(source)
        ]

        valid_source_ids = {
            source["source_id"]
            for source in valid_sources
        }

        # A finding is accepted only when it has a
        # valid source reference.

        def verified_value(field):

            item = record.get(field)

            if not isinstance(item, dict):
                return None

            source_ids = item.get("source_ids", [])

            if not isinstance(source_ids, list):
                return None

            if not source_ids:
                return None

            if not all(
                sid in valid_source_ids
                for sid in source_ids
            ):
                return None

            return item.get("value")

        facts = []

        profile = {
            "company_name": company_name,
            "industry": None,
            "business_description": None,
            "company_size": None,
            "products_services": [],
            "website": None
        }

        # Industry

        industry = verified_value("industry")

        if industry is not None:
            source_ids = record["industry"]["source_ids"]

            profile["industry"] = {
                "value": industry,
                "classification": "FACT",
                "source_ids": source_ids
            }

            facts.append(
                self.make_fact(
                    "industry",
                    industry,
                    source_ids[0]
                )
            )

        # Business description

        description = verified_value(
            "business_description"
        )

        if description is not None:
            profile["business_description"] = description

            facts.append(
                self.make_fact(
                    "business_description",
                    description,
                    record["business_description"]["source_ids"][0]
                )
            )

        # Company size

        company_size = verified_value("company_size")

        if company_size is not None:
            profile["company_size"] = company_size

            facts.append(
                self.make_fact(
                    "company_size",
                    company_size,
                    record["company_size"]["source_ids"][0]
                )
            )

        # Products and services

        products = record.get("products_services", [])

        if isinstance(products, list):

            for product in products:

                if not isinstance(product, dict):
                    continue

                source_ids = product.get("source_ids", [])

                if (
                    not source_ids
                    or not all(
                        sid in valid_source_ids
                        for sid in source_ids
                    )
                ):
                    continue

                value = product.get("value")

                if not isinstance(value, str) or not value.strip():
                    continue

                profile["products_services"].append(value)

                facts.append(
                    self.make_fact(
                        "products_services",
                        value,
                        source_ids[0]
                    )
                )

        # Website

        website = verified_value("website")

        if website is not None:
            parsed = urlparse(website)

            if (
                parsed.scheme in {"http", "https"}
                and parsed.netloc
            ):
                profile["website"] = website

        # --------------------------------------------------
        # 5. BUSINESS INTELLIGENCE
        # --------------------------------------------------

        business_intelligence = {
            "potential_challenges": [],
            "automation_opportunities": [],
            "sales_relevance": []
        }

        assumptions = []

        for field in business_intelligence:

            items = record.get("business_intelligence", {}).get(field, [])

            if not isinstance(items, list):
                continue

            for item in items:

                if not isinstance(item, dict):
                    continue

                value = item.get("value")
                classification = item.get(
                    "classification",
                    "ASSUMPTION"
                )

                if not isinstance(value, str) or not value.strip():
                    continue

                # These business insights are not
                # automatically treated as facts.

                if classification != "ASSUMPTION":
                    classification = "ASSUMPTION"

                result = {
                    "value": value,
                    "classification": classification,
                    "basis": item.get("basis")
                }

                business_intelligence[field].append(result)

                assumptions.append({
                    "field": field,
                    "value": value,
                    "classification": "ASSUMPTION",
                    "basis": item.get("basis")
                })

        # --------------------------------------------------
        # 6. UNVERIFIED INFORMATION
        # --------------------------------------------------

        unverified = []

        expected_fields = [
            "industry",
            "business_description",
            "company_size",
            "products_services",
            "website"
        ]

        for field in expected_fields:

            if field == "products_services":
                if not profile[field]:
                    unverified.append(field)

            elif not profile[field]:
                unverified.append(field)

        # --------------------------------------------------
        # 7. RESEARCH STATUS
        # --------------------------------------------------

        if record.get("source_conflict") is True:

            status = "needs_review"
            notes = ["Conflicting research sources detected."]

        elif not valid_sources:

            status = "needs_review"
            notes = ["No valid research sources available."]

        elif not any([
            profile["industry"],
            profile["business_description"],
            profile["company_size"],
            profile["products_services"]
        ]):

            status = "needs_review"
            notes = ["Insufficient verified company information."]

        else:

            status = "passed"
            notes = ["Research completed using supplied evidence records."]

        # --------------------------------------------------
        # 8. CONFIDENCE
        # --------------------------------------------------

        verified_count = len(facts)

        if verified_count >= 3:
            confidence = "high"

        elif verified_count >= 1:
            confidence = "medium"

        else:
            confidence = "low"

        # --------------------------------------------------
        # 9. FINAL OUTPUT
        # --------------------------------------------------

        return {
            "stage_status": status,

            "company_profile": profile,

            "business_intelligence": business_intelligence,

            "research_sources": valid_sources,

            "verified_facts": facts,

            "assumptions": assumptions,

            "unverified_information": unverified,

            "research_confidence": confidence,

            "notes": notes
        }

    # --------------------------------------------------
    # 10. EMPTY RESEARCH RESULT
    # --------------------------------------------------

    def empty_research_result(
        self,
        company_name,
        message,
        lead=None
    ):
        lead = lead or {}

        industry = lead.get("industry")
        employee_count = lead.get("employee_count")
        requirements = lead.get("requirements", [])

        if not isinstance(requirements, list):
            requirements = []

        requirements = [
            item.strip()
            for item in requirements
            if isinstance(item, str) and item.strip()
        ]

        business_intelligence = {
            "potential_challenges": [],
            "automation_opportunities": [],
            "sales_relevance": []
        }

        assumptions = []

        for requirement in requirements:
            item = {
                "value": requirement,
                "classification": "ASSUMPTION",
                "basis": "Automation requirement explicitly stated by the prospect; opportunity requires discovery."
            }
            business_intelligence["automation_opportunities"].append(item)

            assumptions.append({
                "field": "automation_opportunities",
                **item
            })

        profile_industry = None
        if isinstance(industry, str) and industry.strip():
            profile_industry = {
                "value": industry.strip(),
                "classification": "PROSPECT_PROVIDED",
                "source_ids": []
            }

        valid_employee_count = (
            isinstance(employee_count, int)
            and not isinstance(employee_count, bool)
            and employee_count >= 0
        )

        return {
            "stage_status": "passed",
            "company_profile": {
                "company_name": company_name,
                "industry": profile_industry,
                "business_description": None,
                "company_size": employee_count if valid_employee_count else None,
                "products_services": [],
                "website": None
            },
            "business_intelligence": business_intelligence,
            "research_sources": [],
            "verified_facts": [],
            "prospect_provided": {
                "industry": industry,
                "company_size": employee_count if valid_employee_count else None,
                "requirements": requirements
            },
            "assumptions": assumptions,
            "unverified_information": [
                "business_description",
                "company_size_external_verification",
                "products_services",
                "website",
                "independent_company_research"
            ],
            "research_confidence": "low",
            "notes": [
                message,
                "No independent company facts were invented or marked as verified.",
                "Prospect-provided information is retained separately from verified research."
            ]
        }

    # --------------------------------------------------
    # 11. MAIN AGENT EXECUTION
    # --------------------------------------------------

    def run(self, lead):

        # Protect original input.

        lead_copy = deepcopy(lead)

        self.validate_input(lead_copy)

        try:

            result = self.research_company(lead_copy)

            if result["stage_status"] not in self.ALLOWED_STATUSES:
                raise ResearchAgentError(
                    "Invalid research status returned."
                )

            return result

        except Exception as error:

            raise ResearchAgentError(
                f"Research execution failed: {error}"
            ) from error

# --------------------------------------------------
# ORCHESTRATOR INTEGRATION
# --------------------------------------------------

def run_research(payload: dict) -> dict:
    from database.mock_research_data import MOCK_RESEARCH_DATABASE

    if not isinstance(payload, dict):
        raise ValueError("Research payload must be a dictionary.")

    lead = payload.get("lead")

    if not isinstance(lead, dict):
        raise ValueError("Research payload must contain a lead dictionary.")

    return ResearchAgent(MOCK_RESEARCH_DATABASE).run(lead)
