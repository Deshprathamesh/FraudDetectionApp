# FraudGraph AI

FraudGraph AI is an Agentic Fraud Investigation and Next-Best Action system that combines graph-powered analytics (TigerGraph, GraphRAG) with autonomous reasoning agents (LangGraph, FastAPI) and an interactive analyst cockpit (Next.js) to detect complex fraud networks, explain suspicious transaction patterns, and recommend policy-compliant next-best remediation actions.

## Workstream Ownership

| Workstream | Owner | Owned Folders | Core Responsibilities |
| :--- | :--- | :--- | :--- |
| **Person 1 — Brain** | Person 1 | `backend/`<br>`agent/` | FastAPI backend, LangGraph agent, agent workflow / state machine, agent tools, risk / confidence / uncertainty calculation, Next Best Action (NBA), policy / permission engine, approval logic, LLM integration, explainability, mock action APIs |
| **Person 2 — Graph** | Person 2 | `tigergraph/`<br>`graphrag/`<br>`data/` | TigerGraph instance, dataset ingestion, graph schema, GSQL queries, graph algorithms, TigerGraph MCP server, GraphRAG pipeline, policy / document retrieval, similar-case retrieval, case memory |
| **Person 3 — Product** | Person 3 | `frontend/` | Next.js frontend, dashboard, investigation UI, case management UI, evidence UI, graph visualization, recommendation UI, approval UI, case timeline, frontend API integration, demo experience |
| **Shared** | All (Person 1, 2, 3) | `tests/`<br>`docs/`<br>`README.md` | Integration testing, contract documentation, repository guidelines, benchmark evaluation, and final demo presentation |

## Repository Structure

```text
fraudgraph-ai/
│
├── frontend/
│   ├── app/
│   ├── components/
│   ├── pages/
│   ├── services/
│   ├── types/
│   └── hooks/
│
├── backend/
│   ├── api/
│   ├── models/
│   ├── services/
│   └── policy/
│
├── agent/
│   ├── workflows/
│   ├── tools/
│   ├── prompts/
│   ├── memory/
│   └── reasoning/
│
├── tigergraph/
│   ├── schema/
│   ├── gsql/
│   ├── loaders/
│   └── queries/
│
├── graphrag/
│   ├── retrieval/
│   ├── documents/
│   └── embeddings/
│
├── data/
├── tests/
├── docs/
│
├── .env.example
├── .gitignore
└── README.md
```

## Project Status

**Current Status**: `Phase 1 — Repository scaffolding`

> **Note**: Implementation contracts (data models, API schemas, graph schema, agent state workflows, and error definitions in `docs/`) will be formally defined and approved before feature development begins. No application or business logic is implemented at this phase.

## Future Setup Placeholder

Detailed setup commands and environment requirements will be documented here upon completion of the implementation contracts:

- **Environment Configuration**: Copy `.env.example` to `.env` and fill in required TigerGraph credentials and LLM API keys.
- **Backend & Agent Setup**: Python virtual environment (`.venv`), dependency installation via `pip`, and FastAPI server start (`uvicorn`).
- **Graph & GraphRAG Setup**: TigerGraph connection configuration, schema deployment, and dataset loading jobs.
- **Frontend Setup**: Node.js dependency installation via `npm install` and development server start via `npm run dev`.
