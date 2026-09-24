# ==============================================================================
# FraudGraph AI - Stage 3 Risk + Uncertainty Engine Test Suite
# tests/test_stage3_risk.py
# Workstream: Person 1 (Brain) - Stage 3 Risk + Uncertainty Engine
# ==============================================================================

import time
import math
import unittest
from unittest.mock import MagicMock, patch

from backend.errors import ValidationError
from pydantic import ValidationError as PydanticValidationError
from backend.models.domain import (
    InvestigationResult,
    InvestigationStatus,
    EvidenceItem,
    RiskAssessment,
    RiskLevel,
    RiskSignal,
    SignalDirection,
    IndependenceGroup,
    InformationGap,
    StoppingDecision,
    StoppingStatus,
)
from agent.investigation.engine import investigation_engine
from agent.risk.signals import SignalExtractor, signal_extractor
from agent.risk.evaluator import RiskEvaluator, risk_evaluator
from agent.risk.service import RiskUncertaintyService, risk_uncertainty_service
from agent.workflows.state import create_initial_agent_state
from agent.workflows.workflow import (
    create_risk_assessment_workflow,
    risk_uncertainty_node,
)


class TestStage3NumericBoundsAndInvariants(unittest.TestCase):
    """Verifies mathematical invariants, numeric bounds [0.0, 1.0], and rejection of NaN/inf."""

    def test_probability_confidence_uncertainty_bounds(self):
        """Probability, confidence, and uncertainty must strictly fall in [0.0, 1.0]."""
        signals = [
            RiskSignal(
                signal_id="SIG-01",
                name="Suspicious Amount",
                direction=SignalDirection.SUPPORTS_FRAUD,
                independence_group=IndependenceGroup.TRANSACTION_ATTRIBUTES,
                weight=0.9,
                evidence_refs=["EV-1"],
            )
        ]
        prob, _ = risk_evaluator.compute_fraud_probability(signals)
        conf = risk_evaluator.compute_confidence(signals, prob)
        unc = risk_evaluator.compute_uncertainty(conf)

        self.assertGreaterEqual(prob, 0.0)
        self.assertLessEqual(prob, 1.0)
        self.assertGreaterEqual(conf, 0.0)
        self.assertLessEqual(conf, 1.0)
        self.assertGreaterEqual(unc, 0.0)
        self.assertLessEqual(unc, 1.0)

    def test_epistemic_uncertainty_identity(self):
        """Epistemic uncertainty must equal exactly 1.0 - confidence."""
        for c in [0.0, 0.25, 0.5, 0.725, 0.88, 1.0]:
            u = risk_evaluator.compute_uncertainty(c)
            self.assertAlmostEqual(u, round(1.0 - c, 4), places=4)
            self.assertAlmostEqual(c + u, 1.0, places=4)

    def test_pydantic_model_rejects_out_of_bounds_and_nan(self):
        """Pydantic model must reject NaN, inf, and values outside [0.0, 1.0]."""
        # Exceeds 1.0
        with self.assertRaises((PydanticValidationError, ValidationError)):
            RiskAssessment(
                risk_score=1.5,
                risk_level=RiskLevel.CRITICAL,
                fraud_probability=1.5,
                confidence=0.8,
                uncertainty=0.2,
            )

        # Less than 0.0
        with self.assertRaises((PydanticValidationError, ValidationError)):
            RiskAssessment(
                risk_score=-0.1,
                risk_level=RiskLevel.LOW,
                fraud_probability=-0.1,
                confidence=0.8,
                uncertainty=0.2,
            )

        # NaN
        with self.assertRaises((PydanticValidationError, ValidationError)):
            RiskAssessment(
                risk_score=float("nan"),
                risk_level=RiskLevel.LOW,
                fraud_probability=float("nan"),
                confidence=0.8,
                uncertainty=0.2,
            )

        # Infinity
        with self.assertRaises((PydanticValidationError, ValidationError)):
            RiskAssessment(
                risk_score=float("inf"),
                risk_level=RiskLevel.CRITICAL,
                fraud_probability=float("inf"),
                confidence=0.8,
                uncertainty=0.2,
            )


class TestStage3SignalExtraction(unittest.TestCase):
    """Verifies evidence signal extraction, taxonomy weighting, and untrusted dampening."""

    def setUp(self):
        self.sample_investigation = InvestigationResult(
            case_id="CASE-TEST-S3",
            transaction_id="TXN-001",
            status=InvestigationStatus.COMPLETE,
            transaction={"transaction_id": "TXN-001", "amount": 9500.0, "risk_score": 0.82, "device_id": "DEV-99"},
            customer={"customer_id": "CUST-001", "name": "Jane Doe", "kyc_status": "VERIFIED", "risk_rating": "LOW"},
            transaction_history=[
                {"transaction_id": "TXN-H1", "amount": 100.0},
                {"transaction_id": "TXN-H2", "amount": 150.0},
                {"transaction_id": "TXN-H3", "amount": 120.0},
                {"transaction_id": "TXN-H4", "amount": 130.0},
                {"transaction_id": "TXN-H5", "amount": 110.0},
            ],
            connected_entities={"total_connections": 15, "high_risk_connections": 4},
            fraud_pattern_evidence=[{"pattern_id": "PAT-01", "name": "Device Cycling", "confidence": 0.9}],
            similar_cases=[{"case_id": "C-PAST-1", "verdict": "FRAUD", "similarity_score": 0.88}],
            graphrag_context={"prompt_context": "Sample retrieved prompt context", "policy": {"requires_action": True}},
            evidence=[
                EvidenceItem(
                    evidence_id="EV-1",
                    category="TRANSACTION",
                    source="tigergraph.get_transaction",
                    claim="Transaction amount 9500.0 exceeds 95th percentile",
                    fact_level="FACT",
                    is_direct=True,
                    confidence=1.0,
                    entity_ids=["TXN-001"],
                    supporting=True,
                ),
                EvidenceItem(
                    evidence_id="EV-2",
                    category="TOPOLOGY",
                    source="tigergraph.detect_fraud_patterns",
                    claim="Device cycling pattern detected across 6 cards",
                    fact_level="OBSERVATION",
                    is_direct=False,
                    confidence=0.9,
                    entity_ids=["DEV-99"],
                    supporting=True,
                ),
            ],
            warnings=[],
            timeline=[],
            created_at=int(time.time()),
            completed_at=int(time.time()),
        )

    def test_extract_signals_categorization(self):
        """Verifies signals are categorized into SUPPORTS_FRAUD, SUPPORTS_LEGITIMATE, or NEUTRAL."""
        signals = signal_extractor.extract_signals(self.sample_investigation)
        self.assertGreater(len(signals), 0)

        supporting = [s for s in signals if s.direction == SignalDirection.SUPPORTS_FRAUD]
        contradicting = [s for s in signals if s.direction == SignalDirection.SUPPORTS_LEGITIMATE]
        neutral = [s for s in signals if s.direction == SignalDirection.NEUTRAL]

        self.assertGreater(len(supporting), 0)
        # Customer KYC is VERIFIED and risk_rating is LOW, so we expect legitimate signals
        self.assertGreater(len(contradicting), 0)

    def test_fact_level_quality_multipliers(self):
        """FACT (1.0) must produce higher weight than OBSERVATION (0.85) and INFERENCE (0.70)."""
        ev_fact = EvidenceItem(
            evidence_id="EV-F",
            category="TRANSACTION",
            source="test",
            claim="Fact level test",
            fact_level="FACT",
            is_direct=True,
            confidence=0.8,
            entity_ids=[],
            supporting=True,
        )
        ev_obs = EvidenceItem(
            evidence_id="EV-O",
            category="TRANSACTION",
            source="test",
            claim="Observation level test",
            fact_level="OBSERVATION",
            is_direct=True,
            confidence=0.8,
            entity_ids=[],
            supporting=True,
        )
        ev_inf = EvidenceItem(
            evidence_id="EV-I",
            category="TRANSACTION",
            source="test",
            claim="Inference level test",
            fact_level="INFERENCE",
            is_direct=True,
            confidence=0.8,
            entity_ids=[],
            supporting=True,
        )

        inv = self.sample_investigation.model_copy(update={"evidence": [ev_fact, ev_obs, ev_inf]})
        signals = signal_extractor.extract_signals(inv)

        sig_f = next(s for s in signals if "EV-F" in s.evidence_refs)
        sig_o = next(s for s in signals if "EV-O" in s.evidence_refs)
        sig_i = next(s for s in signals if "EV-I" in s.evidence_refs)

        self.assertAlmostEqual(sig_f.weight, 0.8 * 1.0 * 1.0, places=3)
        self.assertAlmostEqual(sig_o.weight, 0.8 * 0.85 * 1.0, places=3)
        self.assertAlmostEqual(sig_i.weight, 0.8 * 0.70 * 1.0, places=3)
        self.assertGreater(sig_f.weight, sig_o.weight)
        self.assertGreater(sig_o.weight, sig_i.weight)

    def test_direct_vs_indirect_evidence_weighting(self):
        """Direct evidence (1.0) must produce higher weight than indirect evidence (0.90)."""
        ev_direct = EvidenceItem(
            evidence_id="EV-D",
            category="TRANSACTION",
            source="test",
            claim="Direct test",
            fact_level="FACT",
            is_direct=True,
            confidence=0.8,
            entity_ids=[],
            supporting=True,
        )
        ev_indirect = EvidenceItem(
            evidence_id="EV-ID",
            category="TRANSACTION",
            source="test",
            claim="Indirect test",
            fact_level="FACT",
            is_direct=False,
            confidence=0.8,
            entity_ids=[],
            supporting=True,
        )

        inv = self.sample_investigation.model_copy(update={"evidence": [ev_direct, ev_indirect]})
        signals = signal_extractor.extract_signals(inv)

        sig_d = next(s for s in signals if "EV-D" in s.evidence_refs)
        sig_id = next(s for s in signals if "EV-ID" in s.evidence_refs)

        self.assertGreater(sig_d.weight, sig_id.weight)
        self.assertAlmostEqual(sig_d.weight, 0.8 * 1.0 * 1.0, places=3)
        self.assertAlmostEqual(sig_id.weight, 0.8 * 1.0 * 0.90, places=3)

    def test_untrusted_context_dampening(self):
        """Retrieved context flagged as untrusted must have weight dampened by 0.50."""
        ev_trusted = EvidenceItem(
            evidence_id="EV-T",
            source="test",
            claim="Trusted rule",
            fact_level="FACT",
            is_direct=True,
            confidence=0.8,
            entity_ids=[],
            untrusted_data_flag=False,
        )
        ev_untrusted = EvidenceItem(
            evidence_id="EV-UT",
            source="test",
            claim="Untrusted text with prompt injection attempt",
            fact_level="FACT",
            is_direct=True,
            confidence=0.8,
            entity_ids=[],
            untrusted_data_flag=True,
        )

        inv = self.sample_investigation.model_copy(update={"evidence": [ev_trusted, ev_untrusted]})
        signals = signal_extractor.extract_signals(inv)

        sig_t = next(s for s in signals if "EV-T" in s.evidence_refs)
        sig_ut = next(s for s in signals if "EV-UT" in s.evidence_refs)

        self.assertAlmostEqual(sig_t.weight, 0.8, places=3)
        self.assertAlmostEqual(sig_ut.weight, 0.8 * 0.50, places=3)
        self.assertGreater(sig_t.weight, sig_ut.weight)

    def test_independence_grouping_no_double_counting(self):
        """Multiple signals from the same IndependenceGroup do not inflate independent count."""
        # Create 3 signals all belonging to DEVICE_SHARING
        signals = [
            RiskSignal(
                signal_id="S1",
                name="Shared Device Account Count",
                direction=SignalDirection.SUPPORTS_FRAUD,
                independence_group=IndependenceGroup.DEVICE_SHARING,
                weight=0.7,
                evidence_refs=["E1"],
            ),
            RiskSignal(
                signal_id="S2",
                name="Emulator Flag",
                direction=SignalDirection.SUPPORTS_FRAUD,
                independence_group=IndependenceGroup.DEVICE_SHARING,
                weight=0.8,
                evidence_refs=["E2"],
            ),
            RiskSignal(
                signal_id="S3",
                name="Rapid Fingerprint Switch",
                direction=SignalDirection.SUPPORTS_FRAUD,
                independence_group=IndependenceGroup.DEVICE_SHARING,
                weight=0.6,
                evidence_refs=["E3"],
            ),
        ]
        prob, breakdown = risk_evaluator.compute_fraud_probability(signals)
        group_weights = breakdown["group_net_weights"]
        # In breakdown, DEVICE_SHARING should appear exactly once
        self.assertEqual(len(group_weights), 1)
        self.assertIn("DEVICE_SHARING", group_weights)
        # Dominant weight should be max (0.8)
        self.assertEqual(group_weights["DEVICE_SHARING"], 0.8)


class TestStage3InformationGaps(unittest.TestCase):
    """Verifies identification of missing evidence, contradictions, and partial investigation deductions."""

    def test_missing_customer_profile_gap(self):
        """Missing customer data generates MISSING_CUSTOMER_PROFILE information gap."""
        inv = InvestigationResult(
            case_id="C-1",
            transaction_id="TXN-001",
            status=InvestigationStatus.COMPLETE,
            transaction={"transaction_id": "TXN-001", "amount": 500.0},
            customer=None, # Missing customer
            evidence=[],
            created_at=100,
            completed_at=101,
        )
        gaps = risk_evaluator.identify_information_gaps(inv, [], 0.5, 0.5)
        gap_types = [g.gap_type for g in gaps]
        self.assertIn("MISSING_CUSTOMER_PROFILE", gap_types)

    def test_sparse_transaction_history_gap(self):
        """Transaction history with < 3 transactions triggers SPARSE_TRANSACTION_HISTORY gap."""
        inv = InvestigationResult(
            case_id="C-1",
            transaction_id="TXN-001",
            status=InvestigationStatus.COMPLETE,
            transaction={"transaction_id": "TXN-001", "amount": 500.0},
            customer={"customer_id": "C-1"},
            transaction_history=[{"transaction_id": "H-1"}], # Only 1 transaction
            evidence=[],
            created_at=100,
            completed_at=101,
        )
        gaps = risk_evaluator.identify_information_gaps(inv, [], 0.5, 0.5)
        gap_types = [g.gap_type for g in gaps]
        self.assertIn("SPARSE_TRANSACTION_HISTORY", gap_types)

    def test_uncorroborated_signal_gap(self):
        """A single fraud signal without corroboration triggers UNCORROBORATED_EVIDENCE gap."""
        signals = [
            RiskSignal(
                signal_id="S1",
                name="High Risk Score",
                direction=SignalDirection.SUPPORTS_FRAUD,
                independence_group=IndependenceGroup.TRANSACTION_ATTRIBUTES,
                weight=0.9,
                evidence_refs=["E1"],
            )
        ]
        inv = InvestigationResult(
            case_id="C-1",
            transaction_id="TXN-001",
            status=InvestigationStatus.COMPLETE,
            transaction={"transaction_id": "TXN-001"},
            customer={"customer_id": "C-1"},
            transaction_history=[{"id": 1}, {"id": 2}, {"id": 3}],
            evidence=[],
            created_at=100,
            completed_at=101,
        )
        gaps = risk_evaluator.identify_information_gaps(inv, signals, 0.6, 0.8)
        gap_types = [g.gap_type for g in gaps]
        self.assertIn("UNCORROBORATED_EVIDENCE", gap_types)

    def test_contradictory_evidence_gap(self):
        """Presence of both fraud and legitimate signals triggers CONTRADICTORY_EVIDENCE gap."""
        signals = [
            RiskSignal(
                signal_id="S1",
                name="Fraud Pattern",
                direction=SignalDirection.SUPPORTS_FRAUD,
                independence_group=IndependenceGroup.FRAUD_PATTERN,
                weight=0.8,
                evidence_refs=["E1"],
            ),
            RiskSignal(
                signal_id="S2",
                name="Verified Customer",
                direction=SignalDirection.SUPPORTS_LEGITIMATE,
                independence_group=IndependenceGroup.CUSTOMER_PROFILE,
                weight=0.8,
                evidence_refs=["E2"],
            ),
        ]
        inv = InvestigationResult(
            case_id="C-1",
            transaction_id="TXN-001",
            status=InvestigationStatus.COMPLETE,
            transaction={"transaction_id": "TXN-001"},
            customer={"customer_id": "C-1"},
            transaction_history=[{"id": 1}, {"id": 2}, {"id": 3}],
            evidence=[],
            created_at=100,
            completed_at=101,
        )
        gaps = risk_evaluator.identify_information_gaps(inv, signals, 0.6, 0.5)
        gap_types = [g.gap_type for g in gaps]
        self.assertIn("CONTRADICTORY_EVIDENCE", gap_types)

    def test_partial_investigation_confidence_penalty(self):
        """Investigation with warnings/errors has confidence penalized by 0.15."""
        signals = [
            RiskSignal(
                signal_id="S1",
                name="Fraud Pattern",
                direction=SignalDirection.SUPPORTS_FRAUD,
                independence_group=IndependenceGroup.FRAUD_PATTERN,
                weight=0.8,
                evidence_refs=["E1"],
            ),
            RiskSignal(
                signal_id="S2",
                name="Device Ring",
                direction=SignalDirection.SUPPORTS_FRAUD,
                independence_group=IndependenceGroup.DEVICE_SHARING,
                weight=0.8,
                evidence_refs=["E2"],
            ),
        ]
        # Clean investigation
        inv_clean = InvestigationResult(
            case_id="C-1",
            transaction_id="TXN-001",
            status=InvestigationStatus.COMPLETE,
            warnings=[],
            evidence=[],
            created_at=100,
            completed_at=101,
        )
        conf_clean = risk_evaluator.compute_confidence(signals, 0.9, inv_clean)

        # Partial investigation with warnings
        inv_warn = InvestigationResult(
            case_id="C-1",
            transaction_id="TXN-001",
            status=InvestigationStatus.PARTIAL,
            warnings=["tigergraph timeout on transaction history"],
            evidence=[],
            created_at=100,
            completed_at=101,
        )
        conf_warn = risk_evaluator.compute_confidence(signals, 0.9, inv_warn)

        self.assertAlmostEqual(conf_clean - conf_warn, 0.15, places=3)
        self.assertGreater(conf_clean, conf_warn)


class TestStage3OrganizerStoppingDecisions(unittest.TestCase):
    """Verifies stopping conditions from organizer specification."""

    def test_stopping_sufficient_evidence_high_fraud(self):
        """P >= 0.85 with >= 2 independent supporting groups -> SUFFICIENT_EVIDENCE."""
        signals = [
            RiskSignal(
                signal_id="S1",
                name="Typology Pattern",
                direction=SignalDirection.SUPPORTS_FRAUD,
                independence_group=IndependenceGroup.FRAUD_PATTERN,
                weight=0.9,
                evidence_refs=["E1"],
            ),
            RiskSignal(
                signal_id="S2",
                name="Device Ring Shared",
                direction=SignalDirection.SUPPORTS_FRAUD,
                independence_group=IndependenceGroup.DEVICE_SHARING,
                weight=0.9,
                evidence_refs=["E2"],
            ),
        ]
        inv = InvestigationResult(
            case_id="C-1",
            transaction_id="TXN-001",
            status=InvestigationStatus.COMPLETE,
            evidence=[],
            created_at=100,
            completed_at=101,
        )
        stopping = risk_evaluator.evaluate_stopping(
            fraud_probability=0.88,
            confidence=0.85,
            signals=signals,
            investigation=inv,
            gaps=[],
        )
        self.assertEqual(stopping.status, StoppingStatus.SUFFICIENT_EVIDENCE)
        self.assertIn("High fraud probability", stopping.rationale)

    def test_stopping_sufficient_evidence_low_fraud(self):
        """P <= 0.15 with >= 2 independent legitimate groups -> SUFFICIENT_EVIDENCE."""
        signals = [
            RiskSignal(
                signal_id="S1",
                name="Verified KYC",
                direction=SignalDirection.SUPPORTS_LEGITIMATE,
                independence_group=IndependenceGroup.CUSTOMER_PROFILE,
                weight=0.9,
                evidence_refs=["E1"],
            ),
            RiskSignal(
                signal_id="S2",
                name="Consistent History",
                direction=SignalDirection.SUPPORTS_LEGITIMATE,
                independence_group=IndependenceGroup.TRANSACTION_HISTORY,
                weight=0.9,
                evidence_refs=["E2"],
            ),
        ]
        inv = InvestigationResult(
            case_id="C-1",
            transaction_id="TXN-001",
            status=InvestigationStatus.COMPLETE,
            evidence=[],
            created_at=100,
            completed_at=101,
        )
        stopping = risk_evaluator.evaluate_stopping(
            fraud_probability=0.08,
            confidence=0.85,
            signals=signals,
            investigation=inv,
            gaps=[],
        )
        self.assertEqual(stopping.status, StoppingStatus.SUFFICIENT_EVIDENCE)
        self.assertIn("Low fraud probability", stopping.rationale)

    def test_stopping_sufficient_evidence_customer_settled(self):
        """Customer verification settled -> SUFFICIENT_EVIDENCE even with single group."""
        signals = [
            RiskSignal(
                signal_id="S1",
                name="Customer Confirmed Unauthorized Transaction",
                direction=SignalDirection.SUPPORTS_FRAUD,
                independence_group=IndependenceGroup.CUSTOMER_VERIFICATION,
                weight=1.0,
                evidence_refs=["E1"],
            )
        ]
        inv = InvestigationResult(
            case_id="C-1",
            transaction_id="TXN-001",
            status=InvestigationStatus.COMPLETE,
            evidence=[],
            created_at=100,
            completed_at=101,
        )
        stopping = risk_evaluator.evaluate_stopping(
            fraud_probability=0.95,
            confidence=0.90,
            signals=signals,
            investigation=inv,
            gaps=[],
        )
        self.assertEqual(stopping.status, StoppingStatus.SUFFICIENT_EVIDENCE)
        self.assertIn("Customer verification settled", stopping.rationale)

    def test_stopping_more_evidence_required_unsupported_high(self):
        """P >= 0.85 but only 1 independent group -> MORE_EVIDENCE_REQUIRED."""
        signals = [
            RiskSignal(
                signal_id="S1",
                name="Raw Risk Score High",
                direction=SignalDirection.SUPPORTS_FRAUD,
                independence_group=IndependenceGroup.TRANSACTION_ATTRIBUTES,
                weight=0.95,
                evidence_refs=["E1"],
            )
        ]
        inv = InvestigationResult(
            case_id="C-1",
            transaction_id="TXN-001",
            status=InvestigationStatus.COMPLETE,
            evidence=[],
            created_at=100,
            completed_at=101,
        )
        stopping = risk_evaluator.evaluate_stopping(
            fraud_probability=0.88,
            confidence=0.60,
            signals=signals,
            investigation=inv,
            gaps=[InformationGap(gap_type="MISSING_CORROBORATION", description="Uncorroborated single signal", impact_score=0.4)],
        )
        self.assertEqual(stopping.status, StoppingStatus.MORE_EVIDENCE_REQUIRED)
        self.assertIn("lacks >= 2 independent corroborating groups", stopping.rationale)
        self.assertIsNotNone(stopping.recommended_next_query)

    def test_stopping_investigation_blocked(self):
        """Blocked data source -> INVESTIGATION_BLOCKED."""
        inv = InvestigationResult(
            case_id="C-1",
            transaction_id="TXN-001",
            status=InvestigationStatus.PARTIAL,
            warnings=["TigerGraph database offline connection refused"],
            evidence=[],
            created_at=100,
            completed_at=101,
        )
        stopping = risk_evaluator.evaluate_stopping(
            fraud_probability=0.50,
            confidence=0.30,
            signals=[],
            investigation=inv,
            gaps=[InformationGap(gap_type="PARTIAL_INVESTIGATION_WARNINGS", description="DB offline", impact_score=0.8)],
        )
        self.assertEqual(stopping.status, StoppingStatus.INVESTIGATION_BLOCKED)
        self.assertIn("critical data sources unavailable", stopping.rationale)

    def test_stopping_inconclusive(self):
        """Moderate probability without blocking -> INCONCLUSIVE."""
        inv = InvestigationResult(
            case_id="C-1",
            transaction_id="TXN-001",
            status=InvestigationStatus.COMPLETE,
            warnings=[],
            evidence=[],
            created_at=100,
            completed_at=101,
        )
        stopping = risk_evaluator.evaluate_stopping(
            fraud_probability=0.52,
            confidence=0.55,
            signals=[],
            investigation=inv,
            gaps=[],
        )
        self.assertEqual(stopping.status, StoppingStatus.INCONCLUSIVE)
        self.assertIn("remains indeterminate", stopping.rationale)


class TestStage3ExplainabilitySummary(unittest.TestCase):
    """Verifies generation of structured, human-readable explainability summaries."""

    def test_explainability_summary_contains_required_sections(self):
        """Summary must contain verdict/probability, confidence, factors, and next step."""
        assessment = RiskAssessment(
            risk_score=0.88,
            risk_level=RiskLevel.CRITICAL,
            fraud_probability=0.88,
            confidence=0.82,
            uncertainty=0.18,
            evidence_count=5,
            independent_evidence_count=3,
            supporting_signals=["Device Cycling detected", "High amount outlier"],
            contradicting_signals=["KYC Verified"],
            stopping_decision=StoppingDecision(
                status=StoppingStatus.SUFFICIENT_EVIDENCE,
                reason="High fraud probability with 3 corroborating groups",
            ),
            information_gaps=[
                InformationGap(gap_type="DEVICE_HISTORY", description="Only 7 days of device telemetry", impact_score=0.2)
            ],
        )
        summary = risk_uncertainty_service.format_explainability_summary(assessment)

        self.assertIn("FRAUD PROBABILITY: 0.8800 (CRITICAL)", summary)
        self.assertIn("EPISTEMIC CONFIDENCE: 0.8200", summary)
        self.assertIn("EPISTEMIC UNCERTAINTY: 0.1800", summary)
        self.assertIn("SUPPORTING FRAUD FACTORS", summary)
        self.assertIn("CONTRADICTING / LEGITIMATE FACTORS", summary)
        self.assertIn("KEY UNCERTAINTY SOURCES", summary)
        self.assertIn("STOPPING DECISION: SUFFICIENT_EVIDENCE", summary)


class TestStage3StrictBoundaries(unittest.TestCase):
    """Verifies Person 1 Stage 3 does not violate architectural constraints or boundaries."""

    def setUp(self):
        self.sample_inv = InvestigationResult(
            case_id="C-STRICT",
            transaction_id="TXN-BOUND-1",
            status=InvestigationStatus.COMPLETE,
            transaction={"transaction_id": "TXN-BOUND-1", "amount": 2500.0, "risk_score": 0.5},
            customer={"customer_id": "C-BOUND"},
            evidence=[],
            created_at=100,
            completed_at=101,
        )

    def test_zero_person2_requerying(self):
        """RiskUncertaintyService must strictly consume InvestigationResult without querying Person 2."""
        with patch("agent.tools.graph_adapter.graph_adapter.get_transaction") as mock_get_txn, \
             patch("agent.tools.graph_adapter.graph_adapter.get_customer") as mock_get_cust, \
             patch("agent.tools.graph_adapter.graph_adapter.detect_fraud_patterns") as mock_patterns, \
             patch("agent.tools.graph_adapter.graph_adapter.retrieve_investigation_context") as mock_rag:

            assessment = risk_uncertainty_service.assess(self.sample_inv)

            mock_get_txn.assert_not_called()
            mock_get_cust.assert_not_called()
            mock_patterns.assert_not_called()
            mock_rag.assert_not_called()

            self.assertIsNotNone(assessment)
            self.assertIsInstance(assessment, RiskAssessment)

    def test_zero_stage4_nba_formulation(self):
        """Stage 3 must NOT formulate next best actions."""
        assessment = risk_uncertainty_service.assess(self.sample_inv)
        as_dict = assessment.model_dump()
        self.assertNotIn("next_best_action", as_dict)
        self.assertNotIn("recommended_action", as_dict)

    def test_zero_stage5_policy_and_approval(self):
        """Stage 3 must NOT evaluate policy rules R1-R10 or route approvals."""
        assessment = risk_uncertainty_service.assess(self.sample_inv)
        as_dict = assessment.model_dump()
        self.assertNotIn("policy_evaluation", as_dict)
        self.assertNotIn("approval_request", as_dict)
        self.assertNotIn("sar", as_dict)

    def test_zero_stage6_action_execution_and_writeback(self):
        """Stage 3 must NOT execute mock actions or write back to TigerGraph."""
        with patch("backend.services.mock_actions.mock_action_service.execute_action") as mock_exec, \
             patch("agent.tools.graph_adapter.graph_adapter.write_case_to_graph") as mock_write:

            assessment = risk_uncertainty_service.assess(self.sample_inv)

            mock_exec.assert_not_called()
            mock_write.assert_not_called()


class TestStage3Monotonicity(unittest.TestCase):
    """Verifies directional sensitivity: adding fraud signals increases probability, legitimate decreases."""

    def test_monotonicity_supporting_signals_increase_probability(self):
        """Adding supporting fraud signals strictly increases (or maintains at ceiling) fraud probability."""
        base_signals = [
            RiskSignal(
                signal_id="S1",
                name="Base Risk",
                direction=SignalDirection.SUPPORTS_FRAUD,
                independence_group=IndependenceGroup.TRANSACTION_ATTRIBUTES,
                weight=0.5,
                evidence_refs=["E1"],
            )
        ]
        p1, _ = risk_evaluator.compute_fraud_probability(base_signals)

        more_signals = base_signals + [
            RiskSignal(
                signal_id="S2",
                name="Device Ring",
                direction=SignalDirection.SUPPORTS_FRAUD,
                independence_group=IndependenceGroup.DEVICE_SHARING,
                weight=0.8,
                evidence_refs=["E2"],
            )
        ]
        p2, _ = risk_evaluator.compute_fraud_probability(more_signals)

        even_more_signals = more_signals + [
            RiskSignal(
                signal_id="S3",
                name="Typology Match",
                direction=SignalDirection.SUPPORTS_FRAUD,
                independence_group=IndependenceGroup.FRAUD_PATTERN,
                weight=0.9,
                evidence_refs=["E3"],
            )
        ]
        p3, _ = risk_evaluator.compute_fraud_probability(even_more_signals)

        self.assertGreater(p2, p1)
        self.assertGreater(p3, p2)

    def test_monotonicity_legitimate_signals_decrease_probability(self):
        """Adding legitimate signals strictly decreases (or maintains at floor) fraud probability."""
        base_signals = [
            RiskSignal(
                signal_id="S1",
                name="Base Risk",
                direction=SignalDirection.SUPPORTS_FRAUD,
                independence_group=IndependenceGroup.TRANSACTION_ATTRIBUTES,
                weight=0.6,
                evidence_refs=["E1"],
            )
        ]
        p1, _ = risk_evaluator.compute_fraud_probability(base_signals)

        with_legit = base_signals + [
            RiskSignal(
                signal_id="S2",
                name="Long Standing Customer KYC",
                direction=SignalDirection.SUPPORTS_LEGITIMATE,
                independence_group=IndependenceGroup.CUSTOMER_PROFILE,
                weight=0.8,
                evidence_refs=["E2"],
            )
        ]
        p2, _ = risk_evaluator.compute_fraud_probability(with_legit)

        with_more_legit = with_legit + [
            RiskSignal(
                signal_id="S3",
                name="Consistent History",
                direction=SignalDirection.SUPPORTS_LEGITIMATE,
                independence_group=IndependenceGroup.TRANSACTION_HISTORY,
                weight=0.85,
                evidence_refs=["E3"],
            )
        ]
        p3, _ = risk_evaluator.compute_fraud_probability(with_more_legit)

        self.assertLess(p2, p1)
        self.assertLess(p3, p2)


class TestStage3WorkflowIntegration(unittest.TestCase):
    """Verifies risk & uncertainty node execution within the stateful workflow engine."""

    def test_workflow_risk_assessment_pipeline(self):
        """Workflow pipeline runs through RISK_ASSESSMENT_COMPLETE and updates AgentState."""
        initial_state = create_initial_agent_state("TXN-104829")
        workflow = create_risk_assessment_workflow()
        final_state = workflow.run(initial_state)

        self.assertEqual(final_state["current_workflow_state"], "RISK_ASSESSMENT_COMPLETE")
        self.assertIsNotNone(final_state.get("risk_assessment"))
        self.assertIsNotNone(final_state.get("fraud_probability"))
        self.assertIsNotNone(final_state.get("uncertainty_assessment"))
        self.assertIsNotNone(final_state.get("stopping_decision"))

        # Invariants on AgentState
        p = final_state["fraud_probability"]
        self.assertGreaterEqual(p, 0.0)
        self.assertLessEqual(p, 1.0)

        conf = final_state["uncertainty_assessment"]["confidence"]
        unc = final_state["uncertainty_assessment"]["uncertainty"]
        self.assertAlmostEqual(conf + unc, 1.0, places=4)


class TestStage3RealDataSyndicateAndBenign(unittest.TestCase):
    """Tests Stage 3 engine against Person 2 graph data: TXN-104829 (syndicate) and TXN-209144 (benign)."""

    def test_real_data_syndicate_txn_104829(self):
        """
        TXN-104829 is a known fraud syndicate transaction (rapid transactions, shared devices, high score).
        Stage 3 must evaluate P >= 0.85, confidence >= 0.75, and status == SUFFICIENT_EVIDENCE.
        """
        inv_result = investigation_engine.investigate("TXN-104829")
        self.assertEqual(inv_result.status, InvestigationStatus.COMPLETE)

        assessment = risk_uncertainty_service.assess(inv_result)

        self.assertGreaterEqual(assessment.fraud_probability, 0.85)
        self.assertEqual(assessment.risk_level, RiskLevel.CRITICAL)
        self.assertGreaterEqual(assessment.confidence, 0.75)
        self.assertLessEqual(assessment.uncertainty, 0.25)
        self.assertGreaterEqual(assessment.independent_evidence_count, 2)
        self.assertEqual(assessment.stopping_decision.status, StoppingStatus.SUFFICIENT_EVIDENCE)
        self.assertIn("High fraud probability", assessment.stopping_decision.rationale)

    def test_real_data_benign_txn_209144(self):
        """
        TXN-209144 is a legitimate/benign transaction with low risk score and no fraud patterns.
        Stage 3 must evaluate P <= 0.35, recognizing legitimate factors and lower risk.
        """
        inv_result = investigation_engine.investigate("TXN-209144")
        self.assertEqual(inv_result.status, InvestigationStatus.COMPLETE)

        assessment = risk_uncertainty_service.assess(inv_result)

        self.assertLessEqual(assessment.fraud_probability, 0.35)
        self.assertIn(assessment.risk_level, [RiskLevel.LOW, RiskLevel.MEDIUM])
        self.assertGreater(len(assessment.contradicting_signals), 0)



class TestStage3HistoricalPrecedentAggregation(unittest.TestCase):
    """
    Focused tests for the Stage 3 Historical Precedent aggregation fix.
    
    Verifies:
    1. Unanimous fraud precedents (3:0) scale positively.
    2. Majority fraud precedents (2:1) do NOT cancel to 0.0, but contribute positive net weight.
    3. Balanced precedents (1:1) contribute exactly 0.0 net weight.
    4. Majority legitimate precedents (1:2) contribute negative net weight.
    5. Unanimous legitimate precedents (0:3) scale negatively.
    6. Correlated case protection prevents linear multiplication sum(w).
    7. Similarity / quality weighting continues to matter.
    8. No double counting across independent evidence groups.
    """

    def test_unanimous_fraud_precedents(self):
        """Unanimous fraud precedents (3:0) contribute full max fraud weight."""
        signals = [
            RiskSignal(
                signal_id="PREC-1",
                name="Precedent 1",
                direction=SignalDirection.SUPPORTS_FRAUD,
                independence_group=IndependenceGroup.HISTORICAL_CASE,
                weight=0.85,
                evidence_refs=["E1"],
            ),
            RiskSignal(
                signal_id="PREC-2",
                name="Precedent 2",
                direction=SignalDirection.SUPPORTS_FRAUD,
                independence_group=IndependenceGroup.HISTORICAL_CASE,
                weight=0.80,
                evidence_refs=["E2"],
            ),
            RiskSignal(
                signal_id="PREC-3",
                name="Precedent 3",
                direction=SignalDirection.SUPPORTS_FRAUD,
                independence_group=IndependenceGroup.HISTORICAL_CASE,
                weight=0.70,
                evidence_refs=["E3"],
            ),
        ]
        prob, breakdown = risk_evaluator.compute_fraud_probability(signals)
        net_w = breakdown["group_net_weights"][IndependenceGroup.HISTORICAL_CASE.value]

        # Balance = (3 - 0)/3 = 1.0 -> net_w = 1.0 * 0.85 = 0.85
        self.assertAlmostEqual(net_w, 0.85, places=4)
        self.assertGreater(prob, 0.20)

    def test_fraud_majority_precedents(self):
        """2:1 fraud majority does NOT cancel to 0.0; contributes direction_balance * max_fraud_w."""
        signals = [
            RiskSignal(
                signal_id="PREC-1",
                name="Precedent Fraud 1",
                direction=SignalDirection.SUPPORTS_FRAUD,
                independence_group=IndependenceGroup.HISTORICAL_CASE,
                weight=0.80,
                evidence_refs=["E1"],
            ),
            RiskSignal(
                signal_id="PREC-2",
                name="Precedent Fraud 2",
                direction=SignalDirection.SUPPORTS_FRAUD,
                independence_group=IndependenceGroup.HISTORICAL_CASE,
                weight=0.75,
                evidence_refs=["E2"],
            ),
            RiskSignal(
                signal_id="PREC-3",
                name="Precedent Legit 1",
                direction=SignalDirection.SUPPORTS_LEGITIMATE,
                independence_group=IndependenceGroup.HISTORICAL_CASE,
                weight=0.80,
                evidence_refs=["E3"],
            ),
        ]
        prob, breakdown = risk_evaluator.compute_fraud_probability(signals)
        net_w = breakdown["group_net_weights"][IndependenceGroup.HISTORICAL_CASE.value]

        # Balance = (2 - 1)/3 = 0.3333... -> net_w = 0.3333... * 0.80 = 0.2667
        # Old broken behavior gave 0.80 - 0.80 = 0.0000!
        self.assertGreater(net_w, 0.0)
        self.assertAlmostEqual(net_w, round((1.0 / 3.0) * 0.80, 4), places=4)
        self.assertGreater(prob, 0.20)

    def test_balanced_precedents(self):
        """1:1 balanced precedents yield exactly 0.0 net weight."""
        signals = [
            RiskSignal(
                signal_id="PREC-1",
                name="Precedent Fraud 1",
                direction=SignalDirection.SUPPORTS_FRAUD,
                independence_group=IndependenceGroup.HISTORICAL_CASE,
                weight=0.80,
                evidence_refs=["E1"],
            ),
            RiskSignal(
                signal_id="PREC-2",
                name="Precedent Legit 1",
                direction=SignalDirection.SUPPORTS_LEGITIMATE,
                independence_group=IndependenceGroup.HISTORICAL_CASE,
                weight=0.80,
                evidence_refs=["E2"],
            ),
        ]
        prob, breakdown = risk_evaluator.compute_fraud_probability(signals)
        net_w = breakdown["group_net_weights"][IndependenceGroup.HISTORICAL_CASE.value]

        # Balance = (1 - 1)/2 = 0.0 -> net_w = 0.0
        self.assertEqual(net_w, 0.0)
        self.assertAlmostEqual(prob, 0.20, places=4)

    def test_legitimate_majority_precedents(self):
        """1:2 legitimate majority contributes negative net weight."""
        signals = [
            RiskSignal(
                signal_id="PREC-1",
                name="Precedent Fraud 1",
                direction=SignalDirection.SUPPORTS_FRAUD,
                independence_group=IndependenceGroup.HISTORICAL_CASE,
                weight=0.80,
                evidence_refs=["E1"],
            ),
            RiskSignal(
                signal_id="PREC-2",
                name="Precedent Legit 1",
                direction=SignalDirection.SUPPORTS_LEGITIMATE,
                independence_group=IndependenceGroup.HISTORICAL_CASE,
                weight=0.80,
                evidence_refs=["E2"],
            ),
            RiskSignal(
                signal_id="PREC-3",
                name="Precedent Legit 2",
                direction=SignalDirection.SUPPORTS_LEGITIMATE,
                independence_group=IndependenceGroup.HISTORICAL_CASE,
                weight=0.75,
                evidence_refs=["E3"],
            ),
        ]
        prob, breakdown = risk_evaluator.compute_fraud_probability(signals)
        net_w = breakdown["group_net_weights"][IndependenceGroup.HISTORICAL_CASE.value]

        # Balance = (1 - 2)/3 = -0.3333... -> net_w = -0.3333... * 0.80 = -0.2667
        self.assertLess(net_w, 0.0)
        self.assertAlmostEqual(net_w, round((-1.0 / 3.0) * 0.80, 4), places=4)
        self.assertLess(prob, 0.20)

    def test_unanimous_legitimate_precedents(self):
        """Unanimous legitimate precedents (0:3) contribute full negative max legit weight."""
        signals = [
            RiskSignal(
                signal_id="PREC-1",
                name="Precedent Legit 1",
                direction=SignalDirection.SUPPORTS_LEGITIMATE,
                independence_group=IndependenceGroup.HISTORICAL_CASE,
                weight=0.85,
                evidence_refs=["E1"],
            ),
            RiskSignal(
                signal_id="PREC-2",
                name="Precedent Legit 2",
                direction=SignalDirection.SUPPORTS_LEGITIMATE,
                independence_group=IndependenceGroup.HISTORICAL_CASE,
                weight=0.80,
                evidence_refs=["E2"],
            ),
            RiskSignal(
                signal_id="PREC-3",
                name="Precedent Legit 3",
                direction=SignalDirection.SUPPORTS_LEGITIMATE,
                independence_group=IndependenceGroup.HISTORICAL_CASE,
                weight=0.70,
                evidence_refs=["E3"],
            ),
        ]
        prob, breakdown = risk_evaluator.compute_fraud_probability(signals)
        net_w = breakdown["group_net_weights"][IndependenceGroup.HISTORICAL_CASE.value]

        # Balance = (0 - 3)/3 = -1.0 -> net_w = -1.0 * 0.85 = -0.85
        self.assertAlmostEqual(net_w, -0.85, places=4)
        self.assertLess(prob, 0.10)

    def test_correlated_case_protection(self):
        """Correlated case protection ensures adding duplicate cases does not multiply linearly."""
        single_case = [
            RiskSignal(
                signal_id="PREC-1",
                name="Precedent 1",
                direction=SignalDirection.SUPPORTS_FRAUD,
                independence_group=IndependenceGroup.HISTORICAL_CASE,
                weight=0.80,
                evidence_refs=["E1"],
            )
        ]
        ten_cases = [
            RiskSignal(
                signal_id=f"PREC-{i}",
                name=f"Precedent {i}",
                direction=SignalDirection.SUPPORTS_FRAUD,
                independence_group=IndependenceGroup.HISTORICAL_CASE,
                weight=0.80,
                evidence_refs=[f"E{i}"],
            )
            for i in range(10)
        ]
        prob_1, breakdown_1 = risk_evaluator.compute_fraud_probability(single_case)
        prob_10, breakdown_10 = risk_evaluator.compute_fraud_probability(ten_cases)

        net_w_1 = breakdown_1["group_net_weights"][IndependenceGroup.HISTORICAL_CASE.value]
        net_w_10 = breakdown_10["group_net_weights"][IndependenceGroup.HISTORICAL_CASE.value]

        # Both have balance = 1.0, max_w = 0.80 -> net_w = 0.80
        # It is strictly bounded by max_w and does NOT sum linearly to 8.0
        self.assertEqual(net_w_1, 0.80)
        self.assertEqual(net_w_10, 0.80)
        self.assertEqual(prob_1, prob_10)

    def test_similarity_still_matters(self):
        """Higher similarity / quality weight produces stronger effect under same majority ratio."""
        high_sim = [
            RiskSignal(
                signal_id="H1",
                name="High Sim Fraud 1",
                direction=SignalDirection.SUPPORTS_FRAUD,
                independence_group=IndependenceGroup.HISTORICAL_CASE,
                weight=0.90,
                evidence_refs=["E1"],
            ),
            RiskSignal(
                signal_id="H2",
                name="High Sim Fraud 2",
                direction=SignalDirection.SUPPORTS_FRAUD,
                independence_group=IndependenceGroup.HISTORICAL_CASE,
                weight=0.90,
                evidence_refs=["E2"],
            ),
            RiskSignal(
                signal_id="H3",
                name="High Sim Legit",
                direction=SignalDirection.SUPPORTS_LEGITIMATE,
                independence_group=IndependenceGroup.HISTORICAL_CASE,
                weight=0.90,
                evidence_refs=["E3"],
            ),
        ]
        low_sim = [
            RiskSignal(
                signal_id="L1",
                name="Low Sim Fraud 1",
                direction=SignalDirection.SUPPORTS_FRAUD,
                independence_group=IndependenceGroup.HISTORICAL_CASE,
                weight=0.45,
                evidence_refs=["E1"],
            ),
            RiskSignal(
                signal_id="L2",
                name="Low Sim Fraud 2",
                direction=SignalDirection.SUPPORTS_FRAUD,
                independence_group=IndependenceGroup.HISTORICAL_CASE,
                weight=0.45,
                evidence_refs=["E2"],
            ),
            RiskSignal(
                signal_id="L3",
                name="Low Sim Legit",
                direction=SignalDirection.SUPPORTS_LEGITIMATE,
                independence_group=IndependenceGroup.HISTORICAL_CASE,
                weight=0.45,
                evidence_refs=["E3"],
            ),
        ]
        prob_high, breakdown_high = risk_evaluator.compute_fraud_probability(high_sim)
        prob_low, breakdown_low = risk_evaluator.compute_fraud_probability(low_sim)

        net_w_high = breakdown_high["group_net_weights"][IndependenceGroup.HISTORICAL_CASE.value]
        net_w_low = breakdown_low["group_net_weights"][IndependenceGroup.HISTORICAL_CASE.value]

        self.assertGreater(net_w_high, net_w_low)
        self.assertGreater(prob_high, prob_low)

    def test_no_double_counting_across_groups(self):
        """Historical precedent group remains an isolated independent group alongside other evidence groups."""
        signals = [
            # 2:1 fraud precedent majority
            RiskSignal(
                signal_id="PREC-1",
                name="Precedent Fraud 1",
                direction=SignalDirection.SUPPORTS_FRAUD,
                independence_group=IndependenceGroup.HISTORICAL_CASE,
                weight=0.80,
                evidence_refs=["E1"],
            ),
            RiskSignal(
                signal_id="PREC-2",
                name="Precedent Fraud 2",
                direction=SignalDirection.SUPPORTS_FRAUD,
                independence_group=IndependenceGroup.HISTORICAL_CASE,
                weight=0.75,
                evidence_refs=["E2"],
            ),
            RiskSignal(
                signal_id="PREC-3",
                name="Precedent Legit",
                direction=SignalDirection.SUPPORTS_LEGITIMATE,
                independence_group=IndependenceGroup.HISTORICAL_CASE,
                weight=0.80,
                evidence_refs=["E3"],
            ),
            # Transaction attributes group
            RiskSignal(
                signal_id="TXN-1",
                name="High Amount",
                direction=SignalDirection.SUPPORTS_FRAUD,
                independence_group=IndependenceGroup.TRANSACTION_ATTRIBUTES,
                weight=0.60,
                evidence_refs=["E4"],
            ),
            # Device sharing group
            RiskSignal(
                signal_id="DEV-1",
                name="Shared Device",
                direction=SignalDirection.SUPPORTS_FRAUD,
                independence_group=IndependenceGroup.DEVICE_SHARING,
                weight=0.70,
                evidence_refs=["E5"],
            ),
        ]
        prob, breakdown = risk_evaluator.compute_fraud_probability(signals)
        group_weights = breakdown["group_net_weights"]

        # 3 distinct independent groups present
        self.assertIn(IndependenceGroup.HISTORICAL_CASE.value, group_weights)
        self.assertIn(IndependenceGroup.TRANSACTION_ATTRIBUTES.value, group_weights)
        self.assertIn(IndependenceGroup.DEVICE_SHARING.value, group_weights)

        # Expected weights
        expected_hist = round((1.0 / 3.0) * 0.80, 4)
        expected_txn = 0.60
        expected_dev = 0.70

        self.assertEqual(group_weights[IndependenceGroup.HISTORICAL_CASE.value], expected_hist)
        self.assertEqual(group_weights[IndependenceGroup.TRANSACTION_ATTRIBUTES.value], expected_txn)
        self.assertEqual(group_weights[IndependenceGroup.DEVICE_SHARING.value], expected_dev)

        # Total delta log-odds = (w_hist + w_txn + w_dev) * 1.6
        expected_delta_l = (expected_hist + expected_txn + expected_dev) * 1.6
        expected_total_l = risk_evaluator.BASE_PRIOR_L0 + expected_delta_l
        self.assertAlmostEqual(breakdown["total_log_odds"], round(expected_total_l, 4), places=3)


if __name__ == "__main__":
    unittest.main()
