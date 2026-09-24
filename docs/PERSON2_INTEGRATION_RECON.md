# Person 2 Integration Reconnaissance

**Inspection Date**: September 24, 2026  
**Inspector**: Person 1 (Brain / Agent & Backend Lead)  
**Target Workstream**: Person 2 (Graph & GraphRAG Lead)  
**Repository**: `FraudGraph AI`  
**Git Commit Inspected**: `c550d45` (*feat(tigergraph,graphrag): complete TigerGraph tool suite, schema, loading jobs, GSQL queries, and GraphRAG engine*)

---

## 1. Current Repository State

### 1.1 Repository Tree & File Inventory
The repository has been structured around three collaborative workstreams (Person 1: Brain, Person 2: Graph, Person 3: Product). A full directory and file audit reveals:

```text
fraudgraph-ai/
├── README.md                                    # Project description & workstream definitions
├── .env.example                                 # Environment variable template
├── .gitignore                                   # Standard Python / Node gitignore
│
├── tigergraph/                                  # [Person 2 - Implemented]
│   ├── __init__.py                              # Package export
│   ├── config.py                                # Configuration loader (USE_MOCK_GRAPH, ports, auth)
│   ├── client.py                                # Live pyTigerGraph client & schema loader
│   ├── mock_provider.py                         # Deterministic mock provider (9 tools, in-memory fixtures)
│   ├── tools.py                                 # 9 Contract Tool functions & Pydantic response models
│   ├── schema/
│   │   └── schema.gsql                          # Full GSQL DDL: 12 vertices, 13 edge types
│   ├── queries/
│   │   ├── detect_card_testing.gsql             # Micro-transaction burst GSQL query
│   │   ├── detect_geo_impossibility.gsql        # Distance & proxy detection GSQL query
│   │   ├── detect_shared_device_ring.gsql       # Multi-account device ring GSQL query
│   │   ├── detect_velocity_abuse.gsql           # Volume & velocity threshold GSQL query
│   │   └── find_similar_case_cluster.gsql       # Graph case similarity traversal GSQL query
│   ├── loaders/
│   │   ├── __init__.py                          # Loader module export
│   │   ├── load_identity.gsql                   # Loading job for Device, IP, and edges
│   │   └── load_transactions.gsql               # Loading job for Transaction, Card, and edges
│   └── mcp/
│       ├── __init__.py                          # MCP server exports
│       ├── server.py                            # FastMCP / MCPServer JSON-RPC 2.0 stdio server
│       └── README.md                            # MCP documentation & client integration guide
│
├── graphrag/                                    # [Person 2 - Implemented]
│   ├── __init__.py                              # Exports GraphRAGPipeline & retrieve_investigation_context
│   ├── pipeline.py                              # Orchestrator formatting LLM reasoning prompts
│   ├── embeddings/
│   │   ├── __init__.py                          # Embeddings export
│   │   └── embedder.py                          # MiniLM-L6-v2 + deterministic hash fallback
│   ├── retrieval/
│   │   ├── __init__.py                          # Retrieval exports
│   │   ├── case_retriever.py                    # Hybrid vector + typology case retriever
│   │   └── policy_retriever.py                  # Semantic bank policy & SAR rule retriever
│   └── documents/
│       ├── cases/
│       │   └── historical_cases.json            # 4 detailed historical case precedents
│       ├── policies/
│       │   └── fraud_policy.md                  # Enterprise bank fraud policy POL-FRAUD-2026-V1
│       └── typologies/
│           └── known_patterns.md                # 5 fraud pattern specifications (FP-01 to FP-05)
│
├── data/                                        # [Person 2 - Implemented]
│   ├── identity.csv                             # Sample identity & device network dataset (37 rows)
│   ├── transactions.csv                         # Sample IEEE-CIS format transaction records (37 rows)
│   └── graph_entities.json                      # Seeded graph entities (customers, accounts, devices)
│
├── scripts/                                     # [Person 2 - Verification Scripts]
│   ├── verify_mock_layer.py                     # Sweeps all 9 mock tools across 4 personas (PASSED)
│   ├── verify_graphrag.py                       # Tests GraphRAG policy & case retrieval (PASSED)
│   ├── verify_mcp_server.py                     # MCP SDK tool listing and execution verification
│   ├── verify_mcp_stdio.py                      # JSON-RPC 2.0 stdio subprocess tester
│   └── verify_prompt24.py                       # Live vs mock shape parity & GraphRAG check
│
├── tests/                                       # [Person 2 - Implemented Contract Tests]
│   └── test_graph_tools.py                      # 541 lines of pytest contract assertions for all 9 tools
│
├── backend/                                     # [Person 1 - Brain: EMPTY DIRECTORY SKELETON]
│   ├── api/                                     # 0 files (.gitkeep only)
│   ├── models/                                  # 0 files (.gitkeep only)
│   ├── policy/                                  # 0 files (.gitkeep only)
│   └── services/                                # 0 files (.gitkeep only)
│
├── agent/                                       # [Person 1 - Brain: EMPTY DIRECTORY SKELETON]
│   ├── memory/                                  # 0 files (.gitkeep only)
│   ├── prompts/                                 # 0 files (.gitkeep only)
│   ├── reasoning/                               # 0 files (.gitkeep only)
│   ├── tools/                                   # 0 files (.gitkeep only)
│   └── workflows/                               # 0 files (.gitkeep only)
│
├── frontend/                                    # [Person 3 - Product: EMPTY DIRECTORY SKELETON]
│   ├── app/                                     # 0 files (.gitkeep only)
│   ├── components/                              # 0 files (.gitkeep only)
│   ├── hooks/                                   # 0 files (.gitkeep only)
│   ├── pages/                                   # 0 files (.gitkeep only)
│   ├── services/                                # 0 files (.gitkeep only)
│   └── types/                                   # 0 files (.gitkeep only)
│
└── docs/                                        # [Scaffolding Placeholders]
    ├── AGENT_WORKFLOW.md                        # Placeholder (10 lines)
    ├── API_CONTRACT.md                          # Placeholder (12 lines)
    ├── ARCHITECTURE.md                          # Placeholder (11 lines)
    ├── CONTRIBUTING.md                          # Placeholder (10 lines)
    ├── DATA_MODELS.md                           # Placeholder (11 lines)
    ├── ERROR_CONTRACT.md                        # Placeholder (11 lines)
    ├── EVALUATION.md                            # Placeholder (11 lines)
    ├── TECH_STACK.md                            # Placeholder (11 lines)
    ├── TIGERGRAPH_CONTRACT.md                   # Placeholder (11 lines)
    └── UI_DATA_MAPPING.md                       # Placeholder (11 lines)
```

### 1.2 Git Commit History
1. `5f0c407` — *Initial repository scaffolding for FraudGraph AI* (authored by Deshprathamesh): Created initial folder skeletons and placeholder `.md` docs in `docs/`.
2. `c550d45` — *feat(tigergraph,graphrag): complete TigerGraph tool suite, schema, loading jobs, GSQL queries, and GraphRAG engine* (authored by Mayank Kalbhor / Person 2): Added 37 files across `tigergraph/`, `graphrag/`, `data/`, `scripts/`, and `tests/`.

### 1.3 State of Workstream Folders
- **`backend/`**: Contains 4 empty directories (`api/`, `models/`, `policy/`, `services/`). **Zero files implemented.** Person 2 did not place code here.
- **`agent/`**: Contains 5 empty directories (`memory/`, `prompts/`, `reasoning/`, `tools/`, `workflows/`). **Zero files implemented.** Person 2 did not place code here.
- **`frontend/`**: Contains 6 empty directories. **Zero files implemented.**
- **`docs/`**: All markdown files in `docs/` are 10-line placeholders from repository scaffolding. None of Person 2's contracts are currently documented in `docs/`. Person 2's contracts are instead encoded within code docstrings, Pydantic models in `tigergraph/tools.py`, and test assertions in `tests/test_graph_tools.py`.

---

## 2. Person 2 Implemented Components

| Component | Location | Purpose | Status | Important Files | Public Interfaces |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **TigerGraph Configuration** | `tigergraph/config.py` | Safe configuration management with offline mock default | IMPLEMENTED | `tigergraph/config.py` | `USE_MOCK_GRAPH`, `get_config_summary()`, connection constants |
| **TigerGraph Live Client** | `tigergraph/client.py` | Live pyTigerGraph connection manager, schema loader, and case writer | PARTIAL | `tigergraph/client.py` | `TigerGraphLiveClient`, `live_client`, `test_connection()`, `load_schema()`, `write_case_to_graph()` |
| **TigerGraph Mock Provider** | `tigergraph/mock_provider.py` | Deterministic simulation of all 9 agent tool operations with in-memory fixtures | IMPLEMENTED | `tigergraph/mock_provider.py` | `TigerGraphMockProvider`, `mock_provider`, `GraphError` |
| **TigerGraph Tool Suite** | `tigergraph/tools.py` | 9 clean Python tool functions with Pydantic response models | IMPLEMENTED | `tigergraph/tools.py` | `get_graph_tools()`, 9 tool functions, 11 Pydantic response models |
| **TigerGraph Schema DDL** | `tigergraph/schema/schema.gsql` | Formal GSQL schema defining 12 vertices and 13 edge types | IMPLEMENTED | `tigergraph/schema/schema.gsql` | Graph `FraudGraph` |
| **GSQL Query Suite** | `tigergraph/queries/` | 5 GSQL pattern detection and case clustering queries | PARTIAL | 5 `.gsql` files in `tigergraph/queries/` | GSQL queries (not yet wired to live client Python methods) |
| **GSQL Data Loaders** | `tigergraph/loaders/` | Loading jobs for IEEE-CIS identity and transaction records | IMPLEMENTED | `load_identity.gsql`, `load_transactions.gsql` | Jobs: `load_identity`, `load_transactions` |
| **Model Context Protocol (MCP)** | `tigergraph/mcp/` | JSON-RPC 2.0 stdio MCP server exposing all 9 tools | IMPLEMENTED (Requires dependency) | `server.py`, `README.md` | `create_mcp_server()`, stdio CLI `python -m tigergraph.mcp.server` |
| **GraphRAG Embedder** | `graphrag/embeddings/` | MiniLM-L6-v2 local vector embedder with deterministic hash fallback | IMPLEMENTED | `embedder.py` | `embed_text()`, `embed_batch()`, `cosine_similarity()` |
| **GraphRAG Policy Retriever** | `graphrag/retrieval/policy_retriever.py` | Semantic vector search over bank fraud policy POL-FRAUD-2026-V1 | IMPLEMENTED | `policy_retriever.py` | `get_policy_context()` |
| **GraphRAG Case Retriever** | `graphrag/retrieval/case_retriever.py` | Hybrid vector + pattern typology search over historical cases | IMPLEMENTED | `case_retriever.py` | `find_similar_cases()` |
| **GraphRAG Pipeline Orchestrator** | `graphrag/pipeline.py` | Unifies policy and case memory into concise LLM reasoning prompts | IMPLEMENTED | `pipeline.py` | `GraphRAGPipeline`, `pipeline`, `retrieve_investigation_context()` |
| **Knowledge Base Documents** | `graphrag/documents/` | Policy markdown, typology guides, and 4 historical case precedent JSONs | IMPLEMENTED | `fraud_policy.md`, `known_patterns.md`, `historical_cases.json` | Static Markdown and JSON knowledge sources |
| **Contract Verification & Tests** | `tests/`, `scripts/` | Comprehensive pytest suite (541 lines) and verification runners | IMPLEMENTED | `tests/test_graph_tools.py`, `scripts/verify_mock_layer.py`, `scripts/verify_graphrag.py` | Executable verification scripts |
| **Datasets** | `data/` | CSV files for identity/transactions and entity seed JSON | IMPLEMENTED | `identity.csv`, `transactions.csv`, `graph_entities.json` | Raw data fixtures |

---

## 3. Graph Integration Interfaces

Person 1's agent/backend can communicate with Person 2's graph layer via clean, typed Python interfaces in `tigergraph/tools.py` and `graphrag/pipeline.py`.

### Tool 1: `get_transaction`
- **Name**: `get_transaction`
- **Purpose**: Retrieve full transaction attributes, risk score, merchant info, device token, IP, and behavioral counters (`c1`–`c14`, `dist1`, `dist2`).
- **Input**: `transaction_id: str` (e.g. `"TXN-104829"`)
- **Output**: `TransactionDetailResponse` (Pydantic model)
  - Fields: `transaction_id` (str), `customer_id` (str), `account_id` (str), `amount` (float), `currency` (str), `timestamp` (int), `risk_score` (float), `channel` (str), `card_network` (str), `merchant_name` (str), `device_id` (str), `ip_str` (str), `dist1` (float), `dist2` (float), `c1`–`c14` (int).
- **Errors**: Returns Section 9 error dictionary on unknown ID:
  ```json
  {"error": {"code": "TRANSACTION_NOT_FOUND", "message": "Transaction '...' was not found in graph database.", "details": {"transaction_id": "..."}}}
  ```
- **File**: `tigergraph/tools.py` (L164–L184)
- **Status**: IMPLEMENTED (Dispatches to `mock_provider.get_transaction`)

### Tool 2: `get_customer`
- **Name**: `get_customer`
- **Purpose**: Retrieve customer profile, risk tier, linked accounts, cards, email, and historical customer risk score.
- **Input**: `customer_id: str` (e.g. `"C-45821"`)
- **Output**: `CustomerDetailResponse` (Pydantic model)
  - Fields: `customer_id` (str), `name` (str), `risk_tier` (str: `"LOW"`, `"MEDIUM"`, `"HIGH"`, `"CRITICAL"`), `created_at` (int), `accounts` (List[str]), `linked_cards` (List[str]), `email` (str), `risk_score` (float).
- **Errors**: Returns Section 9 error dictionary on unknown ID:
  ```json
  {"error": {"code": "CUSTOMER_NOT_FOUND", "message": "Customer '...' was not found in graph database.", "details": {"customer_id": "..."}}}
  ```
- **File**: `tigergraph/tools.py` (L186–L206)
- **Status**: IMPLEMENTED (Dispatches to `mock_provider.get_customer`)

### Tool 3: `get_transaction_history`
- **Name**: `get_transaction_history`
- **Purpose**: Retrieve historical transactions and 30-day velocity/behavioral summary for a customer or account.
- **Input**: Keyword args: `entity_id: Optional[str]`, `customer_id: Optional[str]`, `account_id: Optional[str]`, `limit: int = 10`
- **Output**: `TransactionHistoryResponse` (Pydantic model)
  - Fields: `transactions` (List[TransactionHistoryItem]), `summary` (TransactionHistorySummary: `total_transactions`, `avg_amount`, `max_amount`, `velocity_30d`, `risk_distribution` dict).
- **Errors**: Graph-traversal query: Unmatched ID returns valid empty model (`transactions: []`, zeroed summary), not an error dict.
- **File**: `tigergraph/tools.py` (L208–L234)
- **Status**: IMPLEMENTED (Dispatches to `mock_provider.get_transaction_history`)

### Tool 4: `get_connected_entities`
- **Name**: `get_connected_entities`
- **Purpose**: Multi-hop graph BFS traversal returning connected nodes and edges for graph visualization and network analysis.
- **Input**: `entity_id: str`, `depth: int = 1`
- **Output**: `ConnectedEntitiesResponse` (Pydantic model)
  - Fields: `nodes` (List[GraphNode]: `id`, `label`, `type`, `risk_score`), `edges` (List[GraphEdge]: `source`, `target`, `type`).
- **Errors**: Unmatched ID returns 1 disconnected node of type `"Unknown"` with 0 edges.
- **File**: `tigergraph/tools.py` (L236–L256)
- **Status**: IMPLEMENTED (Dispatches to `mock_provider.get_connected_entities`)

### Tool 5: `find_shared_devices`
- **Name**: `find_shared_devices`
- **Purpose**: Query for devices linked across multiple customer accounts to detect device-hopping syndicates and account takeover rings.
- **Input**: Keyword args: `entity_id: Optional[str]`, `customer_id: Optional[str]`, `account_id: Optional[str]`, `device_id: Optional[str]`
- **Output**: `SharedDevicesResponse` (Pydantic model)
  - Fields: `devices` (List[SharedDeviceItem]: `device_id`, `linked_accounts`, `risk_score`, `associated_account_ids`).
- **Errors**: Unmatched ID returns `devices: []`.
- **File**: `tigergraph/tools.py` (L258–L284)
- **Status**: IMPLEMENTED (Dispatches to `mock_provider.find_shared_devices`)

### Tool 6: `detect_fraud_patterns`
- **Name**: `detect_fraud_patterns`
- **Purpose**: Execute algorithmic graph pattern detection (syndicate rings, velocity bursts, mule accounts, proxy churn, card testing) and return evidence references.
- **Input**: Keyword args: `case_context: Optional[str]`, `entity_id: Optional[str]`, `transaction_id: Optional[str]`
- **Output**: `DetectFraudPatternsResponse` (Pydantic model)
  - Fields: `patterns` (List[FraudPatternItem]: `pattern_id`, `name`, `description`, `evidence_refs`, `confidence`).
- **Errors**: Unmatched ID returns `patterns: []`.
- **File**: `tigergraph/tools.py` (L286–L311)
- **Status**: IMPLEMENTED (Dispatches to `mock_provider.detect_fraud_patterns`)

### Tool 7: `find_similar_cases`
- **Name**: `find_similar_cases`
- **Purpose**: Retrieve similar historical closed cases, similarity scores, matched pattern typologies, and past investigation outcomes from case memory.
- **Input**: Keyword args: `case_context: Optional[str]`, `case_id: Optional[str]`
- **Output**: `SimilarCasesResponse` (Pydantic model)
  - Fields: `similar_cases` (List[SimilarCaseItem]: `case_id`, `similarity_score`, `status`, `risk_score`, `outcome`, `matched_patterns`, `key_findings`).
- **Errors**: Unmatched query returns top matches from historical case precedents.
- **File**: `tigergraph/tools.py` (L313–L338) & `graphrag/retrieval/case_retriever.py`
- **Status**: IMPLEMENTED (Dual implementation: `mock_provider` and `graphrag.retrieval.case_retriever`)

### Tool 8: `get_policy_context`
- **Name**: `get_policy_context`
- **Purpose**: Retrieve governing bank fraud policy clauses, mandatory SAR filing requirements, and human approval obligations for a proposed action or risk context.
- **Input**: Keyword args: `action: Optional[str]`, `pattern_id: Optional[str]`, `amount: Optional[float]`, `case_context: Optional[str]`
- **Output**: `PolicyContextResponse` (Pydantic model)
  - Fields: `policy_id` (str), `policy_basis` (str), `approval_required` (bool), `sar_required` (bool), `confidence_threshold` (float), `allowed_actions` (List[str]), `escalation_notes` (Optional[str]).
- **Errors**: Falls back to baseline risk mitigation policy tier POL-101 / standard tier.
- **File**: `tigergraph/tools.py` (L340–L369) & `graphrag/retrieval/policy_retriever.py`
- **Status**: IMPLEMENTED (Dual implementation: rule-based in `mock_provider`, vector-retrieval in `graphrag.retrieval.policy_retriever`)

### Tool 9: `write_case_to_graph`
- **Name**: `write_case_to_graph`
- **Purpose**: Commit an investigated fraud case payload (status, evidence, findings, decisions, actions) into TigerGraph case memory for audit and future retrieval.
- **Input**: `case_payload: Optional[Dict[str, Any]] = None, **kwargs` (Must contain `case_id`, plus optional `transaction_id`, `customer_id`, `status`, `risk_score`, `confidence`, `evidence`, `actions`/`action_records`, `fraud_patterns`).
- **Output**: `WriteCaseResponse` (Pydantic model)
  - Fields: `status` (str: `"SUCCESS"`), `case_id` (str), `graph_ids` (List[str]), `nodes_written` (int), `edges_written` (int), `message` (str).
- **Errors**: Missing `case_id` returns Section 9 error dictionary:
  ```json
  {"error": {"code": "CASE_NOT_FOUND", "message": "Case payload missing required 'case_id' field.", "details": {...}}}
  ```
- **File**: `tigergraph/tools.py` (L371–L407)
- **Status**: IMPLEMENTED (Switches to `live_client.write_case_to_graph` if `USE_MOCK_GRAPH=false`, otherwise writes to `mock_provider.MOCK_WRITTEN_CASES`)

### Single Registry Loader: `get_graph_tools()`
- **Name**: `get_graph_tools`
- **Purpose**: Provides a single dictionary mapping tool names to callable Python functions:
  ```python
  from tigergraph.tools import get_graph_tools
  tools = get_graph_tools()
  txn = tools["get_transaction"]("TXN-104829")
  ```
- **File**: `tigergraph/tools.py` (L413–L432)
- **Status**: IMPLEMENTED

---

## 4. Graph Tools Available to the Agent

| Capability | Existing Function / Interface | Backing Implementation | Realistic Data / Seeded Context |
| :--- | :--- | :--- | :--- |
| **Transaction Lookup** | `get_transaction(transaction_id)` | `mock_provider.MOCK_TRANSACTIONS` | 4 Seeded transactions (`TXN-104829`, `TXN-209144`, `TXN-301855`, `TXN-405112`) |
| **Customer Lookup** | `get_customer(customer_id)` | `mock_provider.MOCK_CUSTOMERS` | 4 Seeded customers (`C-45821`, `C-77109`, `C-10294`, `C-99321`) |
| **Transaction History** | `get_transaction_history(entity_id, limit)` | `mock_provider.get_transaction_history` | Dynamic filtering & aggregation (velocity, avg, max, risk distribution) |
| **Connected Entities** | `get_connected_entities(entity_id, depth)` | `mock_provider.get_connected_entities` | Multi-hop traversal (Customer, Account, Device, IP, Merchant, FraudCase) |
| **Shared Devices** | `find_shared_devices(entity_id)` | `mock_provider.MOCK_DEVICE_RINGS` | 4 Seeded devices (`D-421` has 4 accounts; `D-884` has 3 accounts; `D-302` has 2; `D-119` has 1) |
| **Fraud Pattern Detection** | `detect_fraud_patterns(entity_id)` | `mock_provider.MOCK_FRAUD_PATTERNS` | 5 Pattern typologies (`FP-01` to `FP-05`) returning distinct profiles per transaction |
| **Similar Cases** | `find_similar_cases(case_context)` | `graphrag.retrieval.case_retriever` & `mock_provider` | 4 Precedent cases (`CASE-0842`, `CASE-0773`, `CASE-0915`, `CASE-0620`) |
| **Policy Context** | `get_policy_context(action, amount)` | `graphrag.retrieval.policy_retriever` & `mock_provider` | Bank Policy POL-FRAUD-2026-V1 (`POL-101`, `POL-201`, `POL-402`, `POL-601`, `POL-804`, `POL-901`) |
| **Case Memory Persistence** | `write_case_to_graph(case_payload)` | `mock_provider.MOCK_WRITTEN_CASES` & `client.py` | Upserts `FraudCase`, `Evidence`, `ActionRecord`, links `Transaction`, `Customer`, `FraudPattern` |

---

## 5. GraphRAG Interfaces

Person 2 implemented an offline, local GraphRAG pipeline in `graphrag/` that does not require any external LLM or vector database service:

### 5.1 Pipeline Orchestrator (`graphrag/pipeline.py`)
- **Class**: `GraphRAGPipeline`
  - Method: `retrieve_context(case_context: str, pattern_id: Optional[str] = None, proposed_action: Optional[str] = None, amount: Optional[float] = None) -> str`
    - Formats retrieved policy constraints, SAR requirements, human approval rules, and historical case precedents into a compact, human- and LLM-readable prompt block.
  - Method: `get_structured_context(...) -> Dict[str, Any]`
    - Returns a dictionary containing `{"prompt_context": str, "policy": PolicyContextResponse, "similar_cases": SimilarCasesResponse}`.
- **Convenience Function**: `retrieve_investigation_context(...) -> str`
  - 1-line helper: `context_str = retrieve_investigation_context(case_context="...", proposed_action="BLOCK_TRANSACTION", amount=8500.0)`

### 5.2 Policy Retriever (`graphrag/retrieval/policy_retriever.py`)
- **Function**: `get_policy_context(case_context, pattern_id, proposed_action, amount) -> PolicyContextResponse`
- **Backing Mechanism**: 
  - Chunks `graphrag/documents/policies/fraud_policy.md` into 7 granular clauses (`POL-101`, `POL-201`, `POL-402`, `POL-601`, `POL-804`, `POL-901`, `POL-950`).
  - Pre-embeds clauses using `embed_text`.
  - Applies a regulatory threshold hierarchy:
    - High-value transactions ($\ge \$5,000$) override to `POL-804` (mandatory secondary human approval + SAR).
    - `FREEZE_ACCOUNT` overrides to `POL-601` (mandatory supervisor sign-off).
    - `BLOCK_TRANSACTION` (< $5,000) maps to `POL-402` (automated block permitted).
    - `REQUEST_STEP_UP_AUTH` maps to `POL-201` (authorized when confidence < 0.70).
    - Mule pattern `FP-03` triggers mandatory `POL-901` SAR filing.
    - Fallback: Vector cosine similarity against all policy clauses.

### 5.3 Similar Case Retriever (`graphrag/retrieval/case_retriever.py`)
- **Function**: `find_similar_cases(case_context: str, top_k: int = 3) -> SimilarCasesResponse`
- **Backing Mechanism**:
  - Loads 4 historical precedent cases from `graphrag/documents/cases/historical_cases.json`.
  - Computes hybrid similarity: $0.65 \times \text{CosineSimilarity} + \text{TypologyBoost}$ (boosts for keywords like "device", "velocity", "mule", "proxy", "card test").
  - Returns top $k$ sorted `SimilarCaseItem` objects.

### 5.4 Embedder (`graphrag/embeddings/embedder.py`)
- **Functions**: `embed_text(text: str) -> List[float]`, `embed_batch(texts: List[str]) -> List[List[float]]`, `cosine_similarity(v1, v2) -> float`.
- **Backing Mechanism**:
  - Attempts lazy load of `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions).
  - If `sentence-transformers` is not installed or offline, falls back to `_fallback_embed()`, a deterministic, normalized 384-dimensional semantic unigram/bigram hash embedder. **Zero network calls or missing-model crashes.**

---

## 6. Case Memory Interfaces

Person 2 provided mechanisms for writing and reading case memory across both mock and live modes:

### 6.1 Writing to Case Memory
- **Interface**: `write_case_to_graph(case_payload: Dict[str, Any]) -> WriteCaseResponse`
- **In Mock Mode (`USE_MOCK_GRAPH=true`)**:
  - Stores the case payload in `mock_provider.MOCK_WRITTEN_CASES[case_id]`.
  - Normalizes `evidence` list (ensures both `type` and `evidence_type` are populated).
  - Normalizes `actions` / `action_records` list.
  - Updates timestamp `updated_at`.
  - Generates graph IDs: `vertex_fraudcase_{case_id}`, `edge_involved_{txn_id}`, `edge_customer_{cust_id}`, etc.
- **In Live Mode (`USE_MOCK_GRAPH=false`)**:
  - Executed by `TigerGraphLiveClient.write_case_to_graph()` in `tigergraph/client.py`.
  - Upserts vertices:
    - `FraudCase(case_id, transaction_id, customer_id, status, risk_score, confidence, created_at, summary)`
    - `Evidence(id, evidence_type, source, summary, confidence, timestamp)`
    - `ActionRecord(id, action_type, status, requested_at, executed_at, approval)`
  - Upserts edges:
    - `INVOLVED_IN_CASE` (`FraudCase` $\to$ `Transaction`)
    - `LINKED_CUSTOMER` (`FraudCase` $\to$ `Customer`)
    - `HAS_EVIDENCE` (`FraudCase` $\to$ `Evidence`)
    - `EXECUTED_ACTION` (`FraudCase` $\to$ `ActionRecord`)
    - `DETECTED_PATTERN` (`FraudCase` $\to$ `FraudPattern`)

### 6.2 Reading from Case Memory
- **Via Connected Entities**: `get_connected_entities(entity_id=case_id)` in `mock_provider.py` checks `MOCK_WRITTEN_CASES` or `CASE-*` prefixes. If found, returns the `FraudCase` node, linked `Transaction`, `Customer`, `Evidence`, and `FraudPattern` nodes.
- **Via Graph Algorithm**: `tigergraph/queries/find_similar_case_cluster.gsql` traverses `SIMILAR_TO_CASE` edges to find connected historical cases.
- **Via Historical Cases**: `graphrag.retrieval.case_retriever.find_similar_cases()` reads `historical_cases.json`.

---

## 7. Data Models

### 7.1 Pydantic Response Models (`tigergraph/tools.py`)
All models enforce snake_case naming per the contract:

1. `TransactionDetailResponse`:
   ```python
   transaction_id: str
   customer_id: str
   account_id: str
   amount: float
   currency: str = "USD"
   timestamp: int
   risk_score: float
   channel: str
   card_network: str
   merchant_name: str
   device_id: str
   ip_str: str
   dist1: Optional[float] = None
   dist2: Optional[float] = None
   c1: Optional[int] = None ... c14: Optional[int] = None
   ```
2. `CustomerDetailResponse`:
   ```python
   customer_id: str
   name: str
   risk_tier: str          # "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
   created_at: int
   accounts: List[str]
   linked_cards: List[str]
   email: str
   risk_score: float
   ```
3. `TransactionHistoryResponse`:
   ```python
   transactions: List[TransactionHistoryItem]  # transaction_id, amount, timestamp, merchant_name, risk_score, channel
   summary: TransactionHistorySummary          # total_transactions, avg_amount, max_amount, velocity_30d, risk_distribution
   ```
4. `ConnectedEntitiesResponse`:
   ```python
   nodes: List[GraphNode]  # id, label, type, risk_score
   edges: List[GraphEdge]  # source, target, type
   ```
5. `SharedDevicesResponse`:
   ```python
   devices: List[SharedDeviceItem]  # device_id, linked_accounts, risk_score, associated_account_ids
   ```
6. `DetectFraudPatternsResponse`:
   ```python
   patterns: List[FraudPatternItem]  # pattern_id, name, description, evidence_refs, confidence
   ```
7. `SimilarCasesResponse`:
   ```python
   similar_cases: List[SimilarCaseItem]  # case_id, similarity_score, status, risk_score, outcome, matched_patterns, key_findings
   ```
8. `PolicyContextResponse`:
   ```python
   policy_id: str
   policy_basis: str
   approval_required: bool
   sar_required: bool
   confidence_threshold: float
   allowed_actions: List[str]
   escalation_notes: Optional[str] = None
   ```
9. `WriteCaseResponse`:
   ```python
   status: str             # "SUCCESS"
   case_id: str
   graph_ids: List[str]
   nodes_written: int
   edges_written: int
   message: str
   ```

### 7.2 Error Model (`tigergraph/mock_provider.py`)
```python
class GraphError(Exception):
    code: str
    message: str
    details: Dict[str, Any]

# Serializes to Section 9 standard format:
{
    "error": {
        "code": "TRANSACTION_NOT_FOUND",
        "message": "Transaction '...' was not found in graph database.",
        "details": {"transaction_id": "..."}
    }
}
```

### 7.3 TigerGraph Schema DDL (`tigergraph/schema/schema.gsql`)
- **12 Vertex Types**: `Customer`, `Account`, `Transaction`, `Device`, `IPAddress`, `Email`, `CreditCard`, `Merchant`, `FraudPattern`, `FraudCase`, `Evidence`, `ActionRecord`.
- **12 Directed Edge Pairs (with `REVERSE_*`)**:
  - `HAS_ACCOUNT` (`Customer` $\to$ `Account`)
  - `PERFORMED_TRANSACTION` (`Account` $\to$ `Transaction`)
  - `TARGETS_MERCHANT` (`Transaction` $\to$ `Merchant`)
  - `USED_DEVICE` (`Transaction` $\to$ `Device`)
  - `ASSOCIATED_IP` (`Transaction` $\to$ `IPAddress`)
  - `USED_CARD` (`Transaction` $\to$ `CreditCard`)
  - `USED_EMAIL` (`Account` $\to$ `Email`)
  - `INVOLVED_IN_CASE` (`FraudCase` $\to$ `Transaction`)
  - `LINKED_CUSTOMER` (`FraudCase` $\to$ `Customer`)
  - `DETECTED_PATTERN` (`FraudCase` $\to$ `FraudPattern`)
  - `HAS_EVIDENCE` (`FraudCase` $\to$ `Evidence`)
  - `EXECUTED_ACTION` (`FraudCase` $\to$ `ActionRecord`)
- **1 Undirected Edge**:
  - `SIMILAR_TO_CASE` (`FraudCase` $\leftrightarrow$ `FraudCase`, attribute: `similarity_score DOUBLE`)

---

## 8. Configuration / Environment

Person 2's `tigergraph/config.py` manages configuration with safe fallbacks:

| Variable | Type | Default Value | Notes |
| :--- | :--- | :--- | :--- |
| `USE_MOCK_GRAPH` | bool | `"true"` | When true, runs completely offline via mock fixtures. Live TigerGraph is opt-in (`false`). |
| `TIGERGRAPH_HOST` | str | `"http://127.0.0.1"` | TigerGraph server host URL or IP |
| `TIGERGRAPH_REST_PORT` | int | `9000` | REST++ endpoint port |
| `TIGERGRAPH_GS_PORT` | int | `14240` | GraphStudio / GSQL port |
| `TIGERGRAPH_USERNAME` | str | `"tigergraph"` | Cluster username |
| `TIGERGRAPH_PASSWORD` | str | `"tigergraph"` | Cluster password (also used as Savanna Cloud secret) |
| `TIGERGRAPH_GRAPH_NAME` | str | `"FraudGraph"` | Target graph name |
| `TIGERGRAPH_SECRET` | str | `None` | Optional explicit TigerGraph Cloud secret |
| `TIGERGRAPH_API_TOKEN` | str | `None` | Optional pre-generated API token |

> [!NOTE]
> `.env.example` in the repository currently only defines `TIGERGRAPH_HOST`, `TIGERGRAPH_USERNAME`, and `TIGERGRAPH_PASSWORD`. The other variables (`USE_MOCK_GRAPH`, `TIGERGRAPH_REST_PORT`, `TIGERGRAPH_GRAPH_NAME`, `TIGERGRAPH_SECRET`) are read by `tigergraph/config.py` but are not listed in `.env.example`.

---

## 9. Dependencies

### 9.1 Required Runtime Dependencies
- **`pydantic` (v2.x)**: Required by `tigergraph/tools.py` for data validation and response models. *(Installed in current environment)*
- **`python-dotenv`**: Read in `tigergraph/config.py`. *(Installed in current environment)*

### 9.2 Optional / Conditional Dependencies
- **`pyTigerGraph`**: Imported conditionally in `tigergraph/client.py`. Only needed when `USE_MOCK_GRAPH=false`. If absent when live client is initialized, raises a helpful `RuntimeError("pyTigerGraph is not installed. Run 'pip install pyTigerGraph'.")`.
- **`sentence-transformers`**: Imported conditionally in `graphrag/embeddings/embedder.py`. If absent, gracefully falls back to deterministic unigram/bigram semantic hash embeddings.
- **`mcp`**: Required ONLY if launching the MCP server via `python -m tigergraph.mcp.server` or importing `tigergraph.mcp.server`. Not required when calling Python tool functions directly in-process.
- **`pytest`**: Required for executing the test suite `tests/test_graph_tools.py`.

---

## 10. Integration Gaps

The following gaps and contracts must be noted by Person 1 before building the Agent and Backend:

### Gap 1: Incomplete Live Wiring in `tigergraph/tools.py` [PARTIAL]
In `tigergraph/tools.py`, only Tool 9 (`write_case_to_graph`) contains a live dispatch switch:
```python
if not getattr(config, "USE_MOCK_GRAPH", True):
    from tigergraph.client import live_client
    raw_data = live_client.write_case_to_graph(case_payload=payload)
```
Tools 1 through 8 unconditionally call `mock_provider.*`! Even if `USE_MOCK_GRAPH=false` is set, Tools 1–8 still query `mock_provider`. Person 2 has created the GSQL queries in `tigergraph/queries/`, but has not yet written the corresponding Python methods on `TigerGraphLiveClient` in `tigergraph/client.py` to invoke them via `conn.runInstalledQuery()`.

### Gap 2: Disconnected Case Memory in Mock Mode [PARTIAL]
When `write_case_to_graph` writes a case in mock mode, it stores the case in `mock_provider.MOCK_WRITTEN_CASES`. However:
- `find_similar_cases` in `case_retriever.py` searches static `graphrag/documents/cases/historical_cases.json`.
- `mock_provider.find_similar_cases` searches static `MOCK_SIMILAR_CASES`.
Neither retriever searches `MOCK_WRITTEN_CASES`. Therefore, cases written by the agent during a run are not dynamically discoverable by subsequent `find_similar_cases` calls in mock mode unless Person 1 or 2 explicitly bridges them.

### Gap 3: Missing `get_case` Tool [MISSING]
There is no `get_case(case_id: str)` tool function in `tigergraph/tools.py`. If the agent or frontend needs to load a previously investigated case by ID:
- It can partially inspect it via `get_connected_entities(entity_id=case_id)`.
- But there is no dedicated `get_case` tool returning a full `Case` model.

### Gap 4: Section 5 Case vs Section 7 Response Contract Asymmetry [PARTIAL]
As discovered in `scripts/verify_mock_layer.py`:
- Section 5 of the design specification defines a `Case` object with 10 fields (`case_id`, `transaction_id`, `customer_id`, `status`, `risk_score`, `confidence`, `fraud_patterns`, `evidence`, `recommendation`, `approval`/`approval_required`, `timeline`).
- `write_case_to_graph` accepts this 10-field payload, but returns only `WriteCaseResponse` (`case_id`, `status`, `graph_ids`, `nodes_written`, `edges_written`, `message`).
- **Implication for Person 1**: The Agent State and Backend Database (FastAPI/SQLAlchemy/PostgreSQL or in-memory) must manage the full authoritative `Case` state. TigerGraph acts as the graph persistence and audit layer, not the sole state store.

### Gap 5: Data Divergence Across Fixtures [UNCLEAR]
There are discrepancies in field values between Person 2's dataset files:
- In `tigergraph/mock_provider.py`: `TXN-104829` has `amount = 1249.50`, customer is `Alex Mercer`.
- In `data/transactions.csv`: `TXN-104829` has `TransactionAmt = 8450.0`, customer is `Elena Vance` in `data/graph_entities.json`.
- In `tigergraph/mock_provider.py`: `TXN-301855` has `amount = 8450.00`, customer is `Dmitri Volkov`.
- In `data/transactions.csv`: `TXN-301855` has `TransactionAmt = 1249.0`, customer is `Amina Rossi` in `data/graph_entities.json`.
Person 1's mock agent flows should bind to `tigergraph/mock_provider.py` (which matches `tests/test_graph_tools.py`), rather than assuming `transactions.csv` values.

---

## 11. Recommended Integration Boundary

Based strictly on Person 2's existing implementation, the cleanest and most robust integration boundary is **Direct In-Process Python Function Calls**:

```text
┌────────────────────────────────────────────────────────┐
│               Person 1: Agent & Backend                │
│                                                        │
│  FastAPI Endpoints (backend/api/)                      │
│  LangGraph Workflow State Machine (agent/workflows/)   │
│  Agent Tools Registry (agent/tools/)                   │
└───────────────────────────┬────────────────────────────┘
                            │
              Direct Python In-Process Calls
     (from tigergraph.tools import get_graph_tools)
     (from graphrag.pipeline import pipeline, retrieve_investigation_context)
                            │
┌───────────────────────────▼────────────────────────────┐
│         Graph Integration Layer (Person 2)             │
│                                                        │
│  tigergraph/tools.py          graphrag/pipeline.py     │
│  - get_transaction           - retrieve_context       │
│  - get_customer              - get_structured_context │
│  - get_transaction_history   - policy_retriever       │
│  - get_connected_entities    - case_retriever         │
│  - find_shared_devices                                │
│  - detect_fraud_patterns                               │
│  - find_similar_cases                                  │
│  - get_policy_context                                  │
│  - write_case_to_graph                                 │
└───────────────────────────┬────────────────────────────┘
                            │
               Controlled by USE_MOCK_GRAPH
             (tigergraph/config.py, default=True)
             ┌──────────────┴──────────────┐
             │                             │
    [USE_MOCK_GRAPH=true]        [USE_MOCK_GRAPH=false]
             │                             │
┌────────────▼──────────────┐ ┌────────────▼─────────────┐
│  tigergraph/              │ │  tigergraph/             │
│    mock_provider.py       │ │    client.py             │
│                           │ │                          │
│  Deterministic fixtures   │ │  pyTigerGraph Live       │
│  In-memory case memory    │ │  TigerGraph Cloud        │
└───────────────────────────┘ └──────────────────────────┘
```

### Why In-Process Python Calls Instead of MCP Server for Agent Integration:
1. **Zero External Processes**: Does not require running an external subprocess or managing JSON-RPC 2.0 pipes over stdio.
2. **Zero Async Impedance Mismatch**: Tool functions in `tigergraph/tools.py` are synchronous functions that return typed Pydantic models immediately. LangGraph tool nodes can wrap them directly.
3. **No Extra Dependencies**: Does not require installing `mcp` into the main application environment.
4. **Preserves MCP for Person 3 / Claude**: The MCP server in `tigergraph/mcp/server.py` remains completely available for external desktop clients or if MCP client adapters are desired later.

---

## 12. Questions / Ambiguities

1. **Live GSQL Query Execution**: When will Person 2 add live query wrappers in `tigergraph/client.py` for the 5 GSQL queries (`detect_card_testing`, `detect_geo_impossibility`, etc.) and connect them to Tools 1–8 in `tigergraph/tools.py`?
2. **Canonical Fixtures**: For initial frontend and demo walkthroughs, should the system use Person 2's `mock_provider.py` personas (Alex Mercer, Sarah Jenkins, Dmitri Volkov, Jordan Lee) or the names in `data/graph_entities.json` (Elena Vance, Marcus Thorne, Amina Rossi, David Chen)?
3. **Dynamic GraphRAG Ingestion**: When new cases are written to TigerGraph case memory via `write_case_to_graph`, is Person 2 planning to automatically embed and index them into `historical_cases.json`, or will dynamic case precedent retrieval query TigerGraph directly via `find_similar_case_cluster.gsql`?
4. **Missing `get_case` Tool**: Should Person 2 add `get_case(case_id: str)` to `tigergraph/tools.py`, or should Person 1 store all case records in the backend database and only use TigerGraph for graph topology and audit?

---

# PERSON 1 STARTING POINT

As Person 1 (Brain lead), you can immediately and safely begin developing the backend and agent without breaking or waiting on Person 2's work. The starting steps are:

### 1. Safely Consume Existing Graph Tools
Import the 9 tools directly in your agent tool registry (`agent/tools/`):
```python
from tigergraph.tools import get_graph_tools, get_transaction, get_customer, ...
from graphrag.pipeline import pipeline, retrieve_investigation_context
```
Because `USE_MOCK_GRAPH=true` is the default, all 9 tools operate immediately and deterministically with full Pydantic validation.

### 2. Implement the Agent State Machine (`agent/workflows/` & `agent/reasoning/`)
You can implement the LangGraph investigation graph using the 4 seeded test transactions (`TXN-104829`, `TXN-209144`, `TXN-301855`, `TXN-405112`):
- **Node 1 (Enrichment)**: Calls `get_transaction`, `get_customer`, `get_transaction_history`.
- **Node 2 (Graph Analytics)**: Calls `get_connected_entities`, `find_shared_devices`, `detect_fraud_patterns`.
- **Node 3 (GraphRAG Context)**: Calls `retrieve_investigation_context` to fetch policy constraints and historical case precedents.
- **Node 4 (Risk & Confidence Calculation)**: Computes risk score, uncertainty, and Next Best Action (NBA).
- **Node 5 (Policy Compliance & Approval Routing)**: Compares against `PolicyContextResponse` (`approval_required`, `sar_required`, `confidence_threshold`).
- **Node 6 (Persistence)**: Calls `write_case_to_graph(case_payload)` to record the case in case memory.

### 3. Build the FastAPI Backend Endpoints (`backend/api/`)
In `backend/api/`, create REST endpoints that the Next.js frontend (Person 3) will consume:
- `GET /api/transactions/{id}` $\to$ calls `get_transaction`
- `GET /api/customers/{id}` $\to$ calls `get_customer`
- `GET /api/graph/{id}` $\to$ calls `get_connected_entities`
- `POST /api/investigate` $\to$ triggers the LangGraph agent run for a given transaction ID
- `POST /api/cases/{id}/approve` $\to$ Human-in-the-loop approval endpoint

### 4. Implement Mock Action APIs (`backend/services/`)
Build action execution handlers for the Next Best Actions recommended by the agent:
- `block_card(card_token: str)`
- `freeze_account(account_id: str)`
- `request_step_up_auth(customer_id: str)`
- `file_sar(sar_narrative: str)`
- `allow_transaction(transaction_id: str)`

All of this can be built with 100% confidence today against the existing contracts in `tigergraph/tools.py` and `graphrag/pipeline.py`.
