# ==============================================================================
# FraudGraph AI - Evidentiary Risk Signal Extractor
# Workstream: Person 1 (Brain) - Stage 3 Risk + Uncertainty Engine
# ==============================================================================

import logging
from typing import Dict, Any, List, Optional
from backend.models.domain import (
    InvestigationResult,
    RiskSignal,
    SignalDirection,
    IndependenceGroup,
    EvidenceItem,
)

logger = logging.getLogger("fraudgraph.risk_signals")


class SignalExtractor:
    """
    Extracts typed evidentiary risk signals from a Stage 2 InvestigationResult.

    Principles:
    - Zero re-querying of TigerGraph or GraphRAG.
    - Explicit IndependenceGroup categorization preventing duplicate counts.
    - Evidence quality weighting based on epistemic fact level (FACT, OBSERVATION, INFERENCE).
    - Untrusted prompt/retrieval text is strictly dampened to prevent injection dominance.
    - Raw input risk_score is treated as an input signal, NOT the final verdict.
    """

    # Heuristic evidence quality multipliers
    # FACT = 1.0 (Direct ground-truth attributes from transaction or customer profile)
    # OBSERVATION = 0.85 (Empirical graph topology, hardware sharing, typology detections)
    # INFERENCE = 0.70 (Historical precedent similarity, statistical comparisons, prompt context)
    QUALITY_MULTIPLIERS = {
        "FACT": 1.0,
        "OBSERVATION": 0.85,
        "INFERENCE": 0.70,
    }

    def __init__(self):
        pass

    def extract_signals(self, investigation: InvestigationResult) -> List[RiskSignal]:
        """Translates structured investigation evidence into typed RiskSignals."""
        signals: List[RiskSignal] = []

        # Index evidence items by evidence_id and evidence_type for fast lookup
        evidence_by_type: Dict[str, List[EvidenceItem]] = {}
        for ev in investigation.evidence:
            evidence_by_type.setdefault(ev.evidence_type, []).append(ev)

        # 1. TRANSACTION_ATTRIBUTES signals
        txn = investigation.transaction or {}
        if txn:
            amount = float(txn.get("amount", 0.0))
            raw_risk = txn.get("risk_score")
            txn_id = txn.get("transaction_id", "UNKNOWN")
            channel = txn.get("channel", "UNKNOWN")

            # 1a. Raw upstream detection risk score (ONE input signal, strictly non-dominating)
            if raw_risk is not None:
                raw_risk_f = float(raw_risk)
                if raw_risk_f >= 0.70:
                    strength = min(1.0, raw_risk_f)
                    direction = SignalDirection.SUPPORTS_FRAUD
                    desc = f"Upstream anomaly detection signal is elevated ({raw_risk_f:.2f})."
                elif raw_risk_f <= 0.30:
                    strength = min(1.0, 1.0 - raw_risk_f)
                    direction = SignalDirection.SUPPORTS_LEGITIMATE
                    desc = f"Upstream anomaly detection signal indicates baseline normalcy ({raw_risk_f:.2f})."
                else:
                    strength = 0.40
                    direction = SignalDirection.NEUTRAL
                    desc = f"Upstream anomaly detection signal is intermediate ({raw_risk_f:.2f})."

                ev_ids = [e.evidence_id for e in evidence_by_type.get("UPSTREAM_DETECTION_SCORE", [])]
                weight = self._compute_effective_weight(strength, "OBSERVATION", is_direct=False, is_untrusted=False)
                signals.append(
                    RiskSignal(
                        category="UPSTREAM_RISK_SCORE",
                        description=desc,
                        direction=direction,
                        strength=strength,
                        weight=weight,
                        source="tigergraph.get_transaction",
                        evidence_ids=ev_ids,
                        provenance=["tigergraph.get_transaction"],
                        independence_group=IndependenceGroup.TRANSACTION_ATTRIBUTES,
                    )
                )

            # 1b. Transaction financial scale & channel exposure
            if amount > 5000.0:
                strength = 0.85
                direction = SignalDirection.SUPPORTS_FRAUD
                desc = f"High-value financial exposure (${amount:,.2f} USD) via {channel} channel."
            elif amount > 1000.0:
                strength = 0.65
                direction = SignalDirection.SUPPORTS_FRAUD
                desc = f"Substantial transaction value (${amount:,.2f} USD) exceeding standard retail baseline."
            elif 0.0 < amount <= 50.0:
                strength = 0.60
                direction = SignalDirection.SUPPORTS_LEGITIMATE
                desc = f"Low-value routine purchase (${amount:,.2f} USD) consistent with typical personal spending."
            else:
                strength = 0.40
                direction = SignalDirection.NEUTRAL
                desc = f"Moderate transaction value (${amount:,.2f} USD)."

            fin_ev_ids = [e.evidence_id for e in evidence_by_type.get("FINANCIAL_ATTRIBUTES", [])]
            signals.append(
                RiskSignal(
                    category="TRANSACTION_SCALE",
                    description=desc,
                    direction=direction,
                    strength=strength,
                    weight=self._compute_effective_weight(strength, "FACT", is_direct=True, is_untrusted=False),
                    source="tigergraph.get_transaction",
                    evidence_ids=fin_ev_ids,
                    provenance=["tigergraph.get_transaction"],
                    independence_group=IndependenceGroup.TRANSACTION_ATTRIBUTES,
                )
            )

        # 2. CUSTOMER_PROFILE signals
        cust = investigation.customer or {}
        if cust:
            cust_tier = str(cust.get("risk_tier", "LOW")).upper()
            linked_cards = cust.get("linked_cards", [])
            accounts = cust.get("accounts", [])
            cust_ev_ids = [e.evidence_id for e in evidence_by_type.get("CUSTOMER_PROFILE", [])]

            if cust_tier in ("CRITICAL", "HIGH"):
                strength = 0.85
                direction = SignalDirection.SUPPORTS_FRAUD
                desc = f"Customer profile is classified under elevated risk tier ({cust_tier})."
            elif cust_tier == "LOW":
                strength = 0.70
                direction = SignalDirection.SUPPORTS_LEGITIMATE
                desc = f"Customer profile is in good standing with verified LOW risk tier ({len(linked_cards)} active card(s))."
            else:
                strength = 0.40
                direction = SignalDirection.NEUTRAL
                desc = f"Customer profile has moderate risk tier ({cust_tier})."

            signals.append(
                RiskSignal(
                    category="CUSTOMER_STANDING",
                    description=desc,
                    direction=direction,
                    strength=strength,
                    weight=self._compute_effective_weight(strength, "FACT", is_direct=True, is_untrusted=False),
                    source="tigergraph.get_customer",
                    evidence_ids=cust_ev_ids,
                    provenance=["tigergraph.get_customer"],
                    independence_group=IndependenceGroup.CUSTOMER_PROFILE,
                )
            )

        # 3. TRANSACTION_HISTORY signals
        history = investigation.transaction_history or []
        hist_ev_ids = [e.evidence_id for e in evidence_by_type.get("TRANSACTION_HISTORY_VELOCITY", [])]
        if len(history) >= 5:
            # Established history with prior non-fraud activity supports legitimacy
            avg_hist_risk = sum(float(t.get("risk_score", 0.2)) for t in history) / len(history)
            if avg_hist_risk < 0.35:
                signals.append(
                    RiskSignal(
                        category="HISTORICAL_STABILITY",
                        description=f"Account displays consistent legitimate baseline history across {len(history)} prior transactions (avg risk: {avg_hist_risk:.2f}).",
                        direction=SignalDirection.SUPPORTS_LEGITIMATE,
                        strength=0.75,
                        weight=self._compute_effective_weight(0.75, "OBSERVATION", is_direct=False, is_untrusted=False),
                        source="tigergraph.get_transaction_history",
                        evidence_ids=hist_ev_ids,
                        provenance=["tigergraph.get_transaction_history"],
                        independence_group=IndependenceGroup.TRANSACTION_HISTORY,
                    )
                )
            elif avg_hist_risk >= 0.70:
                signals.append(
                    RiskSignal(
                        category="HISTORICAL_ANOMALIES",
                        description=f"Account has history of recurring high-risk transactions across {len(history)} records (avg risk: {avg_hist_risk:.2f}).",
                        direction=SignalDirection.SUPPORTS_FRAUD,
                        strength=0.80,
                        weight=self._compute_effective_weight(0.80, "OBSERVATION", is_direct=False, is_untrusted=False),
                        source="tigergraph.get_transaction_history",
                        evidence_ids=hist_ev_ids,
                        provenance=["tigergraph.get_transaction_history"],
                        independence_group=IndependenceGroup.TRANSACTION_HISTORY,
                    )
                )

        # 4. GRAPH_TOPOLOGY signals
        conn = investigation.connected_entities or {}
        nodes = conn.get("nodes", [])
        if nodes:
            high_risk_neighbors = [n for n in nodes if float(n.get("risk_score", 0.0)) >= 0.75]
            graph_ev_ids = [e.evidence_id for e in evidence_by_type.get("GRAPH_NEIGHBORHOOD_TOPOLOGY", [])]
            if len(high_risk_neighbors) >= 2:
                signals.append(
                    RiskSignal(
                        category="GRAPH_NEIGHBORHOOD_RISK",
                        description=f"Multi-hop graph neighborhood contains {len(high_risk_neighbors)} high-risk connected entities.",
                        direction=SignalDirection.SUPPORTS_FRAUD,
                        strength=0.82,
                        weight=self._compute_effective_weight(0.82, "OBSERVATION", is_direct=False, is_untrusted=False),
                        source="tigergraph.get_connected_entities",
                        evidence_ids=graph_ev_ids,
                        provenance=["tigergraph.get_connected_entities"],
                        independence_group=IndependenceGroup.GRAPH_TOPOLOGY,
                    )
                )
            elif len(high_risk_neighbors) == 0:
                signals.append(
                    RiskSignal(
                        category="CLEAN_GRAPH_NEIGHBORHOOD",
                        description=f"Graph neighborhood is clean with no high-risk connected entities across {len(nodes)} nodes.",
                        direction=SignalDirection.SUPPORTS_LEGITIMATE,
                        strength=0.60,
                        weight=self._compute_effective_weight(0.60, "OBSERVATION", is_direct=False, is_untrusted=False),
                        source="tigergraph.get_connected_entities",
                        evidence_ids=graph_ev_ids,
                        provenance=["tigergraph.get_connected_entities"],
                        independence_group=IndependenceGroup.GRAPH_TOPOLOGY,
                    )
                )

        # 5. DEVICE_SHARING signals
        device_sharing_ev = evidence_by_type.get("DEVICE_SHARING", [])
        if device_sharing_ev:
            for ev in device_sharing_ev:
                linked_count = ev.details.get("linked_accounts", ev.details.get("associated_accounts_count", 0))
                risk_flag = ev.details.get("risk_flag", False)
                if linked_count > 1 or risk_flag:
                    signals.append(
                        RiskSignal(
                            category="SHARED_HARDWARE_SYNDICATE",
                            description=f"Device hardware is shared across {linked_count} accounts/customers.",
                            direction=SignalDirection.SUPPORTS_FRAUD,
                            strength=0.88 if linked_count >= 3 else 0.75,
                            weight=self._compute_effective_weight(
                                0.88 if linked_count >= 3 else 0.75,
                                ev.fact_level,
                                is_direct=ev.is_direct,
                                is_untrusted=ev.untrusted_data_flag,
                            ),
                            source="tigergraph.find_shared_devices",
                            evidence_ids=[ev.evidence_id],
                            provenance=ev.provenance_sources or ["tigergraph.find_shared_devices"],
                            independence_group=IndependenceGroup.DEVICE_SHARING,
                        )
                    )

        # 6. FRAUD_PATTERN signals
        patterns = investigation.fraud_pattern_evidence or []
        pattern_ev_ids = [e.evidence_id for e in evidence_by_type.get("FRAUD_TYPOLOGY_MATCH", [])]
        if patterns:
            for p in patterns:
                pat_id = p.get("pattern_id", "FP-UNKNOWN")
                name = p.get("name", "Fraud Pattern")
                conf = float(p.get("confidence", 0.85))
                signals.append(
                    RiskSignal(
                        category="FRAUD_TYPOLOGY",
                        description=f"Graph pattern detected: '{name}' ({pat_id}) with algorithmic confidence {conf:.2f}.",
                        direction=SignalDirection.SUPPORTS_FRAUD,
                        strength=conf,
                        weight=self._compute_effective_weight(conf, "OBSERVATION", is_direct=False, is_untrusted=False),
                        source="tigergraph.detect_fraud_patterns",
                        evidence_ids=pattern_ev_ids,
                        provenance=["tigergraph.detect_fraud_patterns"],
                        independence_group=IndependenceGroup.FRAUD_PATTERN,
                    )
                )

        # 7. HISTORICAL_CASE signals
        cases = investigation.similar_cases or []
        case_ev_ids = [e.evidence_id for e in evidence_by_type.get("CASE_PRECEDENT", [])]
        for c in cases[:3]:
            sim = float(c.get("similarity_score", 0.0))
            outcome = str(c.get("outcome", "UNKNOWN")).upper()
            case_id = c.get("case_id", "CASE-UNKNOWN")

            if sim >= 0.65:
                if outcome in ("FRAUD", "CONFIRMED_FRAUD", "CLOSED_FRAUD"):
                    signals.append(
                        RiskSignal(
                            category="HISTORICAL_PRECEDENT_FRAUD",
                            description=f"Historical precedent {case_id} ({int(sim*100)}% match) resulted in {outcome}.",
                            direction=SignalDirection.SUPPORTS_FRAUD,
                            strength=sim * 0.80, # Scaled because it is an inference
                            weight=self._compute_effective_weight(sim * 0.80, "INFERENCE", is_direct=False, is_untrusted=True),
                            source="graphrag.find_similar_cases",
                            evidence_ids=case_ev_ids,
                            provenance=["graphrag.find_similar_cases"],
                            independence_group=IndependenceGroup.HISTORICAL_CASE,
                        )
                    )
                elif outcome in ("CLEARED", "NON_FRAUD", "BENIGN", "RESOLVED"):
                    signals.append(
                        RiskSignal(
                            category="HISTORICAL_PRECEDENT_CLEARED",
                            description=f"Historical precedent {case_id} ({int(sim*100)}% match) was resolved as benign ({outcome}).",
                            direction=SignalDirection.SUPPORTS_LEGITIMATE,
                            strength=sim * 0.80,
                            weight=self._compute_effective_weight(sim * 0.80, "INFERENCE", is_direct=False, is_untrusted=True),
                            source="graphrag.find_similar_cases",
                            evidence_ids=case_ev_ids,
                            provenance=["graphrag.find_similar_cases"],
                            independence_group=IndependenceGroup.HISTORICAL_CASE,
                        )
                    )

        # 8. CUSTOMER_VERIFICATION signals (if present in evidence from verification inquiries)
        for ev in investigation.evidence:
            if ev.evidence_type in ("CUSTOMER_VERIFICATION", "VERIFICATION_RESPONSE"):
                resp = str(ev.details.get("response", ev.claim or "")).lower()
                if any(w in resp for w in ("not make", "unauthorized", "stolen", "denied", "fraud")):
                    signals.append(
                        RiskSignal(
                            category="CUSTOMER_DENIAL",
                            description="Customer explicitly confirmed unauthorized or fraudulent activity.",
                            direction=SignalDirection.SUPPORTS_FRAUD,
                            strength=0.98,
                            weight=self._compute_effective_weight(0.98, "FACT", is_direct=True, is_untrusted=False),
                            source=ev.source,
                            evidence_ids=[ev.evidence_id],
                            provenance=ev.provenance_sources or [ev.source],
                            independence_group=IndependenceGroup.CUSTOMER_VERIFICATION,
                        )
                    )
                elif any(w in resp for w in ("authorized", "i made this", "valid", "legitimate", "confirmed")):
                    signals.append(
                        RiskSignal(
                            category="CUSTOMER_CONFIRMATION",
                            description="Customer explicitly confirmed the transaction as authorized and legitimate.",
                            direction=SignalDirection.SUPPORTS_LEGITIMATE,
                            strength=0.98,
                            weight=self._compute_effective_weight(0.98, "FACT", is_direct=True, is_untrusted=False),
                            source=ev.source,
                            evidence_ids=[ev.evidence_id],
                            provenance=ev.provenance_sources or [ev.source],
                            independence_group=IndependenceGroup.CUSTOMER_VERIFICATION,
                        )
                    )

        # 9. Direct extraction for any explicit EvidenceItem not yet captured
        referenced_ev_ids = {eid for s in signals for eid in s.evidence_ids}
        for ev in investigation.evidence:
            if ev.evidence_id not in referenced_ev_ids:
                claim_lower = (ev.claim or ev.description or "").lower()
                if ev.details.get("direction"):
                    direction = SignalDirection(ev.details["direction"])
                elif getattr(ev, "supporting", False) or any(w in claim_lower for w in ("exceeds", "cycling", "suspicious", "fraud", "unauthorized", "anomaly", "risk")):
                    direction = SignalDirection.SUPPORTS_FRAUD
                elif any(w in claim_lower for w in ("legitimate", "normal", "verified", "consistent", "benign")):
                    direction = SignalDirection.SUPPORTS_LEGITIMATE
                else:
                    direction = SignalDirection.NEUTRAL

                group = IndependenceGroup.TRANSACTION_ATTRIBUTES
                cat_lower = (getattr(ev, "category", "") or ev.evidence_type or "").lower()
                if "device" in cat_lower or "hardware" in cat_lower:
                    group = IndependenceGroup.DEVICE_SHARING
                elif "topology" in cat_lower or "graph" in cat_lower:
                    group = IndependenceGroup.GRAPH_TOPOLOGY
                elif "pattern" in cat_lower or "typology" in cat_lower:
                    group = IndependenceGroup.FRAUD_PATTERN
                elif "customer" in cat_lower or "kyc" in cat_lower:
                    group = IndependenceGroup.CUSTOMER_PROFILE
                elif "history" in cat_lower or "velocity" in cat_lower:
                    group = IndependenceGroup.TRANSACTION_HISTORY
                elif "policy" in cat_lower:
                    group = IndependenceGroup.POLICY_DIRECTIVE
                elif "case" in cat_lower or "precedent" in cat_lower:
                    group = IndependenceGroup.HISTORICAL_CASE

                is_untrusted = ev.untrusted_data_flag or (
                    ev.details.get("untrusted_data_flag", False) if isinstance(ev.details, dict) else False
                )
                weight = self._compute_effective_weight(
                    strength=ev.confidence,
                    fact_level=ev.fact_level,
                    is_direct=ev.is_direct,
                    is_untrusted=is_untrusted,
                )
                signals.append(
                    RiskSignal(
                        category=getattr(ev, "category", None) or ev.evidence_type,
                        description=ev.claim or ev.description or f"Evidence item {ev.evidence_id}",
                        direction=direction,
                        strength=ev.confidence,
                        weight=weight,
                        source=ev.source,
                        evidence_ids=[ev.evidence_id],
                        provenance=ev.provenance_sources or [ev.source],
                        independence_group=group,
                    )
                )

        return signals

    def _compute_effective_weight(
        self,
        strength: float,
        fact_level: str,
        is_direct: bool,
        is_untrusted: bool,
    ) -> float:
        """Computes effective weight factoring in evidence quality and untrusted data dampening."""
        base_mult = self.QUALITY_MULTIPLIERS.get(fact_level, 0.70)
        direct_mult = 1.0 if is_direct else 0.90
        # If untrusted prompt context or narrative retrieval, dampen by 0.50
        untrusted_mult = 0.50 if is_untrusted else 1.0

        effective = strength * base_mult * direct_mult * untrusted_mult
        return round(max(0.05, min(1.0, effective)), 4)


# Global singleton instance
signal_extractor = SignalExtractor()
