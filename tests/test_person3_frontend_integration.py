# ==============================================================================
# FraudGraph AI - Person 3 Frontend Integration Tests
# ==============================================================================

import unittest
import json
import asyncio
from backend.api.app import create_app
from backend.services.case_memory import case_memory_service


def asgi_request(app, method: str, path: str, body: dict = None, headers: list = None):
    """Synchronous test helper for ASGI application requests."""
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "headers": headers or [(b"host", b"testserver"), (b"content-type", b"application/json")],
        "query_string": b"",
    }
    
    response_body = []
    response_headers = []
    response_status = [None]
    
    async def receive():
        if body is not None:
            return {
                "type": "http.request",
                "body": json.dumps(body).encode("utf-8"),
                "more_body": False,
            }
        return {"type": "http.request", "body": b"", "more_body": False}
        
    async def send(message):
        if message["type"] == "http.response.start":
            response_status[0] = message["status"]
            response_headers.extend(message.get("headers", []))
        elif message["type"] == "http.response.body":
            response_body.append(message.get("body", b""))
            
    async def run():
        await app(scope, receive, send)
        
    asyncio.run(run())
    
    full_body = b"".join(response_body).decode("utf-8")
    parsed_body = json.loads(full_body) if full_body else {}
    return response_status[0], dict(response_headers), parsed_body


class TestPerson3FrontendIntegration(unittest.TestCase):
    """End-to-end verification of all Person 3 Frontend API endpoints and schemas."""

    def setUp(self):
        self.app = create_app()

    def test_start_investigation_with_string_trigger(self):
        """Frontend sends { transaction_id, trigger: 'HIGH_RISK' }."""
        status, _, body = asgi_request(
            self.app,
            "POST",
            "/api/investigations",
            {"transaction_id": "TXN-104829", "trigger": "HIGH_RISK"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["transaction_id"], "TXN-104829")
        self.assertIn("case_id", body)
        self.assertIn("status", body)
        self.assertIn("risk_score", body)
        self.assertGreater(body["risk_score"], 0.0)

        case_id = body["case_id"]
        # Verify case was persisted in server-side case_memory_service
        saved_case = case_memory_service.get_case(case_id)
        self.assertIsNotNone(saved_case)
        self.assertEqual(saved_case.transaction_id, "TXN-104829")

    def test_hero_case_dynamic_seeding(self):
        """GET /api/cases/CASE-1024 dynamically seeds hero demo case if not yet cached."""
        status, _, body = asgi_request(self.app, "GET", "/api/cases/CASE-1024")
        self.assertEqual(status, 200)
        self.assertEqual(body["case_id"], "CASE-1024")
        self.assertEqual(body["transaction_id"], "TXN-104829")
        self.assertIn("graph_entities", body)
        self.assertIn("graph_relationships", body)
        self.assertIn("recommendation", body)
        self.assertIn("timeline", body)
        self.assertIn("amount", body)
        self.assertEqual(body["currency"], "USD")
        self.assertGreater(len(body["graph_entities"]), 0)
        self.assertGreater(len(body["graph_relationships"]), 0)

    def test_get_case_contract_and_types(self):
        """Verify GET /api/cases/{caseId} strictly adheres to frontend InvestigationCase TypeScript interface."""
        # 1. Start investigation
        status, _, start_body = asgi_request(
            self.app,
            "POST",
            "/api/investigations",
            {"transaction_id": "TXN-104829", "trigger": "CUSTOMER_REPORT"},
        )
        self.assertEqual(status, 200)
        case_id = start_body["case_id"]

        # 2. Get case
        status, _, case = asgi_request(self.app, "GET", f"/api/cases/{case_id}")
        self.assertEqual(status, 200)

        # Check all required top-level fields in frontend InvestigationCase
        required_fields = [
            "case_id", "transaction_id", "customer_id", "status", "risk_score",
            "confidence", "fraud_patterns", "evidence", "recommendation",
            "approval_required", "timeline", "amount", "currency",
            "created_at", "updated_at", "transaction_summary",
            "graph_entities", "graph_relationships", "missing_evidence",
        ]
        for field in required_fields:
            self.assertIn(field, case, f"Missing required frontend field '{field}' in case response")

        # Check graph_entities structure
        for ent in case["graph_entities"]:
            self.assertIn("id", ent)
            self.assertIn("type", ent)
            self.assertIn("label", ent)
            self.assertIn("risk_score", ent)
            self.assertIn("flagged", ent)

        # Check graph_relationships structure
        for rel in case["graph_relationships"]:
            self.assertIn("id", rel)
            self.assertIn("source", rel)
            self.assertIn("target", rel)
            self.assertIn("label", rel)

        # Check recommendation structure
        rec = case["recommendation"]
        self.assertIn("action", rec)
        self.assertIn("reason", rec)
        self.assertIn("confidence", rec)
        self.assertIn("approval_required", rec)
        self.assertIn("policy_basis", rec)

    def test_get_case_investigation_and_recommendation(self):
        """Verify GET /cases/{id}/investigation and GET /cases/{id}/recommendation."""
        status, _, body = asgi_request(self.app, "GET", "/api/cases/CASE-1024/investigation")
        self.assertEqual(status, 200)
        self.assertEqual(body["case_id"], "CASE-1024")

        status, _, rec = asgi_request(self.app, "GET", "/api/cases/CASE-1024/recommendation")
        self.assertEqual(status, 200)
        self.assertIn("action", rec)
        self.assertIn("reason", rec)
        self.assertIn("confidence", rec)

    def test_evidence_request_and_submission_lifecycle(self):
        """Verify evidence request and untrusted evidence ingestion lifecycle."""
        # 1. Start investigation
        _, _, start_body = asgi_request(
            self.app,
            "POST",
            "/api/investigations",
            {"transaction_id": "TXN-104829", "trigger": "HIGH_RISK"},
        )
        case_id = start_body["case_id"]

        # 2. Request evidence
        status, _, req_res = asgi_request(
            self.app,
            "POST",
            f"/api/cases/{case_id}/evidence-request",
            {"evidence_type": "CUSTOMER_TRANSACTION_CONFIRMATION"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(req_res["status"], "WAITING_FOR_EVIDENCE")
        self.assertGreater(len(req_res["requested"]), 0)

        # 3. Submit customer response (untrusted input)
        status, _, updated_case = asgi_request(
            self.app,
            "POST",
            f"/api/cases/{case_id}/evidence",
            {
                "type": "CUSTOMER_CONFIRMATION",
                "source": "Controlled customer verification",
                "summary": "I did not recognize this transaction.",
                "related_entities": ["C-45821", "TXN-104829"],
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(updated_case["status"], "ACTION_READY")
        self.assertEqual(updated_case["customer_response"], "I did not recognize this transaction.")
        self.assertTrue(updated_case["approval_required"])
        self.assertGreaterEqual(updated_case["confidence"], 0.95)

        # Check evidence was ingested with untrusted flag
        ev_items = [e for e in updated_case["evidence"] if e["type"] == "CUSTOMER_CONFIRMATION"]
        self.assertEqual(len(ev_items), 1)

        # 4. Human supervisory approval & execution
        status, _, action_res = asgi_request(
            self.app,
            "POST",
            f"/api/cases/{case_id}/action",
            {
                "action": updated_case["recommendation"]["action"],
                "approved": True,
                "approver_id": "COMP-001",
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(action_res["status"], "RESOLVED")
        self.assertIsNotNone(action_res["case_memory"])

    def test_case_not_found(self):
        """Non-existent case ID returns 404."""
        status, _, body = asgi_request(self.app, "GET", "/api/cases/CASE-UNKNOWN-XYZ")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
