# ==============================================================================
# FraudGraph AI - GraphRAG Pipeline Orchestrator
# Workstream: Person 2 (Graph)
#
# Combines vector policy retrieval and historical case memory retrieval into
# concise, LLM-friendly context strings for LangGraph agent reasoning.
# Never outputs raw graph dumps; generates structured, decision-ready prose.
# ==============================================================================

from typing import Optional, Dict, Any, List
from graphrag.retrieval.policy_retriever import get_policy_context
from graphrag.retrieval.case_retriever import find_similar_cases
from tigergraph.tools import PolicyContextResponse, SimilarCasesResponse


class GraphRAGPipeline:
    """
    GraphRAG Orchestrator uniting knowledge-grounded policy compliance
    and historical case precedents into agent-ready context.
    """

    def __init__(self):
        pass

    def retrieve_context(
        self,
        case_context: str,
        pattern_id: Optional[str] = None,
        proposed_action: Optional[str] = None,
        amount: Optional[float] = None,
    ) -> str:
        """
        Retrieves grounded policy and case precedent and formats into a
        compact, readable LLM reasoning prompt.
        """
        # 1. Retrieve policy context via GraphRAG vector engine
        policy_res: PolicyContextResponse = get_policy_context(
            case_context=case_context,
            pattern_id=pattern_id,
            proposed_action=proposed_action,
            amount=amount,
        )

        # 2. Retrieve similar historical cases via hybrid GraphRAG engine
        cases_res: SimilarCasesResponse = find_similar_cases(case_context=case_context)

        # 3. Format into structured, concise prose for LLM ingestion
        lines = [
            "=== GRAPHRAG INVESTIGATION CONTEXT ===",
            "",
            "--- [GOVERNING FRAUD POLICY CONSTRAINTS] ---",
            f"Policy Clause: {policy_res.policy_id}",
            f"Basis: {policy_res.policy_basis}",
            f"Human Approval Required: {'YES (L2 Supervisor approval mandatory)' if policy_res.approval_required else 'NO (Automated action permitted)'}",
            f"SAR Filing Required: {'YES (FinCEN BSA filing required)' if policy_res.sar_required else 'NO'}",
            f"Confidence Threshold Required: {policy_res.confidence_threshold:.2f}",
            f"Allowed Action Types: {', '.join(policy_res.allowed_actions)}",
        ]
        if policy_res.escalation_notes:
            lines.append(f"Escalation Notes: {policy_res.escalation_notes}")

        lines.extend([
            "",
            "--- [HISTORICAL CASE PRECEDENT & MEMORY] ---",
        ])

        if not cases_res.similar_cases:
            lines.append("No prior precedent found matching current graph context.")
        else:
            for idx, c in enumerate(cases_res.similar_cases, 1):
                patterns_str = ", ".join(c.matched_patterns) if c.matched_patterns else "None"
                lines.append(
                    f"{idx}. {c.case_id} (Similarity: {int(c.similarity_score * 100)}% | Outcome: {c.outcome} | Historical Risk: {c.risk_score:.2f})"
                )
                lines.append(f"   Matched Typologies: {patterns_str}")
                if c.key_findings:
                    lines.append(f"   Precedent Resolution: {c.key_findings}")

        lines.extend([
            "",
            "--- [AGENT DECISIONING DIRECTIVE] ---",
            f"Evaluate evidence sufficiency. If confidence < {policy_res.confidence_threshold:.2f}, request additional evidence before final action.",
            "If approval is required, route next-best action to human supervisor queue.",
            "========================================",
        ])

        return "\n".join(lines)

    def get_structured_context(
        self,
        case_context: str,
        pattern_id: Optional[str] = None,
        proposed_action: Optional[str] = None,
        amount: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Returns both structured Pydantic models and the formatted LLM string."""
        policy_res = get_policy_context(
            case_context=case_context,
            pattern_id=pattern_id,
            proposed_action=proposed_action,
            amount=amount,
        )
        cases_res = find_similar_cases(case_context=case_context)
        formatted_prompt = self.retrieve_context(
            case_context=case_context,
            pattern_id=pattern_id,
            proposed_action=proposed_action,
            amount=amount,
        )

        return {
            "prompt_context": formatted_prompt,
            "policy": policy_res,
            "similar_cases": cases_res,
        }


# Global pipeline instance
pipeline = GraphRAGPipeline()


def retrieve_investigation_context(
    case_context: str,
    pattern_id: Optional[str] = None,
    proposed_action: Optional[str] = None,
    amount: Optional[float] = None,
) -> str:
    """Convenience helper function to retrieve grounded LLM context in 1 line."""
    return pipeline.retrieve_context(
        case_context=case_context,
        pattern_id=pattern_id,
        proposed_action=proposed_action,
        amount=amount,
    )


__all__ = ["GraphRAGPipeline", "pipeline", "retrieve_investigation_context"]
