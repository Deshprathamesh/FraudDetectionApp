# FraudGraph AI — Final Source of Truth

**Document Status**: FROZEN PRE-IMPLEMENTATION SPECIFICATION  
**Date**: September 24, 2026  
**Auditor / Author**: Person 1 (Brain / Agent & Backend Lead)  
**Collaborators**: Person 2 (Graph & GraphRAG Lead), Person 3 (Product & Frontend Lead)  
**Scope**: Final architectural reconciliation across all challenge guidelines, datasets, codebases, and integration contracts prior to Person 1 implementation.

---

## 1. Project Status

FraudGraph AI is a 3-person hackathon system designed for the **TigerGraph Agentic Fraud Investigation HHGOA** challenge.

### Workstream Status:
- **Person 2 (Graph)**: **COMPLETED**. Core TigerGraph DDL (`tigergraph/schema/schema.gsql`), GSQL queries (`tigergraph/queries/`), loading jobs (`tigergraph/loaders/`), offline deterministic mock provider (`tigergraph/mock_provider.py`), 9 contract tool functions with Pydantic response models (`tigergraph/tools.py`), MCP server (`tigergraph/mcp/server.py`), GraphRAG vector retrieval pipeline (`graphrag/pipeline.py`), policy retriever (`graphrag/retrieval/policy_retriever.py`), case retriever (`graphrag/retrieval/case_retriever.py`), and test suite (`tests/test_graph_tools.py`) are fully implemented and verified.
- **Person 3 (Product)**: **COMPLETED**. Full Next.js 14 App Router frontend is implemented under `frontend/` (`app/page.tsx`, `app/investigate/page.tsx`, `app/cases/[caseId]/page.tsx`, `components/graph/GraphCanvas.tsx`, `services/api.ts`, `services/mockApi.ts`, `types/index.ts`). Merged into `main` via PR #1 (`ef37220`).
- **Person 1 (Brain)**: **RECONCILIATION PHASE (Current)**. Backend (`backend/`) and agent orchestration (`agent/`) are clean skeletons. This document freezes all contracts and architecture before Person 1 starts implementation.

---

## 2. Source of Truth Hierarchy

When resolving technical, structural, or behavioral discrepancies across materials, all components must strictly follow this authority hierarchy:

```text
┌────────────────────────────────────────────────────────────────────────┐
│ LEVEL 1: Organizer-provided dataset + dataset README (HHGOA_IEEE)      │
├────────────────────────────────────────────────────────────────────────┤
│ LEVEL 2: Organizer challenge PDF (TigerGraph Agentic Fraud HHGOA)      │
├────────────────────────────────────────────────────────────────────────┤
│ LEVEL 3: Actual completed Person 2 implementation (tigergraph/, etc.)  │
├────────────────────────────────────────────────────────────────────────┤
│ LEVEL 4: Actual completed Person 3 implementation (frontend/)          │
├────────────────────────────────────────────────────────────────────────┤
│ LEVEL 5: FraudGraph AI Integration Specification (docs & spec PDF)     │
├────────────────────────────────────────────────────────────────────────┤
│ LEVEL 6: FraudGraph AI PRD / Feature Specification                     │
├────────────────────────────────────────────────────────────────────────┤
│ LEVEL 7: Previous architectural assumptions or informal suggestions    │
└────────────────────────────────────────────────────────────────────────┘
```

> [!IMPORTANT]
> Level 1 (Organizer dataset and README) is the absolute authority for grading, evaluation format, policy rules, and benchmark cases. No team assumption or convenience design may override Level 1.

---

## 3. Organizer Challenge Requirements

Extracted from Level 2 (`TigerGraph Agentic Fraud Investigation HHGOA.pdf`):

1. **Objective**: Build an Agentic Fraud Investigation Agent powered by TigerGraph that investigates fraud, creates and progresses cases, recommends next-best actions when signals are uncertain, requests additional evidence when needed, and decides when there is sufficient information to act.
2. **Trigger Sources**:
   - Fraud signal / real-time model risk score
   - Customer message / report
   - Fraud analyst request
3. **Core Investigation Loop**:
   $$\text{Trigger} \to \text{Investigate} \to \text{Gather Evidence} \to \text{Assess Uncertainty} \to \text{Request Evidence if needed} \to \text{Next Best Action} \to \text{Explain} \to \text{Update Memory}$$
4. **Mandatory Technology Components**:
   - TigerGraph Savanna Cloud or Community Edition
   - GSQL and TigerGraph graph algorithms (traversal, pattern detection, relationship analysis)
   - TigerGraph MCP (Model Context Protocol) exposing graph tools
   - GraphRAG grounding the agent in connected evidence, fraud policies, and typologies
   - User Interface demonstrating investigation, case progression, evidence, uncertainty, and recommendations
5. **Permitted Simulations / Mocks**: Customer messages, account freezing, card blocking, refunds, and CRM updates may be simulated or represented through mock APIs.
6. **Judging Criteria**:
   - Investigation accuracy: **25%**
   - Next-best action (handling uncertainty & updating recommendations): **25%**
   - Case summary and explainability: **10%**
   - Agentic design and engineering (architecture, tool use, workflow, memory, controls): **15%**
   - Innovation (Graph + AI + GraphRAG): **15%**
   - Demo quality and completeness: **10%**
7. **Submission Deliverables**:
   - Working agent
   - GitHub repository
   - Agent output on the 20 provided cases (single answer file per case containing case record, graph persistence flag, SAR when required, and initial/final next best actions with approval routes)
   - 3–5 minute demo video
   - Technical blog post
   - Social post on X/LinkedIn tagging `@TigerGraphDB`

---

## 4. Actual Dataset Structure

Extracted from Level 1 (`Information/drive-download-20260923T192514Z-1-001.zip -> README.md`):

### 4.1 Master Dataset Files (Stored locally in `Information/`, NEVER committed to Git)
1. **`transactions.csv`**:
   - **Scale**: 590,742 transactions, ~708 MB.
   - **Columns**: All 393 original Vesta IEEE-CIS columns + 4 added columns:
     - `TransactionID`: string (e.g. `3514030`)
     - `TransactionAmt`: float (USD)
     - `TransactionDT`: integer (seconds from dataset start)
     - `ProductCD`: string (`W`, `C`, `H`, `R`, `S`)
     - `card1` to `card6`: card attributes (`card4` = network, `card6` = credit/debit)
     - `addr1`, `addr2`: billing region and country
     - `dist1`, `dist2`: physical distances
     - `P_emaildomain`, `R_emaildomain`: email domains
     - `C1`–`C14`: count features
     - `D1`–`D15`: time deltas
     - `M1`–`M9`: match flags
     - `V1`–`V339`: Vesta engineered relationship features
     - `customer_id`: string (e.g. `C12382`)
     - `ts`: timestamp string (`YYYY-MM-DD HH:MM:SS`)
     - `channel`: string (`online` or `in_person`)
     - `risk_score`: float ($0.0$ to $1.0$, detection model score; input signal, NOT an answer)
2. **`identity.csv`**:
   - **Scale**: 144,432 records. Joined to transactions on `TransactionID` for online transactions.
   - **Columns**: 41 columns including `id_01`–`id_38`, `DeviceType`, `DeviceInfo`.
     - Key fields: `id_15` (device `New` / `Found`), `id_23` (proxy type), `id_30` (OS), `id_31` (browser), `id_33` (screen resolution).
3. **`closed_cases_history.csv`**:
   - **Scale**: 5,565 closed investigations (July to October 2016). 4,665 confirmed fraud, 900 cleared.
   - **Columns**: `case_id`, `customer_id`, `card_id`, `opened_at`, `closed_at`, `outcome` (`confirmed_fraud` / `cleared`), `pattern`, `first_fraud_txn_id`, `txn_ids` (pipe-separated), `n_txns`, `exposure_usd`, `connected_card_ids`, `actions_taken`, `report_filed`, `analyst_notes`.
4. **`case_pack.csv`**:
   - **Scale**: 20 benchmark cases (`HHG-001` through `HHG-020`).
   - **Columns**: `case_id`, `opened_at`, `trigger_type` (`risk_score`, `customer_report`, `analyst_request`), `trigger_text`, `flagged_txn_id`, `card_id`, `customer_id`, `risk_score`.

### 4.2 Repository Sample Data (Stored in `data/`, tracked in Git)
- `data/transactions.csv` (37 rows), `data/identity.csv` (37 rows), `data/graph_entities.json` (seeded graph entities). Used for local unit tests and offline mock testing without downloading 700 MB.

---

## 5. Canonical Data Identifiers

All components across Person 1, Person 2, and Person 3 must use these exact names:

| Concept | Canonical Name | Example | Type | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Transaction ID** | `transaction_id` / `TransactionID` | `"3514030"` or `"TXN-104829"` | `str` | Primary transaction identifier |
| **Customer ID** | `customer_id` | `"C12382"` or `"C-45821"` | `str` | Customer entity identifier |
| **Card ID** | `card_id` | `"C12382-K1"` | `str` | Card token identifier |
| **Account ID** | `account_id` | `"ACC-90124"` | `str` | Banking account identifier |
| **Device ID / Profile** | `device_id` / `device_profile` | `"D-421"` / `"Android 7.0 \| Chrome..."` | `str` | Hardware / browser fingerprint |
| **Case ID** | `case_id` | `"HHG-001"` or `"CASE-1024"` | `str` | Investigation case identifier |
| **Evidence ID** | `evidence_id` | `"EV-001"` or `"EVID-001"` | `str` | Unique evidence item identifier |
| **Pattern ID** | `pattern` / `pattern_id` | `"card_testing"` / `"FP-01"` | `str` | Typology identifier |
| **Amount** | `amount` / `TransactionAmt` | `1249.50` | `float` | Monetary transaction amount in USD |
| **Currency** | `currency` | `"USD"` | `str` | Currency code (always `"USD"`) |
| **Risk Score** | `risk_score` | `0.87` | `float` | Model score ($0.0$ to $1.0$) |
| **Confidence** | `confidence` / `fraud_probability`| `0.78` | `float` | Agent confidence / probability ($0.0$ to $1.0$) |
| **Uncertainty** | `uncertainty` | `0.22` | `float` | Remaining ambiguity ($1.0 - \text{confidence}$) |
| **Timestamp** | `timestamp` / `opened_at` | `1718002000` / `"2016-12-05 01:55:28"` | `int` / `str` | Epoch seconds or ISO/SQL string |

---

## 6. Fraud Patterns

### 6.1 The Five Canonical Organizer Fraud Patterns (Level 1)
1. **`card_testing`**: A stolen card number is verified before use: 3+ tiny online authorizations (often $< \$5.00$), followed immediately by a larger purchase. Confirmed by the sequence itself. (Policy R5).
2. **`card_not_present_fraud`**: Card number used online without physical card. Amounts and products inconsistent with cardholder history, often in a burst of 2–4 purchases within 48 hours. Requires customer verification. (Policy R1–R4).
3. **`card_not_present_new_device`**: Online card-not-present activity originating from an identity record marked `New` for this account, sometimes routed via a proxy. (Policy R1–R4).
4. **`out_of_region_use`**: Card-present transactions in a billing region (`addr1`) where the cardholder has no history, while normal activity continues in the home region. (Policy R2, R3).
5. **`account_takeover`**: Mixed-channel activity inconsistent with cardholder behavior, paired with device and match-flag anomalies, indicating stolen credentials rather than just a compromised card number.
6. **`undocumented`**: Coordinated or repeated abuse across customers that fits none of the 5 known categories. Agent must describe the pattern in `pattern_description`. (Policy R9).
7. **`none`**: Benign / legitimate activity cleared by investigation.

### 6.2 Mapping to Person 2's Graph Typologies (Level 3)
| Organizer Pattern (Level 1) | Person 2 Graph Typology (Level 3) | Graph Signature |
| :--- | :--- | :--- |
| `card_testing` | `FP-02` / `FP-05` | Rapid micro-authorizations via `detect_card_testing.gsql` |
| `card_not_present_new_device` | `FP-01` (Syndicate Ring) | `Device.linked_accounts >= 3` via `detect_shared_device_ring.gsql` |
| `out_of_region_use` | `FP-04` (Geo-Velocity Anomaly) | Distance $> 500\text{ miles}$ / proxy via `detect_geo_impossibility.gsql` |
| `account_takeover` | `FP-01` / `FP-05` | Multi-account device hopping and synthetic identity links |
| `undocumented` | `FP-03` (Mule Daisy-Chain) | Rapid inbound deposit $\to$ outbound crypto/wire transfer |

---

## 7. Organizer Fraud Policy

Extracted verbatim from Level 1 (`README.md # Fraud Policy`). This is the authoritative policy governing agent decisioning:

### 7.1 Action Taxonomy
| Action | Description | Impact | Default Approval Route |
| :--- | :--- | :--- | :--- |
| `ALLOW_TRANSACTION` | Let flagged transaction stand | None | `auto` |
| `DECLINE_TRANSACTION` | Decline flagged authorization only; card remains active | Low | `L1` (team lead) |
| `MONITOR_CARD` | Raise monitoring sensitivity for 72 hours | None | `auto` |
| `MONITOR_CONNECTED_CARDS`| Place cards linked to same device/region under monitoring | None | `auto` |
| `WARN_CUSTOMER` | Send informational message / recurring charge reminder | None | `auto` |
| `VERIFY_WITH_CUSTOMER` | Ask cardholder if they made purchase; card stays active | Low | `auto` |
| `STEP_UP_AUTH` | Require OTP or app confirmation before further activity | Low | `auto` |
| `BLOCK_CARD` | Block card and reissue | High | `L1` ($\le \$2,500$) / `L2` ($> \$2,500$) |
| `BLOCK_ALL_CARDS` | Block every card held by the customer | Very High | `L2` (fraud manager) |
| `GENERATE_REPORT` | Write investigation for internal record without case | None | `auto` |
| `CREATE_CASE` | Open internal case with evidence and write to graph | None | `auto` |
| `FILE_REPORT` | File Suspicious Activity Report with regulator | None | `L2` (fraud manager) |
| `ESCALATE_TO_ANALYST` | Hand case to human analyst with evidence | None | `auto` |
| `CLOSE_NO_FRAUD` | Close alert as legitimate | None | `auto` |

### 7.2 Approval Routing Hierarchy
- **`auto`**: Agent may execute autonomously without human intervention.
- **`L1` (Team Lead)**: `DECLINE_TRANSACTION`; `BLOCK_CARD` when exposure $\le \$2,500.00\text{ USD}$.
- **`L2` (Fraud Manager)**: `BLOCK_CARD` when exposure $> \$2,500.00\text{ USD}$; `BLOCK_ALL_CARDS` always; `FILE_REPORT` always.

### 7.3 The 10 Binding Policy Rules
- **Rule R1 (Verify before block on weak signal)**: If investigation rests on a single signal and assessed fraud probability $< 0.70$, recommend `VERIFY_WITH_CUSTOMER` or `STEP_UP_AUTH` before any block. Blocking on a single weak signal is a policy violation.
- **Rule R2 (Customer denies transaction)**: Recommend `BLOCK_CARD` and `CREATE_CASE`. Add `FILE_REPORT` if exposure $> \$1,000.00$ or case connects to a shared device profile or another card's fraud.
- **Rule R3 (Customer confirms transaction)**: Recommend `CLOSE_NO_FRAUD` and record confirmation in case notes.
- **Rule R4 (No reply within 24 hours)**: Recommend `MONITOR_CARD` and `DECLINE_TRANSACTION` for pending authorizations. Escalate if exposure $> \$500.00$.
- **Rule R5 (Card testing)**: 3+ small online authorizations within an hour followed by a larger purchase $\to$ recommend `DECLINE_TRANSACTION` and `STEP_UP_AUTH`. If purchase cleared $> \$100.00 \to$ recommend `BLOCK_CARD`.
- **Rule R6 (Shared origin)**: Multiple cards showing fraud from the same device profile, billing region, or recipient email in one window $\to$ recommend `CREATE_CASE`, `FILE_REPORT`, and `MONITOR_CONNECTED_CARDS`.
- **Rule R7 (Disputed recurring charge)**: Customer disputes recurring charge matching historical pattern $\to$ recommend `CREATE_CASE`, `VERIFY_WITH_CUSTOMER`, `WARN_CUSTOMER`. Do NOT block.
- **Rule R8 (Escalate when uncertain and exposed)**: If verdict is `uncertain` and exposure $> \$500.00$, or evidence conflicts $\to$ recommend `ESCALATE_TO_ANALYST`.
- **Rule R9 (Undocumented patterns)**: Coordinated abuse fitting no known pattern $\to$ recommend `CREATE_CASE`, `FILE_REPORT`, and `ESCALATE_TO_ANALYST`. Describe pattern in analyst notes.
- **Rule R10 (Constraint on `BLOCK_ALL_CARDS`)**: NEVER recommend `BLOCK_ALL_CARDS` unless $\ge 2$ customer cards show confirmed fraud or customer credentials are confirmed compromised.

### 7.4 Exposure Calculation
$$\text{Exposure USD} = \sum_{t \in \text{affected\_txn\_ids}} |\text{amount}(t)|$$

### 7.5 Stopping Criteria
Stop investigating when:
1. Assessed fraud probability is $\ge 0.85$ or $\le 0.15$, supported by $\ge 2$ independent evidence pieces.
2. A verification response settles the question.
3. Further steps will not change the decision (`stop_reason` recorded).

---

## 8. Benchmark and Evaluation Contract

### 8.1 The 20 Benchmark Cases (`case_pack.csv`)
| Case | Opened At | Trigger Type | Flagged Txn | Card ID | Customer ID | Initial Score |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **HHG-001** | 2016-12-05 01:55:28 | `risk_score` | 3514030 | C12382-K1 | C12382 | 0.61 |
| **HHG-002** | 2016-11-22 23:27:07 | `risk_score` | 3478782 | C11891-K1 | C11891 | 0.79 |
| **HHG-003** | 2016-12-10 15:01:21 | `customer_report`| 3530164 | C08623-K2 | C08623 | — |
| **HHG-004** | 2016-12-29 07:53:54 | `customer_report`| 3583227 | C08106-K1 | C08106 | — |
| **HHG-005** | 2016-12-08 03:38:37 | `risk_score` | 3523199 | C02923-K1 | C02923 | 0.54 |
| **HHG-006** | 2016-11-22 02:30:00 | `customer_report`| 3476682 | C07297-K1 | C07297 | — |
| **HHG-007** | 2016-12-05 03:46:14 | `risk_score` | 3514948 | C09933-K2 | C09933 | 0.87 |
| **HHG-008** | 2016-12-20 03:08:56 | `customer_report`| 3558054 | C13171-K2 | C13171 | — |
| **HHG-009** | 2016-12-28 17:10:53 | `customer_report`| 3581141 | C08299-K1 | C08299 | — |
| **HHG-010** | 2016-12-02 18:18:27 | `risk_score` | 3506725 | C10434-K1 | C10434 | 0.90 |
| **HHG-011** | 2016-12-29 06:27:44 | `customer_report`| 3583368 | C11923-K2 | C11923 | — |
| **HHG-012** | 2016-12-18 05:00:31 | `risk_score` | 3553342 | C05876-K2 | C05876 | 0.55 |
| **HHG-013** | 2016-12-09 05:39:29 | `risk_score` | 3526826 | C07671-K2 | C07671 | 0.76 |
| **HHG-014** | 2016-11-22 20:11:00 | `analyst_request`| 3478561 | C13487-K1 | C13487 | — |
| **HHG-015** | 2016-11-17 19:03:36 | `risk_score` | 3464869 | C03042-K1 | C03042 | 0.77 |
| **HHG-016** | 2016-12-12 01:39:08 | `customer_report`| 3534820 | C09988-K1 | C09988 | — |
| **HHG-017** | 2016-11-12 00:46:24 | `risk_score` | 3450629 | C04570-K1 | C04570 | 0.57 |
| **HHG-018** | 2016-11-27 14:41:26 | `customer_report`| 3491361 | C02354-K2 | C02354 | — |
| **HHG-019** | 2016-12-01 22:28:53 | `risk_score` | 3503878 | C07987-K2 | C07987 | 0.90 |
| **HHG-020** | 2016-12-03 12:04:26 | `risk_score` | 3509359 | C12265-K2 | C12265 | 0.52 |

### 8.2 Official Answer File JSON Schema (Level 1)
Every submitted evaluation file must conform exactly to:
```json
{
  "case_id": "HHG-017",
  "case": {
    "status": "closed_fraud",
    "verdict": "fraud",
    "fraud_probability": 0.86,
    "pattern": "card_testing",
    "pattern_description": "",
    "affected_txn_ids": ["T0412877", "T0412878"],
    "first_suspicious_txn_id": "T0412877",
    "connected_card_ids": ["C00877-K1"],
    "connected_device_profiles": ["SAMSUNG SM-G892A Build/NRD90M | Android 7.0..."],
    "exposure_usd": 268.43,
    "evidence": [
      {
        "claim": "string",
        "source": "graph",
        "ref": "query:card_window(card_id=C00377-K1, hours=2)",
        "entity_ids": ["T0412877"]
      }
    ],
    "similar_prior_cases": ["CC-0141"],
    "summary": "Two to six sentence summary...",
    "written_to_graph": true,
    "graph_case_id": "CASE-2016-1187"
  },
  "evidence_requests": [
    {
      "type": "customer_validation",
      "asked_after_step": 4,
      "assumed_response": "Customer states they did not make purchase"
    }
  ],
  "next_best_actions": {
    "initial": [
      { "action": "DECLINE_TRANSACTION", "route": "L1", "reason": "R5: testing sequence observed" }
    ],
    "final": [
      { "action": "BLOCK_CARD", "route": "L1", "reason": "R2 and R5: customer denied" },
      { "action": "CREATE_CASE", "route": "auto", "reason": "R2" },
      { "action": "FILE_REPORT", "route": "L2", "reason": "R2: shared device link" }
    ],
    "what_changed": "Customer denial confirmed block and triggered report."
  },
  "sar": {
    "file": true,
    "reason": "R2: confirmed unauthorized use linked to second card",
    "narrative": "6-12 sentences covering who, what, when, where, how, why...",
    "subjects": ["C00377", "C00377-K1"],
    "total_amount_usd": 268.43,
    "activity_dates": ["2016-11-14", "2016-11-14"]
  },
  "stop_reason": "Defensible decision reached...",
  "tool_calls": 9,
  "tokens": 12480,
  "latency_s": 18.7
}
```

---

## 9. Person 2 Completed Components

Person 2 has completed 100% of their assigned modules under `tigergraph/`, `graphrag/`, and `data/`:
1. `tigergraph/schema/schema.gsql`: 12 vertices (`Customer`, `Account`, `Transaction`, `Device`, `IPAddress`, `Email`, `CreditCard`, `Merchant`, `FraudPattern`, `FraudCase`, `Evidence`, `ActionRecord`) and 13 edges.
2. `tigergraph/queries/`: 5 GSQL queries (`detect_card_testing.gsql`, `detect_geo_impossibility.gsql`, `detect_shared_device_ring.gsql`, `detect_velocity_abuse.gsql`, `find_similar_case_cluster.gsql`).
3. `tigergraph/loaders/`: 2 GSQL loaders (`load_identity.gsql`, `load_transactions.gsql`).
4. `tigergraph/config.py`: Safe environment configuration (`USE_MOCK_GRAPH=true` default).
5. `tigergraph/client.py`: Live pyTigerGraph client with `write_case_to_graph` implementation.
6. `tigergraph/mock_provider.py`: Deterministic offline fixture provider for all 9 tool operations.
7. `tigergraph/tools.py`: 9 clean Python tool functions with Pydantic response models.
8. `tigergraph/mcp/server.py`: Standard JSON-RPC 2.0 stdio MCP server.
9. `graphrag/embeddings/embedder.py`: Local MiniLM-L6-v2 vector embedder with deterministic hash fallback.
10. `graphrag/retrieval/policy_retriever.py`: Semantic policy retrieval engine over `fraud_policy.md`.
11. `graphrag/retrieval/case_retriever.py`: Hybrid vector + pattern typology case retriever over `historical_cases.json`.
12. `graphrag/pipeline.py`: Knowledge-grounded LLM context orchestrator.
13. `tests/test_graph_tools.py`: 541 lines of pytest contract assertions.

---

## 10. Person 2 Public Interfaces

Person 1 can consume these exact Python signatures from Person 2:

```python
# From tigergraph.tools:
from tigergraph.tools import (
    get_graph_tools,            # () -> Dict[str, Callable]
    get_transaction,            # (transaction_id: str) -> TransactionDetailResponse | Dict[str, Any]
    get_customer,               # (customer_id: str) -> CustomerDetailResponse | Dict[str, Any]
    get_transaction_history,    # (entity_id=None, customer_id=None, account_id=None, limit=10) -> TransactionHistoryResponse
    get_connected_entities,     # (entity_id: str, depth: int = 1) -> ConnectedEntitiesResponse
    find_shared_devices,        # (entity_id=None, customer_id=None, account_id=None, device_id=None) -> SharedDevicesResponse
    detect_fraud_patterns,      # (case_context=None, entity_id=None, transaction_id=None) -> DetectFraudPatternsResponse
    find_similar_cases,         # (case_context=None, case_id=None) -> SimilarCasesResponse
    get_policy_context,         # (action=None, pattern_id=None, amount=None, case_context=None) -> PolicyContextResponse
    write_case_to_graph,        # (case_payload: Optional[Dict[str, Any]] = None, **kwargs) -> WriteCaseResponse
)

# From graphrag.pipeline:
from graphrag.pipeline import (
    pipeline,                           # GraphRAGPipeline instance
    retrieve_investigation_context,     # (case_context: str, pattern_id=None, proposed_action=None, amount=None) -> str
)
```

---

## 11. Person 1 ↔ Person 2 Integration Contract

```text
┌────────────────────────────────────────────────────────┐
│               Person 1: Agent & Backend                │
│                                                        │
│  FastAPI Endpoints (backend/api/)                      │
│  Investigation Workflow (agent/workflows/)             │
│  Agent Tool Adapters (agent/tools/graph_adapter.py)    │
└───────────────────────────┬────────────────────────────┘
                            │ (Direct In-Process Python Call)
┌───────────────────────────▼────────────────────────────┐
│         Person 2 Integration Layer (UNTOUCHED)         │
│                                                        │
│  tigergraph/tools.py          graphrag/pipeline.py     │
└───────────────────────────┬────────────────────────────┘
                            │ (Controlled by USE_MOCK_GRAPH)
             ┌──────────────┴──────────────┐
             │                             │
    [USE_MOCK_GRAPH=true]        [USE_MOCK_GRAPH=false]
             │                             │
┌────────────▼──────────────┐ ┌────────────▼─────────────┐
│  tigergraph/              │ │  tigergraph/             │
│    mock_provider.py       │ │    client.py             │
│                           │ │  TigerGraph Cloud / CE   │
└───────────────────────────┘ └──────────────────────────┘
```

### Integration Points Contract Table:
| Tool Name | Owner | Input | Output Model | Read/Write | Person 1 Usage |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `get_transaction` | Person 2 | `transaction_id: str` | `TransactionDetailResponse` | READ | Initial enrichment |
| `get_customer` | Person 2 | `customer_id: str` | `CustomerDetailResponse` | READ | Customer profile & tier |
| `get_transaction_history` | Person 2 | `customer_id/account_id, limit` | `TransactionHistoryResponse` | READ | Behavioral baseline & velocity |
| `get_connected_entities` | Person 2 | `entity_id: str, depth: int` | `ConnectedEntitiesResponse` | READ | Multi-hop graph subgraph |
| `find_shared_devices` | Person 2 | `entity_id/device_id: str` | `SharedDevicesResponse` | READ | Syndicate ring detection |
| `detect_fraud_patterns` | Person 2 | `case_context/txn_id: str` | `DetectFraudPatternsResponse` | READ | Algorithmic pattern detection |
| `find_similar_cases` | Person 2 | `case_context: str` | `SimilarCasesResponse` | READ | Case memory precedent match |
| `get_policy_context` | Person 2 | `action, amount, pattern_id` | `PolicyContextResponse` | READ | Regulatory & policy check |
| `retrieve_investigation_context`| Person 2 | `case_context, action, amount`| `str` (formatted prompt) | READ | GraphRAG prompt grounding |
| `write_case_to_graph` | Person 2 | `case_payload: Dict[str, Any]`| `WriteCaseResponse` | WRITE | Graph persistence / memory |

---

## 12. AgentState Contract

The authoritative internal state schema for Person 1's investigation state machine (`agent/workflows/state.py`):

```python
class AgentState(TypedDict, total=False):
    # Core Identifiers
    case_id: str
    transaction_id: str
    customer_id: Optional[str]
    card_id: Optional[str]
    
    # Trigger Information
    trigger_type: str                   # 'risk_score' | 'customer_report' | 'analyst_request'
    trigger_text: str
    
    # Investigation Evidence & Artifacts
    transaction_data: Optional[Dict[str, Any]]
    customer_data: Optional[Dict[str, Any]]
    transaction_history: Optional[Dict[str, Any]]
    connected_graph: Optional[Dict[str, Any]]
    shared_devices: Optional[List[Dict[str, Any]]]
    detected_patterns: List[Dict[str, Any]]
    similar_cases: List[Dict[str, Any]]
    graphrag_context: Optional[str]
    evidence_list: List[Dict[str, Any]] # claims, sources, refs, entity_ids
    
    # Risk, Confidence & Assessment
    risk_score: float                   # 0.0 to 1.0 (input signal)
    fraud_probability: float            # 0.0 to 1.0 (assessed likelihood)
    confidence: float                   # 0.0 to 1.0 (evidence completeness)
    uncertainty: float                  # 1.0 - confidence
    verdict: str                        # 'fraud' | 'legitimate' | 'uncertain'
    pattern: str                        # canonical pattern value
    pattern_description: str
    affected_txn_ids: List[str]
    exposure_usd: float
    
    # Evidence Gathering Loop
    evidence_sufficient: bool
    evidence_requests: List[Dict[str, Any]]
    simulated_responses: List[Dict[str, Any]]
    
    # Next Best Action & Routing
    initial_recommendations: List[Dict[str, Any]] # action, route, reason
    final_recommendations: List[Dict[str, Any]]   # action, route, reason
    what_changed: str
    
    # Policy & Human-in-the-Loop
    approval_required: bool
    approval_route: str                 # 'auto' | 'L1' | 'L2'
    approval_status: str                # 'PENDING' | 'APPROVED' | 'REJECTED' | 'NOT_REQUIRED'
    approval_token: Optional[str]
    policy_basis: str
    
    # SAR Filing Details
    sar_required: bool
    sar_narrative: str
    sar_subjects: List[str]
    
    # Execution & Persistence
    execution_results: List[Dict[str, Any]]
    written_to_graph: bool
    graph_case_id: str
    
    # Metadata & Tracking
    timeline: List[Dict[str, Any]]
    stop_reason: str
    errors: List[Dict[str, Any]]
    workflow_status: str                # CaseStatus enum
    iteration_count: int
    max_iterations: int
```

---

## 13. Investigation Workflow

The state machine implements the complete two-stage investigation loop with evidence gathering:

```text
                  TRIGGER
                     ↓
                 ENRICHMENT
        (get_transaction, get_customer, history)
                     ↓
             GRAPH_INVESTIGATION
     (connected_entities, shared_devices, patterns)
                     ↓
             GRAPHRAG_CONTEXT
       (policy retrieval, similar cases)
                     ↓
             ASSESS_UNCERTAINTY
       (risk_score, fraud_probability, confidence)
                     ↓
             INITIAL_RECOMMENDATION
                     ↓
           SUFFICIENT EVIDENCE?
          ├── NO (weak signal / uncertain & exposed)
          │     ↓
          │   REQUEST_ADDITIONAL_EVIDENCE
          │     ↓
          │   SIMULATE_RESPONSE (customer / analyst)
          │     ↓
          │   REASSESS
          │     ↓
          └── YES
                ↓
           FINAL_RECOMMENDATION
                ↓
           POLICY_&_APPROVAL_GATE
          ├── Requires L1 / L2 Approval
          │     ↓
          │   PAUSE (AWAITING_APPROVAL)
          │     ↓ (Human approval token submitted)
          └── Auto / Approved
                ↓
           EXECUTE_ACTIONS (Mock APIs)
                ↓
           CASE_PERSISTENCE (write_case_to_graph)
                ↓
           RESOLVED / ESCALATED
```

---

## 14. Risk / Confidence / Uncertainty

The system enforces clear mathematical and conceptual separation:
- **`risk_score`**: The input score ($0.0$ to $1.0$) from the upstream transaction model. A reason to look, never a verdict.
- **`fraud_probability`**: The agent's assessed probability of fraud based on corroborated graph evidence, pattern sequence, and customer response.
- **`confidence`**: Measure of evidence sufficiency ($0.0$ to $1.0$) based on data completeness (profile verified, historical baseline available, multiple signals agreeing).
- **`uncertainty`**: Defined as $1.0 - \text{confidence}$. When uncertainty $> 0.30$ (confidence $< 0.70$), Rule R1 prohibits irreversible blocking on a single signal and mandates verification or step-up authentication.

---

## 15. Next Best Action

The Next Best Action engine evaluates the current evidence state and outputs ordered recommendations with approval routing:
1. **Initial Recommendation**: Produced prior to requesting additional evidence.
2. **Final Recommendation**: Produced after customer validation or analyst evidence is received.
3. **`what_changed`**: Explicit explanation of how the new evidence altered probability, action selection, or approval route.

---

## 16. Policy / Authorization / HITL

1. **Policy Rules Engine**: Executes rules R1 through R10 from Section 7.
2. **Exposure Evaluation**:
   - `BLOCK_CARD`: exposure $\le \$2,500 \to$ `L1`; exposure $> \$2,500 \to$ `L2`.
   - `FILE_REPORT`: exposure $> \$1,000 \to$ `L2`.
3. **Approval Token Binding**:
   - Any `L1` or `L2` action generates an HMAC-signed `ApprovalRequest` bound to:
     `(case_id, action, target_resource, amount, approver_role, timestamp, expires_at)`.
   - Client submission to `/api/cases/{id}/action` must provide valid approver signature and role.
   - Generic client `approved=true` flags are rejected. Fail-closed architecture.

---

## 17. Case Memory / Persistence

1. **Internal Case Write**: Every completed or escalated case is written to TigerGraph case memory via `write_case_to_graph()`, creating `FraudCase`, `Evidence`, `ActionRecord` vertices and linking `INVOLVED_IN_CASE`, `LINKED_CUSTOMER`, and `DETECTED_PATTERN` edges.
2. **Retrieval**: Future investigations query `find_similar_cases()` to retrieve similar case precedents and analyst rationale from prior cases.

---

## 18. Security Architecture

Enforces the mandatory Security Baseline:
1. **LLM as Reasoning Only**: LLM is never the authorization engine, policy engine, or execution authority.
2. **Least Privilege**: Read operations (`tigergraph.tools`) separated from action handlers (`backend/services/mock_actions.py`).
3. **Prompt Injection Defense**: All retrieved text (metadata, graph properties, policy text, GraphRAG documents) is labeled as untrusted `DATA/EVIDENCE` in prompts and strictly delimited from system instructions.
4. **No Arbitrary GSQL**: Person 1 never constructs or executes raw GSQL queries.
5. **Fail-Closed**: If auth, policy, evidence, or approval fails, execution aborts with zero side-effects.
6. **Bounded Loops**: Agent state machine bounded to `max_iterations = 10` and per-node timeouts.
7. **Structured Audit Trail**: Distinguishes `RECOMMENDED`, `APPROVED`, and `EXECUTED` events without logging secrets or unnecessary PII.

---

## 19. Error Contract

All backend API and agent errors strictly follow the Section 9 standard error shape:

```json
{
  "error": {
    "code": "TRANSACTION_NOT_FOUND",
    "message": "Transaction '...' was not found in graph database.",
    "details": {
      "transaction_id": "..."
    }
  }
}
```

### Standard Error Codes:
- `TRANSACTION_NOT_FOUND` (404)
- `CUSTOMER_NOT_FOUND` (404)
- `CASE_NOT_FOUND` (404)
- `GRAPH_QUERY_FAILED` (502)
- `AGENT_TIMEOUT` (504)
- `EVIDENCE_REQUEST_FAILED` (400)
- `POLICY_VIOLATION` (403)
- `APPROVAL_REQUIRED` (403)
- `ACTION_NOT_PERMITTED` (403)
- `INVALID_APPROVAL` (403)
- `VALIDATION_ERROR` (422)
- `LLM_ERROR` (502)

---

## 20. Mock Action Contract

Simulation APIs implemented in `backend/services/mock_actions.py`:
- `mock_block_card(card_id: str, reason: str, case_id: str) -> Dict[str, Any]`
- `mock_decline_transaction(transaction_id: str, reason: str, case_id: str) -> Dict[str, Any]`
- `mock_freeze_account(account_id: str, reason: str, case_id: str) -> Dict[str, Any]`
- `mock_send_customer_message(customer_id: str, message: str, case_id: str) -> Dict[str, Any]`
- `mock_request_verification(customer_id: str, method: str, case_id: str) -> Dict[str, Any]`
- `mock_file_report(case_id: str, sar_payload: Dict[str, Any]) -> Dict[str, Any]`
- `mock_allow_transaction(transaction_id: str, case_id: str) -> Dict[str, Any]`

All return `{ "success": True, "action": "...", "case_id": "...", "timestamp": "...", "details": {...} }`.

---

## 21. Public Repository vs Private Information

- **Public Repository (`fraudgraph-ai/`)**: Contains application code (`frontend/`, `backend/`, `agent/`, `tigergraph/`, `graphrag/`, `data/`, `tests/`, `docs/`). Tracked by Git.
- **Private Information (`Information/`)**: Contains organizer challenge PDF, 67 MB dataset zip (`transactions.csv`, `identity.csv`, `closed_cases_history.csv`, `case_pack.csv`), PRD, and Integration Spec. **Ignored in `.gitignore` (`Information/`), 0 files tracked in Git, strictly local-only.**

---

## 22. P0 / P1 / P2 Scope

| Priority | Features | Status |
| :--- | :--- | :--- |
| **P0 (Must Work)** | Case trigger, graph investigation, fraud patterns, evidence management, risk/confidence/uncertainty, GraphRAG policy context, additional evidence requests & reassessment, next best action (initial & final), policy enforcement (R1–R10), explainability, case timeline, case memory persistence, 20 benchmark case evaluation runner. | Person 1 Target |
| **P1 (Important)** | Human approval UI integration, mock action execution APIs, analyst dashboard API, SAR report generation when required, graph visualization API adapters. | Person 1 Target |
| **P2 (Nice to have)**| Advanced multi-agent expansions, voice interface, complex external webhook integrations. | Post-Hackathon |

---

## 23. Known Conflicts

1. **Policy Threshold Conflict (Level 1 vs Level 3)**:
   - Level 1 defines approval routing at $\le \$2,500$ (L1) vs $> \$2,500$ (L2) and SAR at $> \$1,000$.
   - Level 3 (`mock_provider.py`) defines approval routing at $\ge \$5,000$ (FinCEN BSA rule).
   - **Resolution**: Level 1 governs benchmark scoring. Person 1's policy engine implements Level 1 rules (R1–R10, $2,500 block threshold, $1,000 report threshold) while accepting Person 2's `PolicyContextResponse`.
2. **API Endpoint Path Conflict (Level 4/5 vs Shorthand)**:
   - Level 4 (Person 3 frontend) calls `/api/investigations`, `/api/cases/{id}`, `/api/cases/{id}/action`, etc.
   - Level 7 suggested shorthand `/api/investigate`, `/api/cases/{id}/approve`.
   - **Resolution**: Level 4/5 takes precedence. Person 1 will implement the exact Level 4 endpoints and provide backward-compatible aliases for shorthand endpoints.
3. **Dataset Scale (Level 1 vs Level 3)**:
   - Level 1 master dataset has 590,742 transactions.
   - Level 3 repository sample has 37 transactions.
   - **Resolution**: Both are supported. Local unit tests run against 37-row sample; benchmark evaluation runner reads `Information/drive-download-20260923T192514Z-1-001.zip` (or unzipped files) to process the 20 benchmark cases (`HHG-001` to `HHG-020`).

---

## 24. Known Limitations

1. **Customer / Analyst Interactions**: In the hackathon evaluation, customer and analyst replies are simulated rather than real-time interactive chats. The agent must state its assumptions in `evidence_requests`.
2. **Offline Mock Mode**: By default, Person 2 runs against `mock_provider.py` with deterministic fixtures so the system can run without an active TigerGraph cluster. Live cluster execution is opt-in via `USE_MOCK_GRAPH=false`.
3. **Python 3.14 Environment**: Because the local runtime is Python 3.14.7 without external LangGraph packages installed, Person 1 implements a typed, pure-Python workflow engine that matches LangGraph semantics exactly.

---

## 25. Unresolved Questions

1. **Cluster Loading of Master Dataset**: Will Person 2 load all 590,742 rows into TigerGraph Savanna Cloud for the final demo video, or demonstrate using the representative seeded dataset? (Handled cleanly: both modes use the exact same tool signatures).
2. **Analyst UI Action Confirmation**: Person 3's frontend sends `{ action: string, approved: boolean }` to `/api/cases/{id}/action`. Person 1's backend will validate this against server-side policy and generate the required audit token.

---

## 26. Person 1 Implementation Starting Point

When the user issues the **Person 1 BUILD** instruction, implementation will proceed in this exact sequence:

1. **Domain Models (`backend/models/`)**:
   - `schemas.py`: Pydantic models for `InvestigationCase`, `Evidence`, `FraudPattern`, `Recommendation`, `TimelineEvent`, `NextBestActions`, `SARReport`, `ApprovalSubmission`, matching Level 1 and Level 4.
   - `audit.py`: Structured security audit logger.
2. **Agent Tool Adapters (`agent/tools/`)**:
   - `graph_adapter.py`: Direct in-process adapter wrapping `tigergraph.tools.get_graph_tools()` and `graphrag.pipeline.retrieve_investigation_context`.
3. **Agent State & Reasoning (`agent/workflows/` & `agent/reasoning/`)**:
   - `state.py`: Typed `AgentState` schema.
   - `risk_engine.py`: Distinguishes `risk_score`, `fraud_probability`, `confidence`, and `uncertainty`.
   - `nba_engine.py`: Implements two-stage Next Best Action generation (initial vs final) and `what_changed`.
   - `workflow.py`: Typed state machine executing the 10-stage investigation loop.
4. **Policy & HITL Engine (`backend/policy/`)**:
   - `policy_engine.py`: Enforces Rules R1–R10, $2,500 L1/L2 boundary, $1,000 report boundary, and HMAC-signed approval token validation.
5. **Mock Remediation Services (`backend/services/`)**:
   - `mock_actions.py`: Simulation handlers for card blocking, account freezing, customer messaging, step-up auth, and SAR filing.
6. **FastAPI Application (`backend/api/`)**:
   - `errors.py`: Unified Section 9 error handler.
   - `routes.py`: Implements all Person 3 endpoints (`/api/investigations`, `/api/cases/{id}`, `/api/cases/{id}/investigation`, `/api/cases/{id}/evidence-request`, `/api/cases/{id}/evidence`, `/api/cases/{id}/recommendation`, `/api/cases/{id}/action`) plus diagnostic aliases.
   - `app.py`: FastAPI application factory with security headers and CORS.
7. **Benchmark Evaluation Runner (`scripts/run_benchmark_eval.py`)**:
   - Reads `case_pack.csv`, runs the investigation agent across all 20 cases (`HHG-001` through `HHG-020`), and generates official submission JSON answer files in the exact Level 1 format.
8. **Tests & Security Suite (`tests/`)**:
   - `test_agent_foundation.py`: Full unit test coverage.
   - `test_security_baseline.py`: 20 mandatory security test cases verifying fail-closed controls.
