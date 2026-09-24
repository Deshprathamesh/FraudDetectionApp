# ==============================================================================
# FraudGraph AI - AgentState Definition
# Workstream: Person 1 (Brain) - Stage 1 Foundation
# ==============================================================================

import time
import uuid
from typing import TypedDict, Optional, List, Dict, Any


class AgentState(TypedDict, total=False):
    """
    Comprehensive, typed state schema passed between nodes in the investigation workflow.
    Mirrors LangGraph StateGraph dictionary semantics.
    """
    case_id: str
    transaction_id: str
    customer_id: Optional[str]
    trigger: Dict[str, Any]

    # Enrichment & Graph Data
    transaction_data: Optional[Dict[str, Any]]
    customer_data: Optional[Dict[str, Any]]
    transaction_history: List[Dict[str, Any]]
    graph_evidence: Dict[str, Any]
    graphrag_context: Dict[str, Any]
    fraud_patterns: List[Dict[str, Any]]

    # Reasoning & Policy Outputs
    risk_assessment: Optional[Dict[str, Any]]
    uncertainty_assessment: Optional[Dict[str, Any]]
    next_best_action: Optional[Dict[str, Any]]
    initial_next_best_actions: List[Dict[str, Any]]
    final_next_best_actions: List[Dict[str, Any]]
    what_changed: Optional[str]
    policy_evaluation: Optional[Dict[str, Any]]
    policy_assessment: Optional[Dict[str, Any]]
    approval_level: Optional[str]
    hitl_status: Optional[str]

    # Evidence Gathering & Interactive Loop
    collected_evidence: List[Dict[str, Any]]
    evidence_requests: List[Dict[str, Any]]
    evidence_responses: List[Dict[str, Any]]

    # Human-in-the-Loop & Execution
    approval_request: Optional[Dict[str, Any]]
    approval_status: str # "NOT_REQUIRED", "PENDING", "APPROVED", "REJECTED", "BLOCKED"
    execution_result: Optional[Dict[str, Any]]
    sar: Optional[Dict[str, Any]]

    # Verdict & Summary (Organizer Answer Schema)
    verdict: Optional[str] # "fraud", "non_fraud", "cleared"
    fraud_probability: Optional[float]
    stop_reason: Optional[str]

    # Audit, Timeline & Resilience
    explanation: Optional[str]
    timeline: List[Dict[str, Any]]
    errors: List[Dict[str, Any]]
    warnings: List[str]
    current_workflow_state: str
    iteration_count: int
    max_iterations: int
    untrusted_inputs: List[str]


def create_initial_agent_state(
    transaction_id: str,
    case_id: Optional[str] = None,
    max_iterations: int = 25,
) -> AgentState:
    """Factory creating a well-formed initial AgentState for a transaction investigation."""
    cid = case_id or f"CASE-{uuid.uuid4().hex[:8].upper()}"
    now = int(time.time())

    return AgentState(
        case_id=cid,
        transaction_id=transaction_id,
        customer_id=None,
        trigger={"type": "TRANSACTION_FLAGGED", "timestamp": now, "transaction_id": transaction_id},
        transaction_data=None,
        customer_data=None,
        transaction_history=[],
        graph_evidence={},
        graphrag_context={},
        fraud_patterns=[],
        risk_assessment=None,
        uncertainty_assessment=None,
        next_best_action=None,
        initial_next_best_actions=[],
        final_next_best_actions=[],
        what_changed=None,
        policy_evaluation=None,
        policy_assessment=None,
        approval_level=None,
        hitl_status=None,
        collected_evidence=[],
        evidence_requests=[],
        evidence_responses=[],
        approval_request=None,
        approval_status="NOT_REQUIRED",
        execution_result=None,
        sar=None,
        verdict=None,
        fraud_probability=None,
        stop_reason=None,
        explanation=None,
        timeline=[{
            "event_id": f"EVT-{uuid.uuid4().hex[:8].upper()}",
            "timestamp": now,
            "stage": "TRIGGERED",
            "title": f"Investigation triggered for transaction {transaction_id}",
            "description": f"Initialized investigation case {cid}.",
            "actor": "SYSTEM",
            "metadata": {},
        }],
        errors=[],
        warnings=[],
        current_workflow_state="TRIGGERED",
        iteration_count=0,
        max_iterations=max_iterations,
        untrusted_inputs=[],
    )


def add_timeline_event(
    state: AgentState,
    stage: str,
    title: str,
    description: str = "",
    actor: str = "AGENT",
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Appends an event to the state timeline."""
    event = {
        "event_id": f"EVT-{uuid.uuid4().hex[:8].upper()}",
        "timestamp": int(time.time()),
        "stage": stage,
        "title": title,
        "description": description,
        "actor": actor,
        "metadata": metadata or {},
    }
    if "timeline" not in state or state["timeline"] is None:
        state["timeline"] = []
    state["timeline"].append(event)
