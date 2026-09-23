# ==============================================================================
# Throwaway Verification Script: GraphRAG Pipeline
# scripts/verify_graphrag.py
# ==============================================================================

import sys
sys.path.insert(0, ".")

from graphrag.pipeline import pipeline, retrieve_investigation_context
from graphrag.retrieval.policy_retriever import get_policy_context
from graphrag.retrieval.case_retriever import find_similar_cases
from tigergraph.tools import PolicyContextResponse, SimilarCasesResponse


def verify_graphrag():
    print("=" * 80)
    print("VERIFYING GRAPHRAG PIPELINE (Component 3: Policy & Similar-Case Retrieval)")
    print("=" * 80)

    # Test Scenarios based on the 4 seeded transaction personas
    scenarios = [
        {
            "name": "Scenario 1: High-Risk Syndicate Device Ring (TXN-104829)",
            "context": "Customer Alex Mercer (C-45821) on device D-421. Shared device ring with 4 linked accounts. Rapid credential alternation. Electronic goods purchase $1,249.50.",
            "pattern_id": "FP-01",
            "proposed_action": "BLOCK_TRANSACTION",
            "amount": 1249.50
        },
        {
            "name": "Scenario 2: Critical High-Value Mule & Tor Geo-Velocity (TXN-301855)",
            "context": "Customer Dmitri Volkov (C-10294) via Tor exit node (185.220.101.5). Wire transfer $8,450 to offshore virtual asset exchange. Newly funded mule account exhibiting rapid fan-out.",
            "pattern_id": "FP-03",
            "proposed_action": "FREEZE_ACCOUNT",
            "amount": 8450.00
        },
        {
            "name": "Scenario 3: Elevated Uncertainty / Step-Up Auth (TXN-405112)",
            "context": "Customer Jordan Lee (C-99321) on mobile app. Unfamiliar merchant with card testing indicators. Moderate risk 0.65 with high uncertainty.",
            "pattern_id": "FP-05",
            "proposed_action": "REQUEST_STEP_UP_AUTH",
            "amount": 310.00
        },
        {
            "name": "Scenario 4: Low-Risk Benign Everyday Purchase (TXN-209144)",
            "context": "Customer Sarah Jenkins (C-77109) routine grocery store debit $48.00 from verified home device. Risk score 0.12.",
            "pattern_id": None,
            "proposed_action": "ALLOW_TRANSACTION",
            "amount": 48.00
        }
    ]

    retrieved_policies = []
    retrieved_top_cases = []

    for idx, sc in enumerate(scenarios, 1):
        print(f"\n{'#' * 80}")
        print(f"TEST RUN {idx}: {sc['name']}")
        print(f"{'#' * 80}")

        # Check raw retrieval contract responses
        pol_res = get_policy_context(
            case_context=sc["context"],
            pattern_id=sc["pattern_id"],
            proposed_action=sc["proposed_action"],
            amount=sc["amount"]
        )
        assert isinstance(pol_res, PolicyContextResponse), "Must return PolicyContextResponse"
        assert pol_res.policy_id in pol_res.policy_basis, f"Mismatch! Clause ID {pol_res.policy_id} not in basis: {pol_res.policy_basis}"

        case_res = find_similar_cases(case_context=sc["context"])
        assert isinstance(case_res, SimilarCasesResponse), "Must return SimilarCasesResponse"

        retrieved_policies.append(pol_res.policy_id)
        top_case = case_res.similar_cases[0].case_id if case_res.similar_cases else "NONE"
        retrieved_top_cases.append(top_case)

        print(f"\n[Raw Policy Retrieval]: Clause={pol_res.policy_id} | ApprovalRequired={pol_res.approval_required} | SAR={pol_res.sar_required}")
        print(f"[Raw Case Precedent]: Top Match={top_case} (Similarity: {case_res.similar_cases[0].similarity_score if case_res.similar_cases else 0})")

        # Check full pipeline prompt context
        llm_context = pipeline.retrieve_context(
            case_context=sc["context"],
            pattern_id=sc["pattern_id"],
            proposed_action=sc["proposed_action"],
            amount=sc["amount"]
        )

        print(f"\n--- [Formatted LLM Context String for {sc['name']}] ---")
        print(llm_context)

    # Confirm variation
    print("\n" + "=" * 80)
    print("DIVERSITY & VARIATION ANALYSIS")
    print("=" * 80)
    print(f"Policy Clauses Retrieved across 4 scenarios: {retrieved_policies}")
    print(f"Top Similar Cases Retrieved across 4 scenarios: {retrieved_top_cases}")

    unique_policies = set(retrieved_policies)
    unique_cases = set(retrieved_top_cases)

    print(f"Unique Policy Clauses: {len(unique_policies)} -> {unique_policies}")
    print(f"Unique Top Precedents: {len(unique_cases)} -> {unique_cases}")

    assert len(unique_policies) > 1, "Policy retrieval must vary across different scenarios!"
    assert len(unique_cases) > 1, "Case retrieval must vary across different scenarios!"

    print("\n[SUCCESS]: GraphRAG retrieval demonstrates high sensitivity and variation to context.")
    return True


if __name__ == "__main__":
    success = verify_graphrag()
    sys.exit(0 if success else 1)
