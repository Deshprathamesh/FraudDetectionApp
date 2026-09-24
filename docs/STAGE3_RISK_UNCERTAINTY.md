# Stage 3: Risk + Uncertainty Engine Documentation
**Workstream**: Person 1 (Brain) — Investigation Engine & Reasoning Layer  
**Date**: September 2026  
**Status**: COMPLETE — ALL 29 STAGE 3 TESTS PASSING (85 TOTAL IN PROJECT)

---

## 1. Executive Summary & Objective

Stage 3 implements the **Risk + Uncertainty Engine** for FraudGraph AI.

### Core Responsibility
Stage 3 strictly answers:
> **"HOW RISKY / HOW CERTAIN IS THIS BASED ON THE EVIDENCE?"**

### Strict Boundaries & Non-Goals
Stage 3 does **NOT**:
- Formulate Next Best Actions (Stage 4)
- Evaluate policy rules R1–R10 (Stage 5)
- Route human approvals or handle HITL states (Stage 5)
- Execute simulated actions (Stage 6)
- Persist case remediation to TigerGraph (Stage 6)
- Re-query TigerGraph or GraphRAG (it strictly consumes the Stage 2 `InvestigationResult`)
- Treat raw upstream detection `risk_score` as the final verdict (it is treated as one non-dominating input signal within `TRANSACTION_ATTRIBUTES`)

---

## 2. Mathematical Formulations & Methodology

### 2.1 Methodology Tag
`methodology = "heuristic_probability_estimate"`

### 2.2 Fraud Probability Formulation
To prevent double-counting of correlated signals and avoid dominance by single indicators, evidentiary signals are partitioned into **9 independent groups**:
1. `TRANSACTION_ATTRIBUTES`
2. `CUSTOMER_PROFILE`
3. `TRANSACTION_HISTORY`
4. `GRAPH_TOPOLOGY`
5. `DEVICE_SHARING`
6. `FRAUD_PATTERN`
7. `HISTORICAL_CASE`
8. `POLICY_DIRECTIVE`
9. `CUSTOMER_VERIFICATION`

Within each group $g \in G$, the net dominant weight is calculated:
$$\Delta w_g = \max_{s \in \text{fraud}_g}(w_s) - \max_{s \in \text{legit}_g}(w_s)$$

Log-odds aggregation with prior $P_0 = 0.20$ ($L_0 = \ln(0.20 / 0.80) \approx -1.3863$) and evidence scaling $\beta = 1.6$:
$$L_{\text{final}} = L_0 + \beta \sum_{g \in G} \Delta w_g$$

Mapping to calibrated probability:
$$P(\text{fraud}) = \sigma(L_{\text{final}}) = \frac{1}{1 + e^{-L_{\text{final}}}}$$
Strictly bounded to $[0.01, 0.99]$.

### 2.3 Epistemic Confidence Formulation
Confidence measures **evidence corroboration and quality**, NOT fraud likelihood:
- Corroboration base ($N_{\text{supp}}$ independent groups supporting prevailing conclusion):
  - $N_{\text{supp}} = 0 \implies 0.25$
  - $N_{\text{supp}} = 1 \implies 0.48$ (Single source cannot exceed 0.50 confidence)
  - $N_{\text{supp}} = 2 \implies 0.75$ ($\ge 2$ independent sources achieves solid confidence)
  - $N_{\text{supp}} = 3 \implies 0.86$
  - $N_{\text{supp}} \ge 4 \implies 0.94$
- Evidence quality scaling: $C = C_{\text{base}} \times (0.85 + 0.15 \times \bar{w}_{\text{supp}})$
- Contradiction penalty: $C \leftarrow C - \min\left(0.30, 0.40 \times \frac{w_{\text{opposing}}}{w_{\text{supporting}} + w_{\text{opposing}}}\right)$
- Auxiliary component outage / partial penalty: $-0.15$ deduction if `InvestigationStatus.PARTIAL` or warnings present
- Bounded to $[0.05, 0.98]$ (or $[0.0, 1.0]$ in domain model).

### 2.4 Epistemic Uncertainty Formulation
Epistemic uncertainty is the exact complement of epistemic confidence:
$$\text{uncertainty} = 1.0 - \text{confidence}$$
Strictly satisfies $\text{confidence} + \text{uncertainty} = 1.0$.

---

## 3. Evidence Quality & Security Multipliers

Every signal's effective weight $w_s$ is derived from its raw strength and epistemic quality:
$$w_s = \text{strength} \times \text{mult}_{\text{fact\_level}} \times \text{mult}_{\text{direct}} \times \text{mult}_{\text{untrusted}}$$

- **Fact Levels**:
  - `FACT`: $1.0$ (ground truth attributes from transaction or customer profile)
  - `OBSERVATION`: $0.85$ (empirical graph topology, shared devices, typology detections)
  - `INFERENCE`: $0.70$ (historical precedent similarity, statistical comparisons, prompt context)
- **Direct vs. Derived**:
  - Direct observation (`is_direct=True`): $1.0$
  - Derived relationship (`is_direct=False`): $0.90$
- **Untrusted Prompt Context Dampening (Security Baseline §10 & §20)**:
  - External prompt text, narrative retrieval, or unverified external strings (`untrusted_data_flag=True`): $\mathbf{0.50}$ multiplier. This prevents adversarial prompt injection in GraphRAG from hijacking the numerical probability evaluation.

---

## 4. Organizer Stopping Decision Matrix

The engine evaluates strict organizer stopping criteria:

| Condition | Status | Reason & Behavior |
| :--- | :--- | :--- |
| $P \ge 0.85 \land N_{\text{indep}} \ge 2$ | `SUFFICIENT_EVIDENCE` | High fraud probability supported by $\ge 2$ independent groups. |
| $P \le 0.15 \land N_{\text{indep}} \ge 2$ | `SUFFICIENT_EVIDENCE` | Low fraud probability (legitimate) supported by $\ge 2$ independent groups. |
| Verification Settled | `SUFFICIENT_EVIDENCE` | Direct cardholder verification response confirms or denies unauthorized activity. |
| $P \ge 0.85 \land N_{\text{indep}} < 2$ | `MORE_EVIDENCE_REQUIRED` | Extreme range reached but lacks required corroboration (recommends query). |
| Intermediate $P$ with gaps | `MORE_EVIDENCE_REQUIRED` | Material information gaps remain (e.g. unverified cardholder, missing KYC). |
| Intermediate $P$ with exhausted sources | `INCONCLUSIVE` | Evidence exhausted without reaching decision threshold. |
| Critical dependency outage | `INVESTIGATION_BLOCKED` | Database connection refused or primary investigation failure. |

---

## 5. Domain Models & Artifacts

### 5.1 Enums
- `SignalDirection`: `SUPPORTS_FRAUD`, `SUPPORTS_LEGITIMATE`, `NEUTRAL`
- `IndependenceGroup`: 9 categories preventing double counting
- `StoppingStatus`: `SUFFICIENT_EVIDENCE`, `MORE_EVIDENCE_REQUIRED`, `INCONCLUSIVE`, `INVESTIGATION_BLOCKED`

### 5.2 Models
- `RiskSignal`: Typed evidence signal with category, description, direction, strength, weight, evidence_ids, provenance, and independence_group.
- `InformationGap`: Identified missing evidence or context with severity, description, affected_conclusion, and material_impact.
- `StoppingDecision`: Evaluated stopping status, reason, fraud_probability, confidence, independent_evidence_count, condition_met, missing_information, and recommended_next_query.
- `RiskAssessment`: Unified assessment containing fraud_probability, risk_score, risk_level, confidence, uncertainty, supporting_signals, contradicting_signals, neutral_signals, signal_breakdown, stopping_decision, information_gaps, and reasoning_summary.

---

## 6. Verification & Test Coverage Summary

A 29-test comprehensive test suite was implemented in `tests/test_stage3_risk.py` covering all criteria:

| Test Class | Tests | Status |
| :--- | :--- | :--- |
| `TestStage3NumericBoundsAndInvariants` | 3 | PASSED |
| `TestStage3SignalExtraction` | 6 | PASSED |
| `TestStage3InformationGaps` | 6 | PASSED |
| `TestStage3OrganizerStoppingDecisions` | 6 | PASSED |
| `TestStage3ExplainabilitySummary` | 1 | PASSED |
| `TestStage3StrictBoundaries` | 4 | PASSED |
| `TestStage3Monotonicity` | 2 | PASSED |
| `TestStage3WorkflowIntegration` | 1 | PASSED |
| `TestStage3RealDataSyndicateAndBenign` | 2 | PASSED |
| **Total Stage 3 Tests** | **29** | **ALL PASSED** |

### Regression Verification
- Stage 1 tests (`tests/test_stage1_foundation.py`): **35 passed** (0 failures, 0 errors)
- Stage 2 tests (`tests/test_stage2_investigation.py`): **21 passed** (0 failures, 0 errors)
- Stage 3 tests (`tests/test_stage3_risk.py`): **29 passed** (0 failures, 0 errors)
- **Total Project Tests**: **85 PASSED** (0 failures, 0 errors)

---

## 7. Real-Data Benchmark Results

1. **Syndicate Transaction (`TXN-104829`)**:
   - `fraud_probability`: `0.9419` (`CRITICAL`)
   - `confidence`: `0.8600` ($\ge 0.75$)
   - `uncertainty`: `0.1400`
   - `independent_evidence_count`: 3 (`TRANSACTION_ATTRIBUTES`, `DEVICE_SHARING`, `FRAUD_PATTERN`)
   - `stopping_decision.status`: `SUFFICIENT_EVIDENCE`
   - Supporting drivers: Fast transaction burst, device ring (linked to 4 accounts), high upstream risk score.

2. **Benign Transaction (`TXN-209144`)**:
   - `fraud_probability`: `0.1772` (`LOW`)
   - `confidence`: `0.8033`
   - `uncertainty`: `0.1967`
   - Contradicting signals: Baseline normalcy, verified customer KYC, normal velocity.
