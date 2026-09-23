# scripts/verify_prompt24.py
"""
Prompt 24 Verification Script:
- Part A: Mock/Live Parity verification
- Part B: GraphRAG End-to-End Sanity check
"""
import sys
import time
from pprint import pprint

from tigergraph.mock_provider import mock_provider
from tigergraph.client import live_client
from tigergraph.tools import (
    write_case_to_graph,
    find_similar_cases,
    get_connected_entities,
    WriteCaseResponse,
    SimilarCasesResponse,
    ConnectedEntitiesResponse
)
from graphrag.retrieval.case_retriever import find_similar_cases as rag_find_similar_cases
from graphrag.retrieval.policy_retriever import get_policy_context as rag_get_policy_context

def run_part_a():
    print("=" * 80)
    print("PART A: Mock / Live Parity Verification")
    print("=" * 80)

    test_case_payload = {
        "case_id": "CASE-PARITY-01",
        "transaction_id": "TXN-104829",
        "customer_id": "C-45821",
        "status": "INVESTIGATING",
        "risk_score": 0.88,
        "confidence": 0.92,
        "fraud_patterns": [
            {
                "pattern_id": "FP-01",
                "name": "Shared Device Syndicate Ring",
                "confidence": 0.88
            }
        ],
        "evidence": [
            {
                "evidence_id": "EVID-PARITY-01",
                "evidence_type": "SHARED_DEVICE",
                "type": "SHARED_DEVICE",
                "source": "tigergraph",
                "summary": "Hardware hash D-421 shared across accounts",
                "confidence": 0.94,
                "timestamp": int(time.time())
            }
        ],
        "actions": [
            {
                "action_id": "ACT-PARITY-01",
                "action_type": "BLOCK_TRANSACTION",
                "type": "BLOCK_TRANSACTION",
                "status": "EXECUTED",
                "approval": False
            }
        ]
    }

    # 1. Test Mock Provider write_case_to_graph
    print("\n1. Testing Mock write_case_to_graph response shape:")
    mock_res = mock_provider.write_case_to_graph(test_case_payload)
    pprint(mock_res)

    # 2. Test Live Client write_case_to_graph against live FraudGraph
    print("\n2. Testing Live write_case_to_graph response shape against TigerGraph Cloud:")
    live_res = live_client.write_case_to_graph(test_case_payload)
    pprint(live_res)

    # 3. Compare Keys & Field Parity
    mock_keys = set(mock_res.keys())
    live_keys = set(live_res.keys())
    print(f"\nMock response keys: {sorted(mock_keys)}")
    print(f"Live response keys: {sorted(live_keys)}")
    assert mock_keys == live_keys, f"Keys mismatch! Mock: {mock_keys}, Live: {live_keys}"

    # 4. Check for 'Case' vs 'FraudCase'
    print("\n3. Checking Case naming and graph_ids:")
    print(f"Mock graph_ids[0]: {mock_res['graph_ids'][0]}")
    print(f"Live graph_ids[0]: {live_res['graph_ids'][0]}")
    assert mock_res["graph_ids"][0].startswith("vertex_fraudcase_"), "Mock graph_ids must use vertex_fraudcase_"
    assert live_res["graph_ids"][0].startswith("vertex_fraudcase_"), "Live graph_ids must use vertex_fraudcase_"
    assert "Case" not in mock_keys, "Payload keys must not contain bare 'Case'"
    assert "Case" not in live_keys, "Payload keys must not contain bare 'Case'"

    # 5. Check connected entities FraudCase node type
    print("\n4. Checking get_connected_entities for FraudCase node type:")
    mock_conn = mock_provider.get_connected_entities("CASE-PARITY-01")
    case_nodes = [n for n in mock_conn["nodes"] if n["id"] == "CASE-PARITY-01"]
    assert len(case_nodes) == 1, "Expected CASE-PARITY-01 node in connected entities"
    assert case_nodes[0]["type"] == "FraudCase", f"Expected type 'FraudCase', got {case_nodes[0]['type']}"
    print(f"Node found: {case_nodes[0]}")

    # Clean up live test vertices
    print("\n5. Cleaning up live test vertices...")
    conn = live_client.get_connection()
    conn.delVerticesById("FraudCase", "CASE-PARITY-01")
    conn.delVerticesById("Evidence", "EVID-PARITY-01")
    conn.delVerticesById("ActionRecord", "ACT-PARITY-01")
    print("Cleanup completed successfully.")

    print("\n--> PART A CHECK: PASSED with 100% Mock/Live Shape Parity!")


def run_part_b():
    print("\n" + "=" * 80)
    print("PART B: GraphRAG End-to-End Sanity Check")
    print("=" * 80)

    # 1. Case Retriever Sanity Check
    print("\n1. Running case_retriever.py on realistic query...")
    case_query = "Multiple accounts accessing from single mobile device with rapid sequential checkout"
    print(f"Query: \"{case_query}\"")
    similar_cases_res = rag_find_similar_cases(case_query, top_k=3)
    print(f"Top results returned: {len(similar_cases_res.similar_cases)}")
    for i, c in enumerate(similar_cases_res.similar_cases, 1):
        print(f"  Result {i}:")
        print(f"    Case ID:          {c.case_id}")
        print(f"    Similarity Score: {c.similarity_score}")
        print(f"    Status:           {c.status}")
        print(f"    Outcome:          {c.outcome}")
        print(f"    Matched Patterns: {c.matched_patterns}")
        print(f"    Key Findings:     {c.key_findings}")

    top_case = similar_cases_res.similar_cases[0]
    assert top_case.case_id == "CASE-0842", f"Expected CASE-0842 as top match, got {top_case.case_id}"
    assert "FP-01" in top_case.matched_patterns, "Expected FP-01 (Shared Device Syndicate Ring) in matched patterns"
    assert top_case.similarity_score > 0.30, f"Expected strong similarity score, got {top_case.similarity_score}"

    # 2. Policy Retriever Sanity Check
    print("\n2. Running policy_retriever.py on realistic query...")
    policy_query = "what's the approval threshold for high-risk wire transfers"
    print(f"Query: \"{policy_query}\"")
    policy_res = rag_get_policy_context(case_context=policy_query, amount=8500.0, proposed_action="BLOCK_TRANSACTION")
    print("Matched Policy Result:")
    print(f"  Policy ID:            {policy_res.policy_id}")
    print(f"  Policy Basis:         {policy_res.policy_basis}")
    print(f"  Approval Required:    {policy_res.approval_required}")
    print(f"  SAR Required:         {policy_res.sar_required}")
    print(f"  Confidence Threshold: {policy_res.confidence_threshold}")
    print(f"  Allowed Actions:      {policy_res.allowed_actions}")
    print(f"  Escalation Notes:     {policy_res.escalation_notes}")

    assert policy_res.policy_id == "POL-804", f"Expected POL-804, got {policy_res.policy_id}"
    assert policy_res.approval_required is True, "High-risk wire over $5,000 must require approval"
    assert policy_res.sar_required is True, "High-risk wire over $5,000 must require SAR filing"
    assert "POL-804" in policy_res.policy_basis, "Policy basis must reference POL-804"

    print("\n--> PART B CHECK: PASSED with Sensible, On-Topic Results!")

if __name__ == "__main__":
    run_part_a()
    run_part_b()
