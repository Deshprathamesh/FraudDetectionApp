# ==============================================================================
# FraudGraph AI - Next Best Action (NBA) Engine
# Workstream: Person 1 (Brain) - Stage 4 Next Best Action Engine
# ==============================================================================

import logging
from typing import List, Dict, Any, Optional, Set, Tuple
from backend.models.domain import (
    ActionType,
    CANONICAL_ACTION_NAMES,
    InvestigationResult,
    RiskAssessment,
    RiskLevel,
    StoppingStatus,
    StoppingDecision,
    InformationGap,
    NextBestActionItem,
    NBAWhatChanged,
)

logger = logging.getLogger("fraudgraph.nba_engine")


class NBAEngine:
    """
    Deterministic rule-based Next Best Action engine.

    Translates:
    - Stage 2 InvestigationResult (facts & graph evidence)
    - Stage 3 RiskAssessment (heuristic fraud probability estimate, uncertainty, stopping status, information gaps)
    Into an ordered, prioritized set of canonical remediation and investigation actions.

    Reasoning Hierarchy:
    1. Investigation Stopping Status (BLOCKED, INCONCLUSIVE, MORE_EVIDENCE_REQUIRED, SUFFICIENT_EVIDENCE)
    2. Heuristic Fraud Probability Estimate & Categorical Risk Level
    3. Specific Information Gaps (Targeted inquiries / step-up auth)
    4. Graph Context & Exposure (Multi-card syndicate vs single card compromise)

    Strict Boundaries:
    - Outputs ONLY the 14 organizer canonical actions.
    - Does NOT execute actions (Stage 6).
    - Does NOT calculate human approval hierarchies / routes L1 vs L2 (Stage 5).
    - Does NOT evaluate compliance policy clauses R1-R10 (Stage 5).
    - Does NOT make new graph queries or GraphRAG calls (purely consumes existing evidence).
    """

    METHODOLOGY = "deterministic_evidentiary_nba"

    def __init__(self):
        pass

    def recommend_actions(
        self,
        risk: RiskAssessment,
        investigation: InvestigationResult,
        is_initial: bool = False,
    ) -> List[NextBestActionItem]:
        """
        Computes prioritized list of NextBestActionItems from evidence and risk.
        Ensures all actions belong to the 14 canonical action names.
        """
        stopping = risk.stopping_decision
        prob = risk.fraud_probability
        gaps = risk.information_gaps or []

        actions: List[NextBestActionItem] = []

        # ------------------------------------------------------------------
        # Branch 1: Investigation Blocked
        # ------------------------------------------------------------------
        if stopping.status == StoppingStatus.INVESTIGATION_BLOCKED:
            actions.append(
                NextBestActionItem(
                    action=ActionType.ESCALATE_TO_ANALYST.value,
                    rationale=f"Investigation blocked due to critical dependency outage: {stopping.reason}. Manual analyst review required.",
                    priority=1,
                    supporting_evidence=stopping.missing_information,
                    triggering_gaps=[g.gap_id for g in gaps],
                )
            )
            actions.append(
                NextBestActionItem(
                    action=ActionType.GENERATE_REPORT.value,
                    rationale="Generate technical audit report recording dependency outage details and partial evidence state.",
                    priority=2,
                    supporting_evidence=stopping.missing_information,
                    triggering_gaps=[g.gap_id for g in gaps],
                )
            )
            if prob >= 0.50:
                actions.append(
                    NextBestActionItem(
                        action=ActionType.MONITOR_CARD.value,
                        rationale="Precautionary monitoring while investigation is blocked due to elevated preliminary risk.",
                        priority=3,
                        supporting_evidence=[f"Heuristic fraud probability estimate: {prob:.4f}"],
                        triggering_gaps=[],
                    )
                )
            return self._finalize_and_deduplicate(actions)

        # ------------------------------------------------------------------
        # Branch 2: More Evidence Required (Active Gap Resolution)
        # ------------------------------------------------------------------
        if stopping.status == StoppingStatus.MORE_EVIDENCE_REQUIRED:
            actions = self._resolve_information_gaps(risk, investigation, gaps)
            return self._finalize_and_deduplicate(actions)

        # ------------------------------------------------------------------
        # Branch 3: Inconclusive
        # ------------------------------------------------------------------
        if stopping.status == StoppingStatus.INCONCLUSIVE:
            actions.append(
                NextBestActionItem(
                    action=ActionType.ESCALATE_TO_ANALYST.value,
                    rationale="Available evidence is exhausted without reaching definitive stopping threshold. Specialist analyst adjudication required.",
                    priority=1,
                    supporting_evidence=[f"Heuristic fraud probability estimate: {prob:.4f}", f"Epistemic uncertainty: {risk.epistemic_uncertainty:.4f}"],
                    triggering_gaps=[g.gap_id for g in gaps],
                )
            )
            actions.append(
                NextBestActionItem(
                    action=ActionType.MONITOR_CARD.value,
                    rationale="Place card on heightened surveillance while analyst adjudication is pending.",
                    priority=2,
                    supporting_evidence=[f"Heuristic fraud probability estimate: {prob:.4f}"],
                    triggering_gaps=[],
                )
            )
            actions.append(
                NextBestActionItem(
                    action=ActionType.GENERATE_REPORT.value,
                    rationale="Compile summary report of inconclusive investigation for compliance records.",
                    priority=3,
                    supporting_evidence=[stopping.reason],
                    triggering_gaps=[],
                )
            )
            return self._finalize_and_deduplicate(actions)

        # ------------------------------------------------------------------
        # Branch 4: Sufficient Evidence (Definitive Actions)
        # ------------------------------------------------------------------
        if stopping.status == StoppingStatus.SUFFICIENT_EVIDENCE:
            actions = self._handle_sufficient_evidence(risk, investigation)
            return self._finalize_and_deduplicate(actions)

        # Fallback safety (should not be reached)
        actions.append(
            NextBestActionItem(
                action=ActionType.ESCALATE_TO_ANALYST.value,
                rationale="Unrecognized stopping status. Defaulting to analyst review.",
                priority=1,
                supporting_evidence=[],
                triggering_gaps=[],
            )
        )
        return self._finalize_and_deduplicate(actions)

    def _resolve_information_gaps(
        self,
        risk: RiskAssessment,
        investigation: InvestigationResult,
        gaps: List[InformationGap],
    ) -> List[NextBestActionItem]:
        """
        Determines targeted investigation actions to resolve active information gaps.
        """
        prob = risk.fraud_probability
        gap_types = {g.gap_type for g in gaps}
        gap_ids = [g.gap_id for g in gaps]
        actions: List[NextBestActionItem] = []

        # Contradictory evidence takes top priority for analyst review
        if "CONTRADICTORY_EVIDENCE" in gap_types:
            actions.append(
                NextBestActionItem(
                    action=ActionType.ESCALATE_TO_ANALYST.value,
                    rationale="Conflicting high-weight signals between fraud indicators and legitimate customer history require human analyst adjudication.",
                    priority=1,
                    supporting_evidence=[g.description for g in gaps if g.gap_type == "CONTRADICTORY_EVIDENCE"],
                    triggering_gaps=gap_ids,
                )
            )
            actions.append(
                NextBestActionItem(
                    action=ActionType.VERIFY_WITH_CUSTOMER.value,
                    rationale="Direct cardholder confirmation will definitively resolve conflict between transaction indicators and account history.",
                    priority=2,
                    supporting_evidence=[f"Heuristic fraud probability estimate: {prob:.4f}"],
                    triggering_gaps=gap_ids,
                )
            )
            actions.append(
                NextBestActionItem(
                    action=ActionType.MONITOR_CARD.value,
                    rationale="Maintain surveillance on card while contradiction is investigated.",
                    priority=3,
                    supporting_evidence=[],
                    triggering_gaps=[],
                )
            )
            return actions

        # Unverified customer inquiry or intermediate anomaly
        if "UNVERIFIED_CUSTOMER_INQUIRY" in gap_types:
            if prob >= 0.70:
                # High risk but uncorroborated: protect funds first, then verify
                actions.append(
                    NextBestActionItem(
                        action=ActionType.DECLINE_TRANSACTION.value,
                        rationale=f"Elevated fraud probability ({prob:.2f}) with unverified cardholder. Decline transaction provisionally to prevent potential loss.",
                        priority=1,
                        supporting_evidence=[f"Heuristic fraud probability estimate: {prob:.4f}"],
                        triggering_gaps=gap_ids,
                    )
                )
                actions.append(
                    NextBestActionItem(
                        action=ActionType.VERIFY_WITH_CUSTOMER.value,
                        rationale="Prompt cardholder to confirm or deny transaction authorization.",
                        priority=2,
                        supporting_evidence=[f"Uncertainty: {risk.epistemic_uncertainty:.4f}"],
                        triggering_gaps=gap_ids,
                    )
                )
                actions.append(
                    NextBestActionItem(
                        action=ActionType.MONITOR_CARD.value,
                        rationale="Monitor card for further unauthorized attempts while customer verification is pending.",
                        priority=3,
                        supporting_evidence=[],
                        triggering_gaps=[],
                    )
                )
            elif 0.30 <= prob < 0.70:
                # Moderate anomaly: challenge with 2FA / step-up auth or direct inquiry
                actions.append(
                    NextBestActionItem(
                        action=ActionType.STEP_UP_AUTH.value,
                        rationale=f"Intermediate risk ({prob:.2f}) indicates potential anomaly. Challenge transaction with step-up two-factor authentication.",
                        priority=1,
                        supporting_evidence=[f"Heuristic fraud probability estimate: {prob:.4f}"],
                        triggering_gaps=gap_ids,
                    )
                )
                actions.append(
                    NextBestActionItem(
                        action=ActionType.VERIFY_WITH_CUSTOMER.value,
                        rationale="Inquire with cardholder if step-up authentication is not completed.",
                        priority=2,
                        supporting_evidence=[],
                        triggering_gaps=gap_ids,
                    )
                )
                actions.append(
                    NextBestActionItem(
                        action=ActionType.MONITOR_CARD.value,
                        rationale="Monitor card activity during authentication resolution.",
                        priority=3,
                        supporting_evidence=[],
                        triggering_gaps=[],
                    )
                )
            else:
                # Low risk with minor unverified inquiry
                actions.append(
                    NextBestActionItem(
                        action=ActionType.VERIFY_WITH_CUSTOMER.value,
                        rationale="Verify transaction with cardholder to confirm baseline authenticity.",
                        priority=1,
                        supporting_evidence=[f"Heuristic fraud probability estimate: {prob:.4f}"],
                        triggering_gaps=gap_ids,
                    )
                )
                actions.append(
                    NextBestActionItem(
                        action=ActionType.MONITOR_CARD.value,
                        rationale="Monitor card for any unusual changes in usage pattern.",
                        priority=2,
                        supporting_evidence=[],
                        triggering_gaps=[],
                    )
                )
            return actions

        # Uncorroborated evidence (lacks >= 2 independent evidence groups)
        if "UNCORROBORATED_EVIDENCE" in gap_types:
            if prob >= 0.70:
                actions.append(
                    NextBestActionItem(
                        action=ActionType.DECLINE_TRANSACTION.value,
                        rationale=f"Elevated fraud probability ({prob:.2f}) is supported by only a single independent evidence group. Decline provisionally while gathering corroboration.",
                        priority=1,
                        supporting_evidence=[g.description for g in gaps if g.gap_type == "UNCORROBORATED_EVIDENCE"],
                        triggering_gaps=gap_ids,
                    )
                )
                actions.append(
                    NextBestActionItem(
                        action=ActionType.VERIFY_WITH_CUSTOMER.value,
                        rationale="Inquire with cardholder to provide independent corroboration.",
                        priority=2,
                        supporting_evidence=[],
                        triggering_gaps=gap_ids,
                    )
                )
                if self._has_multi_card_context(investigation):
                    actions.append(
                        NextBestActionItem(
                            action=ActionType.MONITOR_CONNECTED_CARDS.value,
                            rationale="Monitor connected accounts and cards across shared graph entities for corroborating patterns.",
                            priority=3,
                            supporting_evidence=["Multi-card graph connection detected"],
                            triggering_gaps=[],
                        )
                    )
                else:
                    actions.append(
                        NextBestActionItem(
                            action=ActionType.MONITOR_CARD.value,
                            rationale="Monitor card for subsequent transactions.",
                            priority=3,
                            supporting_evidence=[],
                            triggering_gaps=[],
                        )
                    )
            else:
                actions.append(
                    NextBestActionItem(
                        action=ActionType.MONITOR_CARD.value,
                        rationale=f"Low fraud probability ({prob:.2f}) lacks secondary independent corroboration. Place on monitoring to verify baseline.",
                        priority=1,
                        supporting_evidence=[g.description for g in gaps if g.gap_type == "UNCORROBORATED_EVIDENCE"],
                        triggering_gaps=gap_ids,
                    )
                )
                actions.append(
                    NextBestActionItem(
                        action=ActionType.VERIFY_WITH_CUSTOMER.value,
                        rationale="Confirm cardholder activity to resolve single-source gap.",
                        priority=2,
                        supporting_evidence=[],
                        triggering_gaps=gap_ids,
                    )
                )
            return actions

        # Profile / History Gaps (Missing customer or sparse history)
        if "MISSING_CUSTOMER_PROFILE" in gap_types or "SPARSE_TRANSACTION_HISTORY" in gap_types:
            actions.append(
                NextBestActionItem(
                    action=ActionType.STEP_UP_AUTH.value,
                    rationale="Customer profile or history is sparse. Request step-up authentication to verify cardholder identity.",
                    priority=1,
                    supporting_evidence=[g.description for g in gaps if g.gap_type in ("MISSING_CUSTOMER_PROFILE", "SPARSE_TRANSACTION_HISTORY")],
                    triggering_gaps=gap_ids,
                )
            )
            actions.append(
                NextBestActionItem(
                    action=ActionType.VERIFY_WITH_CUSTOMER.value,
                    rationale="Contact customer to verify identity details and account baseline.",
                    priority=2,
                    supporting_evidence=[],
                    triggering_gaps=gap_ids,
                )
            )
            actions.append(
                NextBestActionItem(
                    action=ActionType.MONITOR_CARD.value,
                    rationale="Monitor card pending identity corroboration.",
                    priority=3,
                    supporting_evidence=[],
                    triggering_gaps=[],
                )
            )
            return actions

        # Default gap resolution
        actions.append(
            NextBestActionItem(
                action=ActionType.STEP_UP_AUTH.value,
                rationale=f"Additional evidence required (uncertainty: {risk.epistemic_uncertainty:.2f}). Challenge transaction to verify legitimacy.",
                priority=1,
                supporting_evidence=[stopping.reason],
                triggering_gaps=gap_ids,
            )
        )
        actions.append(
            NextBestActionItem(
                action=ActionType.VERIFY_WITH_CUSTOMER.value,
                rationale="Prompt customer verification to resolve open investigation gaps.",
                priority=2,
                supporting_evidence=[],
                triggering_gaps=gap_ids,
            )
        )
        actions.append(
            NextBestActionItem(
                action=ActionType.MONITOR_CARD.value,
                rationale="Surveil card for further anomalous events.",
                priority=3,
                supporting_evidence=[],
                triggering_gaps=[],
            )
        )
        return actions

    def _handle_sufficient_evidence(
        self,
        risk: RiskAssessment,
        investigation: InvestigationResult,
    ) -> List[NextBestActionItem]:
        """
        Determines definitive remediation and case actions when stopping criteria are met.
        """
        prob = risk.fraud_probability
        evidence_summary: List[str] = []
        for s in (risk.supporting_signals or []):
            if hasattr(s, "name"):
                evidence_summary.append(s.name)
            elif isinstance(s, dict) and "name" in s:
                evidence_summary.append(s["name"])
            else:
                evidence_summary.append(str(s))
        if not evidence_summary and risk.factors:
            evidence_summary = list(risk.factors[:3])
        actions: List[NextBestActionItem] = []

        is_multi_card = self._has_multi_card_context(investigation)

        # Critical Fraud: P >= 0.85
        if prob >= 0.85:
            if is_multi_card:
                actions.append(
                    NextBestActionItem(
                        action=ActionType.BLOCK_ALL_CARDS.value,
                        rationale=f"Critical fraud probability ({prob:.2f}) with coordinated multi-card / syndicate indicators. Block all associated cards immediately to stop systemic fraud exposure.",
                        priority=1,
                        supporting_evidence=evidence_summary + ["Multi-card graph connection detected"],
                        triggering_gaps=[],
                    )
                )
                actions.append(
                    NextBestActionItem(
                        action=ActionType.FILE_REPORT.value,
                        rationale="File formal regulatory Suspicious Activity Report (SAR) due to multi-card syndicate fraud operation.",
                        priority=2,
                        supporting_evidence=evidence_summary,
                        triggering_gaps=[],
                    )
                )
                actions.append(
                    NextBestActionItem(
                        action=ActionType.CREATE_CASE.value,
                        rationale="Create high-priority investigation case for cross-card fraud ring.",
                        priority=3,
                        supporting_evidence=evidence_summary,
                        triggering_gaps=[],
                    )
                )
                actions.append(
                    NextBestActionItem(
                        action=ActionType.DECLINE_TRANSACTION.value,
                        rationale="Decline transaction as part of total syndicate block.",
                        priority=4,
                        supporting_evidence=[f"Heuristic fraud probability estimate: {prob:.4f}"],
                        triggering_gaps=[],
                    )
                )
            else:
                actions.append(
                    NextBestActionItem(
                        action=ActionType.BLOCK_CARD.value,
                        rationale=f"Critical fraud probability ({prob:.2f}) supported by corroborated independent evidence. Block compromised card immediately to prevent further unauthorized transactions.",
                        priority=1,
                        supporting_evidence=evidence_summary,
                        triggering_gaps=[],
                    )
                )
                actions.append(
                    NextBestActionItem(
                        action=ActionType.DECLINE_TRANSACTION.value,
                        rationale="Decline fraudulent transaction immediately.",
                        priority=2,
                        supporting_evidence=[f"Heuristic fraud probability estimate: {prob:.4f}"],
                        triggering_gaps=[],
                    )
                )
                actions.append(
                    NextBestActionItem(
                        action=ActionType.CREATE_CASE.value,
                        rationale="Create fraud case for investigations and dispute tracking.",
                        priority=3,
                        supporting_evidence=evidence_summary,
                        triggering_gaps=[],
                    )
                )
                # If transaction amount is substantial, file report
                amount = getattr(investigation.transaction, "amount", 0.0) if investigation.transaction else 0.0
                if amount >= 5000.0 or any("bust_out" in s.lower() for s in evidence_summary):
                    actions.append(
                        NextBestActionItem(
                            action=ActionType.FILE_REPORT.value,
                            rationale=f"File regulatory SAR due to critical fraud probability ({prob:.2f}) and significant exposure (${amount:,.2f}).",
                            priority=4,
                            supporting_evidence=evidence_summary,
                            triggering_gaps=[],
                        )
                    )
                else:
                    actions.append(
                        NextBestActionItem(
                            action=ActionType.WARN_CUSTOMER.value,
                            rationale="Notify cardholder of detected compromise and card block.",
                            priority=4,
                            supporting_evidence=[],
                            triggering_gaps=[],
                        )
                    )
            return actions

        # High Fraud: 0.70 <= P < 0.85
        if 0.70 <= prob < 0.85:
            actions.append(
                NextBestActionItem(
                    action=ActionType.DECLINE_TRANSACTION.value,
                    rationale=f"Elevated fraud probability ({prob:.2f}) supported by multi-source evidence. Decline transaction to prevent loss.",
                    priority=1,
                    supporting_evidence=evidence_summary,
                    triggering_gaps=[],
                )
            )
            actions.append(
                NextBestActionItem(
                    action=ActionType.BLOCK_CARD.value,
                    rationale="Block card to prevent subsequent exploitation of compromised credentials.",
                    priority=2,
                    supporting_evidence=evidence_summary,
                    triggering_gaps=[],
                )
            )
            actions.append(
                NextBestActionItem(
                    action=ActionType.CREATE_CASE.value,
                    rationale="Open investigation case for claims and recovery tracking.",
                    priority=3,
                    supporting_evidence=evidence_summary,
                    triggering_gaps=[],
                )
            )
            actions.append(
                NextBestActionItem(
                    action=ActionType.WARN_CUSTOMER.value,
                    rationale="Send security alert to cardholder regarding transaction decline and protective block.",
                    priority=4,
                    supporting_evidence=[],
                    triggering_gaps=[],
                )
            )
            return actions

        # Moderate Risk: 0.30 <= P < 0.70 (Sufficient Evidence via verification settled)
        if 0.30 <= prob < 0.70:
            actions.append(
                NextBestActionItem(
                    action=ActionType.STEP_UP_AUTH.value,
                    rationale=f"Moderate risk ({prob:.2f}) requires strong customer authentication before completion.",
                    priority=1,
                    supporting_evidence=evidence_summary,
                    triggering_gaps=[],
                )
            )
            actions.append(
                NextBestActionItem(
                    action=ActionType.MONITOR_CARD.value,
                    rationale="Monitor card for velocity deviations.",
                    priority=2,
                    supporting_evidence=[],
                    triggering_gaps=[],
                )
            )
            actions.append(
                NextBestActionItem(
                    action=ActionType.WARN_CUSTOMER.value,
                    rationale="Issue transaction alert to cardholder.",
                    priority=3,
                    supporting_evidence=[],
                    triggering_gaps=[],
                )
            )
            return actions

        # Low Risk Observation: 0.15 < P < 0.30
        if 0.15 < prob < 0.30:
            actions.append(
                NextBestActionItem(
                    action=ActionType.ALLOW_TRANSACTION.value,
                    rationale=f"Low fraud probability ({prob:.2f}) indicates legitimate transaction. Allow processing to complete.",
                    priority=1,
                    supporting_evidence=evidence_summary,
                    triggering_gaps=[],
                )
            )
            actions.append(
                NextBestActionItem(
                    action=ActionType.MONITOR_CARD.value,
                    rationale="Routine monitoring maintained on card.",
                    priority=2,
                    supporting_evidence=[],
                    triggering_gaps=[],
                )
            )
            return actions

        # Clear Legitimate: P <= 0.15
        actions.append(
            NextBestActionItem(
                action=ActionType.CLOSE_NO_FRAUD.value,
                rationale=f"Very low fraud probability ({prob:.2f}) corroborated by independent legitimacy evidence ({', '.join(evidence_summary[:2]) or 'known customer baseline'}). Close investigation as non-fraud.",
                priority=1,
                supporting_evidence=evidence_summary,
                triggering_gaps=[],
            )
        )
        actions.append(
            NextBestActionItem(
                action=ActionType.ALLOW_TRANSACTION.value,
                rationale="Approve and release transaction for settlement.",
                priority=2,
                supporting_evidence=[f"Heuristic fraud probability estimate: {prob:.4f}"],
                triggering_gaps=[],
            )
        )
        return actions

    def _has_multi_card_context(self, investigation: InvestigationResult) -> bool:
        """
        Determines whether multi-card, syndicate, bust-out, or coordinated ring patterns exist.
        """
        # 1. Check detected patterns
        patterns = (
            getattr(investigation, "fraud_pattern_evidence", None)
            or getattr(investigation, "fraud_patterns", None)
            or []
        )
        for p in patterns:
            if isinstance(p, dict):
                ptype = str(p.get("pattern_type") or p.get("type") or "").lower()
                pname = str(p.get("pattern_name") or p.get("name") or "").lower()
                pdesc = str(p.get("description") or "").lower()
            else:
                ptype = str(getattr(p, "pattern_type", getattr(p, "type", "")) or "").lower()
                pname = str(getattr(p, "pattern_name", getattr(p, "name", "")) or "").lower()
                pdesc = str(getattr(p, "description", "") or "").lower()
            if any(term in ptype or term in pname or term in pdesc for term in ("syndicate", "bust_out", "bustout", "device_sharing", "shared_card", "multi_card")):
                return True

        # 2. Check graph evidence
        graph_ev = getattr(investigation, "connected_entities", None) or getattr(investigation, "graph_evidence", None) or {}
        if isinstance(graph_ev, dict):
            connected = graph_ev.get("connected_cards") or []
            if isinstance(connected, list) and len(connected) > 1:
                return True
            shared_devices = graph_ev.get("shared_devices") or []
            if isinstance(shared_devices, list) and len(shared_devices) > 2:
                return True

        # 3. Check customer connected cards
        customer = investigation.customer
        if customer:
            linked_cards = (
                customer.get("linked_cards") or customer.get("card_ids") or []
                if isinstance(customer, dict)
                else getattr(customer, "linked_cards", []) or getattr(customer, "card_ids", []) or []
            )
            if len(linked_cards) > 2:
                return True

        return False

    def _finalize_and_deduplicate(
        self,
        actions: List[NextBestActionItem],
    ) -> List[NextBestActionItem]:
        """
        Ensures all actions:
        - Are unique (no duplicate ActionTypes in the list)
        - Strictly belong to CANONICAL_ACTION_NAMES
        - Maintain strictly increasing priority rankings (1, 2, 3...)
        """
        seen_actions: Set[str] = set()
        final_list: List[NextBestActionItem] = []

        for item in actions:
            act = item.action
            if act not in CANONICAL_ACTION_NAMES:
                # Should not happen because of Pydantic validator, but enforce defense-in-depth
                logger.warning(f"Dropping non-canonical action '{act}'")
                continue
            if act in seen_actions:
                continue
            seen_actions.add(act)
            final_list.append(item)

        # Re-index priorities 1..N
        for idx, item in enumerate(final_list):
            item.priority = idx + 1

        return final_list

    def explain_changes(
        self,
        initial_actions: List[NextBestActionItem],
        final_actions: List[NextBestActionItem],
        initial_risk: Optional[RiskAssessment] = None,
        final_risk: Optional[RiskAssessment] = None,
        evidence_added: Optional[List[str]] = None,
    ) -> NBAWhatChanged:
        """
        Generates factual, transparent explainability regarding what changed
        between initial and final next best action sets.
        """
        initial_primary = initial_actions[0].action if initial_actions else "NONE"
        final_primary = final_actions[0].action if final_actions else "NONE"

        p_before = initial_risk.fraud_probability if initial_risk else None
        p_after = final_risk.fraud_probability if final_risk else None
        unc_before = initial_risk.epistemic_uncertainty if initial_risk else None
        unc_after = final_risk.epistemic_uncertainty if final_risk else None

        # Determine resolved gaps
        initial_gaps = {g.gap_type for g in (initial_risk.information_gaps if initial_risk else [])}
        final_gaps = {g.gap_type for g in (final_risk.information_gaps if final_risk else [])}
        resolved = sorted(list(initial_gaps - final_gaps))

        # Build clear explanation
        if initial_primary == final_primary and (p_before == p_after or p_after is None):
            explanation = (
                f"Recommendations remain stable. Primary action '{final_primary}' maintained "
                f"with consistent risk profile (heuristic fraud probability estimate: {p_after or p_before or 0.0:.2f})."
            )
        else:
            prob_shift = f"from {p_before:.2f} to {p_after:.2f}" if (p_before is not None and p_after is not None) else "updated"
            unc_shift = f"uncertainty shifted from {unc_before:.2f} to {unc_after:.2f}" if (unc_before is not None and unc_after is not None) else ""
            gaps_str = f"resolved gaps: [{', '.join(resolved)}]" if resolved else "no formal gaps cleared"
            explanation = (
                f"Primary action shifted from '{initial_primary}' to '{final_primary}' after evidence integration. "
                f"Heuristic fraud probability estimate shifted {prob_shift}; {unc_shift}; {gaps_str}."
            )

        return NBAWhatChanged(
            explanation=explanation,
            before_fraud_probability=p_before,
            after_fraud_probability=p_after,
            before_uncertainty=unc_before,
            after_uncertainty=unc_after,
            resolved_gaps=resolved,
            evidence_added=evidence_added or [],
        )


# Global singleton instance
nba_engine = NBAEngine()
