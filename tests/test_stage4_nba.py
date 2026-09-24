# ==============================================================================
# FraudGraph AI - Stage 4 Next Best Action (NBA) Engine Unit Tests
# Workstream: Person 1 (Brain) - Stage 4
# ==============================================================================

import unittest
from unittest.mock import MagicMock, patch
from typing import Dict, Any, List

from backend.models.domain import (
    ActionType,
    CANONICAL_ACTION_NAMES,
    NextBestActionItem,
    NBAWhatChanged,
    NextBestActionAssessment,
    InvestigationResult,
    InvestigationStatus,
    RiskAssessment,
    RiskLevel,
    StoppingStatus,
    StoppingDecision,
    InformationGap,
    RiskSignal,
    SignalDirection,
    IndependenceGroup,
    FraudPattern,
    Transaction,
    Customer,
    ActionRecommendation,
)
from agent.nba.engine import NBAEngine, nba_engine
from agent.nba.service import NBAService, nba_service
from agent.workflows import create_nba_workflow, create_initial_agent_state
from agent.reasoning.interfaces import NextBestActionEngineInterface
from backend.api.app import app
from tests.test_stage1_foundation import asgi_request


class TestStage4ActionVocabulary(unittest.TestCase):
    """Test suite validating canonical action vocabulary constraints."""

    def test_all_14_canonical_actions_defined(self):
        expected_actions = {
            "ALLOW_TRANSACTION",
            "DECLINE_TRANSACTION",
            "MONITOR_CARD",
            "MONITOR_CONNECTED_CARDS",
            "WARN_CUSTOMER",
            "VERIFY_WITH_CUSTOMER",
            "STEP_UP_AUTH",
            "BLOCK_CARD",
            "BLOCK_ALL_CARDS",
            "GENERATE_REPORT",
            "CREATE_CASE",
            "FILE_REPORT",
            "ESCALATE_TO_ANALYST",
            "CLOSE_NO_FRAUD",
        }
        self.assertEqual(CANONICAL_ACTION_NAMES, expected_actions)
        self.assertEqual(len(CANONICAL_ACTION_NAMES), 14)

    def test_canonical_actions_accepted_by_item_model(self):
        for action_name in CANONICAL_ACTION_NAMES:
            item = NextBestActionItem(
                action=action_name,
                rationale=f"Rationale for {action_name}",
                priority=1,
            )
            self.assertEqual(item.action, action_name)
            self.assertEqual(item.reason, f"Rationale for {action_name}")

    def test_legacy_aliases_normalized_to_canonical(self):
        item_block = NextBestActionItem(action="BLOCK_TRANSACTION", rationale="Legacy alias test")
        self.assertEqual(item_block.action, "DECLINE_TRANSACTION")

        item_freeze = NextBestActionItem(action="FREEZE_ACCOUNT", rationale="Legacy alias test")
        self.assertEqual(item_freeze.action, "BLOCK_ALL_CARDS")

        item_step_up = NextBestActionItem(action="REQUEST_STEP_UP_AUTH", rationale="Legacy alias test")
        self.assertEqual(item_step_up.action, "STEP_UP_AUTH")

        item_verif = NextBestActionItem(action="REQUEST_VERIFICATION", rationale="Legacy alias test")
        self.assertEqual(item_verif.action, "VERIFY_WITH_CUSTOMER")

        item_sar = NextBestActionItem(action="FILE_SAR", rationale="Legacy alias test")
        self.assertEqual(item_sar.action, "FILE_REPORT")

        item_mon = NextBestActionItem(action="MONITOR", rationale="Legacy alias test")
        self.assertEqual(item_mon.action, "MONITOR_CARD")

    def test_invalid_action_rejected(self):
        with self.assertRaises(ValueError):
            NextBestActionItem(action="INVALID_ACTION_NAME", rationale="Bad action")

        with self.assertRaises(ValueError):
            NextBestActionItem(action="SUSPEND_USER", rationale="Non-canonical")


class TestStage4NBAEngineRules(unittest.TestCase):
    """Test suite validating deterministic NBA heuristic rule branches."""

    def setUp(self):
        self.engine = NBAEngine()
        self.sample_tx = Transaction(
            transaction_id="TXN-TEST-01",
            customer_id="C-TEST-01",
            account_id="ACC-01",
            amount=500.0,
        )
        self.inv_base = InvestigationResult(
            transaction_id="TXN-TEST-01",
            status=InvestigationStatus.COMPLETE,
            transaction=self.sample_tx.model_dump(),
        )

    def test_investigation_blocked_escalates_to_analyst(self):
        risk = RiskAssessment(
            transaction_id="TXN-TEST-01",
            fraud_probability=0.75,
            risk_level=RiskLevel.HIGH,
            confidence=0.1,
            uncertainty=0.9,
            stopping_decision=StoppingDecision(
                status=StoppingStatus.INVESTIGATION_BLOCKED,
                reason="Graph database offline: connection refused.",
                fraud_probability=0.75,
                confidence=0.1,
                missing_information=["Primary data source offline"],
            ),
        )
        actions = self.engine.recommend_actions(risk, self.inv_base)

        self.assertGreaterEqual(len(actions), 2)
        self.assertEqual(actions[0].action, ActionType.ESCALATE_TO_ANALYST.value)
        self.assertEqual(actions[0].priority, 1)
        self.assertEqual(actions[1].action, ActionType.GENERATE_REPORT.value)
        self.assertEqual(actions[1].priority, 2)
        # Verify no non-canonical actions
        for a in actions:
            self.assertIn(a.action, CANONICAL_ACTION_NAMES)

    def test_inconclusive_escalates_to_analyst_and_monitors(self):
        risk = RiskAssessment(
            transaction_id="TXN-TEST-01",
            fraud_probability=0.45,
            risk_level=RiskLevel.MEDIUM,
            confidence=0.3,
            uncertainty=0.7,
            stopping_decision=StoppingDecision(
                status=StoppingStatus.INCONCLUSIVE,
                reason="Evidence exhausted without conclusive threshold.",
                fraud_probability=0.45,
                confidence=0.3,
            ),
        )
        actions = self.engine.recommend_actions(risk, self.inv_base)

        self.assertGreaterEqual(len(actions), 2)
        self.assertEqual(actions[0].action, ActionType.ESCALATE_TO_ANALYST.value)
        self.assertEqual(actions[1].action, ActionType.MONITOR_CARD.value)

    def test_more_evidence_contradictory_escalates_to_analyst(self):
        risk = RiskAssessment(
            transaction_id="TXN-TEST-01",
            fraud_probability=0.55,
            risk_level=RiskLevel.MEDIUM,
            confidence=0.4,
            uncertainty=0.6,
            stopping_decision=StoppingDecision(
                status=StoppingStatus.MORE_EVIDENCE_REQUIRED,
                reason="Conflicting signals observed.",
                fraud_probability=0.55,
                confidence=0.4,
            ),
            information_gaps=[
                InformationGap(
                    gap_type="CONTRADICTORY_EVIDENCE",
                    description="High-weight fraud pattern vs long legitimate customer history",
                )
            ],
        )
        actions = self.engine.recommend_actions(risk, self.inv_base)

        self.assertEqual(actions[0].action, ActionType.ESCALATE_TO_ANALYST.value)
        self.assertEqual(actions[1].action, ActionType.VERIFY_WITH_CUSTOMER.value)

    def test_more_evidence_unverified_customer_high_risk_declines(self):
        risk = RiskAssessment(
            transaction_id="TXN-TEST-01",
            fraud_probability=0.78,
            risk_level=RiskLevel.HIGH,
            confidence=0.4,
            uncertainty=0.6,
            stopping_decision=StoppingDecision(
                status=StoppingStatus.MORE_EVIDENCE_REQUIRED,
                reason="Uncorroborated high risk pending customer statement.",
                fraud_probability=0.78,
                confidence=0.4,
            ),
            information_gaps=[
                InformationGap(
                    gap_type="UNVERIFIED_CUSTOMER_INQUIRY",
                    description="No direct cardholder confirmation on record",
                )
            ],
        )
        actions = self.engine.recommend_actions(risk, self.inv_base)

        self.assertEqual(actions[0].action, ActionType.DECLINE_TRANSACTION.value)
        self.assertEqual(actions[1].action, ActionType.VERIFY_WITH_CUSTOMER.value)

    def test_more_evidence_unverified_customer_intermediate_requests_step_up(self):
        risk = RiskAssessment(
            transaction_id="TXN-TEST-01",
            fraud_probability=0.45,
            risk_level=RiskLevel.MEDIUM,
            confidence=0.4,
            uncertainty=0.6,
            stopping_decision=StoppingDecision(
                status=StoppingStatus.MORE_EVIDENCE_REQUIRED,
                reason="Intermediate anomaly pending cardholder challenge.",
                fraud_probability=0.45,
                confidence=0.4,
            ),
            information_gaps=[
                InformationGap(
                    gap_type="UNVERIFIED_CUSTOMER_INQUIRY",
                    description="No direct cardholder confirmation",
                )
            ],
        )
        actions = self.engine.recommend_actions(risk, self.inv_base)

        self.assertEqual(actions[0].action, ActionType.STEP_UP_AUTH.value)
        self.assertEqual(actions[1].action, ActionType.VERIFY_WITH_CUSTOMER.value)

    def test_more_evidence_uncorroborated_high_risk_declines(self):
        risk = RiskAssessment(
            transaction_id="TXN-TEST-01",
            fraud_probability=0.88,
            risk_level=RiskLevel.CRITICAL,
            confidence=0.4,
            uncertainty=0.6,
            stopping_decision=StoppingDecision(
                status=StoppingStatus.MORE_EVIDENCE_REQUIRED,
                reason="High probability lacks >= 2 independent evidence groups.",
                fraud_probability=0.88,
                confidence=0.4,
            ),
            information_gaps=[
                InformationGap(
                    gap_type="UNCORROBORATED_EVIDENCE",
                    description="Single source pattern",
                )
            ],
        )
        actions = self.engine.recommend_actions(risk, self.inv_base)

        self.assertEqual(actions[0].action, ActionType.DECLINE_TRANSACTION.value)
        self.assertEqual(actions[1].action, ActionType.VERIFY_WITH_CUSTOMER.value)

    def test_more_evidence_missing_profile_requests_step_up(self):
        risk = RiskAssessment(
            transaction_id="TXN-TEST-01",
            fraud_probability=0.50,
            risk_level=RiskLevel.MEDIUM,
            confidence=0.3,
            uncertainty=0.7,
            stopping_decision=StoppingDecision(
                status=StoppingStatus.MORE_EVIDENCE_REQUIRED,
                reason="Missing profile baseline.",
                fraud_probability=0.50,
                confidence=0.3,
            ),
            information_gaps=[
                InformationGap(
                    gap_type="MISSING_CUSTOMER_PROFILE",
                    description="No KYC or customer record found",
                )
            ],
        )
        actions = self.engine.recommend_actions(risk, self.inv_base)

        self.assertEqual(actions[0].action, ActionType.STEP_UP_AUTH.value)

    def test_sufficient_evidence_critical_multi_card_blocks_all(self):
        inv_syndicate = InvestigationResult(
            transaction_id="TXN-TEST-01",
            status=InvestigationStatus.COMPLETE,
            transaction=self.sample_tx.model_dump(),
            fraud_pattern_evidence=[
                FraudPattern(
                    pattern_id="FP-01",
                    name="Card Syndicate Ring",
                    description="Shared device across multiple compromised cards",
                    severity=RiskLevel.HIGH,
                    confidence=0.9,
                ).model_dump()
            ],
            connected_entities={"connected_cards": ["CARD-01", "CARD-02", "CARD-03"]},
        )
        risk = RiskAssessment(
            transaction_id="TXN-TEST-01",
            fraud_probability=0.92,
            risk_level=RiskLevel.CRITICAL,
            confidence=0.88,
            uncertainty=0.12,
            stopping_decision=StoppingDecision(
                status=StoppingStatus.SUFFICIENT_EVIDENCE,
                reason="Corroborated critical fraud probability with multi-card ring.",
                fraud_probability=0.92,
                confidence=0.88,
                independent_evidence_count=3,
            ),
        )
        actions = self.engine.recommend_actions(risk, inv_syndicate)

        self.assertEqual(actions[0].action, ActionType.BLOCK_ALL_CARDS.value)
        self.assertEqual(actions[1].action, ActionType.FILE_REPORT.value)
        self.assertEqual(actions[2].action, ActionType.CREATE_CASE.value)

    def test_sufficient_evidence_critical_single_card_blocks_card(self):
        inv_single = InvestigationResult(
            transaction_id="TXN-TEST-01",
            status=InvestigationStatus.COMPLETE,
            transaction=self.sample_tx.model_dump(),
            fraud_pattern_evidence=[
                FraudPattern(
                    pattern_id="FP-02",
                    name="Velocity Spike",
                    description="Rapid bursts on single card",
                    severity=RiskLevel.HIGH,
                    confidence=0.85,
                ).model_dump()
            ],
        )
        risk = RiskAssessment(
            transaction_id="TXN-TEST-01",
            fraud_probability=0.89,
            risk_level=RiskLevel.CRITICAL,
            confidence=0.85,
            uncertainty=0.15,
            stopping_decision=StoppingDecision(
                status=StoppingStatus.SUFFICIENT_EVIDENCE,
                reason="Corroborated critical fraud probability.",
                fraud_probability=0.89,
                confidence=0.85,
                independent_evidence_count=2,
            ),
        )
        actions = self.engine.recommend_actions(risk, inv_single)

        self.assertEqual(actions[0].action, ActionType.BLOCK_CARD.value)
        self.assertEqual(actions[1].action, ActionType.DECLINE_TRANSACTION.value)
        self.assertEqual(actions[2].action, ActionType.CREATE_CASE.value)

    def test_sufficient_evidence_high_risk_declines_and_blocks_card(self):
        risk = RiskAssessment(
            transaction_id="TXN-TEST-01",
            fraud_probability=0.76,
            risk_level=RiskLevel.HIGH,
            confidence=0.82,
            uncertainty=0.18,
            stopping_decision=StoppingDecision(
                status=StoppingStatus.SUFFICIENT_EVIDENCE,
                reason="Corroborated high fraud risk.",
                fraud_probability=0.76,
                confidence=0.82,
                independent_evidence_count=2,
            ),
        )
        actions = self.engine.recommend_actions(risk, self.inv_base)

        self.assertEqual(actions[0].action, ActionType.DECLINE_TRANSACTION.value)
        self.assertEqual(actions[1].action, ActionType.BLOCK_CARD.value)
        self.assertEqual(actions[2].action, ActionType.CREATE_CASE.value)

    def test_sufficient_evidence_low_risk_cleared_closes_no_fraud(self):
        risk = RiskAssessment(
            transaction_id="TXN-TEST-01",
            fraud_probability=0.08,
            risk_level=RiskLevel.LOW,
            confidence=0.90,
            uncertainty=0.10,
            stopping_decision=StoppingDecision(
                status=StoppingStatus.SUFFICIENT_EVIDENCE,
                reason="Corroborated legitimate customer transaction.",
                fraud_probability=0.08,
                confidence=0.90,
                independent_evidence_count=2,
            ),
        )
        actions = self.engine.recommend_actions(risk, self.inv_base)

        self.assertEqual(actions[0].action, ActionType.CLOSE_NO_FRAUD.value)
        self.assertEqual(actions[1].action, ActionType.ALLOW_TRANSACTION.value)

    def test_sufficient_evidence_low_risk_observation_allows(self):
        risk = RiskAssessment(
            transaction_id="TXN-TEST-01",
            fraud_probability=0.22,
            risk_level=RiskLevel.LOW,
            confidence=0.75,
            uncertainty=0.25,
            stopping_decision=StoppingDecision(
                status=StoppingStatus.SUFFICIENT_EVIDENCE,
                reason="Low fraud probability under observation.",
                fraud_probability=0.22,
                confidence=0.75,
                independent_evidence_count=2,
            ),
        )
        actions = self.engine.recommend_actions(risk, self.inv_base)

        self.assertEqual(actions[0].action, ActionType.ALLOW_TRANSACTION.value)
        self.assertEqual(actions[1].action, ActionType.MONITOR_CARD.value)

    def test_priorities_are_strictly_monotonic_and_deduplicated(self):
        risk = RiskAssessment(
            transaction_id="TXN-TEST-01",
            fraud_probability=0.95,
            risk_level=RiskLevel.CRITICAL,
            confidence=0.90,
            uncertainty=0.10,
            stopping_decision=StoppingDecision(
                status=StoppingStatus.SUFFICIENT_EVIDENCE,
                reason="Extreme fraud risk.",
                fraud_probability=0.95,
                confidence=0.90,
                independent_evidence_count=3,
            ),
        )
        actions = self.engine.recommend_actions(risk, self.inv_base)

        priorities = [a.priority for a in actions]
        self.assertEqual(priorities, list(range(1, len(actions) + 1)))

        action_names = [a.action for a in actions]
        self.assertEqual(len(action_names), len(set(action_names)))


class TestStage4NBAService(unittest.TestCase):
    """Test suite for NBAService orchestration and explainability."""

    def setUp(self):
        self.service = NBAService()
        self.sample_tx = Transaction(
            transaction_id="TXN-SRV-01",
            customer_id="C-SRV-01",
            account_id="ACC-01",
            amount=1200.0,
        )
        self.inv = InvestigationResult(
            transaction_id="TXN-SRV-01",
            status=InvestigationStatus.COMPLETE,
            transaction=self.sample_tx.model_dump(),
        )

    def test_evaluate_initial_generates_valid_actions(self):
        risk = RiskAssessment(
            transaction_id="TXN-SRV-01",
            fraud_probability=0.40,
            risk_level=RiskLevel.MEDIUM,
            confidence=0.5,
            uncertainty=0.5,
            stopping_decision=StoppingDecision(
                status=StoppingStatus.MORE_EVIDENCE_REQUIRED,
                reason="Need customer verification",
                fraud_probability=0.40,
                confidence=0.5,
            ),
            information_gaps=[
                InformationGap(gap_type="UNVERIFIED_CUSTOMER_INQUIRY", description="Unverified")
            ],
        )
        initial = self.service.evaluate_initial(risk, self.inv)
        self.assertGreaterEqual(len(initial), 1)
        self.assertEqual(initial[0].action, ActionType.STEP_UP_AUTH.value)

    def test_evaluate_final_detects_action_shift_and_explains(self):
        risk_initial = RiskAssessment(
            transaction_id="TXN-SRV-01",
            fraud_probability=0.45,
            risk_level=RiskLevel.MEDIUM,
            confidence=0.4,
            uncertainty=0.6,
            stopping_decision=StoppingDecision(
                status=StoppingStatus.MORE_EVIDENCE_REQUIRED,
                reason="Need customer verification",
                fraud_probability=0.45,
                confidence=0.4,
            ),
            information_gaps=[
                InformationGap(gap_type="UNVERIFIED_CUSTOMER_INQUIRY", description="Unverified")
            ],
        )
        initial_actions = self.service.evaluate_initial(risk_initial, self.inv)

        # Final state after customer verification clears the transaction
        risk_final = RiskAssessment(
            transaction_id="TXN-SRV-01",
            fraud_probability=0.05,
            risk_level=RiskLevel.LOW,
            confidence=0.95,
            uncertainty=0.05,
            stopping_decision=StoppingDecision(
                status=StoppingStatus.SUFFICIENT_EVIDENCE,
                reason="Customer verified valid purchase.",
                fraud_probability=0.05,
                confidence=0.95,
                independent_evidence_count=2,
            ),
            information_gaps=[],
        )

        final_actions, what_changed = self.service.evaluate_final(
            risk=risk_final,
            investigation=self.inv,
            initial_actions=initial_actions,
            initial_risk=risk_initial,
            evidence_added=["Customer confirmed transaction authorization via SMS OTP"],
        )

        self.assertEqual(final_actions[0].action, ActionType.CLOSE_NO_FRAUD.value)
        self.assertIsNotNone(what_changed)
        self.assertIn("STEP_UP_AUTH", what_changed.explanation)
        self.assertIn("CLOSE_NO_FRAUD", what_changed.explanation)
        self.assertEqual(what_changed.before_fraud_probability, 0.45)
        self.assertEqual(what_changed.after_fraud_probability, 0.05)
        self.assertIn("UNVERIFIED_CUSTOMER_INQUIRY", what_changed.resolved_gaps)

    def test_assess_full_cycle_properties(self):
        risk = RiskAssessment(
            transaction_id="TXN-SRV-01",
            fraud_probability=0.10,
            risk_level=RiskLevel.LOW,
            confidence=0.90,
            uncertainty=0.10,
            stopping_decision=StoppingDecision(
                status=StoppingStatus.SUFFICIENT_EVIDENCE,
                reason="Benign activity confirmed.",
                fraud_probability=0.10,
                confidence=0.90,
                independent_evidence_count=2,
            ),
        )
        assessment = self.service.assess(risk, self.inv)

        self.assertIsNotNone(assessment.primary_action)
        self.assertEqual(assessment.primary_action.action, ActionType.CLOSE_NO_FRAUD.value)
        self.assertGreaterEqual(len(assessment.alternative_actions), 1)
        self.assertEqual(assessment.methodology, "deterministic_evidentiary_nba")

    def test_format_explainability_summary(self):
        risk = RiskAssessment(
            transaction_id="TXN-SRV-01",
            fraud_probability=0.88,
            risk_level=RiskLevel.CRITICAL,
            confidence=0.85,
            uncertainty=0.15,
            stopping_decision=StoppingDecision(
                status=StoppingStatus.SUFFICIENT_EVIDENCE,
                reason="Corroborated critical fraud.",
                fraud_probability=0.88,
                confidence=0.85,
                independent_evidence_count=2,
            ),
        )
        assessment = self.service.assess(risk, self.inv)
        summary = self.service.format_explainability_summary(assessment)

        self.assertIn("Next Best Action Recommendations", summary)
        self.assertIn("Primary Action:", summary)
        self.assertIn(assessment.primary_action.action, summary)

    def test_satisfies_reasoning_interface(self):
        self.assertTrue(isinstance(self.service, NextBestActionEngineInterface))
        state: Dict[str, Any] = {
            "transaction_id": "TXN-SRV-01",
            "fraud_probability": 0.90,
            "risk_assessment": {
                "transaction_id": "TXN-SRV-01",
                "fraud_probability": 0.90,
                "risk_level": "CRITICAL",
                "confidence": 0.85,
                "uncertainty": 0.15,
                "stopping_decision": {
                    "status": "SUFFICIENT_EVIDENCE",
                    "reason": "Critical fraud",
                    "fraud_probability": 0.90,
                    "confidence": 0.85,
                    "independent_evidence_count": 2,
                },
            },
        }
        rec = self.service.recommend_action(state)
        self.assertTrue(isinstance(rec, ActionRecommendation))
        self.assertIn(rec.action, CANONICAL_ACTION_NAMES)


class TestStage4NBAWorkflow(unittest.TestCase):
    """Test suite for Stage 4 workflow integration."""

    def test_nba_workflow_execution_reaches_terminal_state(self):
        wf = create_nba_workflow()
        initial_state = create_initial_agent_state("TXN-209144")
        final_state = wf.run(initial_state)

        self.assertEqual(final_state["current_workflow_state"], "NBA_COMPLETE")
        self.assertIn("next_best_action_assessment", final_state)
        self.assertIn("next_best_action", final_state)
        self.assertIn("initial_next_best_actions", final_state)

        primary = final_state["next_best_action"]
        self.assertIn(primary["action"], CANONICAL_ACTION_NAMES)
        self.assertGreaterEqual(primary["priority"], 1)

    def test_nba_workflow_timeline_recorded(self):
        wf = create_nba_workflow()
        initial_state = create_initial_agent_state("TXN-104829")
        final_state = wf.run(initial_state)

        stages = [e["stage"] for e in final_state.get("timeline", [])]
        self.assertIn("TRIGGERED", stages)
        self.assertIn("ENRICHMENT", stages)
        self.assertIn("GRAPH_ANALYTICS", stages)
        self.assertIn("GRAPHRAG_CONTEXT", stages)
        self.assertIn("EVIDENCE_PROCESSOR", stages)
        self.assertIn("INVESTIGATION_COMPLETE", stages)
        self.assertIn("RISK_UNCERTAINTY", stages)
        self.assertIn("RISK_ASSESSMENT_COMPLETE", stages)
        self.assertIn("NEXT_BEST_ACTION", stages)
        self.assertIn("NBA_COMPLETE", stages)


class TestStage4StrictBoundaries(unittest.TestCase):
    """Test suite verifying strict Stage 4 architectural boundaries."""

    @patch("agent.tools.graph_adapter.graph_adapter.get_transaction")
    @patch("agent.tools.graph_adapter.graph_adapter.get_customer")
    @patch("agent.tools.graph_adapter.graph_adapter.detect_fraud_patterns")
    @patch("graphrag.pipeline.pipeline.retrieve_context")
    @patch("backend.services.mock_actions.mock_action_service.execute_action")
    def test_nba_service_makes_zero_external_queries_or_executions(
        self,
        mock_exec,
        mock_rag,
        mock_patterns,
        mock_cust,
        mock_txn,
    ):
        """
        Stage 4 NBA reasoning MUST be purely evidentiary and deterministic.
        Zero calls to Person 2 graph queries, GraphRAG retrieval, or mock execution.
        """
        sample_tx = Transaction(
            transaction_id="TXN-BOUND-01",
            customer_id="C-01",
            account_id="ACC-01",
            amount=250.0,
        )
        inv = InvestigationResult(
            transaction_id="TXN-BOUND-01",
            status=InvestigationStatus.COMPLETE,
            transaction=sample_tx.model_dump(),
        )
        risk = RiskAssessment(
            transaction_id="TXN-BOUND-01",
            fraud_probability=0.20,
            risk_level=RiskLevel.LOW,
            confidence=0.8,
            uncertainty=0.2,
            stopping_decision=StoppingDecision(
                status=StoppingStatus.SUFFICIENT_EVIDENCE,
                reason="Evidence gathered",
                fraud_probability=0.20,
                confidence=0.8,
                independent_evidence_count=2,
            ),
        )

        nba_service.assess(risk, inv)

        # Assert ZERO external calls
        mock_txn.assert_not_called()
        mock_cust.assert_not_called()
        mock_patterns.assert_not_called()
        mock_rag.assert_not_called()
        mock_exec.assert_not_called()


class TestStage4RESTEndpoints(unittest.TestCase):
    """Test suite validating Stage 4 REST API endpoints."""

    def test_post_investigations_nba_endpoint(self):
        status_code, headers, body = asgi_request(
            app,
            "POST",
            "/api/investigations/TXN-104829/nba",
            body={},
        )
        self.assertEqual(status_code, 200)
        self.assertIn("initial", body)
        self.assertIn("methodology", body)
        self.assertEqual(body["methodology"], "deterministic_evidentiary_nba")
        self.assertGreater(len(body["initial"]), 0)
        # Verify action is canonical
        first_action = body["initial"][0]["action"]
        self.assertIn(first_action, CANONICAL_ACTION_NAMES)

    def test_post_investigate_nba_alias_endpoint(self):
        status_code, headers, body = asgi_request(
            app,
            "POST",
            "/api/investigate/TXN-209144/nba",
            body={},
        )
        self.assertEqual(status_code, 200)
        self.assertIn("initial", body)
        self.assertGreater(len(body["initial"]), 0)
        first_action = body["initial"][0]["action"]
        self.assertIn(first_action, CANONICAL_ACTION_NAMES)

    def test_post_investigations_nba_with_initial_actions_returns_what_changed(self):
        initial_payload = {
            "initial_actions": [
                {
                    "action": "STEP_UP_AUTH",
                    "rationale": "Initial challenge",
                    "priority": 1,
                    "supporting_evidence": [],
                    "triggering_gaps": ["GAP-VERIF-01"],
                }
            ],
            "evidence_added": ["Customer successfully authenticated 2FA"],
        }
        status_code, headers, body = asgi_request(
            app,
            "POST",
            "/api/investigations/TXN-209144/nba",
            body=initial_payload,
        )
        self.assertEqual(status_code, 200)
        self.assertIn("final", body)
        self.assertIsNotNone(body.get("what_changed"))


class TestStage4RealDataSmoke(unittest.TestCase):
    """
    Smoke tests against actual seeded test transactions without hardcoding guessed answer keys.
    Asserts consistency with Stage 3 risk output and canonical action rules.
    """

    def test_real_high_risk_transaction_104829(self):
        wf = create_nba_workflow()
        initial_state = create_initial_agent_state("TXN-104829")
        final_state = wf.run(initial_state)

        prob = final_state.get("fraud_probability", 0.0)
        primary = final_state.get("next_best_action", {})
        action = primary.get("action")

        self.assertIn(action, CANONICAL_ACTION_NAMES)
        # Because TXN-104829 has device ring & mule patterns, risk is elevated
        if prob >= 0.70:
            self.assertIn(action, {"BLOCK_ALL_CARDS", "BLOCK_CARD", "DECLINE_TRANSACTION"})
        else:
            self.assertIn(action, CANONICAL_ACTION_NAMES)

    def test_real_benign_transaction_209144(self):
        wf = create_nba_workflow()
        initial_state = create_initial_agent_state("TXN-209144")
        final_state = wf.run(initial_state)

        prob = final_state.get("fraud_probability", 0.0)
        primary = final_state.get("next_best_action", {})
        action = primary.get("action")

        self.assertIn(action, CANONICAL_ACTION_NAMES)
        # Because TXN-209144 is benign $48 grocery POS, risk should be low
        if prob <= 0.30:
            self.assertIn(action, {"ALLOW_TRANSACTION", "CLOSE_NO_FRAUD", "MONITOR_CARD"})
        else:
            self.assertIn(action, CANONICAL_ACTION_NAMES)


if __name__ == "__main__":
    unittest.main()
