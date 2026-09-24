# ==============================================================================
# FraudGraph AI - Investigation Workflow Specification
# Workstream: Person 1 (Brain) - Stage 1 Foundation
# ==============================================================================

import time
import logging
from typing import Dict, Any, Optional, List

from agent.workflows.state import AgentState, add_timeline_event
from agent.workflows.engine import WorkflowEngine
from agent.tools.graph_adapter import graph_adapter
from backend.services.mock_actions import mock_action_service
from backend.services.case_memory import case_memory_service
from backend.models.domain import (
    InvestigationCase,
    CaseStatus,
    InvestigationResult,
    InvestigationStatus,
    EvidenceItem,
    RiskAssessment,
    NextBestActionItem,
    NBAWhatChanged,
    NextBestActionAssessment,
    PolicyAssessment,
    ApprovalLevel,
    HITLStatus,
    ActionType,
    ApprovalRequest,
    ApprovalStatus,
)
from backend.models.audit import audit_logger, AuditEventType
from backend.policy import policy_evaluator
from backend.execution import action_executor, ExecutionResult, ExecutionStatus
from agent.tools.case_memory_adapter import case_memory_adapter
from agent.risk import risk_uncertainty_service
from agent.nba import nba_service

logger = logging.getLogger("fraudgraph.workflow")


# ------------------------------------------------------------------------------
# Workflow Node Implementations (Stage 1 Foundation)
# ------------------------------------------------------------------------------

def triggered_node(state: AgentState) -> AgentState:
    """Entry node: validates input transaction ID and initializes timeline."""
    txn_id = state.get("transaction_id")
    if not txn_id:
        raise ValueError("transaction_id is required to begin an investigation.")
    add_timeline_event(state, stage="TRIGGERED", title="Investigation Initialized", description=f"Target transaction: {txn_id}")
    return state


def enrichment_node(state: AgentState) -> AgentState:
    """Enrichment node: queries transaction and customer profile from graph adapter."""
    txn_id = state["transaction_id"]
    try:
        txn_data = graph_adapter.get_transaction(txn_id)
        state["transaction_data"] = txn_data
        cust_id = txn_data.get("customer_id")
        state["customer_id"] = cust_id

        if cust_id:
            cust_data = graph_adapter.get_customer(cust_id)
            state["customer_data"] = cust_data

            # Fetch history
            history_res = graph_adapter.get_transaction_history(cust_id)
            state["transaction_history"] = history_res.get("transactions", [])

        add_timeline_event(state, stage="ENRICHMENT", title="Entity Enrichment Completed", description=f"Loaded customer {cust_id} and transaction profile.")
    except Exception as e:
        logger.warning(f"Enrichment encountered an issue: {e}")
        # Allow downstream nodes to handle missing data or fail closed
        if "errors" not in state or state["errors"] is None:
            state["errors"] = []
        state["errors"].append({"stage": "ENRICHMENT", "message": str(e)})

    return state


def graph_analytics_node(state: AgentState) -> AgentState:
    """Graph analytics node: traverses connected entities and detects fraud patterns."""
    txn_id = state["transaction_id"]
    try:
        entities = graph_adapter.get_connected_entities(txn_id, depth=2)
        state["graph_evidence"] = entities

        patterns_res = graph_adapter.detect_fraud_patterns(txn_id)
        state["fraud_patterns"] = patterns_res.get("patterns", [])

        add_timeline_event(state, stage="GRAPH_ANALYTICS", title="Graph Analytics Completed", description=f"Detected {len(state['fraud_patterns'])} pattern(s).")
    except Exception as e:
        logger.warning(f"Graph analytics encountered an issue: {e}")
        if "errors" not in state or state["errors"] is None:
            state["errors"] = []
        state["errors"].append({"stage": "GRAPH_ANALYTICS", "message": str(e)})

    return state


def graphrag_context_node(state: AgentState) -> AgentState:
    """GraphRAG context node: retrieves governing policy and similar-case precedents."""
    txn_id = state["transaction_id"]
    try:
        context_res = graph_adapter.retrieve_investigation_context(txn_id, customer_id=state.get("customer_id"))
        state["graphrag_context"] = context_res

        # Tag retrieved external prompt context as untrusted input
        prompt_str = context_res.get("prompt_context", "")
        if "untrusted_inputs" not in state or state["untrusted_inputs"] is None:
            state["untrusted_inputs"] = []
        state["untrusted_inputs"].append(f"[UNTRUSTED_GRAPHRAG_EVIDENCE]: {prompt_str[:120]}...")

        add_timeline_event(state, stage="GRAPHRAG_CONTEXT", title="GraphRAG Context Retrieved", description="Retrieved policy clauses and historical case precedents.")
    except Exception as e:
        logger.warning(f"GraphRAG retrieval encountered an issue: {e}")
        if "errors" not in state or state["errors"] is None:
            state["errors"] = []
        state["errors"].append({"stage": "GRAPHRAG_CONTEXT", "message": str(e)})

    return state


def evidence_processor_node(state: AgentState) -> AgentState:
    """Evidence processor node: normalizes, categorizes, and deduplicates all evidence streams."""
    try:
        from agent.investigation.evidence_processor import evidence_processor
        similar = []
        if state.get("graphrag_context"):
            raw_cases = state["graphrag_context"].get("similar_cases", {})
            if isinstance(raw_cases, dict):
                similar = raw_cases.get("similar_cases", [])
            elif isinstance(raw_cases, list):
                similar = raw_cases

        items = evidence_processor.process_all(
            transaction_data=state.get("transaction_data"),
            customer_data=state.get("customer_data"),
            transaction_history=state.get("transaction_history"),
            connected_entities=state.get("graph_evidence"),
            fraud_patterns=state.get("fraud_patterns"),
            similar_cases=similar,
            graphrag_context=state.get("graphrag_context"),
            trigger_data=state.get("trigger"),
        )
        state["collected_evidence"] = [i.model_dump() for i in items]
        add_timeline_event(
            state,
            stage="EVIDENCE_PROCESSOR",
            title="Evidence Processing Completed",
            description=f"Normalized and deduplicated {len(items)} evidence item(s).",
        )
    except Exception as e:
        logger.warning(f"Evidence processing encountered an issue: {e}")
        if "errors" not in state or state["errors"] is None:
            state["errors"] = []
        state["errors"].append({"stage": "EVIDENCE_PROCESSOR", "message": str(e)})

    return state


def investigation_complete_node(state: AgentState) -> AgentState:
    """Terminal node for Stage 2 investigation workflow."""
    state["current_workflow_state"] = "INVESTIGATION_COMPLETE"
    add_timeline_event(
        state,
        stage="INVESTIGATION_COMPLETE",
        title="Investigation Complete",
        description="Evidence gathering and normalization concluded.",
    )
    return state


def risk_uncertainty_node(state: AgentState) -> AgentState:
    """
    Risk & uncertainty node: consumes investigation evidence, evaluates calibrated
    fraud probability, epistemic confidence, epistemic uncertainty, information gaps,
    and organizer stopping conditions using Stage 3 RiskUncertaintyService.
    """
    txn_id = state.get("transaction_id", "UNKNOWN")
    case_id = state.get("case_id", "CASE-UNKNOWN")

    # If an investigation result is already stored on state, use it directly
    if "investigation_result" in state and isinstance(state["investigation_result"], InvestigationResult):
        inv_result = state["investigation_result"]
    else:
        # Reconstruct canonical InvestigationResult from state
        raw_evidence = state.get("collected_evidence", [])
        evidence_objs: List[EvidenceItem] = []
        for item in raw_evidence:
            if isinstance(item, EvidenceItem):
                evidence_objs.append(item)
            elif isinstance(item, dict):
                try:
                    evidence_objs.append(EvidenceItem(**item))
                except Exception as ex:
                    logger.warning(f"Failed to parse evidence item: {ex}")

        similar_cases: List[Dict[str, Any]] = []
        if state.get("graphrag_context"):
            raw_cases = state["graphrag_context"].get("similar_cases", {})
            if isinstance(raw_cases, dict):
                similar_cases = raw_cases.get("similar_cases", [])
            elif isinstance(raw_cases, list):
                similar_cases = raw_cases

        status = InvestigationStatus.PARTIAL if state.get("errors") else InvestigationStatus.COMPLETE

        inv_result = InvestigationResult(
            case_id=case_id,
            transaction_id=txn_id,
            status=status,
            transaction=state.get("transaction_data"),
            customer=state.get("customer_data"),
            transaction_history=state.get("transaction_history", []),
            connected_entities=state.get("graph_evidence", {}),
            graph_findings=[state["graph_evidence"]] if state.get("graph_evidence") else [],
            fraud_pattern_evidence=state.get("fraud_patterns", []),
            similar_cases=similar_cases,
            graphrag_context=state.get("graphrag_context", {}),
            evidence=evidence_objs,
            warnings=[e.get("message", "") for e in state.get("errors", [])] if state.get("errors") else [],
            timeline=state.get("timeline", []),
            created_at=int(time.time()),
            completed_at=int(time.time()),
        )

    # Perform Stage 3 Risk & Uncertainty evaluation
    assessment = risk_uncertainty_service.assess(inv_result)

    state["risk_assessment"] = assessment.model_dump()
    state["fraud_probability"] = assessment.fraud_probability
    state["uncertainty_assessment"] = {
        "confidence": assessment.confidence,
        "uncertainty": assessment.uncertainty,
        "uncertainty_sources": [gap.description for gap in assessment.information_gaps],
    }
    if assessment.stopping_decision:
        state["stopping_decision"] = assessment.stopping_decision.model_dump()
        state["stop_reason"] = assessment.stopping_decision.rationale

    status_str = assessment.stopping_decision.status.value if assessment.stopping_decision else "UNKNOWN"
    add_timeline_event(
        state,
        stage="RISK_UNCERTAINTY",
        title="Risk & Uncertainty Assessed",
        description=f"P(Fraud): {assessment.fraud_probability:.4f} ({assessment.risk_level.value}), Confidence: {assessment.confidence:.4f}, Status: {status_str}",
    )
    return state


def risk_assessment_complete_node(state: AgentState) -> AgentState:
    """Terminal node for Stage 3 risk & uncertainty workflow."""
    state["current_workflow_state"] = "RISK_ASSESSMENT_COMPLETE"
    add_timeline_event(
        state,
        stage="RISK_ASSESSMENT_COMPLETE",
        title="Risk Assessment Complete",
        description="Fraud probability, confidence, uncertainty, and stopping decision evaluated.",
    )
    return state


def next_best_action_node(state: AgentState) -> AgentState:
    """
    Stage 4 Next Best Action node: consumes Stage 3 RiskAssessment and Stage 2 InvestigationResult,
    evaluates initial/final next best actions using Stage 4 NBAService,
    and populates canonical next best action recommendations.
    """
    txn_id = state.get("transaction_id", "UNKNOWN")
    case_id = state.get("case_id", "CASE-UNKNOWN")

    # 1. Retrieve or reconstruct canonical InvestigationResult
    if "investigation_result" in state and isinstance(state["investigation_result"], InvestigationResult):
        inv_result = state["investigation_result"]
    else:
        raw_evidence = state.get("collected_evidence", [])
        evidence_objs: List[EvidenceItem] = []
        for item in raw_evidence:
            if isinstance(item, EvidenceItem):
                evidence_objs.append(item)
            elif isinstance(item, dict):
                try:
                    evidence_objs.append(EvidenceItem(**item))
                except Exception as ex:
                    logger.warning(f"Failed to parse evidence item: {ex}")

        similar_cases: List[Dict[str, Any]] = []
        if state.get("graphrag_context"):
            raw_cases = state["graphrag_context"].get("similar_cases", {})
            if isinstance(raw_cases, dict):
                similar_cases = raw_cases.get("similar_cases", [])
            elif isinstance(raw_cases, list):
                similar_cases = raw_cases

        status = InvestigationStatus.PARTIAL if state.get("errors") else InvestigationStatus.COMPLETE
        inv_result = InvestigationResult(
            case_id=case_id,
            transaction_id=txn_id,
            status=status,
            transaction=state.get("transaction_data"),
            customer=state.get("customer_data"),
            transaction_history=state.get("transaction_history", []),
            connected_entities=state.get("graph_evidence", {}),
            graph_findings=[state["graph_evidence"]] if state.get("graph_evidence") else [],
            fraud_pattern_evidence=state.get("fraud_patterns", []),
            similar_cases=similar_cases,
            graphrag_context=state.get("graphrag_context", {}),
            evidence=evidence_objs,
            warnings=[e.get("message", "") for e in state.get("errors", [])] if state.get("errors") else [],
            timeline=state.get("timeline", []),
            created_at=int(time.time()),
            completed_at=int(time.time()),
        )

    # 2. Retrieve or compute Stage 3 RiskAssessment
    risk_dict = state.get("risk_assessment")
    if isinstance(risk_dict, RiskAssessment):
        risk_obj = risk_dict
    elif isinstance(risk_dict, dict):
        try:
            risk_obj = RiskAssessment.model_validate(risk_dict)
        except Exception:
            risk_obj = risk_uncertainty_service.assess(inv_result)
    else:
        risk_obj = risk_uncertainty_service.assess(inv_result)
        state["risk_assessment"] = risk_obj.model_dump()
        state["fraud_probability"] = risk_obj.fraud_probability

    # 3. Check for existing initial actions to evaluate update
    initial_actions_raw = state.get("initial_next_best_actions")
    initial_items: Optional[List[NextBestActionItem]] = None
    if initial_actions_raw:
        initial_items = []
        for item in initial_actions_raw:
            if isinstance(item, NextBestActionItem):
                initial_items.append(item)
            elif isinstance(item, dict):
                try:
                    initial_items.append(NextBestActionItem.model_validate(item))
                except Exception:
                    pass

    # 4. Assess Next Best Actions via Stage 4 NBAService
    assessment: NextBestActionAssessment = nba_service.assess(
        risk=risk_obj,
        investigation=inv_result,
        initial_actions=initial_items,
    )

    primary = assessment.primary_action
    state["next_best_action_assessment"] = assessment.model_dump()
    state["initial_next_best_actions"] = [i.model_dump() for i in assessment.initial]
    state["final_next_best_actions"] = [i.model_dump() for i in assessment.final]
    if assessment.what_changed:
        state["what_changed"] = (
            assessment.what_changed.explanation
            if isinstance(assessment.what_changed, NBAWhatChanged)
            else str(assessment.what_changed)
        )
    else:
        state["what_changed"] = None

    if primary:
        state["next_best_action"] = {
            "action": primary.action,
            "priority": primary.priority,
            "reason": primary.rationale,
            "confidence": risk_obj.confidence,
            "approval_required": False,  # Governed by Stage 5 Policy
            "evidence_ids": primary.supporting_evidence,
            "alternative_actions": [alt.action for alt in assessment.alternative_actions],
        }

    primary_str = primary.action if primary else "NONE"
    add_timeline_event(
        state,
        stage="NEXT_BEST_ACTION",
        title="Next Best Action Determined",
        description=f"Recommended: {primary_str} (Priority {primary.priority if primary else 1})",
    )
    return state


def nba_complete_node(state: AgentState) -> AgentState:
    """Terminal node for Stage 4 Next Best Action workflow."""
    state["current_workflow_state"] = "NBA_COMPLETE"
    add_timeline_event(
        state,
        stage="NBA_COMPLETE",
        title="Next Best Action Complete",
        description="Next best action reasoning concluded.",
    )
    return state


def _legacy_next_best_action_node(state: AgentState) -> AgentState:
    """Stage 1 mock NBA node preserved for legacy full lifecycle test backward compatibility."""
    risk = state.get("risk_assessment", {}).get("risk_score", 0.2)
    patterns = state.get("fraud_patterns", [])

    if risk >= 0.85:
        primary_action = "BLOCK_TRANSACTION"
        reason = "Severe risk detected with confirmed fraud patterns."
        approval_req = True
    elif risk >= 0.70:
        primary_action = "BLOCK_TRANSACTION"
        reason = "High risk threshold exceeded."
        approval_req = False
    elif risk >= 0.30:
        primary_action = "REQUEST_STEP_UP_AUTH"
        reason = "Moderate risk; secondary customer authentication advised."
        approval_req = False
    else:
        primary_action = "ALLOW_TRANSACTION"
        reason = "Low risk transaction within acceptable parameters."
        approval_req = False

    policy_approval = state.get("graphrag_context", {}).get("policy", {}).get("approval_required", False)
    if policy_approval and primary_action != "ALLOW_TRANSACTION":
        approval_req = True
        policy_basis = state.get("graphrag_context", {}).get("policy", {}).get("policy_basis", "")
        if policy_basis:
            reason += f" Governing policy requires supervisory approval: {policy_basis}"

    state["next_best_action"] = {
        "action": primary_action,
        "priority": 1,
        "reason": reason,
        "confidence": state.get("uncertainty_assessment", {}).get("confidence", 0.8),
        "approval_required": approval_req,
        "evidence_ids": [p.get("pattern_id") for p in patterns if "pattern_id" in p],
        "alternative_actions": ["MONITOR", "ESCALATE_TO_ANALYST"],
    }

    add_timeline_event(state, stage="NEXT_BEST_ACTION", title="Next Best Action Determined", description=f"Recommended: {primary_action} (Approval Required: {approval_req})")
    return state


def policy_compliance_node(state: AgentState) -> AgentState:
    """
    Stage 5 Policy Compliance Node:
    Consumes Stage 4 Next Best Action, Stage 3 RiskAssessment, and Stage 2 InvestigationResult.
    Deterministically evaluates R1-R10 organizer rules, assigns required approval routing level,
    and updates AgentState with PolicyAssessment and signed ApprovalRequest.
    """
    nba = state.get("next_best_action") or {}
    candidate_action = nba.get("action")
    if not candidate_action:
        # Fall back to primary action from final or initial if available
        if state.get("final_next_best_actions"):
            candidate_action = state["final_next_best_actions"][0].get("action")
        elif state.get("initial_next_best_actions"):
            candidate_action = state["initial_next_best_actions"][0].get("action")

    # Reconstruct or fetch InvestigationResult
    txn_id = state.get("transaction_id", "UNKNOWN")
    case_id = state.get("case_id", "CASE-UNKNOWN")

    if "investigation_result" in state and isinstance(state["investigation_result"], InvestigationResult):
        inv_result = state["investigation_result"]
    else:
        raw_evidence = state.get("collected_evidence", [])
        evidence_objs: List[EvidenceItem] = []
        for item in raw_evidence:
            if isinstance(item, EvidenceItem):
                evidence_objs.append(item)
            elif isinstance(item, dict):
                try:
                    evidence_objs.append(EvidenceItem(**item))
                except Exception:
                    pass

        similar_cases: List[Dict[str, Any]] = []
        if state.get("graphrag_context"):
            raw_cases = state["graphrag_context"].get("similar_cases", {})
            if isinstance(raw_cases, dict):
                similar_cases = raw_cases.get("similar_cases", [])
            elif isinstance(raw_cases, list):
                similar_cases = raw_cases

        status = InvestigationStatus.PARTIAL if state.get("errors") else InvestigationStatus.COMPLETE
        inv_result = InvestigationResult(
            case_id=case_id,
            transaction_id=txn_id,
            status=status,
            transaction=state.get("transaction_data"),
            customer=state.get("customer_data"),
            transaction_history=state.get("transaction_history", []),
            connected_entities=state.get("graph_evidence", {}),
            graph_findings=[state["graph_evidence"]] if state.get("graph_evidence") else [],
            fraud_pattern_evidence=state.get("fraud_patterns", []),
            similar_cases=similar_cases,
            graphrag_context=state.get("graphrag_context", {}),
            evidence=evidence_objs,
            warnings=[e.get("message", "") for e in state.get("errors", [])] if state.get("errors") else [],
            timeline=state.get("timeline", []),
            created_at=int(time.time()),
            completed_at=int(time.time()),
        )

    # Reconstruct or fetch RiskAssessment
    risk_dict = state.get("risk_assessment")
    if isinstance(risk_dict, RiskAssessment):
        risk_obj = risk_dict
    elif isinstance(risk_dict, dict):
        try:
            risk_obj = RiskAssessment.model_validate(risk_dict)
        except Exception:
            risk_obj = None
    else:
        risk_obj = None

    # Amount / exposure
    exposure_usd = None
    if state.get("transaction_data") and "amount" in state["transaction_data"]:
        try:
            exposure_usd = float(state["transaction_data"]["amount"])
        except (ValueError, TypeError):
            exposure_usd = None

    # Evaluate policy
    assessment = policy_evaluator.evaluate(
        action=candidate_action,
        investigation=inv_result,
        risk=risk_obj,
        exposure_usd=exposure_usd,
    )

    state["policy_assessment"] = assessment.model_dump()
    state["approval_level"] = assessment.approval_level.value
    state["hitl_status"] = assessment.hitl_status.value

    # Legacy policy_evaluation dict for backward compatibility
    state["policy_evaluation"] = {
        "policy_id": assessment.policy_version,
        "allowed": assessment.permitted,
        "approval_required": assessment.approval_required,
        "sar_required": assessment.sar_required,
        "reason": assessment.explanation,
        "violated_rules": assessment.violated_rules,
        "satisfied_rules": assessment.satisfied_rules,
    }

    if assessment.sar_required:
        state["sar"] = {
            "file": True,
            "reason": assessment.explanation,
            "total_amount_usd": assessment.exposure_usd,
        }

    now = int(time.time())
    if assessment.approval_required:
        state["approval_status"] = "PENDING"
        expires_at = now + 3600
        token = policy_evaluator.generate_approval_token(
            case_id=case_id,
            action=assessment.action.value,
            target_resource=txn_id,
            amount=assessment.exposure_usd,
            approval_level=assessment.approval_level.value,
            expires_at=expires_at,
        )
        state["approval_request"] = {
            "approval_id": f"APPR-{case_id[-6:]}",
            "case_id": case_id,
            "action": assessment.action.value,
            "target_resource": txn_id,
            "amount": assessment.exposure_usd,
            "requested_at": now,
            "expires_at": expires_at,
            "status": "PENDING",
            "approval_level": assessment.approval_level.value,
            "approval_token": token,
        }
        add_timeline_event(
            state,
            stage="POLICY_COMPLIANCE",
            title=f"{assessment.approval_level.value} Approval Required",
            description=f"Action '{assessment.action.value}' gated for human review: {assessment.explanation}",
            actor="POLICY_ENGINE",
        )
        audit_logger.record_event(
            event_type=AuditEventType.HITL_REQUIRED,
            case_id=case_id,
            action=assessment.action.value,
            actor="POLICY_ENGINE",
            payload={
                "approval_level": assessment.approval_level.value,
                "hitl_status": assessment.hitl_status.value,
                "exposure_usd": assessment.exposure_usd,
                "policy_version": assessment.policy_version,
            },
        )
    elif assessment.permitted:
        state["approval_status"] = "NOT_REQUIRED"
        state["approval_request"] = None
        add_timeline_event(
            state,
            stage="POLICY_COMPLIANCE",
            title="Policy Permitted (Auto-Approved)",
            description=f"Action '{assessment.action.value}' auto-approved under policy limits.",
            actor="POLICY_ENGINE",
        )
        audit_logger.record_event(
            event_type=AuditEventType.POLICY_EVALUATED,
            case_id=case_id,
            action=assessment.action.value,
            actor="POLICY_ENGINE",
            payload={
                "permitted": True,
                "approval_level": assessment.approval_level.value,
                "hitl_status": assessment.hitl_status.value,
                "exposure_usd": assessment.exposure_usd,
            },
        )
    else:
        state["approval_status"] = "BLOCKED"
        state["approval_request"] = None
        add_timeline_event(
            state,
            stage="POLICY_COMPLIANCE",
            title="Action Blocked by Policy",
            description=f"Action '{assessment.action.value}' prohibited: {assessment.explanation}",
            actor="POLICY_ENGINE",
        )
        audit_logger.record_event(
            event_type=AuditEventType.POLICY_BLOCKED,
            case_id=case_id,
            action=assessment.action.value,
            actor="POLICY_ENGINE",
            payload={
                "permitted": False,
                "violated_rules": assessment.violated_rules,
                "hitl_status": assessment.hitl_status.value,
            },
            status="BLOCKED",
        )

    return state


def route_after_policy(state: AgentState) -> str:
    """Conditional edge router out of policy compliance for full lifecycle workflow."""
    if state.get("approval_status") == "PENDING" or state.get("hitl_status") in ("PENDING_L1_APPROVAL", "PENDING_L2_APPROVAL"):
        return "AWAITING_APPROVAL"
    return "EXECUTION_HANDLER"


def hitl_gate_node(state: AgentState) -> AgentState:
    """HITL Gate node: halts investigation when human approval is required."""
    if state.get("approval_status") == "PENDING" or state.get("hitl_status") in ("PENDING_L1_APPROVAL", "PENDING_L2_APPROVAL"):
        state["current_workflow_state"] = "AWAITING_APPROVAL"
        add_timeline_event(
            state,
            stage="HITL_GATE",
            title="Awaiting Human Approval",
            description="Workflow halted at supervisory gate awaiting authorized sign-off.",
            actor="SYSTEM",
        )
    else:
        state["current_workflow_state"] = "POLICY_COMPLETE"
    return state


def policy_complete_node(state: AgentState) -> AgentState:
    """Terminal node for Stage 5 Policy workflow when auto-approved or blocked."""
    state["current_workflow_state"] = "POLICY_COMPLETE"
    add_timeline_event(
        state,
        stage="POLICY_COMPLETE",
        title="Policy Evaluation Concluded",
        description="Policy compliance check finalized.",
        actor="SYSTEM",
    )
    return state


def execution_node(state: AgentState) -> AgentState:
    """
    Stage 6 Execution node:
    Enforces 7-point authorization gating via ActionExecutionService,
    dispatches canonical action simulation, records idempotency and audit logs.
    """
    nba = state.get("next_best_action") or {}
    action_str = nba.get("action", "ALLOW_TRANSACTION")
    case_id = state.get("case_id", "CASE-UNKNOWN")
    txn_id = state.get("transaction_id", "UNKNOWN")
    cust_id = state.get("customer_id")
    txn_data = state.get("transaction_data") or {}
    cust_data = state.get("customer_data") or {}

    # Target resource resolution based on canonical action type
    action_norm = action_str.upper()
    if action_norm in ("BLOCK_CARD", "MONITOR_CARD"):
        cards = state.get("connected_card_ids") or cust_data.get("linked_cards") or []
        target = cards[0] if cards else f"CARD-{txn_id[-6:]}"
    elif action_norm in ("BLOCK_ALL_CARDS", "MONITOR_CONNECTED_CARDS"):
        target = cust_id or cust_data.get("customer_id") or txn_data.get("account_id") or f"C-{txn_id}"
    elif action_norm in ("DECLINE_TRANSACTION", "ALLOW_TRANSACTION", "BLOCK_TRANSACTION", "STEP_UP_AUTH"):
        target = txn_id
    elif action_norm in ("WARN_CUSTOMER", "VERIFY_WITH_CUSTOMER"):
        target = cust_id or cust_data.get("customer_id") or f"C-{txn_id}"
    else:
        target = case_id or txn_id

    # Parse PolicyAssessment if present
    policy_assessment = None
    raw_pa = state.get("policy_assessment")
    if isinstance(raw_pa, PolicyAssessment):
        policy_assessment = raw_pa
    elif isinstance(raw_pa, dict):
        try:
            policy_assessment = PolicyAssessment(**raw_pa)
        except Exception as pa_err:
            logger.warning(f"Could not reconstruct PolicyAssessment: {pa_err}")

    # Parse ApprovalRequest if present
    approval_request = None
    raw_ar = state.get("approval_request")
    if isinstance(raw_ar, ApprovalRequest):
        approval_request = raw_ar
    elif isinstance(raw_ar, dict):
        try:
            approval_request = ApprovalRequest(**raw_ar)
        except Exception as ar_err:
            logger.warning(f"Could not reconstruct ApprovalRequest: {ar_err}")

    try:
        res = action_executor.execute(
            action=action_str,
            case_id=case_id,
            target_resource=target,
            policy_assessment=policy_assessment,
            approval_request=approval_request,
            params={"amount": txn_data.get("amount", 0.0)},
            actor="WORKFLOW_EXECUTION_NODE",
        )
        state["execution_result"] = res.model_dump()
        add_timeline_event(
            state,
            stage="EXECUTION",
            title=f"Action {res.status.value}: {res.action.value}",
            description=res.message,
            actor="EXECUTION_SERVICE",
        )
    except Exception as e:
        logger.error(f"Action execution encountered error: {e}", exc_info=True)
        if "errors" not in state or state["errors"] is None:
            state["errors"] = []
        state["errors"].append({"stage": "EXECUTION", "message": str(e)})

    return state


def case_persistence_node(state: AgentState) -> AgentState:
    """
    Stage 6 Case Persistence node:
    Normalizes completed case context, commits case memory and evidentiary topology
    into TigerGraph via CaseMemoryAdapter with fault isolation.
    """
    case_id = state.get("case_id", "CASE-UNKNOWN")
    txn_id = state.get("transaction_id", "UNKNOWN")

    # Reconstruct evidence objects if present
    evidence_objs: List[EvidenceItem] = []
    for item in state.get("collected_evidence", []):
        if isinstance(item, EvidenceItem):
            evidence_objs.append(item)
        elif isinstance(item, dict):
            try:
                evidence_objs.append(EvidenceItem(**item))
            except Exception:
                pass

    # Save to in-memory case memory service
    case_obj = InvestigationCase(
        case_id=case_id,
        transaction_id=txn_id,
        customer_id=state.get("customer_id"),
        status=CaseStatus.AWAITING_APPROVAL if state.get("approval_status") == "PENDING" else CaseStatus.RESOLVED,
        risk_score=state.get("risk_assessment", {}).get("risk_score") if state.get("risk_assessment") else None,
        confidence=state.get("uncertainty_assessment", {}).get("confidence") if state.get("uncertainty_assessment") else None,
        uncertainty=state.get("uncertainty_assessment", {}).get("uncertainty") if state.get("uncertainty_assessment") else None,
        evidence=evidence_objs,
        fraud_patterns=state.get("fraud_patterns", []),
        timeline=state.get("timeline", []),
    )
    case_memory_service.save_case(case_obj)

    # Commit to TigerGraph case memory via adapter
    exec_results = [state["execution_result"]] if state.get("execution_result") else None
    persist_receipt = case_memory_adapter.persist_case(
        case=case_obj,
        execution_results=exec_results,
        actor="WORKFLOW_PERSISTENCE_NODE",
    )

    state["written_to_graph"] = persist_receipt.get("success", False)
    state["graph_case_id"] = persist_receipt.get("graph_case_id")
    state["current_workflow_state"] = "RESOLVED"

    add_timeline_event(
        state,
        stage="CASE_PERSISTENCE",
        title="Case Persisted to Memory",
        description=persist_receipt.get("message", f"Case {case_id} committed to case memory."),
        actor="CASE_PERSISTENCE_SERVICE",
    )
    return state


def finalized_node(state: AgentState) -> AgentState:
    """Terminal node for finalized fraud investigations."""
    state["current_workflow_state"] = "RESOLVED"
    add_timeline_event(
        state,
        stage="FINALIZED",
        title="Investigation Finalized",
        description="Investigation lifecycle fully concluded with case memory persistence.",
        actor="SYSTEM",
    )
    return state


# ------------------------------------------------------------------------------
# Workflow Graph Factory
# ------------------------------------------------------------------------------

def create_investigation_workflow() -> WorkflowEngine:
    """
    Constructs and binds the Stage 2 investigation workflow terminating at INVESTIGATION_COMPLETE.
    TRIGGERED -> ENRICHMENT -> GRAPH_ANALYTICS -> GRAPHRAG_CONTEXT -> EVIDENCE_PROCESSOR -> INVESTIGATION_COMPLETE
    """
    engine = WorkflowEngine()

    # Add Stage 2 Nodes
    engine.add_node("TRIGGERED", triggered_node)
    engine.add_node("ENRICHMENT", enrichment_node)
    engine.add_node("GRAPH_ANALYTICS", graph_analytics_node)
    engine.add_node("GRAPHRAG_CONTEXT", graphrag_context_node)
    engine.add_node("EVIDENCE_PROCESSOR", evidence_processor_node)
    engine.add_node("INVESTIGATION_COMPLETE", investigation_complete_node)

    # Set Entry Point
    engine.set_entry_point("TRIGGERED")

    # Add Stage 2 Linear Pipeline Transitions
    engine.add_edge("TRIGGERED", "ENRICHMENT")
    engine.add_edge("ENRICHMENT", "GRAPH_ANALYTICS")
    engine.add_edge("GRAPH_ANALYTICS", "GRAPHRAG_CONTEXT")
    engine.add_edge("GRAPHRAG_CONTEXT", "EVIDENCE_PROCESSOR")
    engine.add_edge("EVIDENCE_PROCESSOR", "INVESTIGATION_COMPLETE")

    # Set Terminal Nodes
    engine.set_terminal_nodes(["INVESTIGATION_COMPLETE", "FAILED"])

    return engine


def create_risk_assessment_workflow() -> WorkflowEngine:
    """
    Constructs and binds the Stage 3 risk assessment workflow terminating at RISK_ASSESSMENT_COMPLETE.
    TRIGGERED -> ENRICHMENT -> GRAPH_ANALYTICS -> GRAPHRAG_CONTEXT -> EVIDENCE_PROCESSOR
    -> INVESTIGATION_COMPLETE -> RISK_UNCERTAINTY -> RISK_ASSESSMENT_COMPLETE
    """
    engine = WorkflowEngine()

    engine.add_node("TRIGGERED", triggered_node)
    engine.add_node("ENRICHMENT", enrichment_node)
    engine.add_node("GRAPH_ANALYTICS", graph_analytics_node)
    engine.add_node("GRAPHRAG_CONTEXT", graphrag_context_node)
    engine.add_node("EVIDENCE_PROCESSOR", evidence_processor_node)
    engine.add_node("INVESTIGATION_COMPLETE", investigation_complete_node)
    engine.add_node("RISK_UNCERTAINTY", risk_uncertainty_node)
    engine.add_node("RISK_ASSESSMENT_COMPLETE", risk_assessment_complete_node)

    engine.set_entry_point("TRIGGERED")

    engine.add_edge("TRIGGERED", "ENRICHMENT")
    engine.add_edge("ENRICHMENT", "GRAPH_ANALYTICS")
    engine.add_edge("GRAPH_ANALYTICS", "GRAPHRAG_CONTEXT")
    engine.add_edge("GRAPHRAG_CONTEXT", "EVIDENCE_PROCESSOR")
    engine.add_edge("EVIDENCE_PROCESSOR", "INVESTIGATION_COMPLETE")
    engine.add_edge("INVESTIGATION_COMPLETE", "RISK_UNCERTAINTY")
    engine.add_edge("RISK_UNCERTAINTY", "RISK_ASSESSMENT_COMPLETE")

    engine.set_terminal_nodes(["RISK_ASSESSMENT_COMPLETE", "FAILED"])

    return engine


def create_nba_workflow() -> WorkflowEngine:
    """
    Constructs and binds the Stage 4 Next Best Action workflow terminating at NBA_COMPLETE.
    TRIGGERED -> ENRICHMENT -> GRAPH_ANALYTICS -> GRAPHRAG_CONTEXT -> EVIDENCE_PROCESSOR
    -> INVESTIGATION_COMPLETE -> RISK_UNCERTAINTY -> RISK_ASSESSMENT_COMPLETE
    -> NEXT_BEST_ACTION -> NBA_COMPLETE
    """
    engine = WorkflowEngine()

    engine.add_node("TRIGGERED", triggered_node)
    engine.add_node("ENRICHMENT", enrichment_node)
    engine.add_node("GRAPH_ANALYTICS", graph_analytics_node)
    engine.add_node("GRAPHRAG_CONTEXT", graphrag_context_node)
    engine.add_node("EVIDENCE_PROCESSOR", evidence_processor_node)
    engine.add_node("INVESTIGATION_COMPLETE", investigation_complete_node)
    engine.add_node("RISK_UNCERTAINTY", risk_uncertainty_node)
    engine.add_node("RISK_ASSESSMENT_COMPLETE", risk_assessment_complete_node)
    engine.add_node("NEXT_BEST_ACTION", next_best_action_node)
    engine.add_node("NBA_COMPLETE", nba_complete_node)

    engine.set_entry_point("TRIGGERED")

    engine.add_edge("TRIGGERED", "ENRICHMENT")
    engine.add_edge("ENRICHMENT", "GRAPH_ANALYTICS")
    engine.add_edge("GRAPH_ANALYTICS", "GRAPHRAG_CONTEXT")
    engine.add_edge("GRAPHRAG_CONTEXT", "EVIDENCE_PROCESSOR")
    engine.add_edge("EVIDENCE_PROCESSOR", "INVESTIGATION_COMPLETE")
    engine.add_edge("INVESTIGATION_COMPLETE", "RISK_UNCERTAINTY")
    engine.add_edge("RISK_UNCERTAINTY", "RISK_ASSESSMENT_COMPLETE")
    engine.add_edge("RISK_ASSESSMENT_COMPLETE", "NEXT_BEST_ACTION")
    engine.add_edge("NEXT_BEST_ACTION", "NBA_COMPLETE")

    engine.set_terminal_nodes(["NBA_COMPLETE", "FAILED"])

    return engine


def create_policy_workflow() -> WorkflowEngine:
    """
    Constructs and binds the Stage 5 Policy & HITL Gate workflow terminating at
    POLICY_COMPLETE or AWAITING_APPROVAL.
    TRIGGERED -> ENRICHMENT -> GRAPH_ANALYTICS -> GRAPHRAG_CONTEXT -> EVIDENCE_PROCESSOR
    -> INVESTIGATION_COMPLETE -> RISK_UNCERTAINTY -> RISK_ASSESSMENT_COMPLETE
    -> NEXT_BEST_ACTION -> NBA_COMPLETE -> POLICY_EVALUATION -> HITL_GATE
    -> POLICY_COMPLETE or AWAITING_APPROVAL (halts workflow; zero execution).
    """
    engine = WorkflowEngine()

    engine.add_node("TRIGGERED", triggered_node)
    engine.add_node("ENRICHMENT", enrichment_node)
    engine.add_node("GRAPH_ANALYTICS", graph_analytics_node)
    engine.add_node("GRAPHRAG_CONTEXT", graphrag_context_node)
    engine.add_node("EVIDENCE_PROCESSOR", evidence_processor_node)
    engine.add_node("INVESTIGATION_COMPLETE", investigation_complete_node)
    engine.add_node("RISK_UNCERTAINTY", risk_uncertainty_node)
    engine.add_node("RISK_ASSESSMENT_COMPLETE", risk_assessment_complete_node)
    engine.add_node("NEXT_BEST_ACTION", next_best_action_node)
    engine.add_node("NBA_COMPLETE", nba_complete_node)
    engine.add_node("POLICY_EVALUATION", policy_compliance_node)
    engine.add_node("HITL_GATE", hitl_gate_node)
    engine.add_node("POLICY_COMPLETE", policy_complete_node)
    engine.add_node("AWAITING_APPROVAL", hitl_gate_node)

    engine.set_entry_point("TRIGGERED")

    engine.add_edge("TRIGGERED", "ENRICHMENT")
    engine.add_edge("ENRICHMENT", "GRAPH_ANALYTICS")
    engine.add_edge("GRAPH_ANALYTICS", "GRAPHRAG_CONTEXT")
    engine.add_edge("GRAPHRAG_CONTEXT", "EVIDENCE_PROCESSOR")
    engine.add_edge("EVIDENCE_PROCESSOR", "INVESTIGATION_COMPLETE")
    engine.add_edge("INVESTIGATION_COMPLETE", "RISK_UNCERTAINTY")
    engine.add_edge("RISK_UNCERTAINTY", "RISK_ASSESSMENT_COMPLETE")
    engine.add_edge("RISK_ASSESSMENT_COMPLETE", "NEXT_BEST_ACTION")
    engine.add_edge("NEXT_BEST_ACTION", "NBA_COMPLETE")
    engine.add_edge("NBA_COMPLETE", "POLICY_EVALUATION")
    engine.add_edge("POLICY_EVALUATION", "HITL_GATE")

    def route_policy_gate(s: AgentState) -> str:
        if s.get("hitl_status") in ("PENDING_L1_APPROVAL", "PENDING_L2_APPROVAL") or s.get("approval_status") == "PENDING":
            return "AWAITING_APPROVAL"
        return "POLICY_COMPLETE"

    engine.add_conditional_edges(
        "HITL_GATE",
        route_policy_gate,
        {
            "AWAITING_APPROVAL": "AWAITING_APPROVAL",
            "POLICY_COMPLETE": "POLICY_COMPLETE",
        }
    )

    engine.set_terminal_nodes(["POLICY_COMPLETE", "AWAITING_APPROVAL", "FAILED"])

    return engine


def create_full_lifecycle_workflow() -> WorkflowEngine:
    """
    Modular factory preserving future Stage 3-6 nodes for full lifecycle execution.
    """
    engine = WorkflowEngine()

    engine.add_node("TRIGGERED", triggered_node)
    engine.add_node("ENRICHMENT", enrichment_node)
    engine.add_node("GRAPH_ANALYTICS", graph_analytics_node)
    engine.add_node("GRAPHRAG_CONTEXT", graphrag_context_node)
    engine.add_node("EVIDENCE_PROCESSOR", evidence_processor_node)
    engine.add_node("RISK_UNCERTAINTY", risk_uncertainty_node)
    engine.add_node("NEXT_BEST_ACTION", _legacy_next_best_action_node)
    engine.add_node("POLICY_COMPLIANCE", policy_compliance_node)
    engine.add_node("AWAITING_APPROVAL", hitl_gate_node)
    engine.add_node("EXECUTION_HANDLER", execution_node)
    engine.add_node("CASE_PERSISTENCE", case_persistence_node)

    engine.set_entry_point("TRIGGERED")

    engine.add_edge("TRIGGERED", "ENRICHMENT")
    engine.add_edge("ENRICHMENT", "GRAPH_ANALYTICS")
    engine.add_edge("GRAPH_ANALYTICS", "GRAPHRAG_CONTEXT")
    engine.add_edge("GRAPHRAG_CONTEXT", "EVIDENCE_PROCESSOR")
    engine.add_edge("EVIDENCE_PROCESSOR", "RISK_UNCERTAINTY")
    engine.add_edge("RISK_UNCERTAINTY", "NEXT_BEST_ACTION")
    engine.add_edge("NEXT_BEST_ACTION", "POLICY_COMPLIANCE")

    engine.add_conditional_edges(
        "POLICY_COMPLIANCE",
        route_after_policy,
        {
            "AWAITING_APPROVAL": "AWAITING_APPROVAL",
            "EXECUTION_HANDLER": "EXECUTION_HANDLER",
        }
    )

    engine.add_edge("EXECUTION_HANDLER", "CASE_PERSISTENCE")
    engine.set_terminal_nodes(["AWAITING_APPROVAL", "CASE_PERSISTENCE", "FAILED"])

    return engine


def create_execution_workflow() -> WorkflowEngine:
    """
    Stage 6 full end-to-end execution workflow using canonical Stage 2-6 components.
    TRIGGERED -> ENRICHMENT -> GRAPH_ANALYTICS -> GRAPHRAG_CONTEXT -> EVIDENCE_PROCESSOR
    -> INVESTIGATION_COMPLETE -> RISK_UNCERTAINTY -> RISK_ASSESSMENT_COMPLETE
    -> NEXT_BEST_ACTION -> NBA_COMPLETE -> POLICY_EVALUATION -> HITL_GATE
    -> (conditional) -> EXECUTION_HANDLER -> CASE_PERSISTENCE -> FINALIZED
    """
    engine = WorkflowEngine()

    engine.add_node("TRIGGERED", triggered_node)
    engine.add_node("ENRICHMENT", enrichment_node)
    engine.add_node("GRAPH_ANALYTICS", graph_analytics_node)
    engine.add_node("GRAPHRAG_CONTEXT", graphrag_context_node)
    engine.add_node("EVIDENCE_PROCESSOR", evidence_processor_node)
    engine.add_node("INVESTIGATION_COMPLETE", investigation_complete_node)
    engine.add_node("RISK_UNCERTAINTY", risk_uncertainty_node)
    engine.add_node("RISK_ASSESSMENT_COMPLETE", risk_assessment_complete_node)
    engine.add_node("NEXT_BEST_ACTION", next_best_action_node)
    engine.add_node("NBA_COMPLETE", nba_complete_node)
    engine.add_node("POLICY_EVALUATION", policy_compliance_node)
    engine.add_node("HITL_GATE", hitl_gate_node)
    engine.add_node("AWAITING_APPROVAL", hitl_gate_node)
    engine.add_node("EXECUTION_HANDLER", execution_node)
    engine.add_node("CASE_PERSISTENCE", case_persistence_node)
    engine.add_node("FINALIZED", finalized_node)

    engine.set_entry_point("TRIGGERED")

    engine.add_edge("TRIGGERED", "ENRICHMENT")
    engine.add_edge("ENRICHMENT", "GRAPH_ANALYTICS")
    engine.add_edge("GRAPH_ANALYTICS", "GRAPHRAG_CONTEXT")
    engine.add_edge("GRAPHRAG_CONTEXT", "EVIDENCE_PROCESSOR")
    engine.add_edge("EVIDENCE_PROCESSOR", "INVESTIGATION_COMPLETE")
    engine.add_edge("INVESTIGATION_COMPLETE", "RISK_UNCERTAINTY")
    engine.add_edge("RISK_UNCERTAINTY", "RISK_ASSESSMENT_COMPLETE")
    engine.add_edge("RISK_ASSESSMENT_COMPLETE", "NEXT_BEST_ACTION")
    engine.add_edge("NEXT_BEST_ACTION", "NBA_COMPLETE")
    engine.add_edge("NBA_COMPLETE", "POLICY_EVALUATION")
    engine.add_edge("POLICY_EVALUATION", "HITL_GATE")

    def route_execution_gate(s: AgentState) -> str:
        if s.get("hitl_status") in ("PENDING_L1_APPROVAL", "PENDING_L2_APPROVAL") or s.get("approval_status") == "PENDING":
            return "AWAITING_APPROVAL"
        if s.get("hitl_status") == "POLICY_BLOCKED" or s.get("approval_status") == "BLOCKED":
            return "CASE_PERSISTENCE"
        return "EXECUTION_HANDLER"

    engine.add_conditional_edges(
        "HITL_GATE",
        route_execution_gate,
        {
            "AWAITING_APPROVAL": "AWAITING_APPROVAL",
            "CASE_PERSISTENCE": "CASE_PERSISTENCE",
            "EXECUTION_HANDLER": "EXECUTION_HANDLER",
        }
    )

    engine.add_edge("EXECUTION_HANDLER", "CASE_PERSISTENCE")
    engine.add_edge("CASE_PERSISTENCE", "FINALIZED")
    engine.set_terminal_nodes(["FINALIZED", "AWAITING_APPROVAL", "FAILED"])

    return engine
