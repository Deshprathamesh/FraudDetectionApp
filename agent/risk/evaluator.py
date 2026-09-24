# ==============================================================================
# FraudGraph AI - Risk & Uncertainty Evaluator
# Workstream: Person 1 (Brain) - Stage 3 Risk + Uncertainty Engine
# ==============================================================================

import math
import logging
from typing import Dict, Any, List, Optional, Tuple, Set
from backend.models.domain import (
    InvestigationResult,
    InvestigationStatus,
    RiskSignal,
    SignalDirection,
    IndependenceGroup,
    StoppingStatus,
    StoppingDecision,
    InformationGap,
)

logger = logging.getLogger("fraudgraph.risk_evaluator")


class RiskEvaluator:
    """
    Evaluates fraud probability, epistemic confidence, uncertainty,
    information gaps, and organizer stopping conditions from typed risk signals.

    Explicit Methodology:
    `heuristic_probability_estimate`

    Note: This is an explainable evidentiary aggregation model and is not
    claimed to be an empirically calibrated statistical probability.
    """

    METHODOLOGY = "heuristic_probability_estimate"

    # Heuristic base prior log-odds for transactions entering fraud investigation.
    # Assumes base prior P0 = 0.20 (L0 = ln(0.20 / 0.80) = -1.3863).
    # This reflects that flagged transactions are an enriched sample, but the
    # overwhelming majority of general transactions are non-fraud.
    BASE_PRIOR_P0 = 0.20
    BASE_PRIOR_L0 = math.log(BASE_PRIOR_P0 / (1.0 - BASE_PRIOR_P0))

    # Evidence aggregation scaling factor
    BETA_EVIDENCE_SCALE = 1.6

    def __init__(self):
        pass

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

    def compute_fraud_probability(
        self,
        signals: List[RiskSignal],
        base_prior: Optional[float] = None,
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Computes heuristic fraud probability using independent evidence group aggregation.

        Guarantees:
        - Prevents double-counting within the same IndependenceGroup (takes net dominant weight).
        - Monotonic: adding independent fraud signals increases probability.
        - Monotonic: adding independent legitimate signals decreases probability.
        - Strictly bounded to [0.01, 0.99].
        - Raw risk score does NOT dominate (it is one signal in TRANSACTION_ATTRIBUTES).
        """
        p0 = base_prior if base_prior is not None else self.BASE_PRIOR_P0
        # Clamp prior to valid probability
        p0 = max(0.05, min(0.50, p0))
        l0 = math.log(p0 / (1.0 - p0))

        # Group signals by IndependenceGroup
        group_signals: Dict[IndependenceGroup, List[RiskSignal]] = {}
        for s in signals:
            group_signals.setdefault(s.independence_group, []).append(s)

        group_weights: Dict[str, float] = {}
        total_delta_l = 0.0

        for grp, sig_list in group_signals.items():
            # Net contribution of this independent group
            net_group_w = self._compute_group_net_weight(grp, sig_list)
            group_weights[grp.value] = net_group_w
            total_delta_l += net_group_w * self.BETA_EVIDENCE_SCALE

        l_final = l0 + total_delta_l
        # Sigmoid mapping to [0.01, 0.99]
        prob = 1.0 / (1.0 + math.exp(-l_final))
        bounded_prob = round(max(0.01, min(0.99, prob)), 4)

        breakdown = {
            "methodology": self.METHODOLOGY,
            "base_prior": p0,
            "group_net_weights": group_weights,
            "total_log_odds": round(l_final, 4),
            "raw_probability": bounded_prob,
        }

        return bounded_prob, breakdown

    def compute_confidence(
        self,
        signals: List[RiskSignal],
        fraud_probability: float,
        investigation: Optional[InvestigationResult] = None,
    ) -> float:
        """
        Computes epistemic confidence in the fraud probability estimate.

        Confidence measures evidence corroboration, NOT fraud risk:
        - Corroboration: how many independent groups support the prevailing verdict.
        - Quality: higher fact level and direct evidence yields higher confidence.
        - Contradiction: presence of conflicting signals penalizes confidence.
        - Completeness: warnings and partial investigation outages penalize confidence.
        - Bounded to [0.05, 0.98].
        """
        # Determine prevailing direction
        is_fraud_dominant = fraud_probability >= 0.50

        # Tally independent groups supporting prevailing vs opposing
        group_signals: Dict[IndependenceGroup, List[RiskSignal]] = {}
        for s in signals:
            group_signals.setdefault(s.independence_group, []).append(s)

        supporting_groups = 0
        opposing_groups = 0
        total_supporting_weight = 0.0
        total_opposing_weight = 0.0

        for grp, sig_list in group_signals.items():
            net_w = self._compute_group_net_weight(grp, sig_list)

            if is_fraud_dominant:
                if net_w > 0.10:
                    supporting_groups += 1
                    total_supporting_weight += net_w
                elif net_w < -0.10:
                    opposing_groups += 1
                    total_opposing_weight += abs(net_w)
            else:
                if net_w < -0.10:
                    supporting_groups += 1
                    total_supporting_weight += abs(net_w)
                elif net_w > 0.10:
                    opposing_groups += 1
                    total_opposing_weight += net_w

        # Base confidence from independent corroboration count
        if supporting_groups == 0:
            base_conf = 0.25
        elif supporting_groups == 1:
            base_conf = 0.48 # Single source cannot exceed 0.50 confidence
        elif supporting_groups == 2:
            base_conf = 0.75 # >= 2 independent sources achieves solid confidence
        elif supporting_groups == 3:
            base_conf = 0.86
        else:
            base_conf = 0.94

        # Weight bonus based on evidence quality
        avg_supp_weight = (total_supporting_weight / supporting_groups) if supporting_groups > 0 else 0.5
        conf = base_conf * (0.85 + 0.15 * avg_supp_weight)

        # Contradiction penalty
        if opposing_groups > 0 and total_supporting_weight > 0:
            conflict_ratio = total_opposing_weight / (total_supporting_weight + total_opposing_weight)
            conflict_penalty = min(0.30, conflict_ratio * 0.40)
            conf -= conflict_penalty

        # Partial failure / investigation completeness penalty
        if investigation is not None:
            if investigation.status == InvestigationStatus.PARTIAL or investigation.warnings:
                conf -= 0.15
            elif investigation.status == InvestigationStatus.FAILED:
                conf = 0.10

        return round(max(0.05, min(0.98, conf)), 4)

    def compute_uncertainty(self, confidence: float) -> float:
        """
        Computes epistemic uncertainty as the direct complement of confidence:
        uncertainty = 1.0 - confidence.
        """
        unc = 1.0 - confidence
        return round(max(0.0, min(1.0, unc)), 4)

    def identify_information_gaps(
        self,
        investigation: InvestigationResult,
        signals: List[RiskSignal],
        confidence: float,
        fraud_probability: float,
    ) -> List[InformationGap]:
        """
        Identifies missing context, sparse data, or uncorroborated signals
        that could materially influence the investigation conclusion.
        """
        gaps: List[InformationGap] = []

        # 1. Customer profile gap
        if not investigation.customer:
            gaps.append(
                InformationGap(
                    gap_id="GAP-CUST-01",
                    gap_type="MISSING_CUSTOMER_PROFILE",
                    description="Customer profile and KYC record could not be resolved.",
                    affected_conclusion="Unable to assess customer baseline risk tier or verify account ownership.",
                    severity="HIGH",
                    evidence_currently_available="Transaction record only.",
                    material_impact=True,
                    impact_score=0.8,
                )
            )

        # 2. Transaction history baseline gap
        history_count = len(investigation.transaction_history or [])
        if history_count < 3:
            gaps.append(
                InformationGap(
                    gap_id="GAP-HIST-01",
                    gap_type="SPARSE_TRANSACTION_HISTORY",
                    description=f"Transaction history is sparse ({history_count} record(s) available).",
                    affected_conclusion="Unable to establish long-term spending patterns or velocity baseline.",
                    severity="MEDIUM",
                    evidence_currently_available=f"{history_count} historical transaction(s).",
                    material_impact=True,
                    impact_score=0.5,
                )
            )

        # 3. Single-source corroboration gap
        supporting_fraud = set(s.independence_group for s in signals if s.direction == SignalDirection.SUPPORTS_FRAUD)
        supporting_legit = set(s.independence_group for s in signals if s.direction == SignalDirection.SUPPORTS_LEGITIMATE)
        prevailing_groups = supporting_fraud if fraud_probability >= 0.50 else supporting_legit

        if len(prevailing_groups) < 2 and (fraud_probability >= 0.70 or fraud_probability <= 0.30):
            gaps.append(
                InformationGap(
                    gap_id="GAP-CORR-01",
                    gap_type="UNCORROBORATED_EVIDENCE",
                    description=f"Conclusion is supported by only {len(prevailing_groups)} independent evidence group.",
                    affected_conclusion="Requires secondary independent evidence corroboration to satisfy stopping criteria.",
                    severity="HIGH",
                    evidence_currently_available=", ".join(g.value for g in prevailing_groups),
                    material_impact=True,
                    impact_score=0.7,
                )
            )

        # 4. Contradictory evidence gap
        if len(supporting_fraud) > 0 and len(supporting_legit) > 0:
            if any(s.weight >= 0.70 for s in signals if s.direction == SignalDirection.SUPPORTS_FRAUD) and \
               any(s.weight >= 0.70 for s in signals if s.direction == SignalDirection.SUPPORTS_LEGITIMATE):
                gaps.append(
                    InformationGap(
                        gap_id="GAP-CONFLICT-01",
                        gap_type="CONTRADICTORY_EVIDENCE",
                        description="High-weight evidence points in contradictory directions.",
                        affected_conclusion="Contradiction between fraud signals and established legitimacy history.",
                        severity="HIGH",
                        evidence_currently_available="Both fraud patterns and customer legitimacy signals present.",
                        material_impact=True,
                        impact_score=0.6,
                    )
                )

        # 5. Partial failure gap
        if investigation.status == InvestigationStatus.PARTIAL:
            gaps.append(
                InformationGap(
                    gap_id="GAP-PARTIAL-01",
                    gap_type="PARTIAL_INVESTIGATION_WARNINGS",
                    description=f"Investigation completed with {len(investigation.warnings)} auxiliary component warning(s).",
                    affected_conclusion="Auxiliary query outage may conceal relevant graph or precedent context.",
                    severity="MEDIUM",
                    evidence_currently_available="; ".join(investigation.warnings[:2]),
                    material_impact=False,
                    impact_score=0.4,
                )
            )

        # 6. Customer verification gap (when in intermediate uncertain zone)
        has_verification = any(s.independence_group == IndependenceGroup.CUSTOMER_VERIFICATION for s in signals)
        if not has_verification and 0.20 <= fraud_probability <= 0.80:
            gaps.append(
                InformationGap(
                    gap_id="GAP-VERIF-01",
                    gap_type="UNVERIFIED_CUSTOMER_INQUIRY",
                    description="No direct customer or cardholder verification response on record.",
                    affected_conclusion="Customer confirmation or denial could definitively settle transaction validity.",
                    severity="HIGH",
                    evidence_currently_available="Inferred signals from graph and profile without cardholder response.",
                    material_impact=True,
                    impact_score=0.7,
                )
            )

        return gaps

    def evaluate_stopping(
        self,
        fraud_probability: float,
        confidence: float,
        signals: List[RiskSignal],
        investigation: InvestigationResult,
        gaps: List[InformationGap],
    ) -> StoppingDecision:
        """
        Evaluates organizer-defined stopping conditions.

        Stopping Rules:
        1. Fraud probability is >= 0.85 OR <= 0.15,
           AND conclusion is supported by at least two independent evidence groups.
        2. A verification response settles the question.
        3. Investigation is blocked due to critical tool failure.
        4. Otherwise: MORE_EVIDENCE_REQUIRED (or INCONCLUSIVE if no material gaps remain).
        """
        # Count independent groups supporting prevailing conclusion
        is_fraud = fraud_probability >= 0.50
        supporting_groups: Set[IndependenceGroup] = set()

        for s in signals:
            if is_fraud and s.direction == SignalDirection.SUPPORTS_FRAUD and s.weight >= 0.35:
                supporting_groups.add(s.independence_group)
            elif not is_fraud and s.direction == SignalDirection.SUPPORTS_LEGITIMATE and s.weight >= 0.35:
                supporting_groups.add(s.independence_group)

        indep_count = len(supporting_groups)

        # Check Rule 3: Investigation Blocked
        if investigation.status == InvestigationStatus.FAILED or any(
            "offline" in w.lower() or "connection refused" in w.lower() for w in investigation.warnings
        ):
            return StoppingDecision(
                status=StoppingStatus.INVESTIGATION_BLOCKED,
                reason="Investigation blocked: critical data sources unavailable.",
                fraud_probability=fraud_probability,
                confidence=confidence,
                independent_evidence_count=indep_count,
                condition_met="CRITICAL_DEPENDENCY_OUTAGE",
                missing_information=list(investigation.warnings) or ["Primary data source offline"],
                recommended_next_query=None,
            )

        # Check Rule 2: Verification response settles question
        has_verification_signal = any(
            s.independence_group == IndependenceGroup.CUSTOMER_VERIFICATION for s in signals
        )
        if has_verification_signal:
            verif_signal = next(s for s in signals if s.independence_group == IndependenceGroup.CUSTOMER_VERIFICATION)
            outcome = "fraud" if verif_signal.direction == SignalDirection.SUPPORTS_FRAUD else "legitimate"
            return StoppingDecision(
                status=StoppingStatus.SUFFICIENT_EVIDENCE,
                reason=f"Customer verification settled: customer verification response directly confirms {outcome} status.",
                fraud_probability=fraud_probability,
                confidence=confidence,
                independent_evidence_count=indep_count,
                condition_met="VERIFICATION_SETTLED",
                missing_information=[],
                recommended_next_query=None,
            )

        # Check Rule 1: High/Low Probability + >= 2 independent evidence groups
        if (fraud_probability >= 0.85 or fraud_probability <= 0.15):
            if indep_count >= 2:
                prefix = "High fraud probability" if fraud_probability >= 0.85 else "Low fraud probability"
                verdict_str = "fraudulent" if fraud_probability >= 0.85 else "legitimate"
                return StoppingDecision(
                    status=StoppingStatus.SUFFICIENT_EVIDENCE,
                    reason=f"{prefix} ({fraud_probability:.2f}) indicates {verdict_str} activity, supported by {indep_count} independent evidence groups ({', '.join(g.value for g in supporting_groups)}).",
                    fraud_probability=fraud_probability,
                    confidence=confidence,
                    independent_evidence_count=indep_count,
                    condition_met="PROBABILITY_AND_INDEPENDENT_EVIDENCE_THRESHOLD",
                    missing_information=[],
                    recommended_next_query=None,
                )
            else:
                # Threshold reached but lacks required corroboration!
                missing_info = [g.description for g in gaps if g.material_impact] or ["Secondary independent corroborating evidence group"]
                next_q = "customer_verification" if any(getattr(g, "gap_type", None) == "UNVERIFIED_CUSTOMER_INQUIRY" for g in gaps) else "graph_traversal"
                return StoppingDecision(
                    status=StoppingStatus.MORE_EVIDENCE_REQUIRED,
                    reason=f"Fraud probability ({fraud_probability:.2f}) reached extreme range, but lacks >= 2 independent corroborating groups (supported by only {indep_count} independent evidence group; minimum 2 required).",
                    fraud_probability=fraud_probability,
                    confidence=confidence,
                    independent_evidence_count=indep_count,
                    condition_met=None,
                    missing_information=missing_info,
                    recommended_next_query=next_q,
                )

        # Check intermediate range
        material_gaps = [g for g in gaps if g.material_impact]
        if material_gaps:
            next_q = "customer_verification" if any(getattr(g, "gap_type", None) == "UNVERIFIED_CUSTOMER_INQUIRY" for g in gaps) else (
                "transaction_history" if any(getattr(g, "gap_type", None) == "SPARSE_TRANSACTION_HISTORY" for g in gaps) else "graph_traversal"
            )
            return StoppingDecision(
                status=StoppingStatus.MORE_EVIDENCE_REQUIRED,
                reason=f"Intermediate fraud probability ({fraud_probability:.2f}) with {len(material_gaps)} material information gap(s) remaining.",
                fraud_probability=fraud_probability,
                confidence=confidence,
                independent_evidence_count=indep_count,
                condition_met=None,
                missing_information=[g.description for g in material_gaps],
                recommended_next_query=next_q,
            )

        # Intermediate with all available sources exhausted
        return StoppingDecision(
            status=StoppingStatus.INCONCLUSIVE,
            reason=f"Intermediate fraud probability ({fraud_probability:.2f}) remains indeterminate with all available evidence exhausted.",
            fraud_probability=fraud_probability,
            confidence=confidence,
            independent_evidence_count=indep_count,
            condition_met="FURTHER_EVIDENCE_UNLIKELY_TO_CHANGE",
            missing_information=[],
            recommended_next_query=None,
        )


# Global singleton instance
risk_evaluator = RiskEvaluator()
