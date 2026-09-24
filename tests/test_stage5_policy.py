# ==============================================================================
# FraudGraph AI - Stage 5 Test Suite: Policy Compliance + HITL Gate
# Workstream: Person 1 (Brain)
# ==============================================================================

import time
import math
import unittest
from unittest.mock import patch, MagicMock
from typing import Dict, Any

from backend.models.domain import (
    ActionType,
    ApprovalLevel,
    HITLStatus,
    RuleEvaluationStatus,
    PolicyRuleResult,
    PolicyAssessment,
    ApprovalRequest,
    ApprovalStatus,
    CaseStatus,
    InvestigationCase,
    InvestigationResult,
    InvestigationStatus,
    RiskAssessment,
    RiskLevel,
    EvidenceItem,
    NextBestActionItem,
    NextBestActionAssessment,
)
from backend.models.audit import audit_logger, AuditEventType
from backend.policy.evaluator import PolicyEvaluator, policy_evaluator
from backend.policy.rules import (
    evaluate_all_rules,
    evaluate_r1,
    evaluate_r2,
    evaluate_r3,
    evaluate_r4,
    evaluate_r5,
    evaluate_r6,
    evaluate_r7,
    evaluate_r8,
    evaluate_r9,
    evaluate_r10,
)
from backend.services.case_memory import case_memory_service
from backend.services.mock_actions import mock_action_service
from agent.workflows.workflow import (
    create_policy_workflow,
    policy_compliance_node,
    hitl_gate_node,
    policy_complete_node,
)
from agent.workflows.state import create_initial_agent_state
from backend.api.app import create_app


def run_asgi_request(app, method: str, path: str, json_body: Dict[str, Any] = None):
    """Synchronous test helper executing ASGI requests without httpx."""
    import asyncio
    import json

    body_bytes = json.dumps(json_body).encode("utf-8") if json_body else b""
    response_headers = []
    response_body = []
    status_code = None

    async def run():
        nonlocal status_code
        scope = {
            "type": "http",
            "method": method.upper(),
            "path": path,
            "raw_path": path.encode("utf-8"),
            "query_string": b"",
            "headers": [
                (b"host", b"testserver"),
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body_bytes)).encode("utf-8")),
            ],
        }

        async def receive():
            return {"type": "http.request", "body": body_bytes, "more_body": False}

        async def send(msg):
            nonlocal status_code
            if msg["type"] == "http.response.start":
                status_code = msg["status"]
                response_headers.extend(msg.get("headers", []))
            elif msg["type"] == "http.response.body":
                response_body.append(msg.get("body", b""))

        await app(scope, receive, send)

    asyncio.run(run())
    full_body = b"".join(response_body).decode("utf-8")
    parsed_json = json.loads(full_body) if full_body else {}
    return status_code, parsed_json


class TestStage5PolicyRules(unittest.TestCase):
    """Section 33.1: Deterministic evaluation of organizer rules R1 through R10."""

    def setUp(self):
        self.evaluator = PolicyEvaluator()

    def test_r1_weak_signal_blocks_prohibited(self):
        """R1: Single weak signal (P < 0.70) strictly prohibits BLOCK_CARD."""
        res = evaluate_r1(
            action=ActionType.BLOCK_CARD,
            facts={"signals_count": 1, "fraud_probability": 0.55},
        )
        self.assertEqual(res.status, RuleEvaluationStatus.VIOLATED)
        self.assertIn("R1 Violation", res.reason)

        # Full evaluator check
        assessment = self.evaluator.evaluate(
            action=ActionType.BLOCK_CARD,
            exposure_usd=500.0,
            facts={"signals_count": 1, "fraud_probability": 0.55},
        )
        self.assertFalse(assessment.permitted)
        self.assertEqual(assessment.hitl_status, HITLStatus.POLICY_BLOCKED)
        self.assertIn("R1", assessment.violated_rules)

    def test_r1_weak_signal_permits_verification(self):
        """R1: Single weak signal permits VERIFY_WITH_CUSTOMER and STEP_UP_AUTH."""
        res_v = evaluate_r1(
            action=ActionType.VERIFY_WITH_CUSTOMER,
            facts={"signals_count": 1, "fraud_probability": 0.40},
        )
        self.assertEqual(res_v.status, RuleEvaluationStatus.SATISFIED)

        res_s = evaluate_r1(
            action=ActionType.STEP_UP_AUTH,
            facts={"signals_count": 1, "fraud_probability": 0.40},
        )
        self.assertEqual(res_s.status, RuleEvaluationStatus.SATISFIED)

    def test_r1_not_applicable_when_multiple_signals_or_high_probability(self):
        """R1: Multiple signals (>= 2) or P >= 0.70 makes R1 not applicable."""
        res_multi = evaluate_r1(
            action=ActionType.BLOCK_CARD,
            facts={"signals_count": 3, "fraud_probability": 0.65},
        )
        self.assertEqual(res_multi.status, RuleEvaluationStatus.NOT_APPLICABLE)

        res_high_p = evaluate_r1(
            action=ActionType.BLOCK_CARD,
            facts={"signals_count": 1, "fraud_probability": 0.85},
        )
        self.assertEqual(res_high_p.status, RuleEvaluationStatus.NOT_APPLICABLE)

    def test_r2_customer_denies_permits_block_and_create_case(self):
        """R2: Customer denies transaction permits BLOCK_CARD and CREATE_CASE."""
        res_block = evaluate_r2(
            action=ActionType.BLOCK_CARD,
            facts={"customer_denied": True},
        )
        self.assertEqual(res_block.status, RuleEvaluationStatus.SATISFIED)

        res_case = evaluate_r2(
            action=ActionType.CREATE_CASE,
            facts={"customer_denied": True},
        )
        self.assertEqual(res_case.status, RuleEvaluationStatus.SATISFIED)

    def test_r2_customer_denies_prohibits_allow_transaction(self):
        """R2: Customer denies transaction prohibits ALLOW_TRANSACTION and CLOSE_NO_FRAUD."""
        res = evaluate_r2(
            action=ActionType.ALLOW_TRANSACTION,
            facts={"customer_denied": True},
        )
        self.assertEqual(res.status, RuleEvaluationStatus.VIOLATED)

    def test_r2_high_exposure_requires_sar(self):
        """R2: Customer denies transaction with exposure > $1,000 requires/permits FILE_REPORT."""
        assessment = self.evaluator.evaluate(
            action=ActionType.FILE_REPORT,
            exposure_usd=1500.0,
            facts={"customer_denied": True},
        )
        self.assertTrue(assessment.permitted)
        self.assertTrue(assessment.sar_required)
        self.assertIn("R2", assessment.satisfied_rules)

    def test_r3_customer_confirms_permits_close_no_fraud(self):
        """R3: Customer confirms transaction permits CLOSE_NO_FRAUD and ALLOW_TRANSACTION."""
        res = evaluate_r3(
            action=ActionType.CLOSE_NO_FRAUD,
            facts={"customer_confirmed": True},
        )
        self.assertEqual(res.status, RuleEvaluationStatus.SATISFIED)

        res_allow = evaluate_r3(
            action=ActionType.ALLOW_TRANSACTION,
            facts={"customer_confirmed": True},
        )
        self.assertEqual(res_allow.status, RuleEvaluationStatus.SATISFIED)

    def test_r3_customer_confirms_prohibits_blocking_or_declining(self):
        """R3: Customer confirms transaction prohibits BLOCK_CARD, BLOCK_ALL_CARDS, DECLINE_TRANSACTION."""
        for act in (ActionType.BLOCK_CARD, ActionType.BLOCK_ALL_CARDS, ActionType.DECLINE_TRANSACTION):
            res = evaluate_r3(action=act, facts={"customer_confirmed": True})
            self.assertEqual(res.status, RuleEvaluationStatus.VIOLATED)

    def test_r4_unresponsive_24h(self):
        """R4: Unresponsive after 24h permits MONITOR_CARD and DECLINE_TRANSACTION; escalates if > $500."""
        res_mon = evaluate_r4(action=ActionType.MONITOR_CARD, facts={"unresponsive_24h": True})
        self.assertEqual(res_mon.status, RuleEvaluationStatus.SATISFIED)

        res_dec = evaluate_r4(action=ActionType.DECLINE_TRANSACTION, facts={"unresponsive_24h": True})
        self.assertEqual(res_dec.status, RuleEvaluationStatus.SATISFIED)

        res_esc = evaluate_r4(action=ActionType.ESCALATE_TO_ANALYST, exposure_usd=750.0, facts={"unresponsive_24h": True})
        self.assertEqual(res_esc.status, RuleEvaluationStatus.SATISFIED)

    def test_r5_card_testing_rules(self):
        """R5: Card testing permits DECLINE and STEP_UP; BLOCK_CARD only if cleared > $100."""
        res_dec = evaluate_r5(action=ActionType.DECLINE_TRANSACTION, facts={"card_testing": True})
        self.assertEqual(res_dec.status, RuleEvaluationStatus.SATISFIED)

        res_step = evaluate_r5(action=ActionType.STEP_UP_AUTH, facts={"card_testing": True})
        self.assertEqual(res_step.status, RuleEvaluationStatus.SATISFIED)

        # Cleared <= $100 -> BLOCK_CARD is VIOLATED
        res_block_low = evaluate_r5(action=ActionType.BLOCK_CARD, facts={"card_testing": True, "cleared_over_100": False})
        self.assertEqual(res_block_low.status, RuleEvaluationStatus.VIOLATED)

        # Cleared > $100 -> BLOCK_CARD is SATISFIED
        res_block_high = evaluate_r5(action=ActionType.BLOCK_CARD, facts={"card_testing": True, "cleared_over_100": True})
        self.assertEqual(res_block_high.status, RuleEvaluationStatus.SATISFIED)

    def test_r6_shared_origin_syndicate(self):
        """R6: Shared origin across multiple cards permits CREATE_CASE, FILE_REPORT, MONITOR_CONNECTED_CARDS."""
        for act in (ActionType.CREATE_CASE, ActionType.FILE_REPORT, ActionType.MONITOR_CONNECTED_CARDS):
            res = evaluate_r6(action=act, facts={"shared_origin": True})
            self.assertEqual(res.status, RuleEvaluationStatus.SATISFIED)

    def test_r7_disputed_recurring_charge_prohibits_blocking(self):
        """R7: Disputed recurring charge prohibits blocking; permits case, verify, warn."""
        res_block = evaluate_r7(action=ActionType.BLOCK_CARD, facts={"disputed_recurring": True})
        self.assertEqual(res_block.status, RuleEvaluationStatus.VIOLATED)

        res_warn = evaluate_r7(action=ActionType.WARN_CUSTOMER, facts={"disputed_recurring": True})
        self.assertEqual(res_warn.status, RuleEvaluationStatus.SATISFIED)

    def test_r8_escalate_when_uncertain_and_exposed(self):
        """R8: Uncertain verdict + exposure > $500 permits and satisfies ESCALATE_TO_ANALYST."""
        res = evaluate_r8(
            action=ActionType.ESCALATE_TO_ANALYST,
            exposure_usd=800.0,
            facts={"verdict": "uncertain"},
        )
        self.assertEqual(res.status, RuleEvaluationStatus.SATISFIED)

    def test_r9_undocumented_patterns(self):
        """R9: Undocumented patterns permit CREATE_CASE, FILE_REPORT, ESCALATE_TO_ANALYST."""
        for act in (ActionType.CREATE_CASE, ActionType.FILE_REPORT, ActionType.ESCALATE_TO_ANALYST):
            res = evaluate_r9(action=act, facts={"pattern": "undocumented"})
            self.assertEqual(res.status, RuleEvaluationStatus.SATISFIED)

    def test_r10_block_all_cards_constraint(self):
        """R10: Prohibits BLOCK_ALL_CARDS unless >= 2 cards confirmed fraud or credentials compromised."""
        # 1 card only, no credential compromise -> VIOLATED
        res_violation = evaluate_r10(
            action=ActionType.BLOCK_ALL_CARDS,
            facts={"confirmed_fraud_cards_count": 1, "credentials_compromised": False},
        )
        self.assertEqual(res_violation.status, RuleEvaluationStatus.VIOLATED)

        # 2 cards confirmed fraud -> SATISFIED
        res_cards_ok = evaluate_r10(
            action=ActionType.BLOCK_ALL_CARDS,
            facts={"confirmed_fraud_cards_count": 2, "credentials_compromised": False},
        )
        self.assertEqual(res_cards_ok.status, RuleEvaluationStatus.SATISFIED)

        # Credentials compromised -> SATISFIED
        res_creds_ok = evaluate_r10(
            action=ActionType.BLOCK_ALL_CARDS,
            facts={"confirmed_fraud_cards_count": 0, "credentials_compromised": True},
        )
        self.assertEqual(res_creds_ok.status, RuleEvaluationStatus.SATISFIED)

        # Other action (e.g. BLOCK_CARD) -> NOT_APPLICABLE
        res_na = evaluate_r10(action=ActionType.BLOCK_CARD)
        self.assertEqual(res_na.status, RuleEvaluationStatus.NOT_APPLICABLE)


class TestStage5ApprovalHierarchy(unittest.TestCase):
    """Section 33.2: Exact organizer approval routing hierarchy and boundary thresholds."""

    def setUp(self):
        self.evaluator = PolicyEvaluator()

    def test_block_card_under_threshold_is_l1(self):
        """BLOCK_CARD with exposure <= $2,500.00 routes to L1_SUPERVISOR."""
        assessment = self.evaluator.evaluate(
            action=ActionType.BLOCK_CARD,
            exposure_usd=1200.0,
            facts={"signals_count": 2, "fraud_probability": 0.85},
        )
        self.assertTrue(assessment.permitted)
        self.assertTrue(assessment.approval_required)
        self.assertEqual(assessment.approval_level, ApprovalLevel.L1_SUPERVISOR)
        self.assertEqual(assessment.hitl_status, HITLStatus.PENDING_L1_APPROVAL)

    def test_block_card_exact_boundary_is_l1(self):
        """BLOCK_CARD at exact boundary $2,500.00 routes to L1_SUPERVISOR."""
        assessment = self.evaluator.evaluate(
            action=ActionType.BLOCK_CARD,
            exposure_usd=2500.0,
            facts={"signals_count": 2, "fraud_probability": 0.85},
        )
        self.assertTrue(assessment.permitted)
        self.assertEqual(assessment.approval_level, ApprovalLevel.L1_SUPERVISOR)
        self.assertEqual(assessment.hitl_status, HITLStatus.PENDING_L1_APPROVAL)

    def test_block_card_over_threshold_is_l2(self):
        """BLOCK_CARD with exposure > $2,500.00 routes to L2_COMPLIANCE."""
        assessment = self.evaluator.evaluate(
            action=ActionType.BLOCK_CARD,
            exposure_usd=2500.01,
            facts={"signals_count": 2, "fraud_probability": 0.85},
        )
        self.assertTrue(assessment.permitted)
        self.assertEqual(assessment.approval_level, ApprovalLevel.L2_COMPLIANCE)
        self.assertEqual(assessment.hitl_status, HITLStatus.PENDING_L2_APPROVAL)

    def test_block_all_cards_is_always_l2(self):
        """BLOCK_ALL_CARDS (when permitted by R10) always routes to L2_COMPLIANCE."""
        assessment = self.evaluator.evaluate(
            action=ActionType.BLOCK_ALL_CARDS,
            exposure_usd=100.0, # even small exposure
            facts={"credentials_compromised": True},
        )
        self.assertTrue(assessment.permitted)
        self.assertEqual(assessment.approval_level, ApprovalLevel.L2_COMPLIANCE)
        self.assertEqual(assessment.hitl_status, HITLStatus.PENDING_L2_APPROVAL)

    def test_file_report_is_always_l2(self):
        """FILE_REPORT always routes to L2_COMPLIANCE and sets sar_required."""
        assessment = self.evaluator.evaluate(
            action=ActionType.FILE_REPORT,
            exposure_usd=300.0,
        )
        self.assertTrue(assessment.permitted)
        self.assertEqual(assessment.approval_level, ApprovalLevel.L2_COMPLIANCE)
        self.assertEqual(assessment.hitl_status, HITLStatus.PENDING_L2_APPROVAL)
        self.assertTrue(assessment.sar_required)

    def test_decline_transaction_is_always_l1(self):
        """DECLINE_TRANSACTION always routes to L1_SUPERVISOR."""
        assessment = self.evaluator.evaluate(
            action=ActionType.DECLINE_TRANSACTION,
            exposure_usd=50.0,
        )
        self.assertTrue(assessment.permitted)
        self.assertEqual(assessment.approval_level, ApprovalLevel.L1_SUPERVISOR)
        self.assertEqual(assessment.hitl_status, HITLStatus.PENDING_L1_APPROVAL)

    def test_auto_actions_route_to_auto(self):
        """Actions without supervisory requirements evaluate to AUTO."""
        auto_actions = [
            ActionType.ALLOW_TRANSACTION,
            ActionType.MONITOR_CARD,
            ActionType.MONITOR_CONNECTED_CARDS,
            ActionType.WARN_CUSTOMER,
            ActionType.VERIFY_WITH_CUSTOMER,
            ActionType.STEP_UP_AUTH,
            ActionType.GENERATE_REPORT,
            ActionType.CREATE_CASE,
            ActionType.ESCALATE_TO_ANALYST,
            ActionType.CLOSE_NO_FRAUD,
        ]
        for act in auto_actions:
            assessment = self.evaluator.evaluate(action=act, exposure_usd=100.0)
            self.assertTrue(assessment.permitted)
            self.assertFalse(assessment.approval_required)
            self.assertEqual(assessment.approval_level, ApprovalLevel.AUTO)
            self.assertEqual(assessment.hitl_status, HITLStatus.AUTO_APPROVED)

    def test_legacy_aliases_normalized_before_policy_evaluation(self):
        """Legacy aliases like FREEZE_ACCOUNT and BLOCK_TRANSACTION map cleanly to canonical actions."""
        # FREEZE_ACCOUNT -> BLOCK_ALL_CARDS (L2)
        assessment_freeze = self.evaluator.evaluate(
            action="FREEZE_ACCOUNT",
            exposure_usd=500.0,
            facts={"credentials_compromised": True},
        )
        self.assertEqual(assessment_freeze.action, ActionType.BLOCK_ALL_CARDS)
        self.assertEqual(assessment_freeze.approval_level, ApprovalLevel.L2_COMPLIANCE)

        # BLOCK_TRANSACTION -> DECLINE_TRANSACTION (L1)
        assessment_decline = self.evaluator.evaluate(
            action="BLOCK_TRANSACTION",
            exposure_usd=500.0,
        )
        self.assertEqual(assessment_decline.action, ActionType.DECLINE_TRANSACTION)
        self.assertEqual(assessment_decline.approval_level, ApprovalLevel.L1_SUPERVISOR)


class TestStage5FailClosedBehavior(unittest.TestCase):
    """Section 33.3: Fail-closed validation for missing, invalid, or corrupt data."""

    def setUp(self):
        self.evaluator = PolicyEvaluator()

    def test_missing_action_fails_closed(self):
        """Missing or empty action fails closed to POLICY_INDETERMINATE."""
        for bad_action in (None, "", "   "):
            assessment = self.evaluator.evaluate(action=bad_action)
            self.assertFalse(assessment.permitted)
            self.assertEqual(assessment.hitl_status, HITLStatus.POLICY_INDETERMINATE)

    def test_unknown_action_fails_closed(self):
        """Unrecognized action fails closed to POLICY_INDETERMINATE."""
        assessment = self.evaluator.evaluate(action="EXPLODE_ACCOUNT")
        self.assertFalse(assessment.permitted)
        self.assertEqual(assessment.hitl_status, HITLStatus.POLICY_INDETERMINATE)

    def test_missing_exposure_when_required_fails_closed(self):
        """Missing exposure for BLOCK_CARD fails closed to POLICY_INDETERMINATE."""
        assessment = self.evaluator.evaluate(
            action=ActionType.BLOCK_CARD,
            exposure_usd=None,
        )
        self.assertFalse(assessment.permitted)
        self.assertEqual(assessment.hitl_status, HITLStatus.POLICY_INDETERMINATE)

    def test_negative_exposure_fails_closed(self):
        """Negative exposure fails closed to POLICY_INDETERMINATE."""
        assessment = self.evaluator.evaluate(
            action=ActionType.BLOCK_CARD,
            exposure_usd=-250.0,
        )
        self.assertFalse(assessment.permitted)
        self.assertEqual(assessment.hitl_status, HITLStatus.POLICY_INDETERMINATE)

    def test_nan_exposure_fails_closed(self):
        """NaN exposure fails closed to POLICY_INDETERMINATE."""
        assessment = self.evaluator.evaluate(
            action=ActionType.BLOCK_CARD,
            exposure_usd=float("nan"),
        )
        self.assertFalse(assessment.permitted)
        self.assertEqual(assessment.hitl_status, HITLStatus.POLICY_INDETERMINATE)

    def test_corrupt_risk_state_fails_closed(self):
        """Corrupt risk assessment metrics fail closed."""
        # RiskAssessment with mock corrupt values
        mock_risk = MagicMock()
        mock_risk.fraud_probability = float("nan")
        mock_risk.confidence = 0.5
        mock_risk.independent_evidence_count = 1
        mock_risk.supporting_signals = []

        assessment = self.evaluator.evaluate(
            action=ActionType.BLOCK_CARD,
            exposure_usd=500.0,
            risk=mock_risk,
        )
        self.assertFalse(assessment.permitted)
        self.assertEqual(assessment.hitl_status, HITLStatus.POLICY_INDETERMINATE)


class TestStage5HITLSecurity(unittest.TestCase):
    """Section 33.4 & 33.5: Cryptographic HMAC tokens, server-side authority, and idempotency."""

    def setUp(self):
        self.evaluator = PolicyEvaluator(hmac_secret="test-secret-hitl-key")

    def test_hmac_token_valid_generation_and_verification(self):
        """HMAC token correctly generated and validated with matching parameters."""
        now = int(time.time())
        token = self.evaluator.generate_approval_token(
            case_id="CASE-101",
            action="BLOCK_CARD",
            target_resource="TXN-104829",
            amount=1500.0,
            approval_level="L1",
            expires_at=now + 3600,
        )
        self.assertTrue(token.startswith("v1:"))

        valid = self.evaluator.verify_approval_token(
            token=token,
            case_id="CASE-101",
            action="BLOCK_CARD",
            target_resource="TXN-104829",
            amount=1500.0,
            approval_level="L1",
        )
        self.assertTrue(valid)

    def test_tampered_token_rejected(self):
        """Tampering with case_id, action, amount, or level rejects token."""
        now = int(time.time())
        token = self.evaluator.generate_approval_token(
            case_id="CASE-101",
            action="BLOCK_CARD",
            target_resource="TXN-104829",
            amount=1500.0,
            approval_level="L1",
            expires_at=now + 3600,
        )

        # Tampered amount
        self.assertFalse(self.evaluator.verify_approval_token(
            token=token, case_id="CASE-101", action="BLOCK_CARD",
            target_resource="TXN-104829", amount=9999.0, approval_level="L1",
        ))

        # Tampered action
        self.assertFalse(self.evaluator.verify_approval_token(
            token=token, case_id="CASE-101", action="BLOCK_ALL_CARDS",
            target_resource="TXN-104829", amount=1500.0, approval_level="L1",
        ))

        # Tampered case_id
        self.assertFalse(self.evaluator.verify_approval_token(
            token=token, case_id="CASE-999", action="BLOCK_CARD",
            target_resource="TXN-104829", amount=1500.0, approval_level="L1",
        ))

    def test_expired_token_rejected(self):
        """Token with past expires_at timestamp is rejected."""
        past_time = int(time.time()) - 100
        token = self.evaluator.generate_approval_token(
            case_id="CASE-101",
            action="BLOCK_CARD",
            target_resource="TXN-104829",
            amount=1500.0,
            approval_level="L1",
            expires_at=past_time,
        )
        self.assertFalse(self.evaluator.verify_approval_token(
            token=token,
            case_id="CASE-101",
            action="BLOCK_CARD",
            target_resource="TXN-104829",
            amount=1500.0,
            approval_level="L1",
        ))

    def test_server_side_approver_authority_hierarchy(self):
        """L1 supervisor cannot approve L2 compliance; L2 manager can approve both L1 and L2."""
        # L1 approver
        self.assertTrue(self.evaluator.verify_approver_authority("analyst_1", ApprovalLevel.L1_SUPERVISOR))
        self.assertFalse(self.evaluator.verify_approver_authority("analyst_1", ApprovalLevel.L2_COMPLIANCE))

        # L2 approver
        self.assertTrue(self.evaluator.verify_approver_authority("compliance_l2", ApprovalLevel.L1_SUPERVISOR))
        self.assertTrue(self.evaluator.verify_approver_authority("compliance_l2", ApprovalLevel.L2_COMPLIANCE))

        # Unknown approver
        self.assertFalse(self.evaluator.verify_approver_authority("mallory_hacker", ApprovalLevel.L1_SUPERVISOR))

    def test_api_approval_insufficient_authority_rejected(self):
        """API rejects L1 supervisor attempting to approve an L2 compliance case."""
        app = create_app()
        case_id = "CASE-TEST-L2-AUTH"
        now = int(time.time())

        # Seed case awaiting L2 compliance approval
        token = policy_evaluator.generate_approval_token(
            case_id=case_id,
            action="BLOCK_CARD",
            target_resource="TXN-200",
            amount=5000.0,
            approval_level="L2",
            expires_at=now + 3600,
        )
        case = InvestigationCase(
            case_id=case_id,
            transaction_id="TXN-200",
            status=CaseStatus.AWAITING_APPROVAL,
            approval_request=ApprovalRequest(
                case_id=case_id,
                action="BLOCK_CARD",
                target_resource="TXN-200",
                amount=5000.0,
                approval_level=ApprovalLevel.L2_COMPLIANCE,
                approval_token=token,
                status=ApprovalStatus.PENDING,
            ),
        )
        case_memory_service.save_case(case)

        # L1 analyst attempts to approve L2 case -> HTTP 403 Forbidden
        status, body = run_asgi_request(
            app,
            "POST",
            f"/api/cases/{case_id}/approve",
            {
                "approver_id": "analyst_1", # L1 only
                "decision": "APPROVED",
                "approval_token": token,
            },
        )
        self.assertEqual(status, 403)
        self.assertIn("insufficient authority", body.get("error", {}).get("message", "").lower())

    def test_api_approval_idempotency_duplicate_approval_rejected(self):
        """API rejects duplicate approval or rejection on an already-resolved case."""
        app = create_app()
        case_id = "CASE-TEST-IDEMPOTENT"
        now = int(time.time())

        token = policy_evaluator.generate_approval_token(
            case_id=case_id,
            action="BLOCK_CARD",
            target_resource="TXN-300",
            amount=1000.0,
            approval_level="L1",
            expires_at=now + 3600,
        )
        case = InvestigationCase(
            case_id=case_id,
            transaction_id="TXN-300",
            status=CaseStatus.AWAITING_APPROVAL,
            approval_request=ApprovalRequest(
                case_id=case_id,
                action="BLOCK_CARD",
                target_resource="TXN-300",
                amount=1000.0,
                approval_level=ApprovalLevel.L1_SUPERVISOR,
                approval_token=token,
                status=ApprovalStatus.PENDING,
            ),
        )
        case_memory_service.save_case(case)

        # First approval -> 200 OK
        status1, body1 = run_asgi_request(
            app,
            "POST",
            f"/api/cases/{case_id}/approve",
            {"approver_id": "analyst_1", "decision": "APPROVED", "approval_token": token},
        )
        self.assertEqual(status1, 200)
        self.assertEqual(body1["status"], "APPROVED")

        # Second approval on resolved case -> 403 / 400 rejection
        status2, body2 = run_asgi_request(
            app,
            "POST",
            f"/api/cases/{case_id}/approve",
            {"approver_id": "analyst_1", "decision": "APPROVED", "approval_token": token},
        )
        self.assertEqual(status2, 403)
        self.assertIn("already", body2.get("error", {}).get("message", "").lower())


class TestStage5ExecutionAndWorkflowBoundaries(unittest.TestCase):
    """Section 33.6 & 33.8: Verification of zero execution and workflow halting at AWAITING_APPROVAL."""

    def test_approve_endpoint_makes_zero_execution_calls(self):
        """Section 33.6: /api/cases/{id}/approve does NOT call execute_action or write_to_graph."""
        app = create_app()
        case_id = "CASE-TEST-ZERO-EXEC"
        now = int(time.time())

        token = policy_evaluator.generate_approval_token(
            case_id=case_id,
            action="BLOCK_CARD",
            target_resource="TXN-400",
            amount=1200.0,
            approval_level="L1",
            expires_at=now + 3600,
        )
        case = InvestigationCase(
            case_id=case_id,
            transaction_id="TXN-400",
            status=CaseStatus.AWAITING_APPROVAL,
            approval_request=ApprovalRequest(
                case_id=case_id,
                action="BLOCK_CARD",
                target_resource="TXN-400",
                amount=1200.0,
                approval_level=ApprovalLevel.L1_SUPERVISOR,
                approval_token=token,
                status=ApprovalStatus.PENDING,
            ),
        )
        case_memory_service.save_case(case)

        with patch.object(mock_action_service, "execute_action") as mock_exec:
            status, body = run_asgi_request(
                app,
                "POST",
                f"/api/cases/{case_id}/approve",
                {"approver_id": "analyst_1", "decision": "APPROVED", "approval_token": token},
            )
            self.assertEqual(status, 200)
            self.assertFalse(body.get("executed"))
            # STRICT REQUIREMENT: zero execution calls in Stage 5!
            mock_exec.assert_not_called()

    def test_policy_workflow_halts_at_awaiting_approval(self):
        """Section 33.8: create_policy_workflow halts at AWAITING_APPROVAL for held actions."""
        workflow = create_policy_workflow()
        state = create_initial_agent_state(transaction_id="TXN-104829")

        # Inject high-risk state that triggers BLOCK_CARD
        final_state = workflow.run(state)
        # For high-risk TXN-104829, NBA recommends BLOCK_CARD which requires supervisory approval
        self.assertIn(final_state["current_workflow_state"], ("AWAITING_APPROVAL", "POLICY_COMPLETE"))
        if final_state.get("hitl_status") in ("PENDING_L1_APPROVAL", "PENDING_L2_APPROVAL"):
            self.assertEqual(final_state["current_workflow_state"], "AWAITING_APPROVAL")
            # Verify workflow stopped: no execution_result present
            self.assertIsNone(final_state.get("execution_result"))

    def test_policy_workflow_completes_for_auto_action(self):
        """Section 33.8: create_policy_workflow terminates at POLICY_COMPLETE for AUTO actions."""
        workflow = create_policy_workflow()
        state = create_initial_agent_state(transaction_id="TXN-209144")

        final_state = workflow.run(state)
        # TXN-209144 is benign, NBA recommends ALLOW_TRANSACTION or CLOSE_NO_FRAUD (AUTO)
        self.assertEqual(final_state["current_workflow_state"], "POLICY_COMPLETE")
        self.assertEqual(final_state.get("hitl_status"), "AUTO_APPROVED")
        self.assertFalse(final_state.get("policy_assessment", {}).get("approval_required", True))


class TestStage5RealDataSmokeTests(unittest.TestCase):
    """Section 36: Smoke tests using real benchmark transactions through Stage 5 policy."""

    def setUp(self):
        self.app = create_app()

    def test_real_data_txn_104829_policy_evaluation(self):
        """Real transaction TXN-104829 (fraud pattern) through Stage 5 policy API."""
        status, body = run_asgi_request(
            self.app,
            "POST",
            "/api/investigations/TXN-104829/policy",
        )
        self.assertEqual(status, 200)
        self.assertIn("action", body)
        self.assertIn("permitted", body)
        self.assertIn("approval_level", body)
        self.assertIn("hitl_status", body)
        self.assertIn("rule_results", body)
        self.assertTrue(len(body["rule_results"]) == 10) # all R1-R10 evaluated

    def test_real_data_txn_209144_policy_evaluation(self):
        """Real transaction TXN-209144 (benign transaction) through Stage 5 policy API."""
        status, body = run_asgi_request(
            self.app,
            "POST",
            "/api/investigations/TXN-209144/policy",
        )
        self.assertEqual(status, 200)
        self.assertTrue(body["permitted"])
        self.assertEqual(body["approval_level"], "auto")
        self.assertEqual(body["hitl_status"], "AUTO_APPROVED")
        self.assertFalse(body["approval_required"])


if __name__ == "__main__":
    unittest.main()
