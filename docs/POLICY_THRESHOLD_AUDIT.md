# Policy Threshold Audit

**Audit Date**: September 24, 2026  
**Auditor**: Person 1 (Brain / Agent & Backend Lead)  
**Target Subject**: The `5000` / `5000.0` / `$5,000 USD` Monetary Policy Threshold & Currency Dependencies  
**Scope**: Entire repository (`tigergraph/`, `graphrag/`, `data/`, `tests/`, `scripts/`, `docs/`, `backend/`, `agent/`)

---

## 1. Executive Summary

An exhaustive repository-wide audit was conducted to identify every reference to the monetary policy threshold `5000` (`5000.0`, `5000.00`, `$5,000`, `$5,000.00 USD`), the currency `USD`, and associated policy gates (`approval_required`, `sar_required`, `FREEZE_ACCOUNT`).

### Key Findings:
1. **Source of Truth**: The threshold originates from federal banking regulations—specifically the **U.S. Bank Secrecy Act (BSA)** and **FinCEN Regulations (31 CFR § 1020.320)**, which establish a mandatory Suspicious Activity Report (SAR) filing threshold of **$5,000.00 USD** for suspicious transactions with an identified subject.
2. **Person 2 Implementation**: Person 2 has **already implemented** this threshold across multiple core components:
   - Hardcoded in `tigergraph/mock_provider.py` (`amount >= 5000.0` triggers `approval_required = True`, `sar_required = True`, and clause `POL-804`).
   - Hardcoded in `graphrag/retrieval/policy_retriever.py` (`amount >= 5000.0` triggers `POL-804` override).
   - Hardcoded in GSQL query `tigergraph/queries/detect_velocity_abuse.gsql` (`@@total_volume >= 5000.0`).
   - Formally specified in `graphrag/documents/policies/fraud_policy.md` (`POL-FRAUD-2026-V1`).
   - Recorded in case precedent fixture `graphrag/documents/cases/historical_cases.json` (`CASE-0773`).
3. **Benchmark Test Dependencies**: The 4 benchmark personas (`TXN-104829`, `TXN-209144`, `TXN-301855`, `TXN-405112`) are deliberately calibrated against this exact $5,000 USD boundary:
   - `TXN-301855` is **$8,450.00 USD** (intentionally above $5,000 to trigger mandatory HITL approval + SAR).
   - `TXN-104829` is **$1,249.50 USD** (intentionally below $5,000 to verify automated blocking without HITL).
4. **Existing Test Suite**: The automated test suite `tests/test_graph_tools.py` and verification scripts `scripts/verify_prompt24.py` and `scripts/verify_graphrag.py` **explicitly assert** that amounts $\ge \$5,000$ trigger `POL-804`, `approval_required = True`, and `sar_required = True`, while sub-$5,000 amounts do not.
5. **Currency Consistency**: The dataset, loaders, schemas, and Pydantic models are **100% USD**. There is zero mention of INR, Rupee, or foreign exchange logic in the repository.
6. **Verdict**: **SAFE TO CHANGE: NO**. Unilaterally modifying or replacing this threshold in Person 1 would create an immediate contract mismatch with Person 2, break existing tests, violate FinCEN SAR regulatory rules in the policy documents, and fail benchmark evaluations.

---

## 2. All 5000 References

The following table documents every functional, documentation, and fixture reference to the `5000` monetary threshold and associated policy rules across the repository:

| File | Line | Value | Category | Purpose | Dependency |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `tigergraph/mock_provider.py` | 580 | `amount >= 5000.0` | **B** (Person 2 implementation) | Triggers secondary supervisor approval and SAR filing obligation | Consumed by Tool 8 `get_policy_context` |
| `tigergraph/mock_provider.py` | 583 | `$5,000` | **B** (Person 2 implementation) | Policy basis explanation text citing `Bank Policy POL-804` | Returned in `PolicyContextResponse.policy_basis` |
| `graphrag/retrieval/policy_retriever.py` | 55 | `$5,000` | **B** (Person 2 implementation) | Chunk text for clause `POL-402` (automated block permitted under $5,000) | Vector embedding retrieval index |
| `graphrag/retrieval/policy_retriever.py` | 73 | `$5,000.00 USD` | **B** (Person 2 implementation) | Chunk text for clause `POL-804` (high-value mandatory approval) | Vector embedding retrieval index |
| `graphrag/retrieval/policy_retriever.py` | 82 | `$5,000` | **B** (Person 2 implementation) | Chunk text for clause `POL-901` (FinCEN BSA mandatory SAR filing threshold) | Vector embedding retrieval index |
| `graphrag/retrieval/policy_retriever.py` | 122 | `amount >= 5000.0` | **B** (Person 2 implementation) | Context enrichment logic adding high-value transfer flag to query | Query embedding synthesis |
| `graphrag/retrieval/policy_retriever.py` | 138 | `amount >= 5000.0` | **B** (Person 2 implementation) | Regulatory hierarchy override forcing `POL-804`, `approval_required=True`, `sar_required=True` | Consumed by `GraphRAGPipeline` & Agent |
| `graphrag/retrieval/policy_retriever.py` | 144 | `$5,000.00` | **B** (Person 2 implementation) | Formatted basis explanation string citing threshold | Returned in `PolicyContextResponse.policy_basis` |
| `graphrag/retrieval/policy_retriever.py` | 162 | `$5,000` | **B** (Person 2 implementation) | Basis explanation string citing automated block limit | Returned in `PolicyContextResponse.policy_basis` |
| `tigergraph/queries/detect_velocity_abuse.gsql` | 23 | `@@total_volume >= 5000.0` | **B** (Person 2 implementation) | GSQL query logic detecting velocity abuse if total volume exceeds 5000 | TigerGraph compiled query output |
| `graphrag/documents/policies/fraud_policy.md` | 28 | `< $5,000` | **E** (Policy configuration) | Section 2.1 rule: Automated block permitted for transactions under $5,000 | Bank enterprise policy specification |
| `graphrag/documents/policies/fraud_policy.md` | 29 | `≥ $5,000` | **E** (Policy configuration) | Section 2.1 rule: Mandatory L2 human analyst approval required prior to action | Bank enterprise policy specification |
| `graphrag/documents/policies/fraud_policy.md` | 34 | `≥ $5,000` | **E** (Policy configuration) | Escalation criteria for analyst review | Bank enterprise policy specification |
| `graphrag/documents/policies/fraud_policy.md` | 41 | `$5,000.00 USD` | **E** (Policy configuration) | Section 3.1: Secondary approval threshold definition | Bank enterprise policy specification |
| `graphrag/documents/policies/fraud_policy.md` | 42 | `$5,000` | **E** (Policy configuration) | Governance rule: Automated agents strictly prohibited from unilateral action | Bank enterprise policy specification |
| `graphrag/documents/policies/fraud_policy.md` | 52 | `$5,000 or more` | **E** (Policy configuration) | FinCEN 31 CFR § 1020.320 BSA statutory threshold for identified subject SAR | Bank enterprise policy specification |
| `graphrag/documents/typologies/known_patterns.md` | 52 | `≥ $5,000` | **A** (Challenge spec / docs) | FinCEN BSA rule: Mandatory SAR filing for fund transfers aggregating ≥ $5,000 | Typology reference guide |
| `graphrag/documents/typologies/known_patterns.md` | 68 | `> $5,000` | **A** (Challenge spec / docs) | Geo-velocity anomaly rule: Block if transfer > $5,000 | Typology reference guide |
| `graphrag/documents/cases/historical_cases.json` | 109 | `> $5,000` | **D** (Benchmark/test fixture) | Historical case `CASE-0773` policy basis text | Precedent retrieval match for mule cases |
| `graphrag/documents/cases/historical_cases.json` | 116 | `> $5,000` | **D** (Benchmark/test fixture) | Historical case `CASE-0773` timeline summary | Precedent retrieval match for mule cases |
| `tests/test_graph_tools.py` | 472 | `amount=8450.00` | **D** (Benchmark/test fixture) | Test input using benchmark `TXN-301855` amount to assert approval & SAR | Direct assertion on `res_high.approval_required is True` |
| `tests/test_graph_tools.py` | 475 | `POL-804` | **D** (Benchmark/test fixture) | Asserts that high-value amount triggers clause `POL-804` | Direct assertion on `res_high.policy_basis` |
| `tests/test_graph_tools.py` | 481 | `sub-$5000 block` | **D** (Benchmark/test fixture) | Test comment distinguishing sub-$5000 behavior | Code documentation |
| `tests/test_graph_tools.py` | 482 | `amount=1249.50` | **D** (Benchmark/test fixture) | Test input using benchmark `TXN-104829` amount to assert sub-threshold bypass | Direct assertion on `res_low.approval_required is False` |
| `scripts/verify_prompt24.py` | 139 | `amount=8500.0` | **D** (Benchmark/test fixture) | Verification test calling `rag_get_policy_context` with high-value amount | Asserts `policy_res.policy_id == 'POL-804'` |
| `scripts/verify_prompt24.py` | 150 | `$5,000` | **D** (Benchmark/test fixture) | Assertion message: *"High-risk wire over $5,000 must require approval"* | Direct assertion on `policy_res.approval_required is True` |
| `scripts/verify_prompt24.py` | 151 | `$5,000` | **D** (Benchmark/test fixture) | Assertion message: *"High-risk wire over $5,000 must require SAR filing"* | Direct assertion on `policy_res.sar_required is True` |
| `scripts/verify_graphrag.py` | 34 | `amount: 8450.00` | **D** (Benchmark/test fixture) | Scenario 2 high-value wire input testing `POL-804` retrieval | Asserts `pol_res.policy_id == 'POL-804'` |
| `data/transactions.csv` | 13 | `4900.0` | **I** (Dataset value) | Transfer `TXN-700001` structured intentionally just below $5,000 | AML structuring pattern detection |
| `data/transactions.csv` | 14 | `4850.0` | **I** (Dataset value) | Transfer `TXN-700002` structured intentionally just below $5,000 | AML structuring pattern detection |
| `data/transactions.csv` | 15 | `4950.0` | **I** (Dataset value) | Transfer `TXN-700003` structured intentionally just below $5,000 | AML structuring pattern detection |
| `docs/PERSON2_INTEGRATION_RECON.md` | 297 | `$\ge \$5,000$` | **A** (Challenge spec / docs) | Documenting Person 2's regulatory hierarchy override | Reconnaissance documentation |
| `docs/PERSON2_INTEGRATION_RECON.md` | 299 | `< $5,000` | **A** (Challenge spec / docs) | Documenting Person 2's automated block mapping | Reconnaissance documentation |

---

## 3. Actual Source of the Threshold

The `$5,000` threshold is **NOT an arbitrary application parameter**. It is grounded directly in federal banking law and compliance policy:

1. **FinCEN Bank Secrecy Act (BSA) Regulations (31 CFR § 1020.320)**:
   - Federal regulations mandate that depository institutions file a Suspicious Activity Report (SAR) with FinCEN for:
     > *"Any transaction conducted or attempted by, at, or through the bank and aggregating $5,000 or more, if the bank knows, suspects, or has reason to suspect that the transaction involves funds derived from illegal activities or is intended or conducted in order to disguise funds."*
   - This exact regulation is cited verbatim in `graphrag/documents/policies/fraud_policy.md` (Lines 4, 49–55).

2. **Enterprise Bank Fraud Policy `POL-FRAUD-2026-V1`**:
   - Authored by Person 2 in `graphrag/documents/policies/fraud_policy.md`.
   - Establishes two specific clauses:
     - **`POL-402` (Automated Transaction Blocking)**: Automated block permitted without analyst sign-off only if the transaction amount is strictly `< $5,000.00 USD`.
     - **`POL-804` (High-Value Transaction Secondary Approval)**: Any suspicious transaction or transfer $\ge \$5,000.00\text{ USD}$ requires mandatory L2 Human-in-the-Loop (HITL) supervisor approval and triggers mandatory evaluation for FinCEN SAR filing (`sar_required = True`).
     - **`POL-901` (BSA SAR Mandatory Filing)**: Specifically binds mule daisy-chain pattern `FP-03` aggregating $\ge \$5,000$ to mandatory SAR creation.

---

## 4. Person 2 Dependencies

### Person 2 Already Owns and Controls the Policy Context Layer
Person 2 has already implemented the policy evaluation logic in two distinct locations:

1. **`tigergraph/mock_provider.py` (Lines 570–605)**:
   ```python
   def get_policy_context(self, action: str, pattern_id: Optional[str] = None, amount: Optional[float] = None) -> Dict[str, Any]:
       clean_action = (action or "").strip().upper()
       approval_required = False
       sar_required = False
       ...
       if clean_action in ["FREEZE_ACCOUNT", "BLOCK_TRANSACTION"]:
           if amount and amount >= 5000.0:
               approval_required = True
               sar_required = True
               basis = "Bank Policy POL-804: Actions affecting balances over $5,000 require L2 Human-in-the-Loop approval and FinCEN SAR filing evaluation."
               confidence_threshold = 0.85
           else:
               basis = "Bank Policy POL-402: Automated block permitted for confirmed syndicate or velocity violations exceeding risk score 0.80."
               confidence_threshold = 0.80
   ```

2. **`graphrag/retrieval/policy_retriever.py` (Lines 137–145)**:
   ```python
   # 1. High-value transactions (>= $5,000) trigger POL-804 override
   if amount is not None and amount >= 5000.0:
       policy_id = "POL-804"
       approval_required = True
       sar_required = True
       confidence_threshold = 0.85
       allowed_actions = ["ESCALATE_TO_ANALYST", "FREEZE_ACCOUNT", "BLOCK_TRANSACTION"]
       basis_note = f"Bank Policy POL-804: High-value transaction (${amount:,.2f} >= $5,000.00 threshold) requires mandatory secondary supervisory approval and FinCEN SAR filing evaluation."
   ```

3. **GSQL Algorithmic Query `tigergraph/queries/detect_velocity_abuse.gsql` (Line 23)**:
   ```gsql
   (@@tx_count >= 3 AND @@total_volume >= 5000.0) AS velocity_abuse_detected;
   ```

### Exact Interface Person 1 Must Consume
Person 1 must **NOT** reimplement or hardcode independent threshold evaluation rules. Instead, Person 1 must consume Person 2's existing typed tool:

```python
from tigergraph.tools import get_policy_context, PolicyContextResponse

# Person 1 invocation:
policy_res: PolicyContextResponse = get_policy_context(
    action=recommended_action,
    amount=transaction_amount,
    pattern_id=detected_pattern_id,
    case_context=case_summary
)

# Output contract Person 1 consumes:
# policy_res.approval_required -> bool (True if amount >= 5000.0 or action in ['FREEZE_ACCOUNT'])
# policy_res.sar_required      -> bool (True if amount >= 5000.0 or pattern == 'FP-03')
# policy_res.confidence_threshold -> float (e.g. 0.85)
# policy_res.allowed_actions   -> List[str]
# policy_res.policy_id         -> str (e.g. "POL-804")
# policy_res.policy_basis      -> str
```

---

## 5. Benchmark Dependencies

The 4 seeded benchmark cases are calibrated specifically around the 5000 threshold:

| Case ID | Transaction ID | Amount | Currency | Fraud Patterns | Impact of 5000 Threshold | Expected Investigation Outcome |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Benchmark 1** | `TXN-104829` | **$1,249.50** | **USD** | `FP-01` (Syndicate), `FP-02` (Velocity) | **Below $5,000**: Does **NOT** require HITL approval or SAR. Automated block permitted (`POL-402`). | `BLOCK_TRANSACTION` executed automatically. State: `RESOLVED`. |
| **Benchmark 2** | `TXN-209144` | **$48.00** | **USD** | None (Clean baseline) | **Below $5,000**: Benign routine grocery purchase. Automated allow (`POL-101`). | `ALLOW_TRANSACTION` executed automatically. State: `RESOLVED`. |
| **Benchmark 3** | `TXN-301855` | **$8,450.00** | **USD** | `FP-03` (Mule Wire), `FP-04` (Tor Geo-Velocity) | **Above $5,000**: **MANDATORY HITL APPROVAL & MANDATORY SAR** (`POL-804` / `POL-901`). Automated block prohibited! | `FREEZE_ACCOUNT` + `FILE_SAR` halted at HITL gate. State: `AWAITING_APPROVAL`. |
| **Benchmark 4** | `TXN-405112` | **$310.00** | **USD** | `FP-05` (Card Testing Micro-Spurt) | **Below $5,000**: Moderate risk with elevated uncertainty. Pre-decision verification (`POL-201`). | `REQUEST_STEP_UP_AUTH` sent to user. State: `WAITING_FOR_EVIDENCE`. |

### Crucial Benchmark Observations:
1. `TXN-301855` ($8,450.00) is the **only high-value benchmark transaction**. It is designed specifically to test that the system halts before execution, demands an L2 human supervisor approval token, and generates a FinCEN SAR draft.
2. `TXN-104829` ($1,249.50) is designed to prove that high-risk syndicate attacks under $5,000 can be blocked automatically without human interruption.
3. In `data/transactions.csv`, rows 13–15 (`TXN-700001`, `TXN-700002`, `TXN-700003`) have amounts `$4,900.00`, `$4,850.00`, and `$4,950.00`. These amounts are textbook examples of **structuring / smurfing** deliberately placed just below the $5,000 FinCEN reporting threshold. Changing the threshold would invalidate the detection of this structuring typology.

---

## 6. Currency Findings

The repository is built strictly on **USD**:

1. **Pydantic Model Schema (`tigergraph/tools.py`, Line 27)**:
   ```python
   class TransactionDetailResponse(BaseModel):
       ...
       currency: str = "USD"
   ```
2. **Automated Unit Test (`tests/test_graph_tools.py`, Line 98)**:
   ```python
   assert res.currency == "USD"
   ```
   *Any change to currency causes this test to fail immediately.*
3. **TigerGraph GSQL Loading Job (`tigergraph/loaders/load_transactions.gsql`, Line 16)**:
   ```gsql
   LOAD file_trans TO VERTEX Transaction VALUES(
       $0, $1, "USD", $2, ...
   )
   ```
   *Every Transaction vertex loaded into TigerGraph has its `currency` attribute hardcoded to `"USD"`.*
4. **Mock Provider Fixtures (`tigergraph/mock_provider.py`)**:
   All 4 transactions (`TXN-104829`, `TXN-209144`, `TXN-301855`, `TXN-405112`) specify `"currency": "USD"`.
5. **Policy Documentation (`graphrag/documents/policies/fraud_policy.md`, Line 41)**:
   Explicitly defines: `**$5,000.00 USD**`.
6. **Presence of Other Currencies**:
   There is **ZERO** mention of INR, Rupee (₹), EUR, or multi-currency exchange rates anywhere in the repository.

---

## 7. Challenge Compatibility

Changing the threshold or currency would break compatibility with the evaluation harness and hackathon benchmarks:

1. **Contract Tests Would Break**:
   - `tests/test_graph_tools.py` Line 472:
     `res_high = tools["get_policy_context"](action="BLOCK_TRANSACTION", amount=8450.00)`
     `assert res_high.approval_required is True`
     `assert res_high.sar_required is True`
     `assert "POL-804" in res_high.policy_basis`
   - `tests/test_graph_tools.py` Line 482:
     `res_low = tools["get_policy_context"](action="BLOCK_TRANSACTION", amount=1249.50)`
     `assert res_low.approval_required is False`
     `assert res_low.sar_required is False`
2. **Prompt 24 Verification Script Would Break**:
   - `scripts/verify_prompt24.py` Line 139: tests `amount=8500.0` and asserts `policy_res.policy_id == "POL-804"`, `approval_required is True`, `sar_required is True`.
3. **GraphRAG Verification Script Would Break**:
   - `scripts/verify_graphrag.py` Scenario 2: expects `amount: 8450.00` to retrieve `POL-804`.
4. **SAR Evaluation Expectations**:
   - Benchmark evaluation scripts assessing SAR filing accuracy rely on FinCEN BSA 31 CFR § 1020.320 compliance. If the threshold were altered, the agent would either fail to file a required SAR or file an unprompted SAR.

---

## 8. Safe Change Strategy (Future Architecture)

If multi-currency or multi-jurisdictional support (e.g. INR / RBI guidelines) is required in a future phase, it must be introduced through an **isolated configuration layer** without breaking Person 2's contracts:

```text
┌─────────────────────────────────────────────────────────────┐
│                 Jurisdiction & Currency Config              │
│                                                             │
│  DEFAULT_JURISDICTION = "US_FINCEN"                         │
│  THRESHOLDS = {                                             │
│      "US_FINCEN": {"currency": "USD", "sar_amount": 5000.0}│
│      "IN_RBI":    {"currency": "INR", "sar_amount": 50000.0}│
│  }                                                          │
└──────────────────────────────┬──────────────────────────────┘
                               │
                Policy Engine Normalization Layer
                               │
┌──────────────────────────────▼──────────────────────────────┐
│  Converts incoming transaction currency to policy baseline  │
│  before querying Person 2's get_policy_context()            │
└─────────────────────────────────────────────────────────────┘
```

### Necessary Steps for Future Change (When Authorized):
1. **Never alter Person 2's `tigergraph/mock_provider.py` or `graphrag/retrieval/policy_retriever.py` directly**, as that breaks existing tests and Person 2 workstream ownership.
2. Introduce a `Currency` and `Jurisdiction` setting in `backend/policy/config.py` that defaults to `USD` / `5000.0`.
3. If an INR transaction arrives, normalize or evaluate it against an explicit jurisdiction rulebook rather than replacing the US FinCEN $5,000 threshold globally.
4. Update `tests/test_graph_tools.py` concurrently in coordination with Person 2.

---

## 9. Recommendation

1. **Keep the 5000.0 USD Threshold Exactly As-Is for Phase 1 Implementation**:
   - The threshold is not technical debt; it is a regulatory requirement (FinCEN 31 CFR § 1020.320) deeply embedded across Person 2's GSQL, Python tools, policy documents, vector embeddings, mock provider, and unit tests.
2. **Do Not Reimplement or Hardcode the Rule in Person 1**:
   - Person 1's backend/agent should **call Person 2's `get_policy_context(action=..., amount=...)`**.
   - Person 1's policy gate should inspect `policy_res.approval_required` and `policy_res.sar_required`.
   - By delegating threshold evaluation to Person 2's tool, Person 1 avoids duplicating logic and guarantees 100% contract alignment.

---

## Audit Verification Summary

**SAFE TO CHANGE: NO**

### FILES THAT WOULD NEED CHANGES (If Threshold or Currency Were Changed):
1. `tigergraph/mock_provider.py` (Lines 50, 80, 110, 140, 580, 583)
2. `tigergraph/tools.py` (Line 27)
3. `tigergraph/loaders/load_transactions.gsql` (Line 16)
4. `tigergraph/queries/detect_velocity_abuse.gsql` (Line 23)
5. `graphrag/retrieval/policy_retriever.py` (Lines 55, 73, 82, 122, 138, 144, 162)
6. `graphrag/documents/policies/fraud_policy.md` (Lines 28, 29, 34, 41, 42, 52)
7. `graphrag/documents/typologies/known_patterns.md` (Lines 52, 68)
8. `graphrag/documents/cases/historical_cases.json` (Lines 109, 116)
9. `tests/test_graph_tools.py` (Lines 98, 472, 475, 476, 477, 482, 484, 485)
10. `scripts/verify_prompt24.py` (Lines 139, 150, 151)
11. `scripts/verify_graphrag.py` (Lines 27, 34, 65)
12. `data/transactions.csv` (Lines 2, 4, 5, 13, 14, 15)

### FILES THAT MUST NOT BE CHANGED (To Protect Existing Person 2 Contracts & Tests):
1. `tigergraph/mock_provider.py`
2. `tigergraph/tools.py`
3. `tigergraph/loaders/load_transactions.gsql`
4. `tigergraph/queries/detect_velocity_abuse.gsql`
5. `graphrag/retrieval/policy_retriever.py`
6. `graphrag/documents/policies/fraud_policy.md`
7. `graphrag/documents/cases/historical_cases.json`
8. `tests/test_graph_tools.py`
9. `scripts/verify_prompt24.py`
10. `scripts/verify_graphrag.py`
11. `data/transactions.csv`
