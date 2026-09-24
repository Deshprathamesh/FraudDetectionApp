# ==============================================================================
# FraudGraph AI - Risk & Uncertainty Service
# Workstream: Person 1 (Brain) - Stage 3 Risk + Uncertainty Engine
# ==============================================================================

import time
import logging
from typing import Dict, Any, List, Optional
from backend.models.domain import (
    InvestigationResult,
    RiskAssessment,
    RiskLevel,
    SignalDirection,
    IndependenceGroup,
)
from agent.risk.signals import signal_extractor, SignalExtractor
from agent.risk.evaluator import risk_evaluator, RiskEvaluator

logger = logging.getLogger("fraudgraph.risk_service")


class RiskUncertaintyService:
    """
    High-level orchestrator for Stage 3 Risk & Uncertainty assessment.
    Consumes Stage 2 InvestigationResult and outputs an explainable,
    evidence-grounded RiskAssessment.

    Strict Boundary:
    Answers: "HOW RISKY / HOW CERTAIN IS THIS BASED ON THE EVIDENCE?"
    Does NOT answer: "WHAT SHOULD WE DO?" or "ARE WE ALLOWED TO DO IT?"
    """

    def __init__(
        self,
        extractor: Optional[SignalExtractor] = None,
        evaluator: Optional[RiskEvaluator] = None,
    ):
        self._extractor = extractor or signal_extractor
        self._evaluator = evaluator or risk_evaluator

    def assess(
        self,
        investigation: InvestigationResult,
        trigger: Optional[Dict[str, Any]] = None,
    ) -> RiskAssessment:
        """
        Executes end-to-end signal extraction, probability estimation,
        epistemic confidence scoring, uncertainty derivation, gap analysis,
        and organizer stopping evaluation.
        """
        # 1. Signal Extraction (Zero re-querying of Person 2)
        signals = self._extractor.extract_signals(investigation)

        # 2. Partition signals by direction
        supporting = [s for s in signals if s.direction == SignalDirection.SUPPORTS_FRAUD]
        contradicting = [s for s in signals if s.direction == SignalDirection.SUPPORTS_LEGITIMATE]
        neutral = [s for s in signals if s.direction == SignalDirection.NEUTRAL]

        # 3. Compute Fraud Probability (Heuristic evidentiary aggregation)
        fraud_prob, breakdown = self._evaluator.compute_fraud_probability(signals)

        # 4. Compute Epistemic Confidence
        confidence = self._evaluator.compute_confidence(
            signals=signals,
            fraud_probability=fraud_prob,
            investigation=investigation,
        )

        # 5. Compute Epistemic Uncertainty
        uncertainty = self._evaluator.compute_uncertainty(confidence)

        # 6. Identify Information Gaps
        gaps = self._evaluator.identify_information_gaps(
            investigation=investigation,
            signals=signals,
            confidence=confidence,
            fraud_probability=fraud_prob,
        )

        # 7. Evaluate Organizer Stopping Conditions
        stopping = self._evaluator.evaluate_stopping(
            fraud_probability=fraud_prob,
            confidence=confidence,
            signals=signals,
            investigation=investigation,
            gaps=gaps,
        )

        # 8. Categorical Risk Level
        if fraud_prob >= 0.85:
            risk_level = RiskLevel.CRITICAL
        elif fraud_prob >= 0.70:
            risk_level = RiskLevel.HIGH
        elif fraud_prob >= 0.30:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW

        # 9. Independent evidence groups count
        indep_groups_seen = set(s.independence_group for s in signals)

        # 10. Generate Traceable Reasoning Narrative
        reasoning = self._generate_reasoning_summary(
            fraud_prob=fraud_prob,
            confidence=confidence,
            uncertainty=uncertainty,
            risk_level=risk_level,
            supporting=supporting,
            contradicting=contradicting,
            gaps=gaps,
            stopping=stopping,
            investigation=investigation,
        )

        # Factors list for backward compatibility
        factors = [s.description for s in sorted(supporting + contradicting, key=lambda x: x.weight, reverse=True)[:5]]

        return RiskAssessment(
            fraud_probability=fraud_prob,
            risk_score=investigation.transaction.get("risk_score", fraud_prob) if investigation.transaction else fraud_prob,
            risk_level=risk_level,
            confidence=confidence,
            uncertainty=uncertainty,
            evidence_count=len(investigation.evidence),
            independent_evidence_count=len(indep_groups_seen),
            supporting_signals=supporting,
            contradicting_signals=contradicting,
            neutral_signals=neutral,
            signal_breakdown=breakdown,
            stopping_decision=stopping,
            information_gaps=gaps,
            reasoning_summary=reasoning,
            methodology=RiskEvaluator.METHODOLOGY,
            factors=factors,
            timestamp=int(time.time()),
        )

    def _generate_reasoning_summary(
        self,
        fraud_prob: float,
        confidence: float,
        uncertainty: float,
        risk_level: RiskLevel,
        supporting: List[Any],
        contradicting: List[Any],
        gaps: List[Any],
        stopping: Any,
        investigation: InvestigationResult,
    ) -> str:
        """Constructs a deterministic, evidence-traceable explanation."""
        lines = []
        lines.append(f"Risk Assessment: {risk_level.value} (Estimated Fraud Probability: {fraud_prob:.2f})")
        lines.append(f"Confidence: {confidence:.2f} | Epistemic Uncertainty: {uncertainty:.2f} ({RiskEvaluator.METHODOLOGY})")

        # Supporting drivers
        if supporting:
            top_supp = sorted(supporting, key=lambda x: x.weight, reverse=True)[:3]
            supp_strs = [f"{s.description} [Weight: {s.weight:.2f}, Group: {s.independence_group.value}]" for s in top_supp]
            lines.append("Primary Fraud Drivers: " + "; ".join(supp_strs))
        else:
            lines.append("Primary Fraud Drivers: None detected.")

        # Contradicting drivers
        if contradicting:
            top_contra = sorted(contradicting, key=lambda x: x.weight, reverse=True)[:2]
            contra_strs = [f"{s.description} [Weight: {s.weight:.2f}, Group: {s.independence_group.value}]" for s in top_contra]
            lines.append("Legitimacy Indicators: " + "; ".join(contra_strs))

        # Information Gaps
        if gaps:
            gap_strs = [g.description for g in gaps if g.material_impact]
            if gap_strs:
                lines.append(f"Unresolved Gaps ({len(gap_strs)}): " + "; ".join(gap_strs[:2]))

        # Stopping decision
        lines.append(f"Stopping Status: {stopping.status.value} — {stopping.reason}")

        return "\n".join(lines)

    def format_explainability_summary(self, assessment: RiskAssessment) -> str:
        """
        Formats a structured, human-readable explainability summary containing:
        - Assessed fraud probability and categorical rating
        - Epistemic confidence and uncertainty
        - Supporting fraud factors
        - Contradicting / legitimate factors
        - Key uncertainty sources / information gaps
        - Stopping decision and recommended next step
        """
        lines = []
        lines.append("=== FRAUDGRAPH AI RISK & UNCERTAINTY EXPLANATION ===")
        lines.append(f"FRAUD PROBABILITY: {assessment.fraud_probability:.4f} ({assessment.risk_level.value})")
        lines.append(f"EPISTEMIC CONFIDENCE: {assessment.confidence:.4f}")
        lines.append(f"EPISTEMIC UNCERTAINTY: {assessment.uncertainty:.4f} ({assessment.methodology})")
        lines.append("")

        lines.append("SUPPORTING FRAUD FACTORS:")
        if assessment.supporting_signals:
            for s in assessment.supporting_signals:
                desc = s if isinstance(s, str) else s.description
                lines.append(f"  - {desc}")
        else:
            lines.append("  - None identified.")
        lines.append("")

        lines.append("CONTRADICTING / LEGITIMATE FACTORS:")
        if assessment.contradicting_signals:
            for s in assessment.contradicting_signals:
                desc = s if isinstance(s, str) else s.description
                lines.append(f"  - {desc}")
        else:
            lines.append("  - None identified.")
        lines.append("")

        lines.append("KEY UNCERTAINTY SOURCES:")
        if assessment.information_gaps:
            for g in assessment.information_gaps:
                lines.append(f"  - [{g.severity}] {g.description}")
        else:
            lines.append("  - None identified.")
        lines.append("")

        if assessment.stopping_decision:
            lines.append(f"STOPPING DECISION: {assessment.stopping_decision.status.value}")
            lines.append(f"  Reason: {assessment.stopping_decision.reason}")
            if assessment.stopping_decision.recommended_next_query:
                lines.append(f"  Recommended Next Step: {assessment.stopping_decision.recommended_next_query}")
        lines.append("====================================================")
        return "\n".join(lines)


# Global singleton instance
risk_uncertainty_service = RiskUncertaintyService()
