# ==============================================================================
# FraudGraph AI - Stage 6 Test Suite: Execution Engine + Case Memory
# Workstream: Person 1 (Brain)
# ==============================================================================

import time
import json
import unittest
from unittest.mock import patch, MagicMock
from typing import Dict, Any, Optional

from backend.models.domain import (
    ActionType,
    ApprovalLevel,
    ApprovalStatus,
    ApprovalRequest,
    CaseStatus,
    HITLStatus,
    PolicyAssessment,
    InvestigationCase,
    InvestigationResult,
    InvestigationStatus,
    EvidenceItem,
    FraudPattern,
    TimelineEvent,
)
from backend.models.audit import audit_logger, AuditEventType
from backend.execution.models import ExecutionStatus, ExecutionResult
from backend.execution.mock_executor import mock_action_executor, MockActionExecutor
from backend.execution.executor import ActionExecutionService, action_executor
from agent.tools.case_memory_adapter import CaseMemoryAdapter, case_memory_adapter
from backend.services.case_memory import case_memory_service
from agent.workflows.workflow import (
    execution_node,
    case_persistence_node,
    finalized_node,
    create_full_lifecycle_workflow,
    create_execution_workflow,
)
from agent.workflows.state import create_initial_agent_state
from backend.api.app import create_app


def run_asgi_request(app, method: str, path: str, json_body: Dict[str, Any] = None):
    """Synchronous test helper executing ASGI requests without httpx."""
    import asyncio

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

        async def send(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                response_headers.extend(message.get("headers", []))
            elif message["type"] == "http.response.body":
                response_body.append(message.get("body", b""))

        await app(scope, receive, send)

    asyncio.run(run())

    headers_dict = {k.decode("latin1").lower(): v.decode("latin1") for k, v in response_headers}
    raw_content = b"".join(response_body).decode("utf-8")
    try:
        parsed_body = json.loads(raw_content) if raw_content else {}
    except Exception:
        parsed_body = raw_content

    return status_code, headers_dict, parsed_body


class BaseStage6TestCase(unittest.TestCase):
    def setUp(self):
        audit_logger.clear()
        action_executor.clear()
        case_memory_service._cases.clear()
        self.app = create_app()

    def create_mock_policy_assessment(
        self,
        action: ActionType = ActionType.ALLOW_TRANSACTION,
        permitted: bool = True,
        approval_level: ApprovalLevel = ApprovalLevel.AUTO,
        hitl_status: HITLStatus = HITLStatus.AUTO_APPROVED,
        exposure_usd: float = 100.0,
    ) -> PolicyAssessment:
        return PolicyAssessment(
            action=action,
            permitted=permitted,
            approval_required=(approval_level != ApprovalLevel.AUTO),
            approval_level=approval_level,
            hitl_status=hitl_status,
            exposure_usd=exposure_usd,
            explanation=f"Policy evaluated for {action.value}",
        )


class TestStage6AuthorizationGate(BaseStage6TestCase):
    """Verifies the 7 authorization checks (A through E)."""

    def test_check_a_missing_case_id_blocked(self):
        pa = self.create_mock_policy_assessment()
        res = action_executor.execute(
            action=ActionType.ALLOW_TRANSACTION,
            case_id="",
            target_resource="TXN-100",
            policy_assessment=pa,
        )
        self.assertEqual(res.status, ExecutionStatus.BLOCKED)
        self.assertIn("case_id is missing", res.message)

    def test_check_b_unsupported_action_blocked(self):
        pa = self.create_mock_policy_assessment()
        res = action_executor.execute(
            action="INVALID_UNSUPPORTED_ACTION",
            case_id="CASE-101",
            target_resource="TXN-100",
            policy_assessment=pa,
        )
        self.assertEqual(res.status, ExecutionStatus.NOT_AUTHORIZED)
        self.assertIn("not a recognized canonical ActionType", res.message)

    def test_check_b_canonical_alias_normalized(self):
        pa = self.create_mock_policy_assessment(action=ActionType.DECLINE_TRANSACTION)
        res = action_executor.execute(
            action="BLOCK_TRANSACTION",
            case_id="CASE-102",
            target_resource="TXN-100",
            policy_assessment=pa,
        )
        self.assertEqual(res.status, ExecutionStatus.EXECUTED)
        self.assertEqual(res.action, ActionType.DECLINE_TRANSACTION)

    def test_check_c_missing_policy_assessment_blocked(self):
        res = action_executor.execute(
            action=ActionType.ALLOW_TRANSACTION,
            case_id="CASE-103",
            target_resource="TXN-100",
            policy_assessment=None,
        )
        self.assertEqual(res.status, ExecutionStatus.BLOCKED)
        self.assertIn("Policy assessment is missing", res.message)

    def test_check_c_policy_prohibited_blocked(self):
        pa = self.create_mock_policy_assessment(
            action=ActionType.BLOCK_CARD,
            permitted=False,
            hitl_status=HITLStatus.POLICY_BLOCKED,
        )
        res = action_executor.execute(
            action=ActionType.BLOCK_CARD,
            case_id="CASE-104",
            target_resource="CARD-4111-XXXX-9940",
            policy_assessment=pa,
        )
        self.assertEqual(res.status, ExecutionStatus.BLOCKED)
        self.assertIn("Execution blocked by policy", res.message)

    def test_check_c_policy_indeterminate_blocked(self):
        pa = self.create_mock_policy_assessment(
            action=ActionType.BLOCK_CARD,
            permitted=True,
            hitl_status=HITLStatus.POLICY_INDETERMINATE,
        )
        res = action_executor.execute(
            action=ActionType.BLOCK_CARD,
            case_id="CASE-105",
            target_resource="CARD-4111-XXXX-9940",
            policy_assessment=pa,
        )
        self.assertEqual(res.status, ExecutionStatus.BLOCKED)

    def test_check_d_auto_approved_executes(self):
        pa = self.create_mock_policy_assessment(
            action=ActionType.ALLOW_TRANSACTION,
            permitted=True,
            approval_level=ApprovalLevel.AUTO,
        )
        res = action_executor.execute(
            action=ActionType.ALLOW_TRANSACTION,
            case_id="CASE-106",
            target_resource="TXN-209144",
            policy_assessment=pa,
        )
        self.assertEqual(res.status, ExecutionStatus.EXECUTED)
        self.assertTrue(res.simulated)
        self.assertEqual(res.approval_reference, "AUTO_APPROVED")

    def test_check_d_l1_missing_approval_request_blocked(self):
        pa = self.create_mock_policy_assessment(
            action=ActionType.DECLINE_TRANSACTION,
            permitted=True,
            approval_level=ApprovalLevel.L1_SUPERVISOR,
        )
        res = action_executor.execute(
            action=ActionType.DECLINE_TRANSACTION,
            case_id="CASE-107",
            target_resource="TXN-100",
            policy_assessment=pa,
            approval_request=None,
        )
        self.assertEqual(res.status, ExecutionStatus.NOT_AUTHORIZED)
        self.assertIn("requires L1 human approval", res.message)

    def test_check_d_l1_pending_approval_blocked(self):
        pa = self.create_mock_policy_assessment(
            action=ActionType.DECLINE_TRANSACTION,
            permitted=True,
            approval_level=ApprovalLevel.L1_SUPERVISOR,
        )
        ar = ApprovalRequest(
            case_id="CASE-108",
            action=ActionType.DECLINE_TRANSACTION.value,
            target_resource="TXN-100",
            status=ApprovalStatus.PENDING,
            approval_level=ApprovalLevel.L1_SUPERVISOR,
        )
        res = action_executor.execute(
            action=ActionType.DECLINE_TRANSACTION,
            case_id="CASE-108",
            target_resource="TXN-100",
            policy_assessment=pa,
            approval_request=ar,
        )
        self.assertEqual(res.status, ExecutionStatus.NOT_AUTHORIZED)
        self.assertIn("expected 'APPROVED'", res.message)

    def test_check_d_l1_rejected_approval_blocked(self):
        pa = self.create_mock_policy_assessment(
            action=ActionType.DECLINE_TRANSACTION,
            permitted=True,
            approval_level=ApprovalLevel.L1_SUPERVISOR,
        )
        ar = ApprovalRequest(
            case_id="CASE-109",
            action=ActionType.DECLINE_TRANSACTION.value,
            target_resource="TXN-100",
            status=ApprovalStatus.REJECTED,
            approval_level=ApprovalLevel.L1_SUPERVISOR,
        )
        res = action_executor.execute(
            action=ActionType.DECLINE_TRANSACTION,
            case_id="CASE-109",
            target_resource="TXN-100",
            policy_assessment=pa,
            approval_request=ar,
        )
        self.assertEqual(res.status, ExecutionStatus.NOT_AUTHORIZED)

    def test_check_d_l1_approved_executes(self):
        pa = self.create_mock_policy_assessment(
            action=ActionType.DECLINE_TRANSACTION,
            permitted=True,
            approval_level=ApprovalLevel.L1_SUPERVISOR,
        )
        ar = ApprovalRequest(
            case_id="CASE-110",
            action=ActionType.DECLINE_TRANSACTION.value,
            target_resource="TXN-100",
            status=ApprovalStatus.APPROVED,
            approval_level=ApprovalLevel.L1_SUPERVISOR,
            approver_id="SUP-001",
        )
        res = action_executor.execute(
            action=ActionType.DECLINE_TRANSACTION,
            case_id="CASE-110",
            target_resource="TXN-100",
            policy_assessment=pa,
            approval_request=ar,
        )
        self.assertEqual(res.status, ExecutionStatus.EXECUTED)
        self.assertEqual(res.approval_reference, ar.approval_id)

    def test_check_e_missing_approver_id_blocked(self):
        pa = self.create_mock_policy_assessment(
            action=ActionType.BLOCK_CARD,
            permitted=True,
            approval_level=ApprovalLevel.L1_SUPERVISOR,
        )
        ar = ApprovalRequest(
            case_id="CASE-111",
            action=ActionType.BLOCK_CARD.value,
            target_resource="CARD-4111-XXXX-9940",
            status=ApprovalStatus.APPROVED,
            approval_level=ApprovalLevel.L1_SUPERVISOR,
            approver_id=None,
        )
        res = action_executor.execute(
            action=ActionType.BLOCK_CARD,
            case_id="CASE-111",
            target_resource="CARD-4111-XXXX-9940",
            policy_assessment=pa,
            approval_request=ar,
            approver_id=None,
        )
        self.assertEqual(res.status, ExecutionStatus.NOT_AUTHORIZED)
        self.assertIn("Approver ID is missing", res.message)

    def test_check_e_insufficient_authority_l1_approving_l2_blocked(self):
        pa = self.create_mock_policy_assessment(
            action=ActionType.BLOCK_ALL_CARDS,
            permitted=True,
            approval_level=ApprovalLevel.L2_COMPLIANCE,
        )
        ar = ApprovalRequest(
            case_id="CASE-112",
            action=ActionType.BLOCK_ALL_CARDS.value,
            target_resource="C-45821",
            status=ApprovalStatus.APPROVED,
            approval_level=ApprovalLevel.L2_COMPLIANCE,
            approver_id="SUP-001",  # L1 supervisor attempting L2 approval
        )
        res = action_executor.execute(
            action=ActionType.BLOCK_ALL_CARDS,
            case_id="CASE-112",
            target_resource="C-45821",
            policy_assessment=pa,
            approval_request=ar,
        )
        self.assertEqual(res.status, ExecutionStatus.NOT_AUTHORIZED)
        self.assertIn("insufficient authority", res.message)

    def test_check_e_sufficient_authority_l2_approving_l2_executes(self):
        pa = self.create_mock_policy_assessment(
            action=ActionType.BLOCK_ALL_CARDS,
            permitted=True,
            approval_level=ApprovalLevel.L2_COMPLIANCE,
        )
        ar = ApprovalRequest(
            case_id="CASE-113",
            action=ActionType.BLOCK_ALL_CARDS.value,
            target_resource="C-45821",
            status=ApprovalStatus.APPROVED,
            approval_level=ApprovalLevel.L2_COMPLIANCE,
            approver_id="COMP-001",  # L2 Compliance Officer
        )
        res = action_executor.execute(
            action=ActionType.BLOCK_ALL_CARDS,
            case_id="CASE-113",
            target_resource="C-45821",
            policy_assessment=pa,
            approval_request=ar,
        )
        self.assertEqual(res.status, ExecutionStatus.EXECUTED)
        self.assertTrue(res.simulated)


class TestStage6TargetValidation(BaseStage6TestCase):
    """Verifies Check G target resource validation."""

    def test_block_card_invalid_target_rejected(self):
        pa = self.create_mock_policy_assessment(
            action=ActionType.BLOCK_CARD,
            permitted=True,
            approval_level=ApprovalLevel.AUTO,
        )
        res = action_executor.execute(
            action=ActionType.BLOCK_CARD,
            case_id="CASE-201",
            target_resource="TXN-104829",  # Invalid for BLOCK_CARD
            policy_assessment=pa,
        )
        self.assertEqual(res.status, ExecutionStatus.BLOCKED)
        self.assertIn("Target resource 'TXN-104829' is invalid", res.message)

    def test_block_card_valid_target_accepted(self):
        pa = self.create_mock_policy_assessment(
            action=ActionType.BLOCK_CARD,
            permitted=True,
            approval_level=ApprovalLevel.AUTO,
        )
        res = action_executor.execute(
            action=ActionType.BLOCK_CARD,
            case_id="CASE-202",
            target_resource="CARD-4111-XXXX-9940",
            policy_assessment=pa,
        )
        self.assertEqual(res.status, ExecutionStatus.EXECUTED)

    def test_block_all_cards_invalid_target_rejected(self):
        pa = self.create_mock_policy_assessment(
            action=ActionType.BLOCK_ALL_CARDS,
            permitted=True,
            approval_level=ApprovalLevel.AUTO,
        )
        res = action_executor.execute(
            action=ActionType.BLOCK_ALL_CARDS,
            case_id="CASE-203",
            target_resource="INVALID_TARGET_XYZ",
            policy_assessment=pa,
        )
        self.assertEqual(res.status, ExecutionStatus.BLOCKED)

    def test_block_all_cards_valid_target_accepted(self):
        pa = self.create_mock_policy_assessment(
            action=ActionType.BLOCK_ALL_CARDS,
            permitted=True,
            approval_level=ApprovalLevel.AUTO,
        )
        res = action_executor.execute(
            action=ActionType.BLOCK_ALL_CARDS,
            case_id="CASE-204",
            target_resource="C-45821",
            policy_assessment=pa,
        )
        self.assertEqual(res.status, ExecutionStatus.EXECUTED)

    def test_decline_transaction_valid_target(self):
        pa = self.create_mock_policy_assessment(
            action=ActionType.DECLINE_TRANSACTION,
            permitted=True,
            approval_level=ApprovalLevel.AUTO,
        )
        res = action_executor.execute(
            action=ActionType.DECLINE_TRANSACTION,
            case_id="CASE-205",
            target_resource="TXN-104829",
            policy_assessment=pa,
        )
        self.assertEqual(res.status, ExecutionStatus.EXECUTED)

    def test_warn_customer_invalid_target(self):
        pa = self.create_mock_policy_assessment(
            action=ActionType.WARN_CUSTOMER,
            permitted=True,
            approval_level=ApprovalLevel.AUTO,
        )
        res = action_executor.execute(
            action=ActionType.WARN_CUSTOMER,
            case_id="CASE-206",
            target_resource="CARD-4111-XXXX-9940",  # Card is invalid for WARN_CUSTOMER
            policy_assessment=pa,
        )
        self.assertEqual(res.status, ExecutionStatus.BLOCKED)

    def test_warn_customer_valid_target(self):
        pa = self.create_mock_policy_assessment(
            action=ActionType.WARN_CUSTOMER,
            permitted=True,
            approval_level=ApprovalLevel.AUTO,
        )
        res = action_executor.execute(
            action=ActionType.WARN_CUSTOMER,
            case_id="CASE-207",
            target_resource="C-99321",
            policy_assessment=pa,
        )
        self.assertEqual(res.status, ExecutionStatus.EXECUTED)

    def test_empty_target_resource_rejected(self):
        pa = self.create_mock_policy_assessment()
        res = action_executor.execute(
            action=ActionType.ALLOW_TRANSACTION,
            case_id="CASE-208",
            target_resource="   ",
            policy_assessment=pa,
        )
        self.assertEqual(res.status, ExecutionStatus.BLOCKED)


class TestStage6ExecutionIdempotency(BaseStage6TestCase):
    """Verifies Check F idempotency registry and duplicate suppression."""

    def test_first_execution_returns_executed(self):
        pa = self.create_mock_policy_assessment()
        res = action_executor.execute(
            action=ActionType.ALLOW_TRANSACTION,
            case_id="CASE-301",
            target_resource="TXN-100",
            policy_assessment=pa,
        )
        self.assertEqual(res.status, ExecutionStatus.EXECUTED)

    def test_second_execution_returns_already_executed(self):
        pa = self.create_mock_policy_assessment()
        res1 = action_executor.execute(
            action=ActionType.ALLOW_TRANSACTION,
            case_id="CASE-302",
            target_resource="TXN-100",
            policy_assessment=pa,
        )
        self.assertEqual(res1.status, ExecutionStatus.EXECUTED)

        res2 = action_executor.execute(
            action=ActionType.ALLOW_TRANSACTION,
            case_id="CASE-302",
            target_resource="TXN-100",
            policy_assessment=pa,
        )
        self.assertEqual(res2.status, ExecutionStatus.ALREADY_EXECUTED)
        self.assertEqual(res2.execution_id, res1.execution_id)
        self.assertIn("Duplicate execution prevented", res2.message)

    def test_executor_called_once_on_duplicate(self):
        mock_exec = MagicMock(wraps=mock_action_executor)
        svc = ActionExecutionService(executor=mock_exec)
        pa = self.create_mock_policy_assessment()

        svc.execute(ActionType.ALLOW_TRANSACTION, "CASE-303", "TXN-100", pa)
        svc.execute(ActionType.ALLOW_TRANSACTION, "CASE-303", "TXN-100", pa)

        self.assertEqual(mock_exec.execute.call_count, 1)

    def test_different_target_executes_separately(self):
        pa = self.create_mock_policy_assessment()
        res1 = action_executor.execute(ActionType.ALLOW_TRANSACTION, "CASE-304", "TXN-100", pa)
        res2 = action_executor.execute(ActionType.ALLOW_TRANSACTION, "CASE-304", "TXN-200", pa)

        self.assertEqual(res1.status, ExecutionStatus.EXECUTED)
        self.assertEqual(res2.status, ExecutionStatus.EXECUTED)
        self.assertNotEqual(res1.execution_id, res2.execution_id)

    def test_registry_lookup_and_clear(self):
        pa = self.create_mock_policy_assessment()
        action_executor.execute(ActionType.ALLOW_TRANSACTION, "CASE-305", "TXN-100", pa)

        cached = action_executor.get_execution("CASE-305", ActionType.ALLOW_TRANSACTION, "TXN-100")
        self.assertIsNotNone(cached)
        self.assertEqual(cached.case_id, "CASE-305")

        case_execs = action_executor.get_executions_for_case("CASE-305")
        self.assertEqual(len(case_execs), 1)

        action_executor.clear()
        self.assertIsNone(action_executor.get_execution("CASE-305", ActionType.ALLOW_TRANSACTION, "TXN-100"))


class TestStage6MockExecution(BaseStage6TestCase):
    """Verifies deterministic simulation for all 14 canonical actions."""

    def test_all_14_canonical_actions_simulated(self):
        canonical_targets = {
            ActionType.ALLOW_TRANSACTION: "TXN-104829",
            ActionType.DECLINE_TRANSACTION: "TXN-104829",
            ActionType.MONITOR_CARD: "CARD-4111-XXXX-9940",
            ActionType.MONITOR_CONNECTED_CARDS: "C-45821",
            ActionType.WARN_CUSTOMER: "C-45821",
            ActionType.VERIFY_WITH_CUSTOMER: "C-45821",
            ActionType.STEP_UP_AUTH: "TXN-104829",
            ActionType.BLOCK_CARD: "CARD-4111-XXXX-9940",
            ActionType.BLOCK_ALL_CARDS: "C-45821",
            ActionType.GENERATE_REPORT: "CASE-401",
            ActionType.CREATE_CASE: "TXN-104829",
            ActionType.FILE_REPORT: "CASE-401",
            ActionType.ESCALATE_TO_ANALYST: "CASE-401",
            ActionType.CLOSE_NO_FRAUD: "CASE-401",
        }

        for action, target in canonical_targets.items():
            pa = self.create_mock_policy_assessment(action=action, permitted=True)
            res = action_executor.execute(
                action=action,
                case_id=f"CASE-ALL-{action.name}",
                target_resource=target,
                policy_assessment=pa,
            )
            self.assertEqual(res.status, ExecutionStatus.EXECUTED, f"Action {action.value} failed to execute.")
            self.assertTrue(res.simulated, f"Action {action.value} missing simulated=True flag.")
            self.assertIn("[SIMULATED]", res.message)

    def test_execution_result_schema_fields(self):
        pa = self.create_mock_policy_assessment()
        res = action_executor.execute(
            action=ActionType.ALLOW_TRANSACTION,
            case_id="CASE-402",
            target_resource="TXN-100",
            policy_assessment=pa,
            params={"amount": 49.99},
        )
        self.assertTrue(res.execution_id.startswith("EXEC-"))
        self.assertIsInstance(res.executed_at, int)
        self.assertEqual(res.idempotency_key, "CASE-402:ALLOW_TRANSACTION:TXN-100")
        self.assertIsNotNone(res.audit_event_id)
        self.assertEqual(res.details["amount"], 49.99)


class TestStage6AuditTrail(BaseStage6TestCase):
    """Verifies structured audit events recorded during action execution."""

    def test_audit_event_requested_and_executed(self):
        pa = self.create_mock_policy_assessment()
        res = action_executor.execute(
            action=ActionType.ALLOW_TRANSACTION,
            case_id="CASE-501",
            target_resource="TXN-100",
            policy_assessment=pa,
        )
        events = audit_logger.get_events(case_id="CASE-501")
        req_events = [e for e in events if e.event_type == AuditEventType.ACTION_EXECUTION_REQUESTED]
        exec_events = [e for e in events if e.event_type == AuditEventType.ACTION_EXECUTED]

        self.assertEqual(len(req_events), 1)
        self.assertEqual(len(exec_events), 1)
        self.assertEqual(exec_events[0].status, "SUCCESS")

    def test_audit_event_blocked(self):
        pa = self.create_mock_policy_assessment(permitted=False)
        action_executor.execute(
            action=ActionType.BLOCK_CARD,
            case_id="CASE-502",
            target_resource="CARD-4111-XXXX-9940",
            policy_assessment=pa,
        )
        events = audit_logger.get_events(case_id="CASE-502", event_type=AuditEventType.ACTION_EXECUTION_BLOCKED)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].status, "BLOCKED")

    def test_audit_event_failed(self):
        broken_exec = MagicMock()
        broken_exec.validate_target.return_value = True
        broken_exec.execute.side_effect = RuntimeError("Simulated switch failure")
        svc = ActionExecutionService(executor=broken_exec)

        pa = self.create_mock_policy_assessment()
        res = svc.execute(
            action=ActionType.ALLOW_TRANSACTION,
            case_id="CASE-503",
            target_resource="TXN-100",
            policy_assessment=pa,
        )
        self.assertEqual(res.status, ExecutionStatus.FAILED)
        events = audit_logger.get_events(case_id="CASE-503", event_type=AuditEventType.ACTION_EXECUTION_FAILED)
        self.assertEqual(len(events), 1)


class TestStage6CaseMemoryPersistence(BaseStage6TestCase):
    """Verifies CaseMemoryAdapter persistence and fault isolation."""

    def test_persist_case_success_returns_graph_ids(self):
        case = InvestigationCase(
            case_id="CASE-601",
            transaction_id="TXN-104829",
            customer_id="C-45821",
            status=CaseStatus.RESOLVED,
            risk_score=0.92,
            confidence=0.88,
            evidence=[EvidenceItem(source="GRAPH", description="Syndicate match")],
        )
        receipt = case_memory_adapter.persist_case(case)

        self.assertTrue(receipt["success"])
        self.assertEqual(receipt["case_id"], "CASE-601")
        self.assertGreater(len(receipt["graph_ids"]), 0)
        self.assertTrue(case.written_to_graph)
        self.assertIsNotNone(case.graph_case_id)

    def test_persist_case_audit_events_recorded(self):
        case = InvestigationCase(
            case_id="CASE-602",
            transaction_id="TXN-209144",
            customer_id="C-99321",
        )
        case_memory_adapter.persist_case(case)

        req_events = audit_logger.get_events(case_id="CASE-602", event_type=AuditEventType.CASE_MEMORY_WRITE_REQUESTED)
        written_events = audit_logger.get_events(case_id="CASE-602", event_type=AuditEventType.CASE_MEMORY_WRITTEN)

        self.assertEqual(len(req_events), 1)
        self.assertEqual(len(written_events), 1)

    def test_persist_case_fault_isolation_on_graph_error(self):
        broken_graph = MagicMock()
        broken_graph.write_case_to_graph.side_effect = RuntimeError("TigerGraph unavailable")
        adapter = CaseMemoryAdapter(adapter=broken_graph)

        case = InvestigationCase(
            case_id="CASE-603",
            transaction_id="TXN-100",
        )
        # Should not raise exception
        receipt = adapter.persist_case(case)

        self.assertFalse(receipt["success"])
        self.assertFalse(case.written_to_graph)
        failed_events = audit_logger.get_events(case_id="CASE-603", event_type=AuditEventType.CASE_MEMORY_WRITE_FAILED)
        self.assertEqual(len(failed_events), 1)

    def test_persist_case_includes_action_records(self):
        case = InvestigationCase(
            case_id="CASE-604",
            transaction_id="TXN-104829",
        )
        exec_res = ExecutionResult(
            case_id="CASE-604",
            action=ActionType.BLOCK_CARD,
            target_resource="CARD-4111-XXXX-9940",
            status=ExecutionStatus.EXECUTED,
            idempotency_key="CASE-604:BLOCK_CARD:CARD-4111-XXXX-9940",
            message="Card blocked",
        )
        receipt = case_memory_adapter.persist_case(case, execution_results=[exec_res])
        self.assertTrue(receipt["success"])
        self.assertGreater(receipt["nodes_written"], 1)


class TestStage6WorkflowIntegration(BaseStage6TestCase):
    """Verifies workflow nodes and end-to-end execution flows."""

    def test_execution_node_auto_approved(self):
        state = create_initial_agent_state("TXN-209144")
        state["next_best_action"] = {"action": "ALLOW_TRANSACTION"}
        state["policy_assessment"] = self.create_mock_policy_assessment(
            action=ActionType.ALLOW_TRANSACTION,
            permitted=True,
            approval_level=ApprovalLevel.AUTO,
        ).model_dump()

        res_state = execution_node(state)
        self.assertIsNotNone(res_state.get("execution_result"))
        self.assertEqual(res_state["execution_result"]["status"], ExecutionStatus.EXECUTED.value)

    def test_case_persistence_node_commits_to_graph(self):
        state = create_initial_agent_state("TXN-209144")
        state["customer_id"] = "C-99321"
        state["next_best_action"] = {"action": "ALLOW_TRANSACTION"}

        res_state = case_persistence_node(state)
        self.assertTrue(res_state.get("written_to_graph"))
        self.assertEqual(res_state.get("current_workflow_state"), "RESOLVED")

    def test_full_lifecycle_workflow_benign_txn_209144(self):
        initial = create_initial_agent_state("TXN-209144")
        wf = create_full_lifecycle_workflow()
        final_state = wf.run(initial)

        self.assertEqual(final_state["transaction_id"], "TXN-209144")
        self.assertEqual(final_state["current_workflow_state"], "RESOLVED")
        self.assertTrue(final_state.get("written_to_graph"))
        self.assertIsNotNone(final_state.get("execution_result"))
        self.assertEqual(final_state["execution_result"]["status"], ExecutionStatus.EXECUTED.value)

    def test_full_lifecycle_workflow_high_risk_txn_104829(self):
        initial = create_initial_agent_state("TXN-104829")
        wf = create_full_lifecycle_workflow()
        final_state = wf.run(initial)

        self.assertEqual(final_state["transaction_id"], "TXN-104829")
        self.assertEqual(final_state["current_workflow_state"], "AWAITING_APPROVAL")
        self.assertIsNone(final_state.get("execution_result"))

    def test_create_execution_workflow_auto_approved(self):
        initial = create_initial_agent_state("TXN-209144")
        wf = create_execution_workflow()
        final_state = wf.run(initial)

        self.assertEqual(final_state["current_workflow_state"], "RESOLVED")
        self.assertTrue(final_state.get("written_to_graph"))


class TestStage6APIRoutes(BaseStage6TestCase):
    """Verifies REST endpoints and security against client spoofing."""

    def test_api_take_case_action_auto_approved(self):
        case = InvestigationCase(
            case_id="CASE-701",
            transaction_id="TXN-209144",
            customer_id="C-99321",
            status=CaseStatus.TRIGGERED,
            risk_score=0.15,
            confidence=0.85,
        )
        case_memory_service.save_case(case)

        status_code, _, body = run_asgi_request(
            self.app,
            "POST",
            "/api/cases/CASE-701/action",
            {"action": "ALLOW_TRANSACTION", "approved": False},
        )
        self.assertEqual(status_code, 200)
        self.assertEqual(body["status"], "RESOLVED")

    def test_api_take_case_action_client_spoofed_approval_rejected(self):
        case = InvestigationCase(
            case_id="CASE-702",
            transaction_id="TXN-104829",
            customer_id="C-45821",
            status=CaseStatus.AWAITING_APPROVAL,
            exposure_usd=8450.0,
            approval_request=ApprovalRequest(
                case_id="CASE-702",
                action="BLOCK_ALL_CARDS",
                target_resource="C-45821",
                status=ApprovalStatus.PENDING,
                approval_level=ApprovalLevel.L2_COMPLIANCE,
            ),
        )
        case_memory_service.save_case(case)

        # Client sends approved: True, but server-side status is PENDING
        status_code, _, body = run_asgi_request(
            self.app,
            "POST",
            "/api/cases/CASE-702/action",
            {"action": "BLOCK_ALL_CARDS", "approved": True},
        )
        self.assertIn(status_code, (400, 403))
        self.assertIn("rejected", str(body).lower())

    def test_api_take_case_action_approved_executes(self):
        case = InvestigationCase(
            case_id="CASE-703",
            transaction_id="TXN-104829",
            customer_id="C-45821",
            status=CaseStatus.AWAITING_APPROVAL,
            approval_request=ApprovalRequest(
                case_id="CASE-703",
                action="DECLINE_TRANSACTION",
                target_resource="TXN-104829",
                status=ApprovalStatus.APPROVED,
                approval_level=ApprovalLevel.L1_SUPERVISOR,
                approver_id="SUP-001",
            ),
        )
        case_memory_service.save_case(case)

        status_code, _, body = run_asgi_request(
            self.app,
            "POST",
            "/api/cases/CASE-703/action",
            {"action": "DECLINE_TRANSACTION", "approved": True, "approver_id": "SUP-001"},
        )
        self.assertEqual(status_code, 200)
        self.assertEqual(body["status"], "RESOLVED")

    def test_api_take_case_action_not_found(self):
        status_code, _, _ = run_asgi_request(
            self.app,
            "POST",
            "/api/cases/CASE-NONEXISTENT/action",
            {"action": "ALLOW_TRANSACTION", "approved": True},
        )
        self.assertEqual(status_code, 404)

    def test_api_execute_investigation_auto_approved_txn_209144(self):
        status_code, _, body = run_asgi_request(
            self.app,
            "POST",
            "/api/investigations/TXN-209144/execute",
            {"trigger": {"type": "HIGH_RISK"}},
        )
        self.assertEqual(status_code, 200)
        self.assertEqual(body["status"], "RESOLVED")
        self.assertFalse(body["approval_required"])
        self.assertIsNotNone(body["execution_result"])

    def test_api_execute_investigation_high_risk_halts_txn_301855(self):
        status_code, _, body = run_asgi_request(
            self.app,
            "POST",
            "/api/investigations/TXN-301855/execute",
            {"trigger": {"type": "HIGH_RISK"}},
        )
        self.assertEqual(status_code, 200)
        self.assertEqual(body["status"], "AWAITING_APPROVAL")
        self.assertTrue(body["approval_required"])
        self.assertEqual(body["approval_level"], "L2")
        self.assertIsNone(body["execution_result"])

    def test_api_execute_investigation_action_override_declines_txn_104829(self):
        status_code, _, body = run_asgi_request(
            self.app,
            "POST",
            "/api/investigations/TXN-104829/execute",
            {"action_override": "DECLINE_TRANSACTION"},
        )
        self.assertEqual(status_code, 200)
        self.assertEqual(body["status"], "AWAITING_APPROVAL")
        self.assertTrue(body["approval_required"])
        self.assertEqual(body["approval_level"], "L1")
        self.assertIsNone(body["execution_result"])

    def test_api_execute_investigation_policy_blocked_txn_104829(self):
        status_code, _, body = run_asgi_request(
            self.app,
            "POST",
            "/api/investigations/TXN-104829/execute",
            {"trigger": {"type": "HIGH_RISK"}},
        )
        self.assertEqual(status_code, 200)
        self.assertEqual(body["status"], "POLICY_BLOCKED")
        self.assertFalse(body["approval_required"])
        self.assertIn("R10", body["violated_rules"])


if __name__ == "__main__":
    unittest.main()
