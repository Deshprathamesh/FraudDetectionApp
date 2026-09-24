# FraudGraph AI — Stage 6: Execution Engine + Case Memory Persistence

**Workstream:** Person 1 (Brain)  
**Stage:** 6 (Execution Engine + Case Memory Persistence)  
**Status:** COMPLETE & VERIFIED  

---

## 1. Executive Summary

Stage 6 implements the **Remediation Action Execution Engine** and **Case Memory Persistence Adapter** for FraudGraph AI. It safely operationalizes recommendations vetted by Stage 5 Policy Compliance and authorized by human supervisors or automated policy limits, while persisting the completed investigation into TigerGraph case memory for continuous organizational learning.

Stage 6 directly answers:
> **"Once an action has been recommended, permitted by policy, and appropriately approved, how is it safely executed and how is the completed investigation persisted as case memory for future investigations?"**

### Key Guarantees
1. **Simulation Guarantee (`simulated = True`)**: All action executions in FraudGraph AI are simulated; no live financial funds are moved, and no actual payment instruments or card network switches are disrupted.
2. **7-Point Authorization Gate (A–G)**: Actions cannot execute without passing seven independent checks (valid case context, canonical action type, policy permission, approval level satisfaction, approver authority, idempotency, and target resource syntax).
3. **Execution Idempotency**: In-memory idempotency registry keyed on `f"{case_id}:{action}:{target_resource}"` guarantees duplicate requests return `ExecutionStatus.ALREADY_EXECUTED` without duplicate execution side-effects.
4. **Fault-Isolated Case Memory Persistence**: Failure to write to TigerGraph records `CASE_MEMORY_WRITE_FAILED` in the audit log and updates case metadata, but **never crashes or rolls back the remediation action execution**.
5. **Zero Blind Trust**: API endpoints (`POST /api/cases/{case_id}/action`) strictly verify server-side policy and approval status; client payloads asserting `{"approved": true}` are rejected if server-side approval is missing or pending.

---

## 2. Core Architecture & Components

```
                                    +-----------------------------------+
                                    | Stage 4 Next Best Action Engine   |
                                    +-----------------+-----------------+
                                                      |
                                                      v
                                    +-----------------------------------+
                                    | Stage 5 Policy & HITL Evaluator   |
                                    +-----------------+-----------------+
                                                      |
                                                      v
                                +-------------------------------------------+
                                | Stage 6 Action Execution Service          |
                                | - Check A: Case Context Exists            |
                                | - Check B: Canonical Action Normalization |
                                | - Check C: Policy Permitted & Non-Blocked |
                                | - Check D: Approval Status Satisfied      |
                                | - Check E: Approver Authority Verified    |
                                | - Check F: Idempotency Key Checked        |
                                | - Check G: Target Resource Validated      |
                                +---------------------+---------------------+
                                                      |
                               +----------------------+----------------------+
                               |                                             |
                               v                                             v
               +-------------------------------+             +-------------------------------+
               | MockActionExecutor            |             | Security Audit Trail          |
               | - 14 Canonical Actions        |             | - ACTION_EXECUTION_REQUESTED  |
               | - Simulated Flag = True       |             | - ACTION_EXECUTED             |
               | - Target Syntax Validation    |             | - ACTION_EXECUTION_BLOCKED    |
               +---------------+---------------+             | - ACTION_EXECUTION_FAILED     |
                               |                             +-------------------------------+
                               v
               +-------------------------------------------------------------+
               | CaseMemoryAdapter (Fault Isolated)                          |
               | - Normalizes Evidence Items & Fraud Patterns Topology       |
               | - Attaches Execution Records & Signatures                   |
               | - Calls Person 2 `tigergraph.tools.write_case_to_graph`    |
               | - CASE_MEMORY_WRITE_REQUESTED / CASE_MEMORY_WRITTEN         |
               +-------------------------------------------------------------+
```

### Component Details

#### 1. Execution Domain Models (`backend/execution/models.py`)
- `ExecutionStatus`:
  - `EXECUTED`: Action executed successfully in simulation mode.
  - `FAILED`: Action execution encountered an operational or system exception.
  - `BLOCKED`: Execution prohibited by policy, missing context, or invalid target.
  - `ALREADY_EXECUTED`: Duplicate execution detected; cached result returned.
  - `NOT_AUTHORIZED`: Missing required human approval, pending approval, or insufficient authority.
- `ExecutionResult`:
  - `execution_id`: Unique run identifier (`EXEC-xxxxxxxx`).
  - `case_id`: Associated investigation case ID.
  - `action`: Canonical `ActionType`.
  - `target_resource`: Target entity (card, account, transaction, customer).
  - `status`: Lifecycle `ExecutionStatus`.
  - `executed_at`: Epoch timestamp.
  - `simulated`: Strictly `True`.
  - `idempotency_key`: Composite key `f"{case_id}:{action.value}:{target_resource}"`.
  - `approval_reference`: Associated approval ID or `"AUTO_APPROVED"`.
  - `message`: Clear simulation-labeled narrative.
  - `audit_event_id`: Corresponding security audit record ID.
  - `details`: Execution parameters and metadata.

#### 2. Mock Action Executor (`backend/execution/mock_executor.py`)
- Simulates all 14 canonical actions defined in the organizer specification:
  - `ALLOW_TRANSACTION`: Permits transaction to clear without hold.
  - `DECLINE_TRANSACTION`: Declines transaction at authorization switch.
  - `MONITOR_CARD`: Activates velocity telemetry on target card instrument.
  - `MONITOR_CONNECTED_CARDS`: Fleet telemetry across all payment cards of customer.
  - `WARN_CUSTOMER`: Dispatches out-of-band security advisory.
  - `VERIFY_WITH_CUSTOMER`: Sends interactive confirmation challenge (SMS/Push).
  - `STEP_UP_AUTH`: Initiates 2FA cryptographic challenge for transaction.
  - `BLOCK_CARD`: Restricts card on issuer authorization switch.
  - `BLOCK_ALL_CARDS`: Complete account suspension across all customer instruments.
  - `GENERATE_REPORT`: Formats regulatory audit dossier and evidence summary.
  - `CREATE_CASE`: Opens formal investigative tracking dossier.
  - `FILE_REPORT`: Submits Suspicious Activity Report (SAR) draft.
  - `ESCALATE_TO_ANALYST`: Routes case to senior tier-2 fraud analyst work-queue.
  - `CLOSE_NO_FRAUD`: Closes case as verified false positive / legitimate.

#### 3. Action Execution Service (`backend/execution/executor.py`)
Central orchestrator enforcing the 7 independent authorization checks:
- **Check A**: Case ID is present and non-empty.
- **Check B**: Action normalizes to canonical `ActionType` (including legacy aliases).
- **Check C**: Policy assessment exists, `permitted == True`, and `hitl_status` is not `POLICY_BLOCKED` or `POLICY_INDETERMINATE`.
- **Check D**: Approval conditions met:
  - If `approval_level == AUTO`: auto-approved without human intervention.
  - If `approval_level in (L1, L2)`: case has `ApprovalRequest` with status `APPROVED`.
- **Check E**: Server-side approver authority:
  - Approver ID present in approval record.
  - `policy_evaluator.verify_approver_authority(approver_id, level)` returns `True`.
- **Check F**: Idempotency check:
  - Key `f"{case_id}:{action}:{target_resource}"` checked in memory.
  - If present, returns cached result with status `ALREADY_EXECUTED`.
- **Check G**: Target resource validation:
  - Target syntax matches expected entity type (`CARD-...`, `C-...`, `TXN-...`).

#### 4. Case Memory Persistence Adapter (`agent/tools/case_memory_adapter.py`)
- Adapts heterogeneous case representations (`InvestigationCase`, `AgentState`, dictionaries) to Person 2's TigerGraph schema.
- Normalizes evidence items, fraud patterns, and executed action records.
- Interacts with Person 2's `write_case_to_graph` tool via `graph_adapter`.
- **Fault Isolation**: Graph persistence exceptions are recorded as `CASE_MEMORY_WRITE_FAILED`, but never crash action execution.

---

## 3. Workflow & API Integration

### Workflow Integration (`agent/workflows/workflow.py`)
- `execution_node`: Resolves appropriate target entity from state context, executes action via `action_executor`, and records timeline events.
- `case_persistence_node`: Commits case to `case_memory_service` and TigerGraph via `case_memory_adapter`, setting `state["written_to_graph"] = True` and `state["current_workflow_state"] = "RESOLVED"`.
- `create_full_lifecycle_workflow`: Complete lifecycle from trigger through policy, approval gate, execution, and persistence.
- `create_execution_workflow`: Dedicated Stage 6 canonical workflow factory.

### REST Endpoints (`backend/api/routes.py`)
1. `POST /api/cases/{case_id}/action`:
   - Enforces frontend contract (`frontend/services/api.ts`).
   - Server-side authorization check rejects client-side approval spoofing.
   - Executes remediation action, commits case memory, and returns updated `InvestigationCase`.
2. `POST /api/investigations/{transaction_id}/execute`:
   - Runs investigation -> risk assessment -> next best action -> policy evaluation -> execution (if auto-approved).
   - If human approval is required, stops at `AWAITING_APPROVAL` with signed HMAC token.

---

## 4. Test Verification & Results

A comprehensive test suite of **49 tests** was implemented in `tests/test_stage6_execution.py`.

```text
Ran 204 tests across all stages in 0.345s:
- Stage 1 (Foundation): 35 tests passed
- Stage 2 (Investigation Engine): 21 tests passed
- Stage 3 (Risk & Uncertainty): 29 tests passed
- Stage 4 (Next Best Action): 30 tests passed
- Stage 5 (Policy Compliance & HITL Gate): 40 tests passed
- Stage 6 (Execution Engine & Case Memory): 49 tests passed
Total: 204 passing tests, 0 failures, 0 errors.
```

### Verified Scenarios
1. **Authorization Gating**: Auto-approval execution, unapproved L1/L2 blocking, approved L1/L2 execution, rejected approval blocking, insufficient approver authority blocking, and missing approver ID blocking.
2. **Target Validation**: Rejection of invalid card targets for `BLOCK_CARD`, rejection of non-customer targets for `WARN_CUSTOMER`, acceptance of valid card/customer/transaction IDs.
3. **Idempotency**: Duplicate calls return `ALREADY_EXECUTED` without calling mock executor twice.
4. **Mock Execution**: All 14 canonical actions return `simulated = True` and detailed narratives.
5. **Audit Trail**: Correct recording of `ACTION_EXECUTION_REQUESTED`, `ACTION_EXECUTED`, `ACTION_EXECUTION_BLOCKED`, `ACTION_EXECUTION_FAILED`, `CASE_MEMORY_WRITE_REQUESTED`, `CASE_MEMORY_WRITTEN`, and `CASE_MEMORY_WRITE_FAILED`.
6. **Case Memory Persistence**: Graph IDs and node/edge commit counts verified; fault isolation verified on mock graph failure.
7. **End-to-End Workflow**: Real seeded transaction `TXN-209144` auto-approved, executed, and persisted to `RESOLVED`; high-value wire `TXN-301855` gated at `AWAITING_APPROVAL`.
8. **REST Endpoints**: Server-side approval verification tested against client spoofing (`{"approved": true}` on pending case rejected).

---

## 5. Frozen Architectural Boundaries Compliance

| Boundary | Status | Verification Note |
|---|---|---|
| Person 2 (`tigergraph/`, `graphrag/`, `data/`) | UNTOUCHED | Zero files modified. Public `write_case_to_graph` tool consumed via adapter. |
| Person 3 (`frontend/`) | UNTOUCHED | Zero files modified. Endpoint `POST /api/cases/{case_id}/action` satisfies contract. |
| Stage 1–5 Baseline | UNCHANGED | All 155 pre-existing tests pass without regressions. |
| `Information/` Directory | IGNORED | Directory ignored throughout execution. |
| Git History | CLEAN | Zero commits or pushes executed. Working tree clean. |
