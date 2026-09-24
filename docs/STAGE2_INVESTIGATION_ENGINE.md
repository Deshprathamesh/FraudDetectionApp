# FraudGraph AI — Stage 2: Investigation Engine Architecture & Verification Report

**Workstream:** Person 1 (Brain)  
**Status:** COMPLETE & VERIFIED  
**Date:** September 2026  
**Scope:** "WHAT EVIDENCE DO WE HAVE?"  

---

## 1. Executive Summary

Stage 2 implements the **Investigation Engine** for FraudGraph AI. It systematically triggers, enriches, normalizes, structures, and deduplicates evidence using Person 2's completed TigerGraph tool suite and GraphRAG retrieval pipeline.

### Core Architectural Principle
Stage 2 strictly answers:
> **"WHAT EVIDENCE DO WE HAVE?"**

It deliberately does **NOT** answer:
- *"HOW RISKY IS THIS?"* (Reserved for Stage 3 — Risk, Confidence & Uncertainty)
- *"WHAT SHOULD WE DO?"* (Reserved for Stage 4 — Next Best Action)
- *"ARE WE ALLOWED TO DO IT?"* (Reserved for Stage 5 — Policy Engine & Human-in-the-Loop)

---

## 2. Person 2 Interface Verification & Ingestion Boundary

As frozen during project reconciliation:
1. **TigerGraph Tool Suite (`tigergraph/tools.py`)**:
   - Single canonical import point: `get_graph_tools() -> Dict[str, Callable]`.
   - Returns 9 registered tools with typed Pydantic response models (`TransactionDetailResponse`, `CustomerDetailResponse`, `TransactionHistoryResponse`, `ConnectedEntitiesResponse`, `SharedDevicesResponse`, `DetectFraudPatternsResponse`, `SimilarCasesResponse`, `PolicyContextResponse`, `WriteCaseResponse`).
2. **GraphRAG Pipeline (`graphrag/pipeline.py`)**:
   - Singleton instance: `pipeline = GraphRAGPipeline()`.
   - Canonical method: `pipeline.get_structured_context(case_context, ...) -> Dict[str, Any]` returning `prompt_context`, `policy` model, and `similar_cases` model.
   - Convenience helper: `retrieve_investigation_context(...) -> str`.
3. **Immutability Guarantee**:
   - Zero changes made to `tigergraph/`, `graphrag/`, `data/`, or `frontend/`.

---

## 3. Epistemic Evidence Taxonomy

Every piece of information collected by the Investigation Engine is parsed and normalized into a strongly-typed `EvidenceItem` with an explicit epistemic classification:

| Fact Level | Definition | Sources | Examples | `is_direct` |
|---|---|---|---|---|
| **`FACT`** | Direct, indisputable ground-truth attributes from entity or transaction profiles | `ENRICHMENT`, `GRAPHRAG` | Transaction amount ($1,249.50 USD), currency, channel, merchant, customer name, risk tier, governing policy clauses | `True` |
| **`OBSERVATION`** | Topological or heuristic patterns detected in the graph network | `GRAPH`, `ENRICHMENT` | Multi-hop connected entities (depth 2), shared hardware device links, detected fraud patterns (e.g. FP-01 cycle), raw ingest anomaly score | `False` |
| **`INFERENCE`** | Precedent matches, statistical similarity scores, or model-generated syntheses | `GRAPHRAG` | Historical case similarity percentages, historical resolutions/outcomes, synthesized GraphRAG prompt context | `False` |

---

## 4. Deterministic Deduplication Strategy (Zero LLM Overhead)

To eliminate evidence bloat, prevent hallucinations, and guarantee repeatable execution, deduplication is 100% deterministic and runs without LLM evaluation.

### Deduplication Key
$$\text{Signature} = (\text{source}, \text{evidence\_type}, \text{primary\_entity}, \text{claim\_prefix}_{60})$$

### Merge Semantics
When multiple queries generate duplicate evidence asserting the same factual claim:
1. **Entity IDs**: Set-union merged while preserving ordering.
2. **Provenance Sources**: Set-union merged (`["tigergraph.get_transaction", "tigergraph.find_shared_devices"]`).
3. **Confidence**: Retains $\max(\text{conf}_1, \text{conf}_2)$.
4. **Security Taint**: If any contributing source is untrusted, `untrusted_data_flag` remains `True`.

---

## 5. Security & Fail-Closed Controls

1. **Identifier Sanitization**:
   - Transaction IDs validated against strict regex: `^[A-Za-z0-9_.:\-]+$`.
   - SQL, GSQL, path traversal, script injection, and statement chaining patterns immediately rejected.
2. **Untrusted Data Flagging**:
   - All external prompts and historical narrative retrievals from GraphRAG are marked `untrusted_data_flag = True`.
3. **Input Override Rejection**:
   - The REST API strictly rejects client attempts to supply risk scores (`risk_score`, `confidence`, `uncertainty`) or pre-approved flags (`approved`, `approval_status`).
4. **Zero Currency Conversion**:
   - Currency strictly enforced as `USD`. All non-USD inputs fail validation.

---

## 6. Fault Tolerance & Partial Failure Semantics

To ensure production resilience without fabricating data:
- **Primary Failure**: If the target transaction lookup fails or the ID is invalid, the engine raises `TransactionNotFoundException` (HTTP 404) or `ValidationError` (HTTP 422).
- **Auxiliary Failure**: If an auxiliary tool (e.g. customer profile, history, graph traversal, shared devices, GraphRAG) encounters a timeout or connection issue:
  1. The failure is caught and recorded in `warnings`.
  2. An audit event `PARTIAL_FAILURE` is emitted with details.
  3. Investigation continues with available components.
  4. Status is marked `InvestigationStatus.PARTIAL`.
  5. **No data is fabricated** to fill the gap, and no case is falsely marked fraudulent due to a tool failure.

---

## 7. REST API Endpoints

### Canonical Endpoint
- **`POST /api/investigations`**
  - **Request Body**: `InvestigationStartRequest` (`transaction_id: str`, `trigger: Optional[dict]`)
  - **Response (200)**: `InvestigationResult`
  - **Error Codes**:
    - `404 Not Found`: Transaction does not exist in graph.
    - `422 Unprocessable Entity`: Invalid identifier format or disallowed client overrides.
    - `502 Bad Gateway`: Upstream graph query execution failure.

### Alias Endpoint
- **`POST /api/investigate`**
  - Routes to identical `investigation_engine.investigate` logic for backward compatibility.

---

## 8. Workflow Engine Integration

The LangGraph-equivalent workflow engine binds the Stage 2 pipeline:

```text
TRIGGERED ──▶ ENRICHMENT ──▶ GRAPH_ANALYTICS ──▶ GRAPHRAG_CONTEXT ──▶ EVIDENCE_PROCESSOR ──▶ INVESTIGATION_COMPLETE
```

- Terminates cleanly at `INVESTIGATION_COMPLETE`.
- Modular Stage 3–6 node functions (`risk_uncertainty_node`, `next_best_action_node`, `policy_compliance_node`, `hitl_gate_node`, `execution_node`, `case_persistence_node`) remain intact and modular, ready to be re-bound when Stage 3 arrives.

---

## 9. Verification & Change-Aware Testing Summary

| Test Suite | Tests Executed | Passed | Failed | Execution Time |
|---|---|---|---|---|
| `tests/test_stage2_investigation.py` | 21 | 21 | 0 | 0.058s |
| `tests/test_stage1_foundation.py` | 35 | 35 | 0 | 0.074s |
| **Total** | **56** | **56** | **0** | **0.132s** |

### Verified Test Categories:
- [x] Ground-truth transaction enrichment
- [x] Fail-closed non-existent transaction handling (404)
- [x] Injection blocking on transaction identifiers
- [x] Customer profile resolution and linking
- [x] Bounded transaction history (capped at 50)
- [x] Multi-hop graph neighborhood traversal (depth 2)
- [x] Shared hardware device detection
- [x] Fraud typology and pattern extraction
- [x] Hybrid GraphRAG similar case retrieval (top 3)
- [x] Untrusted data flagging on external prompt context
- [x] Epistemic classification: `FACT`, `OBSERVATION`, `INFERENCE`
- [x] Direct vs. indirect evidence flags
- [x] Deterministic deduplication without LLM
- [x] Entity ID and provenance source merging
- [x] Auxiliary tool partial failure resilience (`PARTIAL` status)
- [x] Audit trail emissions: `INVESTIGATION_STARTED`, `EVIDENCE_COLLECTED`, `INVESTIGATION_COMPLETED`, `PARTIAL_FAILURE`
- [x] Parameter whitelist security enforcement
- [x] Rejection of malicious client risk/approval overrides
- [x] Full workflow graph execution to `INVESTIGATION_COMPLETE`
- [x] Strict Stage 2 boundary compliance (no verdict, no NBA, no action execution)
