
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
    },

    "zenith logistics pvt ltd": {

        "industry": {
            "value": "Logistics",
            "source_ids": ["SRC-003"]
        },

        "business_description": {
            "value": "Synthetic demo logistics company providing freight, warehousing and shipment management services.",
            "source_ids": ["SRC-003"]
        },

        "company_size": {
            "value": 750,
            "source_ids": ["SRC-004"]
        },

        "products_services": [
            {
                "value": "Freight transportation",
                "source_ids": ["SRC-003"]
            },
            {
                "value": "Warehousing and inventory management",
                "source_ids": ["SRC-003"]
            },
            {
                "value": "Shipment tracking",
                "source_ids": ["SRC-003"]
            }
        ],

        "website": {
            "value": "https://example.com/zenith-logistics",
            "source_ids": ["SRC-003"]
        },

        "business_intelligence": {

            "potential_challenges": [
                {
                    "value": "Manual shipment tracking may create operational delays.",
                    "classification": "ASSUMPTION",
                    "basis": "Prospect requested shipment tracking automation."
                },
                {
                    "value": "Manual inventory processes may reduce operational efficiency.",
                    "classification": "ASSUMPTION",
                    "basis": "Prospect requested inventory management automation."
                }
            ],

            "automation_opportunities": [
                {
                    "value": "Shipment tracking automation.",
                    "classification": "ASSUMPTION",
                    "basis": "Prospect explicitly requested shipment tracking automation."
                },
                {
                    "value": "Inventory management automation.",
                    "classification": "ASSUMPTION",
                    "basis": "Prospect explicitly requested inventory management automation."
                },
                {
                    "value": "Customer support automation.",
                    "classification": "ASSUMPTION",
                    "basis": "Prospect explicitly requested customer support automation."
                }
            ],

            "sales_relevance": [
                {
                    "value": "Demonstrate shipment tracking, inventory and customer support automation.",
                    "classification": "ASSUMPTION",
                    "basis": "Prospect's stated requirements."
                }
            ]
        },

        "research_sources": [
            {
                "source_id": "SRC-003",
                "source_name": "Synthetic demo company profile",
                "url": "https://example.com",
                "source_type": "mock"
            },
            {
                "source_id": "SRC-004",
                "source_name": "Synthetic demo company size record",
                "url": "https://example.com/about",
                "source_type": "mock"
            }
        ],

        "source_conflict": False
    }

}
