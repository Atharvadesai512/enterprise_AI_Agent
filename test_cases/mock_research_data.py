
MOCK_RESEARCH_DATABASE = {

    "abc manufacturing pvt ltd": {

        "industry": {
            "value": "Manufacturing",
            "source_ids": ["SRC-001"]
        },

        "business_description": {
            "value": "Manufacturing business producing industrial components.",
            "source_ids": ["SRC-001"]
        },

        "company_size": {
            "value": 450,
            "source_ids": ["SRC-002"]
        },

        "products_services": [
            {
                "value": "Industrial components",
                "source_ids": ["SRC-001"]
            },
            {
                "value": "Manufacturing services",
                "source_ids": ["SRC-001"]
            }
        ],

        "website": {
            "value": "https://example.com",
            "source_ids": ["SRC-001"]
        },

        "business_intelligence": {

            "potential_challenges": [
                {
                    "value": "Manual finance workflows may create processing delays.",
                    "classification": "ASSUMPTION",
                    "basis": "Prospect stated that spreadsheets are currently used."
                }
            ],

            "automation_opportunities": [
                {
                    "value": "Finance workflow automation.",
                    "classification": "ASSUMPTION",
                    "basis": "Prospect explicitly requested finance automation."
                },
                {
                    "value": "HR process automation.",
                    "classification": "ASSUMPTION",
                    "basis": "Prospect explicitly requested HR automation."
                }
            ],

            "sales_relevance": [
                {
                    "value": "Demonstrate finance and HR workflow automation.",
                    "classification": "ASSUMPTION",
                    "basis": "Prospect's stated requirements."
                }
            ]
        },

        "research_sources": [
            {
                "source_id": "SRC-001",
                "source_name": "Sample company profile",
                "url": "https://example.com",
                "source_type": "mock"
            },
            {
                "source_id": "SRC-002",
                "source_name": "Sample company size record",
                "url": "https://example.com/about",
                "source_type": "mock"
            }
        ],

        "source_conflict": False
    }
}
