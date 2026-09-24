# ==============================================================================
# FraudGraph AI - Stage 1 Foundation Test Suite
# tests/test_stage1_foundation.py
# Workstream: Person 1 (Brain) - Stage 1 Foundation
# ==============================================================================

import asyncio
import json
import unittest
from typing import Dict, Any, Optional

from backend.config import BackendSettings, settings
from backend.errors import (
    FraudGraphException,
    ErrorDetail,
    ErrorResponse,
    TransactionNotFoundException,
    CustomerNotFoundException,
    CaseNotFoundException,
    GraphQueryFailedException,
    PolicyViolationException,
    ApprovalRequiredException,
    InvalidApprovalException,
    UnauthorizedToolError,
    WorkflowLoopLimitExceeded,
    ValidationError,
    InternalServerError,
)
from backend.models.domain import (
    ActionType,
    CaseStatus,
    ApprovalStatus,
    RiskLevel,
    Transaction,
    Customer,
    EvidenceItem,
    EvidenceRequest,
    FraudPattern,
    RiskAssessment,
    UncertaintyAssessment,
    ActionRecommendation,
    ActionRouteItem,
    NextBestActions,
    SARReport,
    ApprovalRequest,
    ActionResult,
    TimelineEvent,
    InvestigationCase,
)
from backend.models.audit import (
    AuditEventType,
    AuditEvent,
    AuditLogger,
    audit_logger,
    sanitize_audit_payload,
)
from backend.policy.interface import (
    PolicyDecision,
    PolicyEngineInterface,
    ApprovalServiceInterface,
)
from backend.services.mock_actions import MockActionService, mock_action_service
from backend.services.case_memory import InMemoryCaseMemoryService, case_memory_service
from agent.tools.security import (
    ToolSecurityLevel,
    ToolMetadata,
    ToolSecurityManager,
    tool_security_manager,
)
from agent.tools.graph_adapter import Person2GraphAdapter, graph_adapter
from agent.reasoning.interfaces import (
    RiskEngineInterface,
    UncertaintyEngineInterface,
    NextBestActionEngineInterface,
)
from agent.workflows.state import (
    AgentState,
    create_initial_agent_state,
    add_timeline_event,
)
from agent.workflows.engine import WorkflowEngine, WorkflowNode
from agent.workflows.workflow import create_investigation_workflow, create_full_lifecycle_workflow
from backend.api.app import app


def asgi_request(
    app_instance,
    method: str,
    path: str,
    body: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
) -> tuple[int, Dict[str, str], Dict[str, Any]]:
    """Lightweight ASGI test helper executing requests against FastAPI without external packages."""
    body_bytes = json.dumps(body).encode("utf-8") if body is not None else b""
    header_list = [(b"host", b"testserver")]
    if body is not None:
        header_list.append((b"content-type", b"application/json"))
    if headers:
        for k, v in headers.items():
            header_list.append((k.lower().encode("utf-8"), v.encode("utf-8")))

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": b"",
        "headers": header_list,
    }

    sent_messages = []

    async def receive():
        return {"type": "http.request", "body": body_bytes, "more_body": False}

    async def send(msg):
        sent_messages.append(msg)

    asyncio.run(app_instance(scope, receive, send))

    status_code = 500
    response_headers = {}
    response_body = b""
    for msg in sent_messages:
        if msg["type"] == "http.response.start":
            status_code = msg["status"]
            response_headers = {k.decode("utf-8").lower(): v.decode("utf-8") for k, v in msg.get("headers", [])}
        elif msg["type"] == "http.response.body":
            response_body += msg.get("body", b"")

    try:
        parsed_body = json.loads(response_body.decode("utf-8")) if response_body else {}
    except Exception:
        parsed_body = {"raw": response_body.decode("utf-8", errors="replace")}

    return status_code, response_headers, parsed_body


class TestStage1Foundation(unittest.TestCase):
    """Stage 1 Foundation Verification Test Suite for Person 1."""

    def setUp(self):
        audit_logger.clear()
        case_memory_service.clear()

    # --------------------------------------------------------------------------
    # 1. Configuration & Secret Masking
    # --------------------------------------------------------------------------
    def test_configuration_loading_and_masking(self):
        test_settings = BackendSettings(
            app_env="test",
            llm_api_key="secret-key-12345",
            tigergraph_password="super-secret-password",
        )
        safe_summary = test_settings.get_safe_summary()
        self.assertNotIn("secret-key-12345", json.dumps(safe_summary))
        self.assertNotIn("super-secret-password", json.dumps(safe_summary))
        self.assertTrue(safe_summary["llm_api_key_configured"])
        self.assertEqual(safe_summary["app_env"], "test")

    # --------------------------------------------------------------------------
    # 2. Domain Models Validation
    # --------------------------------------------------------------------------
    def test_transaction_model_currency_enforcement(self):
        # Valid USD transaction
        txn = Transaction(
            transaction_id="TXN-104829",
            customer_id="C-45821",
            account_id="ACC-9912",
            amount=1249.50,
            currency="USD",
        )
        self.assertEqual(txn.currency, "USD")
        self.assertEqual(txn.amount, 1249.50)

        # Invalid currency rejection (strictly USD per project specification)
        with self.assertRaises(ValueError):
            Transaction(
                transaction_id="TXN-104829",
                customer_id="C-45821",
                account_id="ACC-9912",
                amount=1249.50,
                currency="EUR",
            )

    def test_domain_models_creation(self):
        cust = Customer(customer_id="C-45821", name="Alex Mercer", risk_tier=RiskLevel.HIGH)
        self.assertEqual(cust.risk_tier, RiskLevel.HIGH)

        pattern = FraudPattern(
            pattern_id="FP-01",
            name="Shared Device Syndicate Ring",
            description="Linked devices across multiple accounts",
            severity=RiskLevel.CRITICAL,
        )
        self.assertEqual(pattern.pattern_id, "FP-01")

        rec = ActionRecommendation(
            action="BLOCK_TRANSACTION",
            reason="High risk score",
            confidence=0.92,
        )
        self.assertEqual(rec.action, "BLOCK_TRANSACTION")
        self.assertTrue(rec.confidence > 0.9)

        appr = ApprovalRequest(
            case_id="CASE-1024",
            action="FREEZE_ACCOUNT",
            target_resource="ACC-9912",
            amount=8450.00,
        )
        self.assertEqual(appr.status, ApprovalStatus.PENDING)

        # Organizer evidence item with claim, ref, entity_ids
        evid = EvidenceItem(
            source="graph",
            evidence_type="DEVICE_SHARING",
            claim="Hardware fingerprint D-421 linked to 4 accounts",
            ref="query:card_window(card_id=C00377-K1)",
            entity_ids=["T0412877"],
        )
        self.assertEqual(evid.claim, "Hardware fingerprint D-421 linked to 4 accounts")
        self.assertEqual(evid.entity_ids, ["T0412877"])

        # Organizer evidence request
        ev_req = EvidenceRequest(
            type="customer_validation",
            asked_after_step=4,
            assumed_response="Customer states they did not make purchase",
        )
        self.assertEqual(ev_req.asked_after_step, 4)

        # Organizer next best actions with initial, final, what_changed
        nba = NextBestActions(
            initial=[ActionRouteItem(action="DECLINE_TRANSACTION", route="L1", reason="R5: testing observed")],
            final=[ActionRouteItem(action="BLOCK_CARD", route="L1", reason="R2 and R5: customer denied")],
            what_changed="Customer denial confirmed block.",
        )
        self.assertEqual(len(nba.initial), 1)
        self.assertEqual(len(nba.final), 1)
        self.assertEqual(nba.what_changed, "Customer denial confirmed block.")

        # Full organizer InvestigationCase
        full_case = InvestigationCase(
            case_id="HHG-017",
            transaction_id="T0412877",
            status=CaseStatus.RESOLVED,
            verdict="fraud",
            fraud_probability=0.86,
            pattern="card_testing",
            exposure_usd=268.43,
            affected_txn_ids=["T0412877", "T0412878"],
            connected_card_ids=["C00877-K1"],
            written_to_graph=True,
            graph_case_id="CASE-2016-1187",
            stop_reason="Defensible decision reached",
        )
        self.assertEqual(full_case.verdict, "fraud")
        self.assertEqual(full_case.exposure_usd, 268.43)
        self.assertTrue(full_case.written_to_graph)

    # --------------------------------------------------------------------------
    # 3. Section 9 Centralized Error System
    # --------------------------------------------------------------------------
    def test_section_9_error_structure(self):
        err = TransactionNotFoundException("TXN-MISSING-99")
        d = err.to_dict()
        self.assertIn("error", d)
        self.assertEqual(d["error"]["code"], "TRANSACTION_NOT_FOUND")
        self.assertIn("details", d["error"])
        self.assertEqual(d["error"]["details"]["transaction_id"], "TXN-MISSING-99")

        loop_err = WorkflowLoopLimitExceeded(11, 10)
        self.assertEqual(loop_err.code, "WORKFLOW_LOOP_LIMIT_EXCEEDED")
        self.assertEqual(loop_err.status_code, 500)

    # --------------------------------------------------------------------------
    # 4. Audit Trail & Sensitive Data Sanitization
    # --------------------------------------------------------------------------
    def test_audit_payload_sanitization(self):
        raw_payload = {
            "transaction_id": "TXN-104829",
            "password": "plain_text_password",
            "auth_token": "bearer-xyz-12345",
            "api_key": "gemini-secret-api-key",
            "nested": {
                "credit_card": "4111111111111234",
                "safe_field": "visible_data",
            }
        }
        sanitized = sanitize_audit_payload(raw_payload)
        self.assertEqual(sanitized["transaction_id"], "TXN-104829")
        self.assertEqual(sanitized["password"], "[REDACTED]")
        self.assertEqual(sanitized["auth_token"], "[REDACTED]")
        self.assertEqual(sanitized["api_key"], "[REDACTED]")
        self.assertEqual(sanitized["nested"]["credit_card"], "[REDACTED]")
        self.assertEqual(sanitized["nested"]["safe_field"], "visible_data")

    def test_audit_event_recording(self):
        evt = audit_logger.record_event(
            event_type=AuditEventType.RECOMMENDED,
            case_id="CASE-001",
            action="BLOCK_TRANSACTION",
            actor="AGENT",
            payload={"reason": "High fraud score", "secret_token": "must_be_hidden"},
        )
        self.assertEqual(evt.event_type, AuditEventType.RECOMMENDED)
        self.assertEqual(evt.payload["secret_token"], "[REDACTED]")
        
        events = audit_logger.get_events(case_id="CASE-001")
        self.assertEqual(len(events), 1)

    # --------------------------------------------------------------------------
    # 5. Tool Security Manager (Least Privilege & Injection Defense)
    # --------------------------------------------------------------------------
    def test_tool_security_manager_valid_call(self):
        # Should not raise
        tool_security_manager.validate_tool_call("get_transaction", {"transaction_id": "TXN-104829"})

    def test_tool_security_manager_unregistered_tool(self):
        with self.assertRaises(UnauthorizedToolError) as ctx:
            tool_security_manager.validate_tool_call("drop_database_tables", {})
        self.assertIn("not in the authorized tool registry", str(ctx.exception))

    def test_tool_security_manager_disallowed_parameter(self):
        with self.assertRaises(UnauthorizedToolError) as ctx:
            tool_security_manager.validate_tool_call("get_transaction", {"transaction_id": "TXN-104829", "raw_gsql": "TRUE"})
        self.assertIn("not allowed", str(ctx.exception))

    def test_tool_security_manager_gsql_injection_defense(self):
        # Attempt raw GSQL injection
        with self.assertRaises(UnauthorizedToolError) as ctx:
            tool_security_manager.validate_tool_call(
                "get_transaction",
                {"transaction_id": "TXN-104829'; DROP GRAPH FraudGraph; --"}
            )
        self.assertEqual(ctx.exception.code, "UNAUTHORIZED_TOOL_CALL")

    def test_tool_security_manager_invalid_id_characters(self):
        with self.assertRaises(UnauthorizedToolError) as ctx:
            tool_security_manager.validate_tool_call(
                "get_transaction",
                {"transaction_id": "<script>alert(1)</script>"}
            )
        self.assertIn("contains invalid characters", str(ctx.exception))

    # --------------------------------------------------------------------------
    # 6. Person 2 Graph & GraphRAG Adapter
    # --------------------------------------------------------------------------
    def test_graph_adapter_get_transaction_seeded(self):
        txn = graph_adapter.get_transaction("TXN-104829")
        self.assertEqual(txn["transaction_id"], "TXN-104829")
        self.assertEqual(txn["currency"], "USD")
        self.assertGreater(txn["amount"], 0)

    def test_graph_adapter_get_transaction_unknown_raises(self):
        with self.assertRaises(TransactionNotFoundException):
            graph_adapter.get_transaction("TXN-NONEXISTENT-999")

    def test_graph_adapter_get_customer_seeded(self):
        cust = graph_adapter.get_customer("C-45821")
        self.assertEqual(cust["customer_id"], "C-45821")
        self.assertEqual(cust["name"], "Alex Mercer")

    def test_graph_adapter_get_customer_unknown_raises(self):
        with self.assertRaises(CustomerNotFoundException):
            graph_adapter.get_customer("C-UNKNOWN-999")

    def test_graph_adapter_traversals(self):
        # Connected entities
        graph_res = graph_adapter.get_connected_entities("TXN-104829", depth=2)
        self.assertIn("nodes", graph_res)
        self.assertIn("edges", graph_res)
        self.assertGreater(len(graph_res["nodes"]), 0)

        # Shared devices
        devices_res = graph_adapter.find_shared_devices("D-421")
        self.assertIn("devices", devices_res)
        self.assertEqual(len(devices_res["devices"]), 1)
        self.assertEqual(devices_res["devices"][0]["linked_accounts"], 4)

        # Detect fraud patterns
        patterns_res = graph_adapter.detect_fraud_patterns("TXN-104829")
        self.assertIn("patterns", patterns_res)
        self.assertEqual(len(patterns_res["patterns"]), 2)

        # Policy context
        pol_res = graph_adapter.get_policy_context(action="BLOCK_TRANSACTION", amount=8450.00)
        self.assertTrue(pol_res["approval_required"])
        self.assertTrue(pol_res["sar_required"])

    def test_graph_adapter_retrieve_investigation_context(self):
        ctx = graph_adapter.retrieve_investigation_context("TXN-104829")
        self.assertIn("prompt_context", ctx)
        self.assertIn("=== GRAPHRAG INVESTIGATION CONTEXT ===", ctx["prompt_context"])
        self.assertIn("policy", ctx)
        self.assertIn("similar_cases", ctx)

    def test_graph_adapter_write_case_to_graph(self):
        res = graph_adapter.write_case_to_graph({
            "case_id": "CASE-STAGE1-TEST",
            "transaction_id": "TXN-104829",
            "customer_id": "C-45821",
            "status": "INVESTIGATING",
            "risk_score": 0.85,
            "confidence": 0.90,
            "fraud_patterns": [],
            "evidence": [],
        })
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["case_id"], "CASE-STAGE1-TEST")

    # --------------------------------------------------------------------------
    # 7. Services & Interfaces (Mock Action & Case Memory)
    # --------------------------------------------------------------------------
    def test_mock_action_service_execution(self):
        res = mock_action_service.execute_action(
            action="BLOCK_TRANSACTION",
            case_id="CASE-001",
            target_resource="TXN-104829",
            params={"reason": "Syndicate pattern detected"},
        )
        self.assertTrue(res.success)
        self.assertEqual(res.action, "BLOCK_TRANSACTION")
        self.assertEqual(res.case_id, "CASE-001")

        # Unsupported action must raise ValidationError
        with self.assertRaises(ValidationError):
            mock_action_service.execute_action(
                action="NON_EXISTENT_ACTION",
                case_id="CASE-001",
                target_resource="TXN-104829",
            )

    def test_in_memory_case_memory_service(self):
        case = InvestigationCase(
            case_id="CASE-STORE-01",
            transaction_id="TXN-104829",
            customer_id="C-45821",
            status=CaseStatus.INVESTIGATING,
            risk_score=0.88,
        )
        saved = case_memory_service.save_case(case)
        self.assertTrue(saved)

        retrieved = case_memory_service.get_case("CASE-STORE-01")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.case_id, "CASE-STORE-01")
        self.assertEqual(retrieved.risk_score, 0.88)

        similar = case_memory_service.search_similar_cases("TXN-104829")
        self.assertGreater(len(similar), 0)
        self.assertEqual(similar[0]["case_id"], "CASE-STORE-01")

    # --------------------------------------------------------------------------
    # 8. Agent State
    # --------------------------------------------------------------------------
    def test_agent_state_initialization_and_timeline(self):
        state = create_initial_agent_state("TXN-104829", "CASE-TEST-100", max_iterations=10)
        self.assertEqual(state["transaction_id"], "TXN-104829")
        self.assertEqual(state["case_id"], "CASE-TEST-100")
        self.assertEqual(state["iteration_count"], 0)
        self.assertEqual(state["max_iterations"], 10)
        self.assertEqual(len(state["timeline"]), 1)
        self.assertIn("initial_next_best_actions", state)
        self.assertIn("final_next_best_actions", state)
        self.assertIn("what_changed", state)
        self.assertIn("evidence_requests", state)
        self.assertIn("collected_evidence", state)

        add_timeline_event(state, stage="ENRICHMENT", title="Enrichment Test", description="Details")
        self.assertEqual(len(state["timeline"]), 2)
        self.assertEqual(state["timeline"][-1]["stage"], "ENRICHMENT")

    # --------------------------------------------------------------------------
    # 9. Workflow Engine (Pure-Python State Machine)
    # --------------------------------------------------------------------------
    def test_workflow_engine_linear_execution(self):
        engine = WorkflowEngine()

        def node_a(state: AgentState) -> AgentState:
            state["step_a"] = True
            return state

        def node_b(state: AgentState) -> AgentState:
            state["step_b"] = True
            return state

        engine.add_node("A", node_a)
        engine.add_node("B", node_b)
        engine.set_entry_point("A")
        engine.add_edge("A", "B")
        engine.set_terminal_nodes(["B"])

        initial = create_initial_agent_state("TXN-104829")
        res = engine.run(initial)
        self.assertTrue(res.get("step_a"))
        self.assertTrue(res.get("step_b"))
        self.assertEqual(res["current_workflow_state"], "B")

    def test_workflow_engine_conditional_routing(self):
        engine = WorkflowEngine()

        def node_start(state: AgentState) -> AgentState:
            return state

        def node_high(state: AgentState) -> AgentState:
            state["result"] = "HIGH_PATH"
            return state

        def node_low(state: AgentState) -> AgentState:
            state["result"] = "LOW_PATH"
            return state

        def router(state: AgentState) -> str:
            return "high" if state.get("score", 0) > 50 else "low"

        engine.add_node("START", node_start)
        engine.add_node("HIGH", node_high)
        engine.add_node("LOW", node_low)
        engine.set_entry_point("START")
        engine.add_conditional_edges("START", router, {"high": "HIGH", "low": "LOW"})
        engine.set_terminal_nodes(["HIGH", "LOW"])

        state_high = create_initial_agent_state("TXN-104829")
        state_high["score"] = 90
        res_high = engine.run(state_high)
        self.assertEqual(res_high["result"], "HIGH_PATH")

        state_low = create_initial_agent_state("TXN-104829")
        state_low["score"] = 10
        res_low = engine.run(state_low)
        self.assertEqual(res_low["result"], "LOW_PATH")

    def test_workflow_engine_loop_limit_enforcement(self):
        engine = WorkflowEngine()

        def looping_node(state: AgentState) -> AgentState:
            return state

        engine.add_node("LOOP", looping_node)
        engine.set_entry_point("LOOP")
        engine.add_edge("LOOP", "LOOP") # Infinite loop

        state = create_initial_agent_state("TXN-104829", max_iterations=5)

        with self.assertRaises(WorkflowLoopLimitExceeded):
            engine.run(state)

    # --------------------------------------------------------------------------
    # 10. Canonical Investigation Workflow Scenarios
    # --------------------------------------------------------------------------
    def test_investigation_workflow_high_risk_syndicate(self):
        # TXN-104829: Seeded transaction with device ring FP-01
        initial = create_initial_agent_state("TXN-104829")
        workflow = create_full_lifecycle_workflow()
        final_state = workflow.run(initial)

        self.assertEqual(final_state["transaction_id"], "TXN-104829")
        self.assertIsNotNone(final_state["transaction_data"])
        self.assertIsNotNone(final_state["customer_data"])
        self.assertEqual(len(final_state["fraud_patterns"]), 2)
        self.assertEqual(final_state["next_best_action"]["action"], "BLOCK_TRANSACTION")
        self.assertEqual(final_state["current_workflow_state"], "AWAITING_APPROVAL")

    def test_investigation_workflow_high_value_wire(self):
        # TXN-301855: Seeded mule and high-value wire triggering policy approval
        initial = create_initial_agent_state("TXN-301855")
        workflow = create_full_lifecycle_workflow()
        final_state = workflow.run(initial)

        self.assertEqual(final_state["transaction_data"]["amount"], 8450.00)
        self.assertTrue(final_state["next_best_action"]["approval_required"])
        self.assertEqual(final_state["approval_status"], "PENDING")
        self.assertEqual(final_state["current_workflow_state"], "AWAITING_APPROVAL")

    def test_investigation_workflow_benign_transaction(self):
        # TXN-209144: Low risk $48.00 transaction with 0 patterns
        initial = create_initial_agent_state("TXN-209144")
        workflow = create_full_lifecycle_workflow()
        final_state = workflow.run(initial)

        self.assertEqual(final_state["next_best_action"]["action"], "ALLOW_TRANSACTION")
        self.assertFalse(final_state["next_best_action"]["approval_required"])
        self.assertEqual(final_state["current_workflow_state"], "RESOLVED")

    # --------------------------------------------------------------------------
    # 11. FastAPI REST API & Middleware
    # --------------------------------------------------------------------------
    def test_api_health_endpoint(self):
        status, headers, body = asgi_request(app, "GET", "/health")
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "healthy")
        self.assertEqual(body["service"], "fraudgraph-backend")
        self.assertEqual(headers["x-content-type-options"], "nosniff")
        self.assertEqual(headers["x-frame-options"], "DENY")

    def test_api_status_endpoint(self):
        status, headers, body = asgi_request(app, "GET", "/api/status")
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "operational")
        self.assertIn("graph_layer", body["components"])
        self.assertIn("use_mock_graph", body["config"])

    def test_api_get_transaction(self):
        status, _, body = asgi_request(app, "GET", "/api/transactions/TXN-104829")
        self.assertEqual(status, 200)
        self.assertEqual(body["transaction_id"], "TXN-104829")

    def test_api_get_transaction_not_found(self):
        status, _, body = asgi_request(app, "GET", "/api/transactions/TXN-NONEXISTENT")
        self.assertEqual(status, 404)
        self.assertIn("error", body)
        self.assertEqual(body["error"]["code"], "TRANSACTION_NOT_FOUND")

    def test_api_investigate_endpoint(self):
        status, _, body = asgi_request(app, "POST", "/api/investigate", {"transaction_id": "TXN-104829"})
        self.assertEqual(status, 200)
        self.assertEqual(body["transaction_id"], "TXN-104829")
        self.assertIn("evidence", body)
        self.assertEqual(body["status"], "COMPLETE")

    def test_api_investigate_rejects_client_injected_risk_score(self):
        # Security Baseline §19: Client attempting to submit its own risk/confidence
        status, _, body = asgi_request(
            app,
            "POST",
            "/api/investigate",
            {"transaction_id": "TXN-104829", "risk_score": 0.05} # Malicious client override attempt
        )
        self.assertEqual(status, 422)
        self.assertIn("error", body)
        self.assertEqual(body["error"]["code"], "VALIDATION_ERROR")
        self.assertIn("not permitted to supply risk or confidence", body["error"]["message"])

    def test_api_investigate_rejects_client_injected_approval(self):
        # Security Baseline §20: Client attempting to submit approval=true
        status, _, body = asgi_request(
            app,
            "POST",
            "/api/investigate",
            {"transaction_id": "TXN-104829", "approved": True} # Malicious bypass attempt
        )
        self.assertEqual(status, 422)
        self.assertIn("error", body)
        self.assertEqual(body["error"]["code"], "VALIDATION_ERROR")
        self.assertIn("not permitted to submit approval flags", body["error"]["message"])

    def test_api_approve_endpoint_invalid_token(self):
        # Security Baseline §4: Invalid or bypass approval token fails closed
        status, _, body = asgi_request(
            app,
            "POST",
            "/api/cases/CASE-001/approve",
            {"approver_id": "ANALYST-1", "decision": "APPROVED", "approval_token": "bypass-token"}
        )
        self.assertEqual(status, 403)
        self.assertIn("error", body)
        self.assertEqual(body["error"]["code"], "INVALID_APPROVAL")


if __name__ == "__main__":
    unittest.main()
