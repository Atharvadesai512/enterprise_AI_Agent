# NEXORA — Agentic Sales Automation System

An agent-based sales automation prototype built with Python. NEXORA processes incoming leads through a multi-stage sales workflow, from initial intake and validation to research, qualification, scoring, routing, sales strategy, communication drafting, quality assurance and human approval.

## Overview

NEXORA is designed to demonstrate how specialized agents can collaborate through a centralized orchestrator to automate and coordinate key sales operations.

The system processes lead information, evaluates its quality, determines sales priority, recommends an appropriate sales team, generates a sales approach and communication draft, and prepares the result for human review.

It also maintains workflow execution records and provides a local dashboard for monitoring runs and reviewing approval decisions.

## Key Features

- **Lead Intake:** Extracts lead information from raw text and structured inputs.
- **Validation:** Checks required fields, identifies missing information and detects conflicting data.
- **Duplicate Detection:** Checks incoming leads against mock CRM records.
- **Company Research:** Enriches leads using a local mock research dataset and identifies research limitations.
- **Lead Qualification:** Evaluates lead fit and qualification criteria.
- **Lead Scoring:** Calculates a lead score and assigns a priority category.
- **Sales Routing:** Recommends an appropriate sales team and owner.
- **Sales Strategy:** Generates a recommended sales approach based on lead information.
- **Communication Drafting:** Creates suggested sales communication without sending external emails.
- **Quality Assurance:** Runs automated checks on workflow outputs.
- **Human Approval:** Allows authorized reviewers to approve or reject eligible workflow results.
- **Workflow Persistence:** Stores execution details and stage results in SQLite.
- **Local Dashboard:** Provides an interface to submit leads, inspect workflow runs and review decisions.

## System Architecture

NEXORA uses a centralized orchestrator to coordinate specialized agents.

```text
                 INCOMING LEAD
                       |
                       v
                INTAKE AGENT
                       |
                       v
              VALIDATION GATE
                       |
                       v
                RESEARCH AGENT
                       |
                       v
             QUALIFICATION AGENT
                       |
                       v
                SCORING AGENT
                       |
                       v
                ROUTING AGENT
                       |
                       v
               STRATEGY AGENT
                       |
                       v
            COMMUNICATION AGENT
                       |
                       v
                   QA AGENT
                       |
                       v
              HUMAN APPROVAL
                       |
              +--------+--------+
              |                 |
              v                 v
           APPROVED           REJECTED
```

The orchestrator manages stage execution, workflow state, error handling and persistence.

## Project Structure

```text
NEXORA-AGENTIC-SALES-SYSTEM/
|
|-- agents/
|   |-- intake_agent.py
|   |-- research_agent.py
|   |-- qualification_agent.py
|   |-- scoring_agent.py
|   |-- routing_agent.py
|   |-- strategy_agent.py
|   |-- communication_agent.py
|   |-- qa_agent.py
|
|-- architecture/
|   |-- system_architecture.md
|   |-- sales_process.md
|   |-- agent_interactions.md
|
|-- dashboard/
|   |-- app.py
|   |-- approval_service.py
|
|-- database/
|   |-- schema.sql
|   |-- mock_crm.json
|   |-- mock_research_data.py
|
|-- documentation/
|   |-- business_requirements.md
|   |-- technical_documentation.md
|   |-- test_report.md
|   |-- demo_script.md
|
|-- orchestrator/
|   |-- main.py
|
|-- prompts/
|   |-- agent_instructions.md
|
|-- test_cases/
|   |-- normal_lead.json
|   |-- duplicate_lead.json
|   |-- missing_data.json
|   |-- conflicting_data.json
|   |-- mock_research_data.py
|   |-- run_intake_tests.py
|   |-- run_orchestrator_tests.py
|   |-- test_communication_agent.py
|   |-- test_dashboard.py
|   |-- test_end_to_end.py
|   |-- test_qa_agent.py
|   |-- test_qualification_agent.py
|   |-- test_research_agent.py
|   |-- test_routing_agent.py
|   |-- test_scoring_agent.py
|   |-- test_strategy_agent.py
|
|-- workflows/
|   |-- lead_intake.json
|   |-- lead_qualification.json
|   |-- sales_execution.json
|
|-- .gitignore
|-- README.md
```

## Technology Stack

| Technology | Purpose |
|---|---|
| Python 3.12 | Core application |
| SQLite | Workflow persistence |
| JSON | Mock data and workflow configuration |
| HTTP Server | Local dashboard backend |
| HTML | Dashboard interface |
| Pytest | Automated testing |
| Git | Version control |

The application logic uses Python standard-library modules. Pytest is required to run the test suite.

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/YOUR-USERNAME/NEXORA-Agentic-Sales-System.git
cd NEXORA-Agentic-Sales-System
```

Replace `YOUR-USERNAME` with your GitHub username.

### 2. Create a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
```

### 3. Activate the environment

```powershell
.\.venv\Scripts\Activate.ps1
```

### 4. Install dependencies

```powershell
python -m pip install -r requirements.txt
```

### 5. Run the automated tests

```powershell
python -m pytest -v
```

### 6. Start the dashboard

```powershell
python .\dashboard\app.py
```

Open the local dashboard URL displayed in the terminal.

## Example Lead Input

NEXORA accepts lead information through its dashboard and orchestrator workflow.

Example:

```json
{
  "source": "web_form",
  "raw_text": "My name is Rahul Mehta. I am the COO at Orbit Freight Services. We are a logistics company with 850 employees. We need to automate shipment exception handling and customer follow-up emails. Our annual budget is $60,000 and we want to go live within 8 weeks."
}
```

The workflow extracts relevant information and passes it through the configured processing stages.

## Human Approval

The approval process provides a human review step after workflow processing and quality checks.

Reviewers can inspect the workflow information and record an approval or rejection decision.

- Approval decisions are persisted.
- Rejection requires a reason or comment.
- Recorded decisions cannot be changed through the normal approval workflow.
- Approval does not trigger an external email or CRM action.

## Testing

The project includes automated tests covering individual agents, orchestration, dashboard approval functionality and end-to-end workflow scenarios.

Test coverage includes:

- Normal lead processing
- Duplicate lead detection
- Missing information
- Conflicting information
- Research fallback behavior
- Qualification and scoring
- Sales routing
- Strategy generation
- Communication drafting
- QA validation
- Human approval and rejection
- Workflow execution and persistence

Run the complete test suite:

```powershell
python -m pytest -v
```

**Latest verified test result:** 62 tests passed.

## Current Limitations

NEXORA is a functional development prototype, not a production-ready enterprise platform.

Current limitations include:

- Company research uses local mock data rather than a live research provider.
- CRM duplicate detection uses a local mock CRM rather than a connected CRM platform.
- Sales communication is generated as a draft; emails are not sent.
- Agent decisions primarily use deterministic Python rules and templates rather than autonomous LLM-based reasoning.
- Sales routing uses configured application logic.
- External CRM, email and other enterprise integrations have not yet been implemented.
- Production authentication, deployment security, monitoring and scalability controls require further development.

All included lead and CRM examples are synthetic development data.

## Future Enhancements

Potential future development includes:

- Integration with live CRM platforms.
- LLM-powered research and sales reasoning.
- Automated email integration with human authorization.
- Configurable sales scoring models.
- Advanced analytics and performance dashboards.
- Role-based access control.
- Production deployment and monitoring.
- Expanded audit and compliance capabilities.

## Project Goal

The goal of NEXORA is to demonstrate a modular, multi-agent sales workflow in which specialized components collaborate under a centralized orchestrator, with persistent execution records, automated quality checks and human oversight.

---

**NEXORA — Intelligent Sales Workflow Automation**

Built with Python.