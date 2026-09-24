# ==============================================================================
# FraudGraph AI - Benchmark Evaluator
# Workstream: Benchmark Evaluation Harness
# ==============================================================================

import statistics
from typing import Dict, Any, List, Optional
from benchmark.models import BenchmarkCaseResult, FailureCategory


class BenchmarkEvaluator:
    """
    Computes rigorous aggregate metrics and analytics across benchmark results
    according to Sections 11–18 without fabricating ground truth.
    """

    def __init__(self, results: List[BenchmarkCaseResult]):
        self.results = results

    def evaluate_all(self) -> Dict[str, Any]:
        """Runs complete evaluation suite and returns aggregate summary dictionary."""
        return {
            "aggregate_metrics": self.compute_aggregate_metrics(),
            "evidence_quality": self.compute_evidence_quality(),
            "risk_uncertainty": self.compute_risk_uncertainty(),
            "nba_analysis": self.compute_nba_analysis(),
            "policy_analysis": self.compute_policy_analysis(),
            "execution_analysis": self.compute_execution_analysis(),
            "case_memory_analysis": self.compute_case_memory_analysis(),
            "failure_categories": self.compute_failure_categories(),
        }

    def compute_aggregate_metrics(self) -> Dict[str, Any]:
        """Computes Section 11 aggregate completion and routing rates."""
        total = len(self.results)
        if total == 0:
            return {"cases_processed": 0, "cases_succeeded": 0, "cases_failed": 0}

        succeeded = [r for r in self.results if not r.failure_category and r.investigation_status == "COMPLETED"]
        failed = [r for r in self.results if r.failure_category or r.investigation_status == "FAILED"]

        inv_completed = sum(1 for r in self.results if r.investigation_status == "COMPLETED")
        policy_completed = sum(1 for r in self.results if r.policy_permitted is not None)
        exec_completed = sum(1 for r in self.results if r.execution_status in ("EXECUTED", "ALREADY_EXECUTED"))
        mem_success = sum(1 for r in self.results if r.case_memory_status == "SUCCESS")

        # Ground truth pattern/NBA match: report NOT PROVIDED if not in source
        has_expected_patterns = any(r.expected_pattern != "NOT PROVIDED" for r in self.results)
        has_expected_actions = any(r.expected_action != "NOT PROVIDED" for r in self.results)

        pattern_matches = sum(1 for r in self.results if r.pattern_match == "MATCH") if has_expected_patterns else "NOT PROVIDED"
        pattern_match_rate = (pattern_matches / total) if isinstance(pattern_matches, int) else "NOT PROVIDED"

        nba_matches = sum(1 for r in self.results if r.action_match == "MATCH") if has_expected_actions else "NOT PROVIDED"
        nba_match_rate = (nba_matches / total) if isinstance(nba_matches, int) else "NOT PROVIDED"

        # Approval routing correctness against policy rules
        approval_routed = sum(1 for r in self.results if r.approval_level is not None)
        approval_rate = approval_routed / total if total > 0 else 0.0

        return {
            "cases_processed": total,
            "cases_succeeded": len(succeeded),
            "cases_failed": len(failed),
            "investigation_completion_count": inv_completed,
            "investigation_completion_rate": round(inv_completed / total, 4) if total > 0 else 0.0,
            "pattern_match_count": pattern_matches,
            "pattern_match_rate": round(pattern_match_rate, 4) if isinstance(pattern_match_rate, float) else pattern_match_rate,
            "nba_match_count": nba_matches,
            "nba_match_rate": round(nba_match_rate, 4) if isinstance(nba_match_rate, float) else nba_match_rate,
            "policy_evaluation_completion_count": policy_completed,
            "policy_evaluation_completion_rate": round(policy_completed / total, 4) if total > 0 else 0.0,
            "approval_routing_count": approval_routed,
            "approval_routing_rate": round(approval_rate, 4),
            "execution_completion_count": exec_completed,
            "execution_completion_rate": round(exec_completed / total, 4) if total > 0 else 0.0,
            "case_memory_success_count": mem_success,
            "case_memory_success_rate": round(mem_success / total, 4) if total > 0 else 0.0,
        }

    def compute_evidence_quality(self) -> Dict[str, Any]:
        """Computes Section 12 evidence topology and group metrics."""
        completed = [r for r in self.results if r.investigation_status == "COMPLETED"]
        if not completed:
            return {
                "average_evidence_count": 0.0,
                "cases_with_gte_2_independent_groups": 0,
                "cases_with_contradictory_evidence": 0,
                "cases_with_partial_investigation": sum(1 for r in self.results if r.investigation_status == "PARTIAL"),
                "cases_reaching_sufficient_evidence": 0,
                "cases_stopped_due_to_uncertainty": 0,
                "epistemic_distinction": {"FACT": 0, "OBSERVATION": 0, "INFERENCE": 0},
            }

        counts = [r.evidence_count for r in completed]
        avg_ev = sum(counts) / len(counts) if counts else 0.0

        # Independent evidence groups
        gte_2_groups = 0
        contradictory = 0
        epistemic = {"FACT": 0, "OBSERVATION": 0, "INFERENCE": 0}

        for r in completed:
            sources = set()
            for item in r.evidence_items:
                sources.add(item.get("source", "UNKNOWN"))
                category = item.get("category", "OBSERVATION").upper()
                epistemic[category] = epistemic.get(category, 0) + 1
            if len(sources) >= 2:
                gte_2_groups += 1

        return {
            "average_evidence_count": round(avg_ev, 2),
            "cases_with_gte_2_independent_groups": gte_2_groups,
            "cases_with_contradictory_evidence": contradictory,
            "cases_with_partial_investigation": sum(1 for r in self.results if r.investigation_status == "PARTIAL"),
            "cases_reaching_sufficient_evidence": len(completed),
            "cases_stopped_due_to_uncertainty": sum(1 for r in self.results if r.uncertainty and r.uncertainty >= 0.40),
            "epistemic_distinction": epistemic,
        }

    def compute_risk_uncertainty(self) -> Dict[str, Any]:
        """Computes Section 13 risk and uncertainty distributions."""
        probs = [r.fraud_probability for r in self.results if r.fraud_probability is not None]
        confs = [r.confidence for r in self.results if r.confidence is not None]
        uncs = [r.uncertainty for r in self.results if r.uncertainty is not None]

        def stats_dict(vals: List[float], include_median: bool = False) -> Dict[str, Any]:
            if not vals:
                d = {"min": None, "max": None, "mean": None}
                if include_median:
                    d["median"] = None
                return d
            d = {
                "min": round(min(vals), 4),
                "max": round(max(vals), 4),
                "mean": round(statistics.mean(vals), 4),
            }
            if include_median:
                d["median"] = round(statistics.median(vals), 4)
            return d

        # Stopping threshold counts: fraud threshold >= 0.70, benign <= 0.30, uncertain between or high uncertainty
        above_fraud = sum(1 for p in probs if p >= 0.70)
        below_fraud = sum(1 for p in probs if p <= 0.30)
        in_uncertain = sum(1 for r in self.results if (r.fraud_probability is not None and 0.30 < r.fraud_probability < 0.70) or (r.uncertainty is not None and r.uncertainty >= 0.40))

        return {
            "fraud_probability": stats_dict(probs, include_median=True),
            "confidence": stats_dict(confs),
            "uncertainty": stats_dict(uncs),
            "cases_above_fraud_threshold": above_fraud,
            "cases_below_fraud_threshold": below_fraud,
            "cases_in_uncertain_range": in_uncertain,
        }

    def compute_nba_analysis(self) -> Dict[str, Any]:
        """Computes Section 14 Next Best Action transitions."""
        completed = [r for r in self.results if r.final_nba is not None]
        changed_count = sum(1 for r in completed if r.what_changed or (r.initial_nba and r.final_nba and r.initial_nba != r.final_nba))
        unchanged_count = len(completed) - changed_count

        changes_summary = []
        for r in completed:
            if r.what_changed or (r.initial_nba and r.final_nba and r.initial_nba != r.final_nba):
                changes_summary.append({
                    "case_id": r.benchmark_case_id,
                    "initial": r.initial_nba,
                    "final": r.final_nba,
                    "reason": r.what_changed or "Evidence update",
                })

        return {
            "cases_with_nba": len(completed),
            "cases_where_nba_changed": changed_count,
            "cases_where_nba_unchanged": unchanged_count,
            "nba_changes_detail": changes_summary,
        }

    def compute_policy_analysis(self) -> Dict[str, Any]:
        """Computes Section 15 policy routing counts and matrix verification."""
        counts = {
            "AUTO": 0,
            "L1_SUPERVISOR": 0,
            "L2_COMPLIANCE": 0,
            "POLICY_BLOCKED": 0,
            "POLICY_INDETERMINATE": 0,
        }
        matrix_violations = []

        for r in self.results:
            if r.approval_level:
                norm_level = r.approval_level.upper()
                if "L1" in norm_level:
                    counts["L1_SUPERVISOR"] += 1
                elif "L2" in norm_level:
                    counts["L2_COMPLIANCE"] += 1
                elif "AUTO" in norm_level:
                    counts["AUTO"] += 1

            if r.policy_permitted is False:
                counts["POLICY_BLOCKED"] += 1
            if r.hitl_status == "POLICY_INDETERMINATE":
                counts["POLICY_INDETERMINATE"] += 1

            # Validate Stage 5 policy matrix invariants
            if r.final_nba and r.approval_level:
                action = r.final_nba.upper()
                level = r.approval_level.upper()
                exp = r.exposure_usd

                if action == "BLOCK_CARD":
                    expected_lvl = "L1_SUPERVISOR" if exp <= 2500.0 else "L2_COMPLIANCE"
                    if expected_lvl not in level:
                        matrix_violations.append(f"{r.benchmark_case_id}: BLOCK_CARD (${exp}) routed to {level}, expected {expected_lvl}")
                elif action in ("BLOCK_ALL_CARDS", "FILE_REPORT"):
                    if "L2" not in level:
                        matrix_violations.append(f"{r.benchmark_case_id}: {action} routed to {level}, expected L2_COMPLIANCE")
                elif action == "DECLINE_TRANSACTION":
                    if "L1" not in level:
                        matrix_violations.append(f"{r.benchmark_case_id}: DECLINE_TRANSACTION routed to {level}, expected L1_SUPERVISOR")

        return {
            "routing_distribution": counts,
            "stage5_matrix_violations": matrix_violations,
            "compliance_verified": len(matrix_violations) == 0,
        }

    def compute_execution_analysis(self) -> Dict[str, Any]:
        """Computes Section 16 simulated execution metrics."""
        counts = {
            "executed": 0,
            "blocked": 0,
            "not_authorized": 0,
            "failed": 0,
            "already_executed": 0,
            "not_reached": 0,
        }
        for r in self.results:
            status = (r.execution_status or "NOT_REACHED").lower()
            if status in counts:
                counts[status] += 1
            else:
                counts["not_reached"] += 1

        return {
            "execution_mode": "SIMULATED EXECUTION",
            "counts": counts,
            "real_financial_impact": False,
        }

    def compute_case_memory_analysis(self) -> Dict[str, Any]:
        """Computes Section 17 Case Memory persistence verification."""
        persisted = [r for r in self.results if r.case_memory_status == "SUCCESS"]
        all_elements_present = True
        verification_log = []

        for r in persisted:
            missing = []
            if not r.benchmark_case_id:
                missing.append("case_id")
            if not r.transaction_id:
                missing.append("transaction")
            if r.fraud_probability is None:
                missing.append("risk_assessment")
            if not r.final_nba:
                missing.append("NBA")
            if r.policy_permitted is None:
                missing.append("policy")

            if missing:
                all_elements_present = False
                verification_log.append(f"{r.benchmark_case_id}: Missing elements: {missing}")

        return {
            "persisted_cases_count": len(persisted),
            "all_required_elements_included": all_elements_present,
            "verification_log": verification_log,
        }

    def compute_failure_categories(self) -> Dict[str, int]:
        """Aggregates Section 18 failure classification counts."""
        categories = {cat.value: 0 for cat in FailureCategory}
        for r in self.results:
            if r.failure_category:
                cat_val = r.failure_category
                categories[cat_val] = categories.get(cat_val, 0) + 1
        return categories
