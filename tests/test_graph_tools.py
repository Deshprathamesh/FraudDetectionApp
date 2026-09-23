# ==============================================================================
# FraudGraph AI - TigerGraph Tools Contract Tests
# tests/test_graph_tools.py
# Workstream: Person 2 (Graph)
#
# Verification suite asserting tool contracts against the deterministic mock
# provider per Section 7, Section 5, and Section 9 of the Integration Spec.
#
# Architecture Rules:
# - ENTITY-RESOLUTION tools (ID must exist to mean anything):
#   get_transaction, get_customer, write_case_to_graph
#   -> An unknown/missing ID returns the Section 9 error dict.
#
# - GRAPH-TRAVERSAL tools (valid query that legitimately finds nothing):
#   get_transaction_history, get_connected_entities, find_shared_devices,
#   detect_fraud_patterns, find_similar_cases, get_policy_context
#   -> An unknown/unmatched ID returns a valid, empty-but-well-formed response.
# ==============================================================================

import pytest
from typing import Dict, Any

from tigergraph.tools import (
    get_graph_tools,
    TransactionDetailResponse,
    CustomerDetailResponse,
    TransactionHistoryResponse,
    ConnectedEntitiesResponse,
    SharedDevicesResponse,
    DetectFraudPatternsResponse,
    SimilarCasesResponse,
    PolicyContextResponse,
    WriteCaseResponse,
)


@pytest.fixture(scope="module")
def tools() -> Dict[str, Any]:
    """Provides the 9 contract tools from tigergraph.tools.get_graph_tools()."""
    registry = get_graph_tools()
    assert len(registry) == 9, f"Expected 9 contract tools, got {len(registry)}"
    return registry


def assert_section_9_error(res: Any, expected_code: str = None) -> None:
    """
    Asserts that a return value strictly conforms to the Section 9 error dictionary:
    {
        "error": {
            "code": "...",
            "message": "...",
            "details": {...}
        }
    }
    """
    assert res is not None, "Response must not be None on error."
    assert isinstance(res, dict), f"Expected dict error shape, got {type(res)}: {res}"
    assert "error" in res, f"Expected 'error' root key in {res}"
    err = res["error"]
    assert isinstance(err, dict), f"Expected dict inside 'error', got {type(err)}"

    assert "code" in err, f"Missing 'code' in error: {err}"
    assert isinstance(err["code"], str) and len(err["code"]) > 0, "Error code must be a non-empty string"

    assert "message" in err, f"Missing 'message' in error: {err}"
    assert isinstance(err["message"], str) and len(err["message"]) > 0, "Error message must be a non-empty string"

    assert "details" in err, f"Missing 'details' in error: {err}"
    assert isinstance(err["details"], dict), "Error details must be a dictionary"

    if expected_code is not None:
        assert err["code"] == expected_code, f"Expected error code '{expected_code}', got '{err['code']}'"


# ==============================================================================
# SECTION A: ENTITY-RESOLUTION TOOLS (Unknown ID -> Section 9 Error Dict)
# ==============================================================================

# ------------------------------------------------------------------------------
# Tool 1: get_transaction
# ------------------------------------------------------------------------------

def test_tool_1_get_transaction_valid(tools):
    """
    Tool 1: get_transaction with known seeded IDs
    Asserts exact Pydantic model conformance, field presence, and types.
    """
    seeded_txns = ["TXN-104829", "TXN-209144", "TXN-301855", "TXN-405112"]
    for txn_id in seeded_txns:
        res = tools["get_transaction"](txn_id)
        assert isinstance(res, TransactionDetailResponse), f"Expected TransactionDetailResponse for {txn_id}"

        # Assert required fields and types
        assert res.transaction_id == txn_id
        assert isinstance(res.customer_id, str) and len(res.customer_id) > 0
        assert isinstance(res.account_id, str) and len(res.account_id) > 0
        assert isinstance(res.amount, (int, float)) and res.amount > 0
        assert res.currency == "USD"
        assert isinstance(res.timestamp, int) and res.timestamp > 0
        assert isinstance(res.risk_score, float) and 0.0 <= res.risk_score <= 1.0
        assert isinstance(res.channel, str)
        assert isinstance(res.card_network, str)
        assert isinstance(res.merchant_name, str)
        assert isinstance(res.device_id, str)
        assert isinstance(res.ip_str, str)

        # Assert Section 7 frozen field names (snake_case, not camelCase)
        dump = res.model_dump()
        assert "transaction_id" in dump and "transactionId" not in dump
        assert "customer_id" in dump and "customerId" not in dump
        assert "account_id" in dump and "accountId" not in dump
        assert "risk_score" in dump and "riskScore" not in dump
        assert "card_network" in dump and "cardNetwork" not in dump
        assert "merchant_name" in dump and "merchantName" not in dump
        assert "device_id" in dump and "deviceId" not in dump
        assert "ip_str" in dump and "ipStr" not in dump


def test_tool_1_get_transaction_unknown_id(tools):
    """
    Tool 1: get_transaction with unknown ID
    Entity-resolution tool: unknown ID MUST return Section 9 error dictionary.
    """
    unknown_id = "TXN-UNKNOWN-99999"
    res = tools["get_transaction"](unknown_id)
    assert_section_9_error(res, expected_code="TRANSACTION_NOT_FOUND")
    assert res["error"]["details"].get("transaction_id") == unknown_id


# ------------------------------------------------------------------------------
# Tool 2: get_customer
# ------------------------------------------------------------------------------

def test_tool_2_get_customer_valid(tools):
    """
    Tool 2: get_customer with known seeded IDs
    Asserts exact Pydantic model conformance, field presence, and types.
    """
    seeded_custs = ["C-45821", "C-77109", "C-10294", "C-99321"]
    for cust_id in seeded_custs:
        res = tools["get_customer"](cust_id)
        assert isinstance(res, CustomerDetailResponse), f"Expected CustomerDetailResponse for {cust_id}"

        # Assert required fields and types
        assert res.customer_id == cust_id
        assert isinstance(res.name, str) and len(res.name) > 0
        assert res.risk_tier in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        assert isinstance(res.created_at, int) and res.created_at > 0
        assert isinstance(res.accounts, list) and len(res.accounts) > 0
        assert isinstance(res.linked_cards, list) and len(res.linked_cards) > 0
        assert "@" in res.email
        assert isinstance(res.risk_score, float) and 0.0 <= res.risk_score <= 1.0

        # Assert Section 7 frozen field names
        dump = res.model_dump()
        assert "customer_id" in dump and "customerId" not in dump
        assert "risk_tier" in dump and "riskTier" not in dump
        assert "created_at" in dump and "createdAt" not in dump
        assert "linked_cards" in dump and "linkedCards" not in dump
        assert "risk_score" in dump and "riskScore" not in dump


def test_tool_2_get_customer_unknown_id(tools):
    """
    Tool 2: get_customer with unknown ID
    Entity-resolution tool: unknown ID MUST return Section 9 error dictionary.
    """
    unknown_id = "C-NONEXISTENT-999"
    res = tools["get_customer"](unknown_id)
    assert_section_9_error(res, expected_code="CUSTOMER_NOT_FOUND")
    assert res["error"]["details"].get("customer_id") == unknown_id


# ------------------------------------------------------------------------------
# Tool 9: write_case_to_graph
# ------------------------------------------------------------------------------

def test_tool_9_write_case_to_graph_valid(tools):
    """
    Tool 9: write_case_to_graph with valid case payload
    Asserts WriteCaseResponse, write counts, status, and graph vertex/edge IDs.
    """
    payload = {
        "case_id": "CASE-9001",
        "transaction_id": "TXN-104829",
        "customer_id": "C-45821",
        "status": "INVESTIGATING",
        "risk_score": 0.87,
        "confidence": 0.78,
        "fraud_patterns": [
            {
                "pattern_id": "FP-01",
                "name": "Shared Device Syndicate Ring",
                "confidence": 0.88
            }
        ],
        "evidence": [
            {
                "evidence_id": "EVID-001",
                "type": "DEVICE_SHARING",
                "confidence": 0.90
            }
        ]
    }
    res = tools["write_case_to_graph"](payload)
    assert isinstance(res, WriteCaseResponse)
    assert res.status == "SUCCESS"
    assert res.case_id == "CASE-9001"
    assert isinstance(res.graph_ids, list) and len(res.graph_ids) >= 3
    assert res.nodes_written >= 1
    assert res.edges_written >= 1
    assert "CASE-9001" in res.message

    # Assert Section 7 frozen field names
    dump = res.model_dump()
    assert "case_id" in dump and "caseId" not in dump
    assert "graph_ids" in dump and "graphIds" not in dump
    assert "nodes_written" in dump and "nodesWritten" not in dump
    assert "edges_written" in dump and "edgesWritten" not in dump


def test_tool_9_write_case_to_graph_missing_id(tools):
    """
    Tool 9: write_case_to_graph with missing case_id
    Entity-resolution tool: missing required case_id MUST return Section 9 error dictionary.
    """
    res = tools["write_case_to_graph"]({})
    assert_section_9_error(res, expected_code="CASE_NOT_FOUND")


# ==============================================================================
# SECTION B: GRAPH-TRAVERSAL TOOLS (Unmatched ID -> Well-Formed Empty Response)
# ==============================================================================

# ------------------------------------------------------------------------------
# Tool 3: get_transaction_history
# ------------------------------------------------------------------------------

def test_tool_3_get_transaction_history_valid(tools):
    """
    Tool 3: get_transaction_history with known seeded customer/account ID
    Asserts exact Pydantic model conformance, summary metrics, and item typing.
    """
    res = tools["get_transaction_history"](customer_id="C-45821")
    assert isinstance(res, TransactionHistoryResponse)

    # Check transactions list
    assert isinstance(res.transactions, list)
    assert len(res.transactions) >= 1
    item = res.transactions[0]
    assert isinstance(item.transaction_id, str)
    assert isinstance(item.amount, (int, float))
    assert isinstance(item.timestamp, int)
    assert isinstance(item.merchant_name, str)
    assert isinstance(item.risk_score, float)
    assert isinstance(item.channel, str)

    # Check summary metrics
    summary = res.summary
    assert summary.total_transactions >= 1
    assert summary.avg_amount > 0
    assert summary.max_amount > 0
    assert summary.velocity_30d >= 0
    assert isinstance(summary.risk_distribution, dict)
    assert "low" in summary.risk_distribution
    assert "medium" in summary.risk_distribution
    assert "high" in summary.risk_distribution

    # Assert Section 7 frozen field names
    dump = res.model_dump()
    summary_dump = dump["summary"]
    assert "total_transactions" in summary_dump and "totalTransactions" not in summary_dump
    assert "avg_amount" in summary_dump and "avgAmount" not in summary_dump
    assert "max_amount" in summary_dump and "maxAmount" not in summary_dump
    assert "velocity_30d" in summary_dump and "velocity30d" not in summary_dump
    assert "risk_distribution" in summary_dump and "riskDistribution" not in summary_dump


def test_tool_3_get_transaction_history_unmatched(tools):
    """
    Tool 3: get_transaction_history with unmatched ID
    Graph-traversal query: legitimately finding no transactions returns a valid,
    empty-but-well-formed response (empty list + zeroed summary metrics), not an error.
    """
    unknown_id = "NONEXISTENT_CUSTOMER_ACCOUNT"
    res = tools["get_transaction_history"](entity_id=unknown_id)
    assert isinstance(res, TransactionHistoryResponse)
    assert len(res.transactions) == 0
    assert res.summary.total_transactions == 0
    assert res.summary.avg_amount == 0.0
    assert res.summary.max_amount == 0.0
    assert res.summary.velocity_30d == 0
    assert res.summary.risk_distribution == {"low": 0, "medium": 0, "high": 0}


# ------------------------------------------------------------------------------
# Tool 4: get_connected_entities
# ------------------------------------------------------------------------------

def test_tool_4_get_connected_entities_valid(tools):
    """
    Tool 4: get_connected_entities with seeded transaction ID
    Asserts graph node/edge topology and typed fields.
    """
    res = tools["get_connected_entities"]("TXN-104829", depth=2)
    assert isinstance(res, ConnectedEntitiesResponse)
    assert isinstance(res.nodes, list) and len(res.nodes) > 0
    assert isinstance(res.edges, list) and len(res.edges) > 0

    # Validate node schema
    node = res.nodes[0]
    assert hasattr(node, "id") and isinstance(node.id, str)
    assert hasattr(node, "label") and isinstance(node.label, str)
    assert hasattr(node, "type") and isinstance(node.type, str)
    assert hasattr(node, "risk_score") and isinstance(node.risk_score, float)

    # Validate edge schema
    edge = res.edges[0]
    assert hasattr(edge, "source") and isinstance(edge.source, str)
    assert hasattr(edge, "target") and isinstance(edge.target, str)
    assert hasattr(edge, "type") and isinstance(edge.type, str)

    # Assert Section 7 frozen field names
    node_dump = node.model_dump()
    assert "risk_score" in node_dump and "riskScore" not in node_dump


def test_tool_4_get_connected_entities_unmatched(tools):
    """
    Tool 4: get_connected_entities with unmatched ID
    Graph-traversal query: an unknown entity returns a well-formed subgraph response
    with 0 connected edges, not an unhandled error.
    """
    res = tools["get_connected_entities"]("UNKNOWN-ENTITY-ID-999")
    assert isinstance(res, ConnectedEntitiesResponse)
    assert isinstance(res.nodes, list) and len(res.nodes) == 1
    assert res.nodes[0].id == "UNKNOWN-ENTITY-ID-999"
    assert res.nodes[0].type == "Unknown"
    assert len(res.edges) == 0


# ------------------------------------------------------------------------------
# Tool 5: find_shared_devices
# ------------------------------------------------------------------------------

def test_tool_5_find_shared_devices_valid(tools):
    """
    Tool 5: find_shared_devices with seeded device/transaction ID
    Asserts SharedDevicesResponse and device attributes.
    """
    res = tools["find_shared_devices"]("D-421")
    assert isinstance(res, SharedDevicesResponse)
    assert isinstance(res.devices, list) and len(res.devices) > 0

    device = res.devices[0]
    assert device.device_id == "D-421"
    assert isinstance(device.linked_accounts, int) and device.linked_accounts == 4
    assert isinstance(device.risk_score, float)
    assert isinstance(device.associated_account_ids, list)

    # Assert Section 7 frozen field names
    dump = device.model_dump()
    assert "device_id" in dump and "deviceId" not in dump
    assert "linked_accounts" in dump and "linkedAccounts" not in dump
    assert "risk_score" in dump and "riskScore" not in dump
    assert "associated_account_ids" in dump and "associatedAccountIds" not in dump


def test_tool_5_find_shared_devices_unmatched(tools):
    """
    Tool 5: find_shared_devices with unmatched ID
    Graph-traversal query: an unknown entity or entity with no device ring returns
    {"devices": []}, a well-formed empty response, not an error.
    """
    res = tools["find_shared_devices"]("D-NONEXISTENT-999")
    assert isinstance(res, SharedDevicesResponse)
    assert isinstance(res.devices, list)
    assert len(res.devices) == 0


# ------------------------------------------------------------------------------
# Tool 6: detect_fraud_patterns
# ------------------------------------------------------------------------------

def test_tool_6_detect_fraud_patterns_valid(tools):
    """
    Tool 6: detect_fraud_patterns with seeded transaction ID
    Asserts DetectFraudPatternsResponse and pattern details.
    """
    res = tools["detect_fraud_patterns"]("TXN-104829")
    assert isinstance(res, DetectFraudPatternsResponse)
    assert isinstance(res.patterns, list) and len(res.patterns) >= 1

    pattern = res.patterns[0]
    assert isinstance(pattern.pattern_id, str) and pattern.pattern_id.startswith("FP-")
    assert isinstance(pattern.name, str) and len(pattern.name) > 0
    assert isinstance(pattern.description, str) and len(pattern.description) > 0
    assert isinstance(pattern.evidence_refs, list) and len(pattern.evidence_refs) > 0
    assert isinstance(pattern.confidence, float) and 0.0 <= pattern.confidence <= 1.0

    # Assert Section 7 frozen field names
    dump = pattern.model_dump()
    assert "pattern_id" in dump and "patternId" not in dump
    assert "evidence_refs" in dump and "evidenceRefs" not in dump


def test_tool_6_detect_fraud_patterns_unmatched(tools):
    """
    Tool 6: detect_fraud_patterns with unmatched ID
    Graph-traversal query: an unmatched entity context returns {"patterns": []},
    representing 0 detected patterns, not an error.
    """
    res = tools["detect_fraud_patterns"]("TXN-UNKNOWN-999")
    assert isinstance(res, DetectFraudPatternsResponse)
    assert isinstance(res.patterns, list)
    assert len(res.patterns) == 0


# ------------------------------------------------------------------------------
# Tool 7: find_similar_cases
# ------------------------------------------------------------------------------

def test_tool_7_find_similar_cases_valid(tools):
    """
    Tool 7: find_similar_cases with seeded transaction context
    Asserts SimilarCasesResponse and item attributes.
    """
    res = tools["find_similar_cases"]("TXN-301855")
    assert isinstance(res, SimilarCasesResponse)
    assert isinstance(res.similar_cases, list) and len(res.similar_cases) > 0

    case = res.similar_cases[0]
    assert isinstance(case.case_id, str) and case.case_id.startswith("CASE-")
    assert isinstance(case.similarity_score, float) and 0.0 <= case.similarity_score <= 1.0
    assert case.status in ["RESOLVED", "CLOSED", "INVESTIGATING"]
    assert isinstance(case.risk_score, float)
    assert isinstance(case.outcome, str)
    assert isinstance(case.matched_patterns, list)

    # Assert Section 7 frozen field names
    dump = case.model_dump()
    assert "case_id" in dump and "caseId" not in dump
    assert "similarity_score" in dump and "similarityScore" not in dump
    assert "risk_score" in dump and "riskScore" not in dump
    assert "matched_patterns" in dump and "matchedPatterns" not in dump
    assert "key_findings" in dump and "keyFindings" not in dump


def test_tool_7_find_similar_cases_unmatched(tools):
    """
    Tool 7: find_similar_cases with general/unmatched case context
    Graph-traversal query: general or unknown case context returns a valid,
    well-formed list of historical cases from case memory, not an error.
    """
    res = tools["find_similar_cases"]("CASE-UNKNOWN-999")
    assert isinstance(res, SimilarCasesResponse)
    assert isinstance(res.similar_cases, list)
    assert len(res.similar_cases) > 0
    assert all(isinstance(c.case_id, str) for c in res.similar_cases)


# ------------------------------------------------------------------------------
# Tool 8: get_policy_context
# ------------------------------------------------------------------------------

def test_tool_8_get_policy_context_valid(tools):
    """
    Tool 8: get_policy_context with valid actions and amounts
    Asserts PolicyContextResponse and policy attributes.
    """
    # Test high-value action requiring approval and SAR
    res_high = tools["get_policy_context"](action="BLOCK_TRANSACTION", amount=8450.00)
    assert isinstance(res_high, PolicyContextResponse)
    assert res_high.policy_id == "POL-FRAUD-2026-V1"
    assert "POL-804" in res_high.policy_basis
    assert res_high.approval_required is True
    assert res_high.sar_required is True
    assert res_high.confidence_threshold == 0.85
    assert "BLOCK_TRANSACTION" in res_high.allowed_actions

    # Test sub-$5000 block
    res_low = tools["get_policy_context"](action="BLOCK_TRANSACTION", amount=1249.50)
    assert isinstance(res_low, PolicyContextResponse)
    assert res_low.approval_required is False
    assert res_low.sar_required is False

    # Assert Section 7 frozen field names
    dump = res_high.model_dump()
    assert "policy_id" in dump and "policyId" not in dump
    assert "policy_basis" in dump and "policyBasis" not in dump
    assert "approval_required" in dump and "approvalRequired" not in dump
    assert "sar_required" in dump and "sarRequired" not in dump
    assert "confidence_threshold" in dump and "confidenceThreshold" not in dump
    assert "allowed_actions" in dump and "allowedActions" not in dump
    assert "escalation_notes" in dump and "escalationNotes" not in dump


def test_tool_8_get_policy_context_unmatched(tools):
    """
    Tool 8: get_policy_context with unknown or default action
    Policy context retrieval defaults to baseline risk mitigation policy tier,
    returning a well-formed PolicyContextResponse, not an error.
    """
    res = tools["get_policy_context"](action="UNKNOWN_OR_UNSPECIFIED")
    assert isinstance(res, PolicyContextResponse)
    assert res.policy_id == "POL-FRAUD-2026-V1"
    assert res.approval_required is False
    assert res.sar_required is False
    assert res.confidence_threshold == 0.75
    assert "MONITOR" in res.allowed_actions


# ==============================================================================
# SECTION C: REGRESSION TEST (Pattern Variation Across Seeded Transactions)
# ==============================================================================

def test_detect_fraud_patterns_variation_across_all_4_seeded_transactions(tools):
    """
    Regression test asserting that detect_fraud_patterns() returns distinct,
    non-identical pattern sets across all 4 seeded benchmark transactions.
    """
    seeded_txns = ["TXN-104829", "TXN-209144", "TXN-301855", "TXN-405112"]
    pattern_results = {}

    for tx_id in seeded_txns:
        res = tools["detect_fraud_patterns"](tx_id)
        assert isinstance(res, DetectFraudPatternsResponse), f"Expected DetectFraudPatternsResponse for {tx_id}"
        pattern_ids = tuple(sorted(p.pattern_id for p in res.patterns))
        pattern_results[tx_id] = pattern_ids

    # Assert that results are not identical
    unique_profiles = set(pattern_results.values())
    assert len(unique_profiles) > 1, f"All 4 transactions returned identical patterns! {pattern_results}"
    assert len(unique_profiles) == 4, f"Expected 4 distinct pattern profiles, got {len(unique_profiles)}: {pattern_results}"

    # Verify specific signature for each seeded transaction
    assert "FP-01" in pattern_results["TXN-104829"] and "FP-02" in pattern_results["TXN-104829"]
    assert len(pattern_results["TXN-209144"]) == 0, "TXN-209144 is clean baseline and must have 0 patterns"
    assert "FP-03" in pattern_results["TXN-301855"] and "FP-04" in pattern_results["TXN-301855"]
    assert "FP-05" in pattern_results["TXN-405112"]
