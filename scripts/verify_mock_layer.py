# ==============================================================================
# Throwaway Verification Script: TigerGraph Mock Layer vs Integration Spec
# scripts/verify_mock_layer.py
# ==============================================================================

import sys
import json
from pprint import pprint

# Ensure repository root is on sys.path
sys.path.insert(0, ".")

from tigergraph.tools import (
    get_graph_tools,
    get_transaction,
    get_customer,
    get_transaction_history,
    get_connected_entities,
    find_shared_devices,
    detect_fraud_patterns,
    find_similar_cases,
    get_policy_context,
    write_case_to_graph,
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
from tigergraph.mock_provider import GraphError


def run_verification():
    print("=" * 80)
    print("STARTING VERIFICATION: tigergraph/mock_provider.py & tigergraph/tools.py")
    print("=" * 80)

    discrepancies = []

    # --------------------------------------------------------------------------
    # 1. FIELD COVERAGE CHECK
    # --------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("1. FIELD COVERAGE CHECK")
    print("=" * 80)

    # Required fields per Section 5 of the spec (Case object)
    # Spec defines Case as: case_id, transaction_id, customer_id, status, risk_score,
    # confidence, fraud_patterns, evidence, recommendation, approval_required (or approval), timeline
    case_required_fields = [
        "case_id",
        "transaction_id",
        "customer_id",
        "status",
        "risk_score",
        "confidence",
        "fraud_patterns",
        "evidence",
        "recommendation",
        "approval",  # check both 'approval' and 'approval_required'
    ]

    seeded_case_payload = {
        "case_id": "CASE-1024",
        "transaction_id": "TXN-104829",
        "customer_id": "C-45821",
        "status": "INVESTIGATING",
        "risk_score": 0.87,
        "confidence": 0.78,
        "fraud_patterns": [
            {
                "pattern_id": "FP-01",
                "name": "Shared Device Syndicate Ring",
                "description": "Hardware fingerprint D-421 linked across 4 distinct accounts.",
                "evidence_refs": ["EVID-GRAPH-001"],
                "confidence": 0.88
            }
        ],
        "evidence": [
            {
                "evidence_id": "EVID-GRAPH-001",
                "type": "DEVICE_SHARING",
                "source": "tigergraph",
                "summary": "Shared device D-421 linked to 4 accounts",
                "confidence": 0.90,
                "timestamp": 1718002000,
                "related_entities": ["D-421", "ACC-90124"]
            }
        ],
        "recommendation": {
            "action": "BLOCK_TRANSACTION",
            "reason": "High risk device ring identified",
            "confidence": 0.85,
            "approval_required": False,
            "policy_basis": "POL-402"
        },
        "approval_required": False,
        "timeline": []
    }

    print("\n---> Calling write_case_to_graph() with seeded payload:")
    write_res = write_case_to_graph(seeded_case_payload)
    write_res_dict = write_res.model_dump()
    print("Returned write_case_to_graph response:")
    pprint(write_res_dict)

    # Check which of the Case-shaped fields exist in the return object of write_case_to_graph
    write_missing_fields = []
    for f in case_required_fields:
        if f == "approval":
            if "approval" not in write_res_dict and "approval_required" not in write_res_dict:
                write_missing_fields.append("approval (or approval_required)")
        elif f not in write_res_dict:
            write_missing_fields.append(f)

    print(f"\nMissing Case fields in write_case_to_graph() return: {write_missing_fields}")
    if write_missing_fields:
        discrepancies.append({
            "section": "Section 5 vs Section 7",
            "item": "write_case_to_graph return shape",
            "detail": f"Section 7 defines output as 'write status + graph ids' (WriteCaseResponse: status, case_id, graph_ids, nodes_written, edges_written, message), but Section 5 defines Case with 10 fields. Missing in response: {write_missing_fields}"
        })

    print("\n---> Calling get_policy_context() with seeded data:")
    policy_res = get_policy_context(action="BLOCK_TRANSACTION", amount=1249.50)
    policy_res_dict = policy_res.model_dump()
    print("Returned get_policy_context response:")
    pprint(policy_res_dict)

    # Check which of the Case-shaped fields exist in the return object of get_policy_context
    policy_missing_fields = []
    for f in case_required_fields:
        if f == "approval":
            if "approval" not in policy_res_dict and "approval_required" not in policy_res_dict:
                policy_missing_fields.append("approval (or approval_required)")
        elif f not in policy_res_dict:
            policy_missing_fields.append(f)

    print(f"\nMissing Case fields in get_policy_context() return: {policy_missing_fields}")
    if policy_missing_fields:
        discrepancies.append({
            "section": "Section 5 vs Section 7",
            "item": "get_policy_context return shape",
            "detail": f"get_policy_context returns policy context (policy_basis, approval_required, sar_required, etc.) per Section 7, NOT a full Case-shaped object. Missing Case fields: {policy_missing_fields}"
        })

    # --------------------------------------------------------------------------
    # 2. PATTERN VARIATION CHECK
    # --------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("2. PATTERN VARIATION CHECK")
    print("=" * 80)

    test_txns = ["TXN-104829", "TXN-209144", "TXN-301855", "TXN-405112"]
    pattern_results = {}

    for tx_id in test_txns:
        pat_res = detect_fraud_patterns(transaction_id=tx_id)
        pat_dict = pat_res.model_dump()
        pattern_results[tx_id] = [p["pattern_id"] + ": " + p["name"] for p in pat_dict["patterns"]]
        print(f"\nTransaction {tx_id} -> Fraud Patterns ({len(pat_dict['patterns'])}):")
        for p in pat_dict["patterns"]:
            print(f"  - [{p['pattern_id']}] {p['name']} (confidence={p['confidence']})")
            print(f"    Description: {p['description']}")
            print(f"    Evidence Refs: {p['evidence_refs']}")

    # Check if all 4 are identical
    unique_sets = set(tuple(p) for p in pattern_results.values())
    if len(unique_sets) == 1:
        print("\n[FLAG / FAIL]: All 4 transactions returned identical fraud patterns!")
        discrepancies.append({
            "section": "Seeded Data Variation",
            "item": "detect_fraud_patterns variation",
            "detail": "All 4 transactions returned the identical pattern set."
        })
    else:
        print(f"\n[PASS]: Pattern variation confirmed! {len(unique_sets)} distinct pattern profiles across 4 transactions.")

    # --------------------------------------------------------------------------
    # 3. FULL TOOL SWEEP
    # --------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("3. FULL TOOL SWEEP (9 Tools Across 4 Test Cases)")
    print("=" * 80)

    tools = get_graph_tools()
    test_suite = [
        {"txn_id": "TXN-104829", "cust_id": "C-45821", "case_id": "CASE-1024", "dev_id": "D-421"},
        {"txn_id": "TXN-209144", "cust_id": "C-77109", "case_id": "CASE-0915", "dev_id": "D-119"},
        {"txn_id": "TXN-301855", "cust_id": "C-10294", "case_id": "CASE-1025", "dev_id": "D-884"},
        {"txn_id": "TXN-405112", "cust_id": "C-99321", "case_id": "CASE-1026", "dev_id": "D-302"},
    ]

    sweep_failures = []

    for idx, test_case in enumerate(test_suite, 1):
        print(f"\n--- [Test Suite {idx}/4] TXN: {test_case['txn_id']} | CUST: {test_case['cust_id']} ---")

        # Tool 1: get_transaction
        try:
            r1 = tools["get_transaction"](test_case["txn_id"])
            assert isinstance(r1, TransactionDetailResponse)
            assert r1.transaction_id == test_case["txn_id"]
            print(f"  [Tool 1: get_transaction] OK -> amount={r1.amount}, risk_score={r1.risk_score}")
        except Exception as e:
            sweep_failures.append(f"get_transaction failed for {test_case['txn_id']}: {e}")

        # Tool 2: get_customer
        try:
            r2 = tools["get_customer"](test_case["cust_id"])
            assert isinstance(r2, CustomerDetailResponse)
            assert r2.customer_id == test_case["cust_id"]
            print(f"  [Tool 2: get_customer] OK -> name={r2.name}, risk_tier={r2.risk_tier}")
        except Exception as e:
            sweep_failures.append(f"get_customer failed for {test_case['cust_id']}: {e}")

        # Tool 3: get_transaction_history
        try:
            r3 = tools["get_transaction_history"](test_case["cust_id"])
            assert isinstance(r3, TransactionHistoryResponse)
            print(f"  [Tool 3: get_transaction_history] OK -> total={r3.summary.total_transactions}, avg={r3.summary.avg_amount}")
        except Exception as e:
            sweep_failures.append(f"get_transaction_history failed for {test_case['cust_id']}: {e}")

        # Tool 4: get_connected_entities
        try:
            r4 = tools["get_connected_entities"](test_case["txn_id"], depth=2)
            assert isinstance(r4, ConnectedEntitiesResponse)
            assert len(r4.nodes) > 0 and len(r4.edges) > 0
            print(f"  [Tool 4: get_connected_entities] OK -> {len(r4.nodes)} nodes, {len(r4.edges)} edges")
        except Exception as e:
            sweep_failures.append(f"get_connected_entities failed for {test_case['txn_id']}: {e}")

        # Tool 5: find_shared_devices
        try:
            r5 = tools["find_shared_devices"](test_case["dev_id"])
            assert isinstance(r5, SharedDevicesResponse)
            print(f"  [Tool 5: find_shared_devices] OK -> {len(r5.devices)} devices found (linked_accounts={r5.devices[0].linked_accounts if r5.devices else 0})")
        except Exception as e:
            sweep_failures.append(f"find_shared_devices failed for {test_case['dev_id']}: {e}")

        # Tool 6: detect_fraud_patterns
        try:
            r6 = tools["detect_fraud_patterns"](test_case["txn_id"])
            assert isinstance(r6, DetectFraudPatternsResponse)
            print(f"  [Tool 6: detect_fraud_patterns] OK -> {len(r6.patterns)} patterns detected")
        except Exception as e:
            sweep_failures.append(f"detect_fraud_patterns failed for {test_case['txn_id']}: {e}")

        # Tool 7: find_similar_cases
        try:
            r7 = tools["find_similar_cases"](test_case["txn_id"])
            assert isinstance(r7, SimilarCasesResponse)
            assert len(r7.similar_cases) > 0
            print(f"  [Tool 7: find_similar_cases] OK -> {len(r7.similar_cases)} similar cases found (top={r7.similar_cases[0].case_id})")
        except Exception as e:
            sweep_failures.append(f"find_similar_cases failed for {test_case['txn_id']}: {e}")

        # Tool 8: get_policy_context
        try:
            r8 = tools["get_policy_context"]("BLOCK_TRANSACTION", amount=5500.0)
            assert isinstance(r8, PolicyContextResponse)
            print(f"  [Tool 8: get_policy_context] OK -> approval_required={r8.approval_required}, sar={r8.sar_required}")
        except Exception as e:
            sweep_failures.append(f"get_policy_context failed: {e}")

        # Tool 9: write_case_to_graph
        try:
            r9 = tools["write_case_to_graph"]({
                "case_id": test_case["case_id"],
                "transaction_id": test_case["txn_id"],
                "customer_id": test_case["cust_id"],
                "status": "INVESTIGATING",
                "risk_score": 0.85,
                "confidence": 0.80,
                "evidence": [],
                "fraud_patterns": []
            })
            assert isinstance(r9, WriteCaseResponse)
            assert r9.status == "SUCCESS"
            print(f"  [Tool 9: write_case_to_graph] OK -> status={r9.status}, ids={r9.graph_ids}")
        except Exception as e:
            sweep_failures.append(f"write_case_to_graph failed for {test_case['case_id']}: {e}")

    # Unknown ID error behavior check
    print("\n---> Unknown ID Error Handling Check:")
    unknown_id = "TXN-DOES-NOT-EXIST"
    try:
        res = tools["get_transaction"](unknown_id)
        print(f"Direct return received for unknown ID: {res}")
        if isinstance(res, dict) and "error" in res:
            err = res["error"]
            if "code" in err and "message" in err and "details" in err:
                print(f"[PASS]: Returned Section 9 error dict directly (code='{err['code']}', message='{err['message']}').")
            else:
                print(f"[FAIL]: Returned dict missing standard error keys: {res}")
                discrepancies.append({
                    "section": "Section 9",
                    "item": "Error shape conformance",
                    "detail": f"Error dictionary missing required keys. Received: {res}"
                })
        else:
            print(f"[FAIL]: Expected Section 9 error dictionary, but got: {res}")
            discrepancies.append({
                "section": "Section 9",
                "item": "Unknown transaction return format",
                "detail": f"Expected dict with 'error' key, but got: {type(res)}: {res}"
            })
    except Exception as unexpected:
        print(f"[FAIL]: Unexpected exception raised: {type(unexpected)}: {unexpected}")
        discrepancies.append({
            "section": "Section 9",
            "item": "Unhandled exception on unknown ID",
            "detail": f"Crash with unexpected exception: {unexpected}"
        })

    # Summary
    print("\n" + "=" * 80)
    print("VERIFICATION SUMMARY & DISCREPANCIES")
    print("=" * 80)
    print(f"Total Sweep Failures: {len(sweep_failures)}")
    if sweep_failures:
        for f in sweep_failures:
            print(f"  - {f}")

    print(f"\nTotal Discrepancies / Observations: {len(discrepancies)}")
    for d in discrepancies:
        print(f"\n[{d['section']}] {d['item']}:")
        print(f"  {d['detail']}")

    return len(sweep_failures) == 0, discrepancies


if __name__ == "__main__":
    success, disc = run_verification()
    sys.exit(0 if success else 1)
