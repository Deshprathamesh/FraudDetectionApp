# FraudGraph AI — Stage 5 Documentation

## Policy Compliance and Human-in-the-Loop (HITL) Gate

**Workstream:** Person 1 — Brain  
**Stage:** 5  
**Objective:** Deterministic Policy Compliance and Supervisory Approval Gating  
**Status:** COMPLETED & VERIFIED  

---

### 1. Stage 5 Objective

Stage 5 answers the operational and governance question:
> **"IS THE RECOMMENDED ACTION PERMITTED UNDER THE ORGANIZER POLICY, AND IF SO, WHO MUST APPROVE IT BEFORE EXECUTION?"**

Stage 5 consumes:
* `InvestigationResult` (Stage 2)
* `RiskAssessment` (Stage 3)
* `NextBestActionAssessment` (Stage 4)

and produces:
* `PolicyAssessment`
* `ApprovalRequest` (when supervisory approval is mandated)
* `HITLDecision` / `hitl_status`

---

### 2. Sole Policy Authority

The sole authoritative source governing Stage 5 policy decisions is the **organizer-defined policy** specified in Section 7 of `docs/SOURCE_OF_TRUTH.md`:
* **R1 through R10** are the exact binding operational rules.
* **Approval Routing Hierarchy**:
  - `BLOCK_CARD`: exposure $\le \$2,500.00 \to \text{L1\_SUPERVISOR}$; exposure $> \$2,500.00 \to \text{L2\_COMPLIANCE}$.
  - `BLOCK_ALL_CARDS`: always $\text{L2\_COMPLIANCE}$.
  - `FILE_REPORT`: always $\text{L2\_COMPLIANCE}$.
  - `DECLINE_TRANSACTION`: always $\text{L1\_SUPERVISOR}$.
  - All other canonical actions: $\text{AUTO}$.
* **Person 2 Reconciliation**: Person 2's descriptive context (e.g. mock FinCEN $\$5,000$ threshold) was inspected and verified to be non-binding context. In accordance with explicit instructions, no generic $\$5,000$ approval union or threshold was added.

---

### 3. Binding Rules R1 through R10 Implementation (`backend/policy/rules.py`)

All 10 organizer rules are deterministically evaluated by dedicated rule functions returning `PolicyRuleResult` (`rule_id`, `rule_name`, `status`, `reason`, `facts_evaluated`):

1. **Rule R1 (Verify before block on weak signal)**:
   - *Condition*: Investigation rests on a single signal (`signals_count <= 1`) and assessed fraud probability $< 0.70$.
   - *Constraint*: Blocking card (`BLOCK_CARD`, `BLOCK_ALL_CARDS`) is strictly a policy violation (`VIOLATED`).
   - *Permitted*: Requires `VERIFY_WITH_CUSTOMER` or `STEP_UP_AUTH` (`SATISFIED`).
   - *Exemption*: Does not trigger if multiple independent signals exist or confirmed credential compromise/account takeover is present.

2. **Rule R2 (Customer denies transaction)**:
   - *Condition*: Customer explicitly denies the transaction (unauthorized activity).
   - *Permitted*: `BLOCK_CARD` and `CREATE_CASE` are permitted (`SATISFIED`).
   - *Prohibited*: `ALLOW_TRANSACTION` and `CLOSE_NO_FRAUD` are prohibited (`VIOLATED`).
   - *Requirement*: `FILE_REPORT` permitted and required if exposure $> \$1,000.00$ or connected to a shared device/card compromise.

3. **Rule R3 (Customer confirms transaction)**:
   - *Condition*: Customer confirms the transaction as legitimate.
   - *Permitted*: `CLOSE_NO_FRAUD` and `ALLOW_TRANSACTION` are permitted (`SATISFIED`).
   - *Prohibited*: Blocking or declining actions (`BLOCK_CARD`, `BLOCK_ALL_CARDS`, `DECLINE_TRANSACTION`) are strictly prohibited (`VIOLATED`).

4. **Rule R4 (No reply within 24 hours)**:
   - *Condition*: Customer inquiry has received no response after 24 hours.
   - *Permitted*: `MONITOR_CARD` and `DECLINE_TRANSACTION` for pending authorizations (`SATISFIED`).
   - *Requirement*: Escalation to analyst (`ESCALATE_TO_ANALYST`) if exposure $> \$500.00$.

5. **Rule R5 (Card testing sequence)**:
   - *Condition*: 3+ small online authorizations within an hour followed by a larger purchase (`card_testing`).
   - *Permitted*: `DECLINE_TRANSACTION` and `STEP_UP_AUTH` (`SATISFIED`).
   - *Conditional Block*: `BLOCK_CARD` permitted if cleared purchase $> \$100.00$; prohibited if cleared purchase $\le \$100.00$ (`VIOLATED`).

6. **Rule R6 (Shared origin across cards)**:
   - *Condition*: Multiple cards showing fraud from the same device profile, billing region, or recipient email.
   - *Permitted*: `CREATE_CASE`, `FILE_REPORT`, and `MONITOR_CONNECTED_CARDS` (`SATISFIED`).

7. **Rule R7 (Disputed recurring charge)**:
   - *Condition*: Customer disputes recurring charge matching historical pattern.
   - *Permitted*: `CREATE_CASE`, `VERIFY_WITH_CUSTOMER`, and `WARN_CUSTOMER` (`SATISFIED`).
   - *Prohibited*: Card blocking (`BLOCK_CARD`, `BLOCK_ALL_CARDS`) is strictly prohibited (`VIOLATED`).

8. **Rule R8 (Escalate when uncertain and exposed)**:
   - *Condition*: Verdict is uncertain (or confidence $< 0.70$ / uncertainty $> 0.30$) and exposure $> \$500.00$, or evidence conflicts.
   - *Permitted*: `ESCALATE_TO_ANALYST` (`SATISFIED`).

9. **Rule R9 (Undocumented patterns)**:
   - *Condition*: Coordinated abuse fitting no known pattern (`undocumented`).
   - *Permitted*: `CREATE_CASE`, `FILE_REPORT`, and `ESCALATE_TO_ANALYST` (`SATISFIED`).

10. **Rule R10 (Constraint on `BLOCK_ALL_CARDS`)**:
    - *Condition*: Evaluating candidate action `BLOCK_ALL_CARDS`.
    - *Constraint*: Prohibited (`VIOLATED`) unless $\ge 2$ customer cards show confirmed fraud or customer credentials are confirmed compromised.

---

### 4. Canonical Action Handling & Legacy Alias Normalization

Stage 5 strictly enforces the 14 canonical organizer actions (`ActionType` enum):
```text
ALLOW_TRANSACTION, DECLINE_TRANSACTION, MONITOR_CARD, MONITOR_CONNECTED_CARDS,
WARN_CUSTOMER, VERIFY_WITH_CUSTOMER, STEP_UP_AUTH, BLOCK_CARD, BLOCK_ALL_CARDS,
GENERATE_REPORT, CREATE_CASE, FILE_REPORT, ESCALATE_TO_ANALYST, CLOSE_NO_FRAUD
```

Legacy aliases from earlier specifications are automatically normalized to canonical types before policy evaluation:
* `BLOCK_TRANSACTION` $\to$ `DECLINE_TRANSACTION`
* `FREEZE_ACCOUNT` $\to$ `BLOCK_ALL_CARDS`
* `REQUEST_STEP_UP_AUTH` $\to$ `STEP_UP_AUTH`
* `REQUEST_VERIFICATION` $\to$ `VERIFY_WITH_CUSTOMER`
* `FILE_SAR` $\to$ `FILE_REPORT`
* `MONITOR` $\to$ `MONITOR_CARD`

An unrecognized action string immediately fails closed to `hitl_status = POLICY_INDETERMINATE` with `permitted = False`.

---

### 5. Approval Routing Hierarchy

`PolicyEvaluator.determine_approval_level(action, exposure_usd)` calculates approval routing:

| Action | Exposure USD Condition | Required Approval Level |
| :--- | :--- | :--- |
| `BLOCK_CARD` | Exposure $\le \$2,500.00$ | `L1_SUPERVISOR` |
| `BLOCK_CARD` | Exposure $> \$2,500.00$ | `L2_COMPLIANCE` |
| `BLOCK_ALL_CARDS` | Any exposure | `L2_COMPLIANCE` |
| `FILE_REPORT` | Any exposure | `L2_COMPLIANCE` |
| `DECLINE_TRANSACTION` | Any exposure | `L1_SUPERVISOR` |
| All other 10 actions | Any exposure | `AUTO` |

---

### 6. Exposure Source of Truth

The single source of truth for exposure is `InvestigationResult.transaction["amount"]` or `InvestigationResult.exposure_usd`.
* Missing exposure when evaluating exposure-sensitive actions (`BLOCK_CARD`, `BLOCK_ALL_CARDS`, `FILE_REPORT`, `DECLINE_TRANSACTION`, `ESCALATE_TO_ANALYST`) fails closed to `POLICY_INDETERMINATE`.
* Negative or NaN exposure values are strictly rejected.
* The system never guesses $\$0.00$ or assumes `AUTO` for missing values.

---

### 7. Fail-Closed Controls

Fail-closed behavior is enforced across all evaluation paths:
1. **Unrecognized Action**: `permitted = False`, `hitl_status = POLICY_INDETERMINATE`.
2. **Missing Exposure**: `permitted = False`, `hitl_status = POLICY_INDETERMINATE`.
3. **Corrupt Risk Values (NaN/Inf)**: `permitted = False`, `hitl_status = POLICY_INDETERMINATE`.
4. **Policy Violation (R1, R3, R5, R7, R10)**: `permitted = False`, `hitl_status = POLICY_BLOCKED`.

---

### 8. Human-in-the-Loop (HITL) State Machine

The HITL lifecycle progresses through explicit canonical states:
```text
NBA Assessment
      ↓
Policy Evaluator
      ↓
┌─────────────────────────────────┐
│ Policy Permitted?               │
└───────────────┬─────────────────┘
         NO ────┴──── YES
         ↓             ↓
   POLICY_BLOCKED   Approval Required?
                           │
                    NO ────┴──── YES
                    ↓             ↓
              AUTO_APPROVED   PENDING_L1 / PENDING_L2
                                  │
                           HUMAN SUPERVISOR
                                  │
                           ┌──────┴──────┐
                           ↓             ↓
                       APPROVED       REJECTED
```

* When `hitl_status` is `PENDING_L1_APPROVAL` or `PENDING_L2_APPROVAL`, the investigation workflow halts at `current_workflow_state = "AWAITING_APPROVAL"`.
* The workflow never executes the action while awaiting approval.

---

### 9. Approval Endpoint (`POST /api/cases/{case_id}/approve`)

The approval endpoint enforces strict server-side validation:
1. Validates request payload and checks for empty/bypass tokens.
2. Retrieves case from case memory (`CaseNotFoundException` if missing).
3. Verifies that the case is in `AWAITING_APPROVAL` status and `ApprovalRequest.status == PENDING`.
4. Enforces idempotency: rejects duplicate approvals on resolved cases (HTTP 403).
5. Cryptographically verifies HMAC token binding (`case_id`, `action`, `target_resource`, `amount`, `approval_level`, `expires_at`).
6. Verifies server-side approver authority: an L1 supervisor cannot approve an L2 compliance case.
7. Updates case status to `RESOLVED` and approval request to `APPROVED` or `REJECTED`.
8. Records structured security audit event (`APPROVAL_GRANTED` or `APPROVAL_REJECTED`).
9. **ZERO EXECUTION**: Does NOT invoke `execute_action` or `write_case_to_graph`. Returns `executed: false`.

---

### 10. Cryptographic HMAC Token Security

* Token format: `v1:{expires_at}:{sha256_hex_digest}`
* Payload string: `{case_id}:{action}:{target_resource}:{amount:.2f}:{approval_level}:{expires_at}`
* Any tampering with amount, action, target resource, case ID, or approval level invalidates the signature.
* Expiration check: tokens with expired timestamps are strictly rejected.

---

### 11. Server-Side Approver Authority Registry

Authority is determined strictly on the server:
* `analyst_1`, `ANALYST-1`, `team_lead`, `SUPERVISOR-1` $\implies \text{ApprovalLevel.L1\_SUPERVISOR}$
* `compliance_l2`, `COMPLIANCE-1`, `fraud_manager`, `manager_1` $\implies \text{ApprovalLevel.L2\_COMPLIANCE}$
* An L2 manager possesses authority for both L1 and L2 decisions.
* An L1 analyst possesses authority only for L1 decisions.
* Unknown approver IDs are rejected.

---

### 12. Boundaries

* **Stage 4 Boundary**: Stage 4 recommends actions based purely on evidence; Stage 5 evaluates policy constraints and approval routing.
* **Stage 6 Boundary**: Stage 5 records approval decisions but does **not** execute remediation actions or write back cases to TigerGraph.
* **Graph Boundary**: Zero new TigerGraph or GraphRAG queries are performed during policy evaluation.
* **LLM Boundary**: Policy evaluation is 100% deterministic code; no LLM decides policy permissions or approval routing.

---

### 13. Test Results

* **Stage 5 Test Suite (`tests/test_stage5_policy.py`)**: 40 passed, 0 failed.
* **Stage 4 Regression Suite (`tests/test_stage4_nba.py`)**: 30 passed, 0 failed.
* **Full Regression Suite across Stages 1–5**:
  - Stage 1 Foundation: 35 tests passed
  - Stage 2 Investigation: 21 tests passed
  - Stage 3 Risk & Uncertainty: 29 tests passed
  - Stage 4 Next Best Action: 30 tests passed
  - Stage 5 Policy & HITL: 40 tests passed
  - **Total: 155 tests passed, 0 failures, 0 errors in 0.199s**.

---

### 14. Protected Ownership

* `tigergraph/`: Untouched (0 modifications).
* `graphrag/`: Untouched (0 modifications).
* `data/`: Untouched (0 modifications).
* `frontend/`: Untouched (0 modifications).
* `Information/`: Untracked / ignored by `.gitignore`.
* Git operations: Zero commits, pushes, or resets performed.
