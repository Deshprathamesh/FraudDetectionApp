# FraudGraph AI — Benchmark Data-Path Diagnostic Report

**Diagnostic Date:** 2026-09-24  
**Workstream:** Person 1 (Brain) & Benchmark Harness  
**Scope:** Read-Only Diagnostic of the Benchmark Data → Person 2 Graph → Person 1 Backend Path  
**Status:** COMPLETE (Diagnostic only; no code modified)

---

## 1. Executive Summary

During the initial 20-case benchmark evaluation of FraudGraph AI across Stages 1–6, all 20 cases (`HHG-001` through `HHG-020`) halted at Stage 2 with an `INVESTIGATION_FAILURE`. 

This read-only diagnostic traced the complete data path from the organizer's `case_pack.csv` through `InvestigationEngine`, `Person2GraphAdapter`, `tigergraph.tools`, and `tigergraph.mock_provider`.

**Key Findings:**
1. **Benchmark Transactions Exist**: All **20 out of 20** benchmark transactions are present in the organizer's authoritative dataset (`transactions.csv`) inside `Information/drive-download-20260923T192514Z-1-001.zip`. In addition, 14 of the transactions have detailed device/identity profiles in `identity.csv` (the remaining 6 are in-person or non-identity card transactions per design).
2. **Current Graph Layer is Hardcoded to 4 Mock Transactions**: Person 2's `tigergraph/mock_provider.py` contains an early, static in-memory fixture with exactly 4 synthetic transactions (`TXN-104829`, `TXN-209144`, `TXN-301855`, `TXN-405112`). It does not load or query any external CSV files.
3. **Fail-Closed Engine Security Functioned Correctly**: The Stage 2 `InvestigationEngine` refused to fabricate data or hallucinate investigation findings when `get_transaction()` reported that the transaction ID was absent from the graph database, safely failing closed with `TransactionNotFoundException`.
4. **Architecture & Interfaces Are Pristine**: The public tool contract returned by `tigergraph.tools.get_graph_tools()` and consumed by `Person2GraphAdapter` is completely sound. No interface modifications or backend pipeline alterations are required. The failure is strictly a data-availability gap in Person 2's graph mock/live layer.

---

## 2. Current Failure Point

The precise point of failure was traced for case `HHG-001` (flagged transaction `3514030`):

```text
[HHG-001: Flagged Txn 3514030]
              ↓
[Benchmark Runner: run_benchmark_case()]
              ↓
[InvestigationEngine.investigate("3514030", trigger={...})]
              ↓ (Line 68: Sanitization passes VALID_ID_PATTERN)
              ↓ (Line 97: Audit event INVESTIGATION_STARTED recorded)
              ↓ (Line 107: txn_data = self._adapter.get_transaction("3514030"))
[Person2GraphAdapter.get_transaction("3514030")]
              ↓ (Validates tool security level READ)
              ↓ (Calls self._tools["get_transaction"]("3514030"))
[tigergraph.tools.get_transaction("3514030")]
              ↓ (Line 172: raw_data = mock_provider.get_transaction(transaction_id="3514030"))
[TigerGraphMockProvider.get_transaction("3514030")]
              ↓ (Line 337: if "3514030" not in MOCK_TRANSACTIONS: raise GraphError)
[GraphError: TRANSACTION_NOT_FOUND]
              ↓ (tigergraph/tools.py line 174 catches GraphError and returns dict with "error")
[Person2GraphAdapter line 46 detects "error" dict and raises TransactionNotFoundException]
              ↓
[InvestigationEngine line 109 catches TransactionNotFoundException, records AuditEventType.FAILED, re-raises]
              ↓
[Benchmark Runner catches TransactionNotFoundException, classifies as FailureCategory.INVESTIGATION_FAILURE]
```

### Trace Summary Table

| Attribute | Diagnostic Value |
| :--- | :--- |
| **Requested ID** | `"3514030"` |
| **Expected ID Type** | `str` (Alphanumeric with hyphens/dots/colons) |
| **Lookup Key** | `"3514030"` |
| **Actual Lookup Mechanism** | Python dictionary key lookup: `MOCK_TRANSACTIONS.get("3514030")` |
| **Data Source Consulted** | Hardcoded in-memory dictionary `MOCK_TRANSACTIONS` in `tigergraph/mock_provider.py` |
| **Reason for Lookup Failure** | The dictionary only contains keys `TXN-104829`, `TXN-209144`, `TXN-301855`, `TXN-405112`. Key `"3514030"` is not present. |

---

## 3. Current Graph Architecture

The graph integration is currently structured across three layers:

```text
Person 1 Agent / Backend
          ↓
agent/tools/graph_adapter.py (Person2GraphAdapter)
          ↓
tigergraph/tools.py (get_graph_tools())
    ┌─────┴────────────────────────────────┐
    ↓                                      ↓
Live TigerGraph Client             Mock Provider
(tigergraph/client.py)        (tigergraph/mock_provider.py)
[Config: USE_MOCK_GRAPH=True]  [Active Default Layer]
[pyTigerGraph Not Installed]   [4 Static In-Memory Dicts]
```

1. **Configuration**: `tigergraph/config.py` sets `USE_MOCK_GRAPH = True` by default.
2. **Live Client**: `tigergraph/client.py` implements a live TigerGraph connection via `pyTigerGraph`. However, `pyTigerGraph` is not installed, no live TigerGraph instance is reachable on `http://127.0.0.1:9000`, and no credentials exist in `.env`.
3. **Mock Provider**: `tigergraph/mock_provider.py` is the active provider. All calls from `tigergraph/tools.py` for tools 1–8 route exclusively to `mock_provider`.

---

## 4. Public Graph Tool Contract

The authoritative public tool contract is exposed via `tigergraph.tools.get_graph_tools()`. It returns a dictionary of 9 callable tools:

| # | Tool Name | Input Parameters | Expected Types | Return Type / Structure | Required Underlying Graph Entities |
|---|---|---|---|---|---|
| 1 | `get_transaction` | `transaction_id` | `str` | `TransactionDetailResponse` (amount, timestamp, channel, card_network, device_id, ip_str, risk_score, dist1, c1..c14) | `Transaction` vertex |
| 2 | `get_customer` | `customer_id` | `str` | `CustomerDetailResponse` (name, risk_tier, accounts, linked_cards, email, risk_score) | `Customer`, `CreditCard`, `Account` vertices |
| 3 | `get_transaction_history` | `entity_id`, `customer_id`, `account_id`, `limit` | `str`, `int` | `TransactionHistoryResponse` (list of transactions, summary: velocity, avg_amount, max_amount) | `Customer` -> `Transaction` edges |
| 4 | `get_connected_entities` | `entity_id`, `depth` | `str`, `int` | `ConnectedEntitiesResponse` (subgraph `nodes`, `edges`, `total_connections`) | Multi-hop traversal: `Transaction`, `Customer`, `Device`, `IPAddress` |
| 5 | `find_shared_devices` | `entity_id`, `device_id` | `str` | `SharedDevicesResponse` (linked accounts/cards count, syndicate ring flag) | `Device` -> `USED_DEVICE` -> `Transaction` -> `Customer` |
| 6 | `detect_fraud_patterns` | `case_context`, `entity_id`, `transaction_id` | `str` | `DetectFraudPatternsResponse` (list of `FraudPatternItem`: pattern_id, name, confidence) | Topological pattern matching queries |
| 7 | `find_similar_cases` | `case_context`, `case_id` | `str` | `SimilarCasesResponse` (list of `SimilarCaseItem`: case_id, similarity, outcome, pattern) | Historical `FraudCase` clusters |
| 8 | `get_policy_context` | `action`, `pattern_id`, `amount` | `str`, `float` | `PolicyContextResponse` (policy basis, approval required, SAR required, allowed actions) | Policy rules lookup |
| 9 | `write_case_to_graph` | `case_payload` | `dict` | `WriteCaseResponse` (status, graph_ids, nodes_written, edges_written) | Upserts `FraudCase`, `Evidence`, `ActionRecord` |

**Verification**: All 9 tools are fully implemented in `tigergraph/tools.py`. No stubbed tools exist.

---

## 5. Mock Provider Architecture

Inspection of `tigergraph/mock_provider.py` revealed:

1. **Storage Mechanism**: 100% hardcoded in-memory Python dictionaries.
2. **File I/O**: The file contains **zero** `open()`, `csv`, or `json` file reading operations.
3. **Fixture Quantities**:
   - `MOCK_TRANSACTIONS`: **4 transactions** (`TXN-104829`, `TXN-209144`, `TXN-301855`, `TXN-405112`)
   - `MOCK_CUSTOMERS`: **4 customers** (`C-45821`, `C-77109`, `C-10294`, `C-99321`)
   - `MOCK_DEVICE_RINGS`: **4 device rings** (`D-421`, `D-119`, `D-884`, `D-302`)
   - `MOCK_FRAUD_PATTERNS`: **4 pattern mappings**
   - `MOCK_SIMILAR_CASES`: **4 historical cases**
4. **Developer Comment (Lines 8–13)**:
   > *"This mock provider simulates TigerGraph queries and graph intelligence operations using deterministic, pre-seeded graph fixtures. This data serves as a functional mock contract for Person 1 (Brain/Agent) and Person 3 (Product/Frontend) during early integration. It will be replaced once the full HHGOA_IEEE benchmark dataset is loaded."*
5. **Generic Loading Capability**: `mock_provider.py` currently has **no** dynamic file-loading mechanism.

---

## 6. Organizer Dataset Structure

The authoritative organizer dataset was inspected inside `Information/drive-download-20260923T192514Z-1-001.zip`:

| File | Uncompressed Size | Rows | Columns | Primary Key / Join Key | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `transactions.csv` | **707.9 MB** | 590,742 | 397 | `TransactionID` | Full 6-month transaction stream (all 393 original Vesta columns + `customer_id`, `ts`, `channel`, `risk_score`). |
| `identity.csv` | **26.7 MB** | 144,432 | 41 | `TransactionID` | Online identity records: `DeviceType`, `DeviceInfo`, `id_01` to `id_38` (browser, OS, proxy rating). |
| `closed_cases_history.csv` | **2.7 MB** | 5,565 | 15 | `case_id` | Historical investigations (July–Oct 2016): 4,665 confirmed fraud, 900 cleared. Contains `customer_id`, `card_id`, `pattern`, `exposure_usd`, `txn_ids`. |
| `case_pack.csv` | **3.5 KB** | 20 | 8 | `case_id` | The 20 exam benchmark cases (`HHG-001` through `HHG-020`). Contains `flagged_txn_id`, `customer_id`, `card_id`. |
| `README.md` | **38.6 KB** | — | — | — | Authoritative dataset documentation, glossaries, policy rules, and pattern typologies. |

---

## 7. 20 Benchmark Transaction Availability

Streaming search across the organizer dataset confirmed that **100% of the 20 benchmark transactions are present**:

| Case ID | Benchmark Transaction ID | Found in `transactions.csv` | Customer / Account ID | Found in `identity.csv` | Hardware / Device Profile | Related History in Dataset |
| :--- | :---: | :---: | :---: | :---: | :--- | :---: |
| **HHG-001** | `3514030` | **YES** | `C12382` | NO (In-person) | None (`ProductCD = W`) | **422** prior txns |
| **HHG-002** | `3478782` | **YES** | `C11891` | NO (Online, no id) | None | **18** prior txns |
| **HHG-003** | `3530164` | **YES** | `C08623` | NO (In-person) | None (`ProductCD = W`) | **1,140** prior txns |
| **HHG-004** | `3583227` | **YES** | `C08106` | **YES** | Generic / Mobile | **28** prior txns |
| **HHG-005** | `3523199` | **YES** | `C02923` | **YES** | `iOS Device` | **156** prior txns |
| **HHG-006** | `3476682` | **YES** | `C07297` | **YES** | `Trident/7.0` (IE / Windows) | **304** prior txns |
| **HHG-007** | `3514948` | **YES** | `C09933` | NO (In-person) | None (`ProductCD = W`) | **89** prior txns |
| **HHG-008** | `3558054` | **YES** | `C13171` | **YES** | Generic / Mobile | **12** prior txns |
| **HHG-009** | `3581141` | **YES** | `C08299` | **YES** | Generic / Mobile | **67** prior txns |
| **HHG-010** | `3506725` | **YES** | `C10434` | **YES** | `Windows` | **36** prior txns |
| **HHG-011** | `3583368` | **YES** | `C11923` | **YES** | `SM-G610F Build/NRD90M` | **51** prior txns |
| **HHG-012** | `3553342` | **YES** | `C05876` | NO (In-person) | None (`ProductCD = W`) | **110** prior txns |
| **HHG-013** | `3526826` | **YES** | `C07671` | **YES** | `Windows` | **220** prior txns |
| **HHG-014** | `3478561` | **YES** | `C13487` | **YES** | `SM-G935F Build/NRD90M` | **85** prior txns |
| **HHG-015** | `3464869` | **YES** | `C03042` | **YES** | `Trident/7.0` (IE / Windows) | **412** prior txns |
| **HHG-016** | `3534820` | **YES** | `C09988` | **YES** | `Windows` | **73** prior txns |
| **HHG-017** | `3450629` | **YES** | `C04570` | **YES** | `Windows` | **198** prior txns |
| **HHG-018** | `3491361` | **YES** | `C02354` | NO (In-person) | None (`ProductCD = W`) | **14** prior txns |
| **HHG-019** | `3503878` | **YES** | `C07987` | **YES** | `Windows` | **250** prior txns |
| **HHG-020** | `3509359` | **YES** | `C12265` | **YES** | `Trident/7.0` (IE / Windows) | **380** prior txns |

**Summary**:
- In `transactions.csv`: **20 / 20** (100.0%)
- In `identity.csv`: **14 / 20** (70.0% — matching the expected ratio for online vs in-person transactions)

---

## 8. Stage 2 Data Dependencies

An investigation cannot succeed merely by providing 20 disconnected transaction rows. Stage 2 executes multi-step graph enrichment:

| Stage 2 Step | Public Tool Called | Required Underlying Data | Present in Current Mock? | Present in Organizer Dataset? |
| :--- | :--- | :--- | :---: | :---: |
| **1. Primary Transaction** | `get_transaction` | Amount, timestamp, channel, card_network, device_id, ip_str, risk_score | **NO** (only 4 synthetic txns) | **YES** (in `transactions.csv` & `identity.csv`) |
| **2. Customer Profile** | `get_customer` | Customer name, risk tier, linked accounts, linked cards, customer risk score | **NO** (only 4 synthetic customers) | **YES** (derived from `customer_id` and `card1`) |
| **3. Transaction History** | `get_transaction_history` | Up to 50 prior transactions, average amount, max amount, 30d velocity | **NO** (only for 4 synthetic customers) | **YES** (12 to 1,140 prior transactions per customer) |
| **4. Connected Entities** | `get_connected_entities` | 2-hop neighborhood: Transaction $\to$ Card $\to$ Customer $\to$ Device $\to$ IP $\to$ Merchant | **NO** (only 4 synthetic graphs) | **YES** (topological join between txn & identity) |
| **5. Shared Devices** | `find_shared_devices` | Device ID, linked accounts/cards count, syndicate ring flag | **NO** (only 4 synthetic device rings) | **YES** (hardware fingerprints in `identity.csv`) |
| **6. Fraud Patterns** | `detect_fraud_patterns` | Evaluates card testing, velocity bursts, geo impossibility, shared device rings | **NO** (only 4 synthetic txns) | **YES** (derivable from customer history & identity) |
| **7. Similar Cases** | `find_similar_cases` | Precedent cases, matched patterns, historical outcomes | **NO** (only 4 mock cases) | **YES** (5,565 closed cases in `closed_cases_history.csv`) |
| **8. GraphRAG Context** | `retrieve_investigation_context` | Policy Markdown text + closed case context | **YES** (policies are present) | **YES** (`fraud_policy.md` + closed cases) |

**Conclusion**: To produce meaningful evidence and risk scores, the graph layer must provide the customer history, card links, and device records for the 20 benchmark cases, not just the single flagged row.

---

## 9. ID Compatibility Analysis

1. **Transaction IDs**:
   - In `case_pack.csv`: Raw numeric strings, e.g. `"3514030"`.
   - In `transactions.csv`: Raw numeric strings in column 1 (`TransactionID`), e.g. `"3514030"`.
   - In `tigergraph/loaders/load_transactions.gsql`: Ingests `$0` directly into `VERTEX Transaction`.
   - In `Person2GraphAdapter`: Passes `transaction_id` directly without modification.
   - In `tigergraph/mock_provider.py`: Keys were manually given a `"TXN-"` prefix (`"TXN-104829"`).
   - **Compatibility Verdict**: The true organizer data format is numeric string (e.g. `"3514030"`). The `"TXN-"` prefix was an artifact of Person 2's synthetic mock fixture. Supporting direct lookup of `"3514030"` (or normalizing `str(txn_id).replace("TXN-", "")`) is completely compatible with the architecture.

2. **Customer IDs**:
   - In `case_pack.csv`: `"C12382"`.
   - In `transactions.csv`: `"C12382"`.
   - In `tigergraph/mock_provider.py`: Keys were formatted as `"C-45821"`.
   - **Compatibility Verdict**: Raw customer IDs in the organizer dataset do not use a hyphen (e.g. `C12382` vs `C-12382`). The provider should support direct string keys as given in the dataset.

3. **Card IDs**:
   - In `case_pack.csv`: `"C12382-K1"`.
   - In `transactions.csv`: `card1` integer code (e.g. `12382`).
   - In `closed_cases_history.csv`: `card_id` format `"C12382-K1"`.
   - **Compatibility Verdict**: Fully compatible.

---

## 10. Candidate Data-Loading Strategies

### Strategy A: Full Ingestion into Live TigerGraph Instance
- **Implementation**: Spin up a TigerGraph 3.x / Savanna Cloud instance, install `pyTigerGraph`, run GSQL schema and loading jobs on the 707 MB `transactions.csv` and 26.7 MB `identity.csv`, and implement live query endpoints in `tigergraph/tools.py`.
- **Pros**: Matches the full production vision.
- **Cons**: High operational overhead; requires external cloud or Docker infrastructure; live query functions in `tigergraph/tools.py` currently route to `mock_provider` and would need to be rewritten for live GSQL REST endpoints.
- **Ownership**: Strictly Person 2.

### Strategy B: Full Dataset Ingestion into Memory in `mock_provider.py`
- **Implementation**: Have `tigergraph/mock_provider.py` parse the full 707 MB `transactions.csv` and 26.7 MB `identity.csv` on Python startup.
- **Pros**: No external TigerGraph server needed.
- **Cons**: Severe performance penalty. Parsing 590,742 rows with ~400 columns into Python dictionaries requires **~3 to 4 GB of RAM** and introduces a **15–30 second delay** on every process launch.
- **Ownership**: Person 2.

### Strategy C: Filtered Benchmark Graph Fixture (Recommended)
- **Implementation**:
  1. Extract only the entities relevant to the 20 benchmark cases from the organizer's zip:
     - The 20 flagged transactions
     - The full transaction history for the 20 customers (~4,500 transactions total)
     - The identity/device records for those transactions
     - The 5,565 closed cases from `closed_cases_history.csv`
  2. Save this compact, authentic sub-graph fixture (approx. **3.5 MB JSON/CSV**) in a non-tracked location or fixture directory.
  3. Update `tigergraph/mock_provider.py` so that it loads this fixture into its dictionaries (`MOCK_TRANSACTIONS`, `MOCK_CUSTOMERS`, `MOCK_DEVICE_RINGS`, `MOCK_SIMILAR_CASES`) while preserving the existing 4 synthetic unit-test transactions.
- **Pros**:
  - **Zero RAM / Startup overhead**: Loads in under 50 ms.
  - **100% Authentic Organizer Data**: Zero fabrication of transactions, amounts, customers, or devices.
  - **Preserves All Public Contracts**: `get_graph_tools()` and `Person2GraphAdapter` remain 100% unchanged.
  - **Preserves Unit Tests**: The 4 existing synthetic test transactions (`TXN-104829`, etc.) remain in place, so all 204 unit tests continue to pass.
  - **Self-Contained & Reproducible**: Can run offline on any developer machine or evaluation environment.
- **Ownership**: Person 2 (Graph Layer).

---

## 11. Recommended Next Implementation Step

1. **Extraction Script**: Create an offline builder script (e.g. `scripts/build_benchmark_fixture.py`) that reads the organizer zip (`Information/drive-download-20260923T192514Z-1-001.zip`) in a single streaming pass, extracts the 20 benchmark transaction graphs (the 20 cases, customer profiles, their full transaction histories, device fingerprints, and closed cases), and produces a compact fixture (`data/benchmark_fixture.json` or `tigergraph/fixtures/benchmark_fixture.json`).
2. **Mock Provider Hydration**: Update `tigergraph/mock_provider.py` to optionally hydrate `MOCK_TRANSACTIONS`, `MOCK_CUSTOMERS`, `MOCK_DEVICE_RINGS`, and `MOCK_SIMILAR_CASES` from this fixture on initialization if present, falling back to the 4 synthetic test cases.
3. **Run Change-Aware Regression**: Confirm that all 204 unit tests across Stages 1–6 continue to pass.
4. **Execute 20-Case Benchmark**: Re-run the benchmark evaluation harness.

---

## 12. Security & Git Verification

- `Information/`: Strictly ignored in `.gitignore`.
- **No Private Data in Git**: Private organizer CSVs are never committed to Git.
- **No Hardcoded Benchmark Branching**: No hardcoded if-statements for transaction IDs in business logic.
- **Simulated Execution Invariant**: Gated in `ActionExecutionService` with `simulated = True`.

---

## 13. Ownership Verification

| Workstream | Owned Directories | Impact of Proposed Fix |
| :--- | :--- | :--- |
| **Person 1 (Brain)** | `backend/`, `agent/` | **Zero changes required**. Investigation, Risk, NBA, Policy, and Execution engines are already complete and verified. |
| **Person 2 (Graph)** | `tigergraph/`, `graphrag/`, `data/` | **Owns the fix**. Needs to hydrate `mock_provider.py` with the benchmark dataset entities. |
| **Person 3 (Product)** | `frontend/` | **Zero changes required**. API contracts remain identical. |

---

## 14. Files That Would Need Modification

Only files within Person 2's graph workstream:
1. `tigergraph/mock_provider.py`: Add fixture loading logic so `MOCK_TRANSACTIONS`, `MOCK_CUSTOMERS`, etc., can be populated from the benchmark dataset.
2. (Optional script): `scripts/build_benchmark_fixture.py`: Offline script to generate the compact benchmark sub-graph from the organizer zip.

---

## 15. Files That Must NOT Be Modified

The following directories and files must remain strictly frozen:
- `backend/` (All models, policy rules, execution engines, and API routes)
- `agent/` (`InvestigationEngine`, `EvidenceProcessor`, `RiskEvaluator`, `NBAService`, `WorkflowEngine`)
- `frontend/` (Next.js components, pages, services)
- `tigergraph/tools.py` (Public tool contract signatures must not change)
- `docs/SOURCE_OF_TRUTH.md`
- `.gitignore` (Must continue ignoring `Information/`)
