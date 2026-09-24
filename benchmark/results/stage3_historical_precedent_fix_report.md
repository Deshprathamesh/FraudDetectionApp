# FraudGraph AI — Stage 3 Historical Precedent Fix Report
## Resolving Precedent Cancellation Defect in Heuristic Risk Aggregation

**Workstream:** Person 1 (Brain) — Stage 3 Risk + Uncertainty Engine  
**Date:** 2026-09-24  
**Status:** COMPLETE & VERIFIED  
**Baseline Test Count:** 218 passed (29 baseline Stage 3 + 8 new precedent tests + 181 other stages), 0 failures, 0 errors  

---

## 1. Executive Summary

This report documents the implementation and verification of the **Stage 3 Historical Precedent Fix** in FraudGraph AI. 

The preceding Stage 3 reasoning audit (`benchmark/results/stage3_reasoning_audit.md`) identified a critical evidentiary defect: in [`agent/risk/evaluator.py`](file:///c:/Users/prath/Drive/FraudDetection/agent/risk/evaluator.py), evidence from the `HISTORICAL_CASE` independence group was aggregated using:
$$\text{net\_group\_w} = \max(w_{\text{fraud}}) - \max(w_{\text{legitimate}})$$

When GraphRAG retrieved 2 confirmed-fraud precedents and 1 cleared precedent with equal similarity (e.g., $0.90 \implies w = 0.2268$), the calculation yielded $0.2268 - 0.2268 = \mathbf{0.0000}$. This completely erased the 2-to-1 fraud precedent majority in 7 of the 20 benchmark cases and neutralized 99% of precedent evidence in 7 more cases (14 out of 20 benchmark cases affected, or 70%).

### Key Outcomes of the Fix:
1. **Mathematical Correction**: Implemented precedent ratio-scaled directional balance:
   $$\text{balance} = \frac{N_{\text{fraud}} - N_{\text{legit}}}{N_{\text{total}}} = 2 \times \text{precedent\_ratio} - 1$$
   $$\text{net\_w} = \begin{cases} \text{balance} \times \max(w_{\text{fraud}}) & \text{if balance} > 0 \\ \text{balance} \times \max(w_{\text{legit}}) & \text{if balance} < 0 \\ 0.0 & \text{if balance} = 0 \end{cases}$$
2. **Correlated Case Protection**: Preserved `HISTORICAL_CASE` as a single `IndependenceGroup`. Multiple precedents do not sum linearly ($\sum w$); the contribution remains strictly bounded by $\max(w) \le 1.0$.
3. **No Regressions**: All 29 existing Stage 3 unit tests passed without modification. 8 new focused unit tests were added, bringing the Stage 3 suite to 37 passed tests. The full 6-stage test suite passed 218/218 tests.
4. **Benchmark Resolution**: In HHG-003 and HHG-018 (customer dispute reports previously closed as `CLOSE_NO_FRAUD`), the 2:1 precedent majority now contributes $+0.0756$, shifting log-odds by $+0.1210$ and lifting $P$ from $0.1403$ to **$0.1556$**. Because $P > 0.1500$, both cases move out of the premature closure band to **`ALLOW_TRANSACTION`**.

---

## 2. Technical Implementation Details

### 2.1 Code Changes in `agent/risk/evaluator.py`

A dedicated helper method [`_compute_group_net_weight`](file:///c:/Users/prath/Drive/FraudDetection/agent/risk/evaluator.py#L50-L96) was introduced into `RiskEvaluator`. Both [`compute_fraud_probability`](file:///c:/Users/prath/Drive/FraudDetection/agent/risk/evaluator.py#L98-L149) and [`compute_confidence`](file:///c:/Users/prath/Drive/FraudDetection/agent/risk/evaluator.py#L151-L229) call this method.

```python
    def _compute_group_net_weight(
        self,
        grp: IndependenceGroup,
        sig_list: List[RiskSignal],
    ) -> float:
        """
        Computes the net directional weight contribution for a single IndependenceGroup.

        For HISTORICAL_CASE:
            Uses precedent ratio-scaled directional balance:
                direction_balance = (N_fraud - N_legit) / N_total = 2 * precedent_ratio - 1
                If direction_balance > 0: net_w = direction_balance * max(fraud_weights)
                If direction_balance < 0: net_w = direction_balance * max(legit_weights)
                If direction_balance == 0: net_w = 0.0
            This prevents mutual cancellation when precedents are mixed (e.g. 2 fraud vs 1 legit)
            while preserving single-group bounding and preventing linear inflation.

        For all other IndependenceGroups:
            net_w = max(fraud_weights) - max(legit_weights)
        """
        fraud_signals = [s for s in sig_list if s.direction == SignalDirection.SUPPORTS_FRAUD]
        legit_signals = [s for s in sig_list if s.direction == SignalDirection.SUPPORTS_LEGITIMATE]

        fraud_w = max([s.weight for s in fraud_signals], default=0.0)
        legit_w = max([s.weight for s in legit_signals], default=0.0)

        if grp == IndependenceGroup.HISTORICAL_CASE:
            n_fraud = len(fraud_signals)
            n_legit = len(legit_signals)
            n_total = n_fraud + n_legit

            if n_total == 0:
                return 0.0

            precedent_ratio = n_fraud / n_total
            direction_balance = 2.0 * precedent_ratio - 1.0  # (n_fraud - n_legit) / n_total

            if direction_balance > 0:
                return round(direction_balance * fraud_w, 4)
            elif direction_balance < 0:
                return round(direction_balance * legit_w, 4)
            else:
                return 0.0

        return round(fraud_w - legit_w, 4)
```

### 2.2 Preservation of Invariants & Constraints
- **Base Prior**: Retained $P_0 = 0.20$ ($L_0 = -1.3863$).
- **Evidence Scaling Factor**: Retained $\beta = 1.6$.
- **Bounding**: Probability strictly clamped to $[0.01, 0.99]$; confidence in $[0.05, 0.98]$; uncertainty = $1.0 - C$.
- **Independence Group Isolation**: Only `IndependenceGroup.HISTORICAL_CASE` uses ratio-scaled balance. All other groups (`TRANSACTION_ATTRIBUTES`, `CUSTOMER_PROFILE`, `DEVICE_SHARING`, etc.) retain intra-group maximum dominance ($\max(w_f) - \max(w_l)$) to prevent double counting of correlated attributes.
- **Architectural Freezes**: Stages 4, 5, 6, TigerGraph, GraphRAG, frontend, and public schemas remain completely untouched.

---

## 3. Unit Test Verification

Eight focused tests were added in [`tests/test_stage3_risk.py`](file:///c:/Users/prath/Drive/FraudDetection/tests/test_stage3_risk.py#L901-L1250) under the `TestStage3HistoricalPrecedentAggregation` test class:

| Test Case | Test Description | Observed Result | Status |
|:---|:---|:---|:---:|
| `test_unanimous_fraud_precedents` | 3 fraud precedents ($w=0.85, 0.80, 0.70$). $\text{balance} = 1.0 \implies \text{net\_w} = 0.85$. | $\text{net\_w} = 0.8500, P > 0.20$ | **PASS** |
| `test_fraud_majority_precedents` | 2 fraud ($0.80, 0.75$), 1 legit ($0.80$). $\text{balance} = +0.3333 \implies \text{net\_w} = 0.2667$. | $\text{net\_w} = 0.2667 > 0.0, P > 0.20$ | **PASS** |
| `test_balanced_precedents` | 1 fraud ($0.80$), 1 legit ($0.80$). $\text{balance} = 0.0 \implies \text{net\_w} = 0.0$. | $\text{net\_w} = 0.0000, P = 0.2000$ | **PASS** |
| `test_legitimate_majority_precedents` | 1 fraud ($0.80$), 2 legit ($0.80, 0.75$). $\text{balance} = -0.3333 \implies \text{net\_w} = -0.2667$. | $\text{net\_w} = -0.2667 < 0.0, P < 0.20$ | **PASS** |
| `test_unanimous_legitimate_precedents` | 3 legit precedents ($0.85, 0.80, 0.70$). $\text{balance} = -1.0 \implies \text{net\_w} = -0.85$. | $\text{net\_w} = -0.8500, P < 0.10$ | **PASS** |
| `test_correlated_case_protection` | 1 fraud precedent vs 10 fraud precedents (all $w=0.80$). Bounded by max weight. | Both $\text{net\_w} = 0.8000$, $P_1 = P_{10}$ | **PASS** |
| `test_similarity_still_matters` | 2:1 majority at high similarity ($0.90$) vs low similarity ($0.45$). | $P_{\text{high}} > P_{\text{low}}$ | **PASS** |
| `test_no_double_counting_across_groups` | 2:1 precedents + transaction attributes + device sharing in log-odds. | Distinct groups, $L = L_0 + 1.6 \sum w_g$ | **PASS** |

### Test Suite Execution:
- `tests/test_stage3_risk.py`: **37 / 37 passed** in 0.015s.
- `tests/test_stage1_foundation.py` through `tests/test_stage6_execution.py`: **218 / 218 passed** in 0.416s.

---

## 4. 20-Case Benchmark Impact Analysis

The complete 20-case benchmark (`python -m benchmark.runner`) was executed against the updated engine. 

### 4.1 Per-Case Benchmark Results (Before vs After)

| Case ID | Flagged Txn | Top Precedent Mix | Old Hist Net W | New Hist Net W | Old P | New P | Delta P | Old Final NBA | New Final NBA | NBA Shift |
|:---|:---|:---|---:|---:|---:|---:|---:|:---|:---|:---:|
| **HHG-001** | 3514030 | 3 Fraud / 0 Legit | +0.2268 | +0.2268 | 0.1133 | 0.1133 | +0.0000 | `CLOSE_NO_FRAUD` | `CLOSE_NO_FRAUD` | Identical |
| **HHG-002** | 3478782 | 3 Fraud / 0 Legit | +0.2293 | +0.2293 | 0.2523 | 0.2523 | +0.0000 | `VERIFY_WITH_CUSTOMER` | `VERIFY_WITH_CUSTOMER` | Identical |
| **HHG-003** | 3530164 | 2 Fraud / 1 Legit | **0.0000** | **+0.0756** | 0.1403 | **0.1556** | **+0.0153** | `CLOSE_NO_FRAUD` | **`ALLOW_TRANSACTION`** | **OVERTURNED** |
| **HHG-004** | 3583227 | 2 Fraud / 1 Legit | **0.0000** | **+0.0756** | 0.5559 | **0.5855** | +0.0296 | `STEP_UP_AUTH` | `STEP_UP_AUTH` | Elevated P |
| **HHG-005** | 3523199 | 3 Fraud / 0 Legit | +0.2268 | +0.2268 | 0.2728 | 0.2728 | +0.0000 | `VERIFY_WITH_CUSTOMER` | `VERIFY_WITH_CUSTOMER` | Identical |
| **HHG-006** | 3476682 | 2 Fraud / 1 Legit | +0.0479 | **+0.0764** | 0.3505 | **0.3610** | +0.0105 | `STEP_UP_AUTH` | `STEP_UP_AUTH` | Elevated P |
| **HHG-007** | 3514948 | 2 Fraud / 1 Legit | **0.0000** | **+0.0756** | 0.2049 | **0.2253** | +0.0204 | `VERIFY_WITH_CUSTOMER` | `VERIFY_WITH_CUSTOMER` | Elevated P |
| **HHG-008** | 3558054 | 3 Fraud / 0 Legit | +0.2268 | +0.2268 | 0.6428 | 0.6428 | +0.0000 | `STEP_UP_AUTH` | `STEP_UP_AUTH` | Identical |
| **HHG-009** | 3581141 | 2 Fraud / 1 Legit | +0.0479 | **+0.0764** | 0.3410 | **0.3513** | +0.0103 | `STEP_UP_AUTH` | `STEP_UP_AUTH` | Elevated P |
| **HHG-010** | 3506725 | 2 Fraud / 1 Legit | +0.0025 | **+0.0764** | 0.4408 | **0.4701** | +0.0293 | `STEP_UP_AUTH` | `STEP_UP_AUTH` | Elevated P |
| **HHG-011** | 3583368 | 3 Fraud / 0 Legit | +0.2268 | +0.2268 | 0.3800 | 0.3800 | +0.0000 | `STEP_UP_AUTH` | `STEP_UP_AUTH` | Identical |
| **HHG-012** | 3553342 | 2 Fraud / 1 Legit | +0.0025 | **+0.0764** | 0.0330 | **0.0370** | +0.0040 | `CLOSE_NO_FRAUD` | `CLOSE_NO_FRAUD` | Elevated P |
| **HHG-013** | 3526826 | 2 Fraud / 1 Legit | **0.0000** | **+0.0756** | 0.2021 | **0.2223** | +0.0202 | `VERIFY_WITH_CUSTOMER` | `VERIFY_WITH_CUSTOMER` | Elevated P |
| **HHG-014** | 3478561 | 2 Fraud / 1 Legit | +0.0479 | **+0.0764** | 0.0809 | **0.0844** | +0.0035 | `CLOSE_NO_FRAUD` | `CLOSE_NO_FRAUD` | Elevated P |
| **HHG-015** | 3464869 | 2 Fraud / 1 Legit | **0.0000** | **+0.0756** | 0.4011 | **0.4304** | +0.0293 | `STEP_UP_AUTH` | `STEP_UP_AUTH` | Elevated P |
| **HHG-016** | 3534820 | 2 Fraud / 1 Legit | +0.0479 | **+0.0764** | 0.5747 | **0.5858** | +0.0111 | `STEP_UP_AUTH` | `STEP_UP_AUTH` | Elevated P |
| **HHG-017** | 3450629 | 2 Fraud / 1 Legit | +0.0025 | **+0.0764** | 0.2076 | **0.2277** | +0.0201 | `VERIFY_WITH_CUSTOMER` | `VERIFY_WITH_CUSTOMER` | Elevated P |
| **HHG-018** | 3491361 | 2 Fraud / 1 Legit | **0.0000** | **+0.0756** | 0.1403 | **0.1556** | **+0.0153** | `CLOSE_NO_FRAUD` | **`ALLOW_TRANSACTION`** | **OVERTURNED** |
| **HHG-019** | 3503878 | 2 Fraud / 1 Legit | **0.0000** | **+0.0756** | 0.4398 | **0.4698** | +0.0300 | `STEP_UP_AUTH` | `STEP_UP_AUTH` | Elevated P |
| **HHG-020** | 3509359 | 3 Fraud / 0 Legit | +0.2293 | +0.2293 | 0.2736 | 0.2736 | +0.0000 | `VERIFY_WITH_CUSTOMER` | `VERIFY_WITH_CUSTOMER` | Identical |

---

### 4.2 Detailed Analysis of Key Benchmark Shifts

#### 1. HHG-003 and HHG-018: Premature Case Closures Overturned
- **Context**: In both cases, a customer reported an unauthorized transaction ($49.00 and $39.08).
- **The Defect**: Precedents consisted of 2 confirmed fraud cases ($w=0.2268$) and 1 cleared case ($w=0.2268$). Under the old formula, $0.2268 - 0.2268 = 0.0000$. The customer dispute signal ($+0.9800$) and neighborhood risk ($+0.6273$) were counterbalanced by low transaction scale ($-0.6000$), customer standing ($-0.7000$), and historical velocity stability ($-0.5737$). This left net log-odds at $-1.8125$ ($P = 0.1403$). Because $0.1403 \le 0.1500$, both cases triggered premature closure (`CLOSE_NO_FRAUD`).
- **The Fix**: Directional balance is now $(2 - 1)/3 = +0.3333$. Precedent contribution is $+0.3333 \times 0.2268 = \mathbf{+0.0756}$. Total delta log-odds increases by $+0.0756 \times 1.6 = \mathbf{+0.1210}$.
- **Result**: Net log-odds rises from $-1.8125 \to \mathbf{-1.6915}$, shifting probability from $0.1403 \to \mathbf{0.1556}$. This lifts both cases across the $0.1500$ threshold into the intermediate low-risk zone, changing the NBA recommendation from `CLOSE_NO_FRAUD` to **`ALLOW_TRANSACTION`** (which allows the transaction under active monitoring rather than dismissing the customer claim as "no fraud").

#### 2. The 14 Mixed-Precedent Cases
- In all 14 cases with 2:1 mixed precedents, the precedent contribution rose from $\le +0.0479 \to \mathbf{+0.0756}$ or $\mathbf{+0.0764}$.
- Fraud probability increased smoothly by $+0.0035$ to $+0.0300$ across all 14 cases, reflecting the empirical $67\%$ fraud majority among analogous historical transactions.

#### 3. Unanimous Precedent Cases (HHG-001, HHG-002, HHG-005, HHG-008, HHG-011, HHG-020)
- In cases with 3 fraud precedents and 0 cleared precedents, $\text{balance} = (3 - 0)/3 = 1.0$. The net weight remains exactly $\max(w) = +0.2268$ or $+0.2293$.
- Delta P is $+0.0000$, confirming mathematical consistency and preservation of unanimous precedent strength.

---

## 5. Aggregate Benchmark Metrics Comparison

| Metric | Baseline (Pre-Fix) | Current (Post-Fix) | Shift |
|:---|---:|---:|:---:|
| **Cases Processed** | 20 / 20 (100.0%) | 20 / 20 (100.0%) | Unchanged |
| **Cases Succeeded** | 20 / 20 (100.0%) | 20 / 20 (100.0%) | Unchanged |
| **Cases Failed** | 0 / 20 (0.0%) | 0 / 20 (0.0%) | Unchanged |
| **Investigation Completion** | 20 / 20 (100.0%) | 20 / 20 (100.0%) | Unchanged |
| **Policy Evaluation** | 20 / 20 (100.0%) | 20 / 20 (100.0%) | Unchanged |
| **Approval Routing** | 20 / 20 (100.0%) | 20 / 20 (100.0%) | Unchanged |
| **Execution Rate** | 20 / 20 (100.0%) | 20 / 20 (100.0%) | Unchanged |
| **Case Memory Writes** | 20 / 20 (100.0%) | 20 / 20 (100.0%) | Unchanged |
| **Minimum Probability** | 0.0330 | 0.0370 | +0.0040 |
| **Maximum Probability** | 0.6428 | 0.6428 | +0.0000 |
| **Mean Probability** | 0.3024 | 0.3148 | +0.0124 |
| **Median Probability** | 0.2732 | 0.2732 | +0.0000 |
| **Mean Confidence** | 0.5676 | 0.5676 | Unchanged |
| **Mean Uncertainty** | 0.4324 | 0.4324 | Unchanged |

### Action Distribution Shift:

| Recommended Action | Baseline Count | Post-Fix Count | Shift Details |
|:---|---:|---:|:---|
| `CLOSE_NO_FRAUD` | 5 | **3** | HHG-003 and HHG-018 vacated; only HHG-001, HHG-012, HHG-014 remain. |
| `ALLOW_TRANSACTION` | 0 | **2** | HHG-003 and HHG-018 entered low-intermediate monitored band ($P=0.1556$). |
| `VERIFY_WITH_CUSTOMER` | 6 | **6** | Stable across all 6 cases. |
| `STEP_UP_AUTH` | 9 | **9** | Stable across all 9 cases. |
| **Total** | 20 | 20 | |

---

## 6. Architecture Compliance & Quality Gate Summary

1. **Strict File Scope Adherence**:
   - Production modification: [`agent/risk/evaluator.py`](file:///c:/Users/prath/Drive/FraudDetection/agent/risk/evaluator.py) only.
   - Test addition: [`tests/test_stage3_risk.py`](file:///c:/Users/prath/Drive/FraudDetection/tests/test_stage3_risk.py) only.
   - Report: `benchmark/results/stage3_historical_precedent_fix_report.md`.
   - Untouched: `backend/`, `agent/nba/`, `agent/investigation/`, `backend/policy/`, `backend/execution/`, `tigergraph/`, `graphrag/`, `frontend/`.
2. **Quality Multipliers and Weights Preserved**:
   - `BASE_PRIOR_P0 = 0.20`, `BETA_EVIDENCE_SCALE = 1.6`.
   - Quality multipliers (`FACT`, `OBSERVATION`, `INFERENCE`, direct, untrusted) unaltered.
3. **No Branching on Benchmark IDs**:
   - Zero hardcoding of `HHG-` identifiers or specific transaction IDs in reasoning or evaluation modules.
4. **Single-Group Independence**:
   - `HISTORICAL_CASE` remains an isolated independent group with bounded contribution, preventing linear summation exploitation.
