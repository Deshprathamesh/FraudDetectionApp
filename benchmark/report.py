# ==============================================================================
# FraudGraph AI - Benchmark Report Generator
# Workstream: Benchmark Evaluation Harness
# ==============================================================================

import os
import csv
import json
from typing import Dict, Any, List
from benchmark.models import BenchmarkCaseResult


class BenchmarkReporter:
    """
    Generates structured output artifacts in benchmark/results/ matching
    Sections 20 and 21 of the Benchmark Specification.
    """

    def __init__(
        self,
        results: List[BenchmarkCaseResult],
        evaluation: Dict[str, Any],
        output_dir: str = "benchmark/results",
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.results = results
        self.evaluation = evaluation
        self.output_dir = output_dir
        self.metadata = metadata or {}
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_all(self) -> Dict[str, str]:
        """Generates all 4 required benchmark result files."""
        json_path = self.generate_json()
        csv_path = self.generate_csv()
        summary_path = self.generate_summary_md()
        errors_path = self.generate_errors_json()

        return {
            "json": json_path,
            "csv": csv_path,
            "summary_md": summary_path,
            "errors_json": errors_path,
        }

    def generate_json(self) -> str:
        """Writes benchmark/results/benchmark_results.json."""
        target_path = os.path.join(self.output_dir, "benchmark_results.json")
        payload = {
            "metadata": self.metadata,
            "evaluation": self.evaluation,
            "results": [r.model_dump() for r in self.results],
        }
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        return target_path

    def generate_csv(self) -> str:
        """Writes benchmark/results/benchmark_results.csv."""
        target_path = os.path.join(self.output_dir, "benchmark_results.csv")
        fieldnames = [
            "case_id",
            "transaction_id",
            "investigation_status",
            "fraud_probability",
            "confidence",
            "uncertainty",
            "detected_pattern",
            "expected_pattern",
            "initial_nba",
            "final_nba",
            "expected_action",
            "what_changed",
            "policy_permitted",
            "approval_level",
            "hitl_status",
            "execution_status",
            "simulated",
            "case_memory_status",
            "final_workflow_state",
            "failure_category",
        ]

        with open(target_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in self.results:
                writer.writerow({
                    "case_id": r.benchmark_case_id,
                    "transaction_id": r.transaction_id,
                    "investigation_status": r.investigation_status,
                    "fraud_probability": r.fraud_probability if r.fraud_probability is not None else "",
                    "confidence": r.confidence if r.confidence is not None else "",
                    "uncertainty": r.uncertainty if r.uncertainty is not None else "",
                    "detected_pattern": r.detected_pattern or "",
                    "expected_pattern": r.expected_pattern,
                    "initial_nba": r.initial_nba or "",
                    "final_nba": r.final_nba or "",
                    "expected_action": r.expected_action,
                    "what_changed": r.what_changed or "",
                    "policy_permitted": str(r.policy_permitted) if r.policy_permitted is not None else "",
                    "approval_level": r.approval_level or "",
                    "hitl_status": r.hitl_status or "",
                    "execution_status": r.execution_status or "",
                    "simulated": str(r.simulated),
                    "case_memory_status": r.case_memory_status or "",
                    "final_workflow_state": r.final_workflow_state or "",
                    "failure_category": r.failure_category or "",
                })
        return target_path

    def generate_errors_json(self) -> str:
        """Writes benchmark/results/benchmark_errors.json."""
        target_path = os.path.join(self.output_dir, "benchmark_errors.json")
        errors_list = []
        for r in self.results:
            if r.failure_category or r.errors:
                errors_list.append({
                    "benchmark_case_id": r.benchmark_case_id,
                    "transaction_id": r.transaction_id,
                    "failure_category": r.failure_category or "UNKNOWN",
                    "investigation_status": r.investigation_status,
                    "errors": r.errors,
                    "warnings": r.warnings,
                })

        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(errors_list, f, indent=2)
        return target_path

    def generate_summary_md(self) -> str:
        """Writes benchmark/results/benchmark_summary.md matching Section 21."""
        target_path = os.path.join(self.output_dir, "benchmark_summary.md")
        agg = self.evaluation.get("aggregate_metrics", {})
        risk = self.evaluation.get("risk_uncertainty", {})
        nba = self.evaluation.get("nba_analysis", {})
        fc = self.evaluation.get("failure_categories", {})

        p_stats = risk.get("fraud_probability", {})
        c_stats = risk.get("confidence", {})
        u_stats = risk.get("uncertainty", {})

        lines = [
            "# 20-CASE BENCHMARK SUMMARY",
            "",
            f"**Cases processed:** {agg.get('cases_processed', 0)}  ",
            f"**Cases succeeded:** {agg.get('cases_succeeded', 0)}  ",
            f"**Cases failed:** {agg.get('cases_failed', 0)}  ",
            "",
            f"**Investigation completion:** {agg.get('investigation_completion_count', 0)} / {agg.get('cases_processed', 0)} ({agg.get('investigation_completion_rate', 0.0) * 100:.1f}%)  ",
            f"**Pattern agreement:** {agg.get('pattern_match_rate')}  ",
            f"**NBA agreement:** {agg.get('nba_match_rate')}  ",
            "",
            f"**Policy evaluation:** {agg.get('policy_evaluation_completion_count', 0)} / {agg.get('cases_processed', 0)} ({agg.get('policy_evaluation_completion_rate', 0.0) * 100:.1f}%)  ",
            f"**Approval routing:** {agg.get('approval_routing_count', 0)} / {agg.get('cases_processed', 0)} ({agg.get('approval_routing_rate', 0.0) * 100:.1f}%)  ",
            "",
            f"**Execution:** {agg.get('execution_completion_count', 0)} / {agg.get('cases_processed', 0)} (SIMULATED EXECUTION)  ",
            f"**Case memory:** {agg.get('case_memory_success_count', 0)} / {agg.get('cases_processed', 0)}  ",
            "",
            f"**Risk probability summary:** min={p_stats.get('min')}, max={p_stats.get('max')}, mean={p_stats.get('mean')}, median={p_stats.get('median')}  ",
            f"**Confidence summary:** min={c_stats.get('min')}, max={c_stats.get('max')}, mean={c_stats.get('mean')}  ",
            f"**Uncertainty summary:** min={u_stats.get('min')}, max={u_stats.get('max')}, mean={u_stats.get('mean')}  ",
            "",
            f"**NBA changes:** {nba.get('cases_where_nba_changed', 0)} changed, {nba.get('cases_where_nba_unchanged', 0)} unchanged  ",
            "",
            "**Major failure categories:**",
        ]

        active_failures = {k: v for k, v in fc.items() if v > 0}
        if active_failures:
            for cat, count in active_failures.items():
                lines.append(f"- **{cat}**: {count}")
        else:
            lines.append("- None")

        lines.extend([
            "",
            "## Per-case table",
            "",
            "| Case | Transaction | Risk | Pattern | Final NBA | Policy | Approval | Execution | Memory |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ])

        for r in self.results:
            risk_str = f"{r.fraud_probability:.2f}" if r.fraud_probability is not None else "N/A"
            pat_str = r.detected_pattern or "None"
            nba_str = r.final_nba or "N/A"
            pol_str = "Permitted" if r.policy_permitted is True else ("Blocked" if r.policy_permitted is False else "N/A")
            appr_str = r.approval_level or "N/A"
            exec_str = r.execution_status or (r.failure_category if r.failure_category else "NOT_REACHED")
            mem_str = r.case_memory_status or "N/A"

            lines.append(f"| {r.benchmark_case_id} | {r.transaction_id} | {risk_str} | {pat_str} | {nba_str} | {pol_str} | {appr_str} | {exec_str} | {mem_str} |")

        lines.append("")

        with open(target_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return target_path
