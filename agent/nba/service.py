# ==============================================================================
# FraudGraph AI - Next Best Action Service
# Workstream: Person 1 (Brain) - Stage 4 Next Best Action Engine
# ==============================================================================

import logging
from typing import Dict, Any, List, Optional, Tuple, Union
from backend.models.domain import (
    InvestigationResult,
    RiskAssessment,
    NextBestActionItem,
    NBAWhatChanged,
    NextBestActionAssessment,
    ActionRecommendation,
)
from agent.reasoning.interfaces import NextBestActionEngineInterface
from agent.nba.engine import nba_engine, NBAEngine

logger = logging.getLogger("fraudgraph.nba_service")


class NBAService(NextBestActionEngineInterface):
    """
    High-level orchestrator for Stage 4 Next Best Action decisioning.
    Consumes Stage 2 InvestigationResult and Stage 3 RiskAssessment.
    Produces initial, final, and explainable next best action recommendations.

    Strict Boundaries:
    Answers: "WHAT SHOULD THE INVESTIGATION DO NEXT, BASED ON THE CURRENT EVIDENCE AND RISK?"
    Does NOT answer: "ARE WE ALLOWED TO DO IT?" (Stage 5 Policy)
    Does NOT execute: (Stage 6 Execution)
    """

    def __init__(self, engine: Optional[NBAEngine] = None):
        self._engine = engine or nba_engine

    def evaluate_initial(
        self,
        risk: RiskAssessment,
        investigation: InvestigationResult,
    ) -> List[NextBestActionItem]:
        """
        Computes initial ranked next best actions prior to or at start of investigation loop.
        """
        return self._engine.recommend_actions(risk, investigation, is_initial=True)

    def evaluate_final(
        self,
        risk: RiskAssessment,
        investigation: InvestigationResult,
        initial_actions: List[NextBestActionItem],
        initial_risk: Optional[RiskAssessment] = None,
        evidence_added: Optional[List[str]] = None,
    ) -> Tuple[List[NextBestActionItem], Optional[NBAWhatChanged]]:
        """
        Computes final ranked next best actions following evidence gathering and compares with initial.
        """
        final_actions = self._engine.recommend_actions(risk, investigation, is_initial=False)
        what_changed = self._engine.explain_changes(
            initial_actions=initial_actions,
            final_actions=final_actions,
            initial_risk=initial_risk,
            final_risk=risk,
            evidence_added=evidence_added,
        )
        return final_actions, what_changed

    def assess(
        self,
        risk: RiskAssessment,
        investigation: InvestigationResult,
        initial_actions: Optional[List[NextBestActionItem]] = None,
        initial_risk: Optional[RiskAssessment] = None,
        evidence_added: Optional[List[str]] = None,
    ) -> NextBestActionAssessment:
        """
        Produces an end-to-end NextBestActionAssessment.
        If initial_actions is provided, calculates final recommendations and what_changed.
        Otherwise, establishes initial recommendations.
        """
        if initial_actions is None:
            # First pass: generate initial actions
            initial = self.evaluate_initial(risk, investigation)
            top_action = initial[0] if initial else None
            rationale = top_action.rationale if top_action else "No actions determined."
            return NextBestActionAssessment(
                initial=initial,
                final=[],
                what_changed=None,
                rationale=rationale,
                methodology=self._engine.METHODOLOGY,
            )
        else:
            # Second / final pass: evaluate final and determine what changed
            final, what_changed = self.evaluate_final(
                risk=risk,
                investigation=investigation,
                initial_actions=initial_actions,
                initial_risk=initial_risk,
                evidence_added=evidence_added,
            )
            top_action = final[0] if final else (initial_actions[0] if initial_actions else None)
            rationale = top_action.rationale if top_action else "No actions determined."
            return NextBestActionAssessment(
                initial=initial_actions,
                final=final,
                what_changed=what_changed,
                rationale=rationale,
                methodology=self._engine.METHODOLOGY,
            )

    def recommend_action(self, state: Dict[str, Any]) -> ActionRecommendation:
        """
        Adapter satisfying NextBestActionEngineInterface from Stage 1.
        Extracts risk and investigation from state dictionary and returns ActionRecommendation.
        """
        risk_dict = state.get("risk_assessment")
        investigation_dict = state.get("investigation_result") or state.get("collected_evidence")

        # Safely parse or reconstruct models
        if isinstance(risk_dict, RiskAssessment):
            risk = risk_dict
        elif isinstance(risk_dict, dict):
            risk = RiskAssessment.model_validate(risk_dict)
        else:
            # Fallback if state does not yet contain RiskAssessment
            from backend.models.domain import StoppingDecision, StoppingStatus, RiskLevel
            risk = RiskAssessment(
                transaction_id=state.get("transaction_id", "UNKNOWN"),
                fraud_probability=float(state.get("fraud_probability", 0.5)),
                risk_level=RiskLevel.MEDIUM,
                confidence=0.5,
                uncertainty=0.5,
                stopping_decision=StoppingDecision(
                    status=StoppingStatus.MORE_EVIDENCE_REQUIRED,
                    reason="Preliminary state before complete investigation.",
                    fraud_probability=float(state.get("fraud_probability", 0.5)),
                    confidence=0.5,
                ),
            )

        if isinstance(investigation_dict, InvestigationResult):
            investigation = investigation_dict
        elif isinstance(investigation_dict, dict):
            investigation = InvestigationResult.model_validate(investigation_dict)
        else:
            from backend.models.domain import InvestigationStatus
            investigation = InvestigationResult(
                transaction_id=state.get("transaction_id", "UNKNOWN"),
                status=InvestigationStatus.COMPLETE,
            )

        items = self.evaluate_initial(risk, investigation)
        if not items:
            return ActionRecommendation(
                action="ESCALATE_TO_ANALYST",
                priority=1,
                reason="Default analyst escalation.",
                confidence=risk.epistemic_confidence,
            )

        top = items[0]
        alternatives = [item.action for item in items[1:]]

        return ActionRecommendation(
            action=top.action,
            priority=top.priority,
            reason=top.rationale,
            confidence=risk.epistemic_confidence,
            evidence_ids=top.supporting_evidence,
            alternative_actions=alternatives,
        )

    def format_explainability_summary(self, assessment: NextBestActionAssessment) -> str:
        """
        Formats human-readable summary of the next best action recommendations.
        """
        lines = ["### Next Best Action Recommendations", ""]
        primary = assessment.primary_action
        if primary:
            lines.append(f"**Primary Action:** `{primary.action}` (Priority {primary.priority})")
            lines.append(f"**Rationale:** {primary.rationale}")
            if primary.supporting_evidence:
                lines.append(f"**Supporting Evidence:** {', '.join(primary.supporting_evidence)}")
            if primary.triggering_gaps:
                lines.append(f"**Triggering Gaps:** {', '.join(primary.triggering_gaps)}")
            lines.append("")

        if assessment.alternative_actions:
            lines.append("**Alternative / Auxiliary Actions:**")
            for alt in assessment.alternative_actions:
                lines.append(f"- `{alt.action}` (Priority {alt.priority}): {alt.rationale}")
            lines.append("")

        if assessment.what_changed:
            lines.append("**Evidence Impact & What Changed:**")
            if isinstance(assessment.what_changed, NBAWhatChanged):
                lines.append(f"- {assessment.what_changed.explanation}")
                if assessment.what_changed.resolved_gaps:
                    lines.append(f"- Resolved Gaps: {', '.join(assessment.what_changed.resolved_gaps)}")
                if assessment.what_changed.evidence_added:
                    lines.append(f"- Evidence Added: {', '.join(assessment.what_changed.evidence_added)}")
            else:
                lines.append(f"- {assessment.what_changed}")
            lines.append("")

        return "\n".join(lines)


# Global singleton instance
nba_service = NBAService()
