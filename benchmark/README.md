# FraudGraph AI — Benchmark Evaluation Harness

**Workstream:** Shared Evaluation Suite  
**Objective:** Independent, reproducible 20-case benchmark evaluation for FraudGraph AI across Stages 1–6.

---

## 1. Structure

```text
benchmark/
├── __init__.py          # Package initialization
├── models.py            # Typed BenchmarkCase and BenchmarkCaseResult schemas
├── runner.py            # Pipeline execution harness calling public engine interfaces
├── evaluator.py         # Metrics computation (Sections 11–18)
├── report.py            # Result artifact generator (Sections 20–21)
├── data/
│   └── case_pack.csv    # Authoritative 20-case benchmark dataset from organizer
└── results/
    ├── benchmark_results.json   # Full structured execution results
    ├── benchmark_results.csv    # Per-case tabular summary
    ├── benchmark_summary.md     # Markdown executive summary
    └── benchmark_errors.json    # Structured error details
```

---

## 2. Invariants & Rules

1. **Production Pipeline Integrity**: The runner invokes the exact production engines (`investigation_engine`, `risk_uncertainty_service`, `nba_service`, `policy_evaluator`, `action_executor`, `case_memory_adapter`). No benchmark-specific shortcuts, tuning, or heuristics are implemented.
2. **No Data Leakage**: Ground truth is never inferred or fabricated. If not in the source file, fields report `NOT PROVIDED`.
3. **Execution Safety**: All action executions are strictly flagged with `simulated = True`. Zero real-world financial or switch operations occur.
4. **Frozen Boundaries**: `tigergraph/`, `graphrag/`, `data/`, and `frontend/` remain completely untouched. `Information/` remains ignored.

---

## 3. Running the Benchmark

```bash
python -m benchmark.runner
```
