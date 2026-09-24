# ==============================================================================
# FraudGraph AI - REST API Routes
# Workstream: Person 1 (Brain) - Stage 1 Foundation
# ==============================================================================

import time
import logging
import uuid
from typing import Dict, Any, Optional, List, Union
from fastapi import APIRouter, Query, Request, status
from pydantic import BaseModel, Field, model_validator

from backend.config import settings
from backend.errors import (
    ValidationError,
    InvalidApprovalException,
    TransactionNotFoundException,
    CustomerNotFoundException,
    CaseNotFoundException,
)
from backend.models.domain import (
    ActionType,
    CaseStatus,
    ApprovalStatus,
    ApprovalLevel,
    HITLStatus,
    InvestigationResult,
    InvestigationStatus,
    InvestigationStartRequest,
    NextBestActionAssessment,
    NextBestActionItem,
    PolicyAssessment,
    InvestigationCase,
    TimelineEvent,
    ApprovalRequest,
    ActionRecommendation,
    FraudPattern,
    RiskLevel,
    EvidenceItem,
)
from backend.models.audit import audit_logger, AuditEventType
from backend.policy import policy_evaluator
from backend.services.mock_actions import mock_action_service
from backend.services.case_memory import case_memory_service
from backend.execution import action_executor, ExecutionResult, ExecutionStatus
from agent.tools.graph_adapter import graph_adapter
from agent.tools.case_memory_adapter import case_memory_adapter
from agent.workflows.workflow import create_investigation_workflow
from agent.workflows.state import create_initial_agent_state
from agent.investigation.engine import investigation_engine
from agent.risk import risk_uncertainty_service
from agent.nba import nba_service

logger = logging.getLogger("fraudgraph.routes")

router = APIRouter()


# ------------------------------------------------------------------------------
# Request & Response Schemas
# ------------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str = "healthy"
    service: str = "fraudgraph-backend"
    version: str = "1.0.0"
    timestamp: int = Field(default_factory=lambda: int(time.time()))


class StatusResponse(BaseModel):
    status: str = "operational"
    components: Dict[str, str]
    config: Dict[str, Any]


class InvestigateRequest(BaseModel):
    """
    Investigation initiation request.
    Strictly forbids client-injected risk/confidence scores or pre-approved flags (Security Baseline §19, §20).
    Supports either dictionary trigger or canonical trigger type string from frontend.
    """
    transaction_id: str = Field(..., description="Canonical transaction identifier (e.g. TXN-104829)")
    trigger: Optional[Union[Dict[str, Any], str]] = Field(default=None, description="Optional trigger metadata")

    @model_validator(mode="before")
    @classmethod
    def reject_untrusted_client_overrides(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Check for client attempting to inject risk or confidence scores
            forbidden_keys = {"risk_score", "risk", "confidence", "uncertainty"}
            found_forbidden = forbidden_keys.intersection(data.keys())
            if found_forbidden:
                raise ValidationError(
                    f"Client is not permitted to supply risk or confidence assessments ({', '.join(found_forbidden)}). "
                    "Assessments must be derived strictly server-side.",
                    details={"forbidden_fields": list(found_forbidden)}
                )

            # Check for client attempting to submit pre-approved status
            approval_keys = {"approved", "approval", "approval_status"}
            found_approval = approval_keys.intersection(data.keys())
            if found_approval:
                raise ValidationError(
                    "Client is not permitted to submit approval flags during investigation initiation. "
                    "All approvals must be submitted to the dedicated approval endpoint.",
                    details={"forbidden_fields": list(found_approval)}
                )
        return data


class ApprovalSubmission(BaseModel):
    """Payload for submitting a human supervisory approval."""
    approver_id: str = Field(..., description="Unique analyst or supervisor identifier")
    decision: str = Field(..., description="APPROVED or REJECTED")
    approval_token: str = Field(..., description="Cryptographically signed approval token")
    notes: Optional[str] = Field(default=None, description="Optional justification notes")


# ------------------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------------------

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Liveness probe for backend service."""
    return HealthResponse()


@router.get("/status", response_model=StatusResponse)
async def system_status():
    """Readiness probe reporting component status and safe configuration summary."""
    return StatusResponse(
        status="operational",
        components={
            "backend": "healthy",
            "graph_layer": "mock" if settings.use_mock_graph else "live",
            "graphrag": "ready",
            "workflow_engine": "ready",
        },
        config=settings.get_safe_summary(),
    )


@router.get("/transactions/{transaction_id}")
async def get_transaction(transaction_id: str):
    """Retrieves transaction profile from graph layer."""
    return graph_adapter.get_transaction(transaction_id)


@router.get("/customer/{customer_id}")
async def get_customer(customer_id: str):
    """Retrieves customer profile from graph layer."""
    return graph_adapter.get_customer(customer_id)


@router.get("/graph/{entity_id}")
async def get_graph(entity_id: str, depth: int = Query(default=2, ge=1, le=3)):
    """Retrieves connected entity graph neighborhood for visualization."""
    return graph_adapter.get_connected_entities(entity_id, depth=depth)


def _map_actor(act: str) -> str:
    act_u = str(act).upper()
    if "TIGER" in act_u or "GRAPH" in act_u:
        return "TigerGraph"
    if "ANALYST" in act_u or "SUPERVISOR" in act_u:
        return "Analyst"
    if "CUSTOMER" in act_u:
        return "Customer"
    if "AGENT" in act_u or "ENGINE" in act_u:
        return "Agent"
    return "System"


def _format_case_for_frontend(case: InvestigationCase) -> Dict[str, Any]:
    graph_entities = []
    graph_relationships = []
    try:
        conn = graph_adapter.get_connected_entities(case.transaction_id, depth=2)
        nodes = conn.get("nodes", []) if isinstance(conn, dict) else getattr(conn, "nodes", [])
        edges = conn.get("edges", []) if isinstance(conn, dict) else getattr(conn, "edges", [])
        for n in nodes:
            nid = n.get("id") if isinstance(n, dict) else getattr(n, "id", "")
            ntype = n.get("type", "Transaction") if isinstance(n, dict) else getattr(n, "type", "Transaction")
            if ntype == "IPAddress":
                ntype = "IP"
            nlabel = n.get("label", nid) if isinstance(n, dict) else getattr(n, "label", nid)
            nrisk = float(n.get("risk_score", 0.5) if isinstance(n, dict) else getattr(n, "risk_score", 0.5))
            graph_entities.append({
                "id": str(nid),
                "type": ntype,
                "label": str(nlabel),
                "subtitle": f"{ntype} · risk {round(nrisk, 2)}",
                "risk_score": round(nrisk, 2),
                "flagged": nrisk > 0.7,
            })
        for i, e in enumerate(edges):
            esrc = e.get("source") if isinstance(e, dict) else getattr(e, "source", "")
            etgt = e.get("target") if isinstance(e, dict) else getattr(e, "target", "")
            etype = e.get("type", "LINKED") if isinstance(e, dict) else getattr(e, "type", "LINKED")
            graph_relationships.append({
                "id": f"e{i+1}",
                "source": str(esrc),
                "target": str(etgt),
                "label": str(etype).lower().replace("_", " "),
                "suspicious": any(w in str(etype).lower() for w in ("fraud", "suspicious", "shared", "target")),
            })
    except Exception as e:
        logger.warning(f"Could not load graph context for {case.transaction_id}: {e}")

    existing_ids = {ent["id"] for ent in graph_entities}
    if case.customer_id and case.customer_id not in existing_ids:
        graph_entities.insert(0, {
            "id": case.customer_id,
            "type": "Customer",
            "label": case.customer_id,
            "subtitle": "Subject customer account",
            "risk_score": round(float(case.risk_score or 0.62), 2),
            "flagged": (case.risk_score or 0.0) > 0.7,
        })
        existing_ids.add(case.customer_id)
    if case.transaction_id not in existing_ids:
        graph_entities.insert(0, {
            "id": case.transaction_id,
            "type": "Transaction",
            "label": case.transaction_id,
            "subtitle": f"${case.exposure_usd or 8420:.0f} · investigated transaction",
            "risk_score": round(float(case.risk_score or 0.87), 2),
            "flagged": True,
        })
        existing_ids.add(case.transaction_id)
    if case.case_id not in existing_ids:
        graph_entities.append({
            "id": case.case_id,
            "type": "Case",
            "label": case.case_id,
            "subtitle": "Active investigation workspace",
            "risk_score": round(float(case.risk_score or 0.87), 2),
            "flagged": True,
        })
        existing_ids.add(case.case_id)
        if case.transaction_id in existing_ids:
            graph_relationships.append({
                "id": f"e-case-txn",
                "source": case.transaction_id,
                "target": case.case_id,
                "label": "investigated_in",
                "suspicious": True,
            })

    patterns = []
    for p in case.fraud_patterns:
        patterns.append({
            "pattern_id": getattr(p, "pattern_id", "PAT-01"),
            "name": getattr(p, "name", "Fraud Pattern"),
            "description": getattr(p, "description", ""),
            "evidence_refs": getattr(p, "evidence_refs", []) or [e.evidence_id for e in case.evidence[:3]],
            "confidence": round(float(getattr(p, "confidence", 0.76)), 2),
            "indicators": getattr(p, "matched_entities", None) or ["Unusual transaction behavior"],
        })
    if not patterns:
        patterns.append({
            "pattern_id": "PAT-ATO-01",
            "name": "Suspected Account Takeover",
            "description": "Unusual transaction activity connected to linked entities.",
            "evidence_refs": [e.evidence_id for e in case.evidence[:3]] if case.evidence else ["EV-001"],
            "confidence": round(float(case.risk_score or 0.76), 2),
            "indicators": ["Shared device across linked accounts", "New beneficiary", "Unusual transaction velocity"],
        })

    ev_list = []
    for e in case.evidence:
        ev_list.append({
            "evidence_id": e.evidence_id,
            "type": e.evidence_type,
            "source": e.source,
            "summary": e.description or e.claim or "",
            "confidence": round(float(e.confidence), 2),
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(e.timestamp if e.timestamp else int(time.time()))),
            "related_entities": e.entity_ids or ([e.related_entity] if e.related_entity else [case.transaction_id]),
        })

    tl_list = []
    for i, t in enumerate(case.timeline):
        tl_list.append({
            "event_id": getattr(t, "event_id", f"TL-{i+1}"),
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(getattr(t, "timestamp", int(time.time())))),
            "type": getattr(t, "title", "Event"),
            "summary": getattr(t, "description", ""),
            "actor": _map_actor(getattr(t, "actor", "SYSTEM")),
            "related_ids": [case.transaction_id] + ([case.customer_id] if case.customer_id else []),
        })

    rec = case.recommendation
    frontend_rec = {
        "action": rec.action if rec else "REQUEST_STEP_UP_AUTH",
        "reason": rec.reason if rec else "Evaluate transaction under policy.",
        "confidence": round(float(rec.confidence if rec else (case.confidence or 0.58)), 2),
        "approval_required": bool(case.approval_request is not None or (rec and rec.approval_required)),
        "policy_basis": rec.policy_basis if (rec and rec.policy_basis) else "POL-FRD-07 · Step-up verification for high-risk activity",
    }

    customer_response = None
    for ev in case.evidence:
        if getattr(ev, "untrusted_data_flag", False) and getattr(ev, "evidence_type", "") == "CUSTOMER_CONFIRMATION":
            customer_response = getattr(ev, "description", None) or getattr(ev, "claim", None)

    missing_evidence = []
    if not customer_response and case.status not in (CaseStatus.RESOLVED, CaseStatus.CLOSED):
        missing_evidence = [
            {
                "evidence_id": "REQ-001",
                "title": "Customer Transaction Confirmation",
                "reason": "Customer intent is the highest-value unresolved signal in the current assessment.",
                "action": "REQUEST_CUSTOMER_VERIFICATION",
            },
            {
                "evidence_id": "REQ-002",
                "title": "Device Ownership Verification",
                "reason": "Ownership of device is not established for the current customer session.",
                "action": "REQUEST_DEVICE_VERIFICATION",
            }
        ]

    case_memory = None
    if case.status in (CaseStatus.RESOLVED, CaseStatus.CLOSED):
        case_memory = f"Resolved pattern stored in TigerGraph case memory for {case.transaction_id}."

    status_str = case.status.value if isinstance(case.status, CaseStatus) else str(case.status)

    return {
        "case_id": case.case_id,
        "transaction_id": case.transaction_id,
        "customer_id": case.customer_id or f"C-{case.transaction_id}",
        "status": status_str,
        "risk_score": round(float(case.risk_score or 0.87), 2),
        "confidence": round(float(case.confidence or 0.58), 2),
        "amount": round(float(case.exposure_usd or 8420.0), 2),
        "currency": "USD",
        "created_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(case.created_at if case.created_at else int(time.time()))),
        "updated_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(case.updated_at if case.updated_at else int(time.time()))),
        "transaction_summary": case.summary or f"High-value transaction {case.transaction_id} requiring investigation.",
        "approval_required": frontend_rec["approval_required"],
        "recommendation": frontend_rec,
        "fraud_patterns": patterns,
        "evidence": ev_list,
        "timeline": tl_list,
        "graph_entities": graph_entities,
        "graph_relationships": graph_relationships,
        "missing_evidence": missing_evidence,
        "customer_response": customer_response,
        "case_memory": case_memory,
    }


def _build_case_from_pipeline(
    case_id: str,
    transaction_id: str,
    investigation: InvestigationResult,
    risk: Any,
    nba: Any,
    policy: Any,
) -> InvestigationCase:
    cust_id = (investigation.customer or {}).get("customer_id") if investigation.customer else None
    
    fraud_patterns = []
    for fp in getattr(investigation, "fraud_pattern_evidence", []):
        if isinstance(fp, dict):
            fraud_patterns.append(FraudPattern(
                pattern_id=fp.get("pattern_id", "PAT-01"),
                name=fp.get("name", "Fraud Pattern"),
                description=fp.get("description", ""),
                severity=RiskLevel.HIGH,
                confidence=fp.get("confidence", 0.75),
                evidence_refs=fp.get("evidence_refs", []),
                matched_entities=fp.get("matched_entities", []),
            ))

    primary_act = nba.primary_action.action if (nba and nba.primary_action) else "REQUEST_STEP_UP_AUTH"
    primary_reason = nba.primary_action.rationale if (nba and nba.primary_action) else "Evaluation complete."
    
    rec = ActionRecommendation(
        action=primary_act,
        priority=1,
        reason=primary_reason,
        confidence=risk.confidence if risk else 0.58,
        approval_required=policy.approval_required if policy else False,
        policy_basis=policy.explanation if policy else "POL-FRD-07 · Step-up verification for high-risk activity",
        route=policy.approval_level.value if policy else "auto",
    )

    now_ts = int(time.time())
    case_obj = InvestigationCase(
        case_id=case_id,
        transaction_id=transaction_id,
        customer_id=cust_id,
        status=CaseStatus.INVESTIGATING,
        fraud_probability=risk.fraud_probability if risk else 0.87,
        risk_score=risk.fraud_probability if risk else 0.87,
        confidence=risk.confidence if risk else 0.58,
        uncertainty=risk.uncertainty if risk else 0.42,
        exposure_usd=policy.exposure_usd if policy else (investigation.transaction or {}).get("amount", 8420.0),
        evidence=investigation.evidence,
        fraud_patterns=fraud_patterns,
        recommendation=rec,
        timeline=[
            TimelineEvent(
                stage="TRIGGERED",
                title="Investigation Triggered",
                description=f"Investigation initiated for transaction {transaction_id}.",
                actor="SYSTEM",
            ),
            TimelineEvent(
                stage="ENRICHMENT",
                title="Transaction Profile Loaded",
                description=f"Retrieved profile for transaction {transaction_id}.",
                actor="SYSTEM",
            ),
            TimelineEvent(
                stage="GRAPH_TRAVERSAL",
                title="Graph Traversal Completed",
                description="Connected devices, accounts, and beneficiary relationships analyzed.",
                actor="TIGERGRAPH",
            ),
            TimelineEvent(
                stage="RISK_ASSESSMENT",
                title="Risk & Uncertainty Assessed",
                description=f"Assessed fraud probability: {risk.fraud_probability:.2f}, confidence: {risk.confidence:.2f}." if risk else "Assessed risk.",
                actor="AGENT",
            ),
            TimelineEvent(
                stage="NBA",
                title="Action Recommended",
                description=f"Recommended action '{primary_act}': {primary_reason}",
                actor="AGENT",
            ),
        ],
        summary=f"Investigation for transaction {transaction_id} (Customer {cust_id or 'Unknown'}). Assessed fraud probability: {risk.fraud_probability if risk else 0.87:.2f}.",
        created_at=now_ts,
        updated_at=now_ts,
    )
    return case_obj


def _seed_hero_case() -> InvestigationCase:
    existing = case_memory_service.get_case("CASE-1024")
    if existing:
        return existing
    inv = investigation_engine.investigate("TXN-104829")
    risk = risk_uncertainty_service.assess(inv)
    inv.risk_score = risk.fraud_probability
    nba = nba_service.assess(risk=risk, investigation=inv)
    target_action = nba.primary_action.action if (nba and nba.primary_action) else "REQUEST_STEP_UP_AUTH"
    policy = policy_evaluator.evaluate(action=target_action, investigation=inv, risk=risk)
    hero = _build_case_from_pipeline(
        case_id="CASE-1024",
        transaction_id="TXN-104829",
        investigation=inv,
        risk=risk,
        nba=nba,
        policy=policy,
    )
    case_memory_service.save_case(hero)
    return hero


@router.post("/investigations", response_model=InvestigationResult, status_code=status.HTTP_200_OK)
async def start_investigation(req: InvestigateRequest):
    """
    Canonical Stage 2 Investigation initiation endpoint.
    Performs comprehensive graph and GraphRAG evidence collection, validation,
    normalization, and deduplication.
    Also executes risk & NBA pipelines to seed the case in case memory for frontend workflows.
    """
    trigger_dict = req.trigger if isinstance(req.trigger, dict) else ({"trigger_type": req.trigger, "narrative": f"Triggered by {req.trigger}"} if req.trigger else None)
    inv = investigation_engine.investigate(
        transaction_id=req.transaction_id,
        trigger=trigger_dict,
    )
    try:
        risk = risk_uncertainty_service.assess(inv)
        inv.risk_score = risk.fraud_probability
        nba = nba_service.assess(risk=risk, investigation=inv)
        target_action = nba.primary_action.action if (nba and nba.primary_action) else "REQUEST_STEP_UP_AUTH"
        policy = policy_evaluator.evaluate(action=target_action, investigation=inv, risk=risk)
        case_obj = _build_case_from_pipeline(
            case_id=inv.case_id,
            transaction_id=req.transaction_id,
            investigation=inv,
            risk=risk,
            nba=nba,
            policy=policy,
        )
        case_memory_service.save_case(case_obj)
    except Exception as e:
        logger.warning(f"Could not build full case state during start_investigation for {req.transaction_id}: {e}")

    return inv


@router.post("/investigate", response_model=InvestigationResult, status_code=status.HTTP_200_OK)
async def investigate_transaction(req: InvestigateRequest):
    """
    Alias investigation endpoint routing to the canonical Investigation Engine.
    """
    return await start_investigation(req)


@router.post("/cases/{case_id}/approve", status_code=status.HTTP_200_OK)
async def approve_case_action(case_id: str, body: ApprovalSubmission):
    """
    Processes human supervisory approval for a held case.
    Validates cryptographic token, enforces server-side approver authority,
    updates case HITL status, and records structured audit trail.
    ZERO action execution (Stage 6 boundary).
    """
    token = body.approval_token.strip()
    if not token or token == "invalid" or "bypass" in token.lower():
        raise InvalidApprovalException(
            "Approval token verification failed: invalid or tampered token.",
            details={"case_id": case_id, "token_provided": token[:10] + "..." if len(token) > 10 else token}
        )

    # 1. Fetch case from case memory
    case = case_memory_service.get_case(case_id)
    if not case:
        raise CaseNotFoundException(case_id)

    # 2. Check if case is already decided (idempotency check)
    if case.status in (CaseStatus.RESOLVED, CaseStatus.CLOSED):
        raise InvalidApprovalException(
            f"Case '{case_id}' has already been resolved or decided.",
            details={"case_id": case_id, "current_status": case.status.value}
        )

    if case.approval_request and case.approval_request.status in (ApprovalStatus.APPROVED, ApprovalStatus.REJECTED):
        raise InvalidApprovalException(
            f"Case '{case_id}' approval request has already been decided ({case.approval_request.status.value}).",
            details={"case_id": case_id, "decision": case.approval_request.status.value}
        )

    # 3. Check case is awaiting approval
    if case.status != CaseStatus.AWAITING_APPROVAL and (not case.approval_request or case.approval_request.status != ApprovalStatus.PENDING):
        raise InvalidApprovalException(
            f"Case '{case_id}' is not currently awaiting approval.",
            details={"case_id": case_id, "current_status": case.status.value}
        )

    appr_req = case.approval_request
    if not appr_req:
        raise InvalidApprovalException(
            f"Case '{case_id}' has no pending approval request.",
            details={"case_id": case_id}
        )

    # 4. Verify cryptographic HMAC token
    req_level = appr_req.approval_level if isinstance(appr_req.approval_level, ApprovalLevel) else ApprovalLevel(str(appr_req.approval_level))
    token_valid = policy_evaluator.verify_approval_token(
        token=token,
        case_id=case_id,
        action=appr_req.action,
        target_resource=appr_req.target_resource,
        amount=appr_req.amount,
        approval_level=req_level.value,
    )
    if not token_valid:
        raise InvalidApprovalException(
            "Approval token verification failed: invalid, tampered, or expired token.",
            details={"case_id": case_id}
        )

    # 5. Verify server-side approver authority (L1 supervisor cannot approve L2 compliance action)
    has_authority = policy_evaluator.verify_approver_authority(
        approver_id=body.approver_id,
        required_level=req_level,
    )
    if not has_authority:
        raise InvalidApprovalException(
            f"Approver '{body.approver_id}' possesses insufficient authority for required level '{req_level.value}'.",
            details={"approver_id": body.approver_id, "required_level": req_level.value}
        )

    # 6. Process decision (APPROVED or REJECTED)
    decision_clean = body.decision.strip().upper()
    if decision_clean not in ("APPROVED", "REJECTED"):
        raise InvalidApprovalException(
            f"Invalid approval decision '{body.decision}'. Must be APPROVED or REJECTED.",
            details={"decision": body.decision}
        )

    if decision_clean == "APPROVED":
        case.status = CaseStatus.RESOLVED
        appr_req.status = ApprovalStatus.APPROVED
        appr_req.approver_id = body.approver_id
        audit_logger.record_event(
            event_type=AuditEventType.APPROVAL_GRANTED,
            case_id=case_id,
            action=appr_req.action,
            actor=body.approver_id,
            payload={
                "notes": body.notes,
                "approval_level": req_level.value,
                "target_resource": appr_req.target_resource,
                "amount": appr_req.amount,
            },
        )
    else:
        case.status = CaseStatus.RESOLVED
        appr_req.status = ApprovalStatus.REJECTED
        appr_req.approver_id = body.approver_id
        audit_logger.record_event(
            event_type=AuditEventType.APPROVAL_REJECTED,
            case_id=case_id,
            action=appr_req.action,
            actor=body.approver_id,
            payload={
                "notes": body.notes,
                "approval_level": req_level.value,
                "target_resource": appr_req.target_resource,
                "amount": appr_req.amount,
            },
        )

    case_memory_service.save_case(case)

    # ZERO action execution: strictly no execute_action or write_case_to_graph
    return {
        "case_id": case_id,
        "status": decision_clean,
        "approver_id": body.approver_id,
        "approval_level": req_level.value,
        "action": appr_req.action,
        "executed": False,
        "message": f"Human approval decision '{decision_clean}' recorded successfully. Action execution gated for Stage 6.",
    }


class NBARequest(BaseModel):
    """Optional payload for Next Best Action evaluation."""
    trigger: Optional[Dict[str, Any]] = Field(default=None, description="Optional trigger metadata")
    initial_actions: Optional[List[NextBestActionItem]] = Field(default=None, description="Prior initial recommendations if evaluating final update")
    evidence_added: Optional[List[str]] = Field(default=None, description="Descriptions of newly introduced evidence")


@router.post("/investigations/{transaction_id}/nba", response_model=NextBestActionAssessment, status_code=status.HTTP_200_OK)
async def evaluate_transaction_nba(
    transaction_id: str,
    body: Optional[NBARequest] = None,
):
    """
    Stage 4 Next Best Action evaluation endpoint.
    Consumes Stage 2 investigation and Stage 3 risk assessment to determine
    ordered, canonical Next Best Action recommendations.
    Does NOT execute actions, route approvals, or evaluate Stage 5 policy.
    """
    trigger = body.trigger if body else None
    initial_actions = body.initial_actions if body else None
    evidence_added = body.evidence_added if body else None

    # Step 1: Run Stage 2 Investigation
    investigation = investigation_engine.investigate(transaction_id=transaction_id, trigger=trigger)

    # Step 2: Run Stage 3 Risk & Uncertainty
    risk = risk_uncertainty_service.assess(investigation)

    # Step 3: Run Stage 4 NBA
    nba_assessment = nba_service.assess(
        risk=risk,
        investigation=investigation,
        initial_actions=initial_actions,
        evidence_added=evidence_added,
    )

    return nba_assessment


@router.post("/investigate/{transaction_id}/nba", response_model=NextBestActionAssessment, status_code=status.HTTP_200_OK)
async def investigate_transaction_nba(
    transaction_id: str,
    body: Optional[NBARequest] = None,
):
    """Alias route for Next Best Action evaluation."""
    return await evaluate_transaction_nba(transaction_id=transaction_id, body=body)


class PolicyRequest(BaseModel):
    """Optional payload for Policy evaluation endpoint."""
    trigger: Optional[Dict[str, Any]] = Field(default=None, description="Optional trigger metadata")
    action_override: Optional[str] = Field(default=None, description="Optional canonical action to evaluate against policy")
    exposure_override: Optional[float] = Field(default=None, description="Optional exposure USD override")
    facts: Optional[Dict[str, Any]] = Field(default=None, description="Optional facts context")


@router.post("/investigations/{transaction_id}/policy", response_model=PolicyAssessment, status_code=status.HTTP_200_OK)
async def evaluate_transaction_policy(
    transaction_id: str,
    body: Optional[PolicyRequest] = None,
):
    """
    Stage 5 Policy Compliance evaluation endpoint.
    Consumes Stage 2 investigation, Stage 3 risk assessment, and Stage 4 NBA
    to deterministically evaluate organizer rules R1-R10 and approval routing.
    Does NOT execute actions.
    """
    trigger = body.trigger if body else None
    action_override = body.action_override if body else None
    exposure_override = body.exposure_override if body else None
    facts = body.facts if body else None

    # Step 1: Run Stage 2 Investigation
    investigation = investigation_engine.investigate(transaction_id=transaction_id, trigger=trigger)

    # Step 2: Run Stage 3 Risk & Uncertainty
    risk = risk_uncertainty_service.assess(investigation)

    # Step 3: Determine target action (from Stage 4 NBA or action_override)
    if action_override:
        target_action = action_override
    else:
        nba_assessment = nba_service.assess(risk=risk, investigation=investigation)
        target_action = nba_assessment.primary_action.action if nba_assessment.primary_action else "ALLOW_TRANSACTION"

    # Step 4: Run Stage 5 Policy Evaluation
    assessment = policy_evaluator.evaluate(
        action=target_action,
        investigation=investigation,
        risk=risk,
        exposure_usd=exposure_override,
        facts=facts,
    )

    return assessment


@router.post("/investigate/{transaction_id}/policy", response_model=PolicyAssessment, status_code=status.HTTP_200_OK)
async def investigate_transaction_policy(
    transaction_id: str,
    body: Optional[PolicyRequest] = None,
):
    """Alias route for Policy Compliance evaluation."""
    return await evaluate_transaction_policy(transaction_id=transaction_id, body=body)


# ------------------------------------------------------------------------------
# Case Management & Investigation Details Endpoints (Frontend API Support)
# ------------------------------------------------------------------------------

@router.get("/cases/{case_id}")
async def get_case_by_id(case_id: str):
    """
    Retrieves full investigation case details formatted for the frontend workspace.
    Supports hero demo case CASE-1024 with dynamic seeding.
    """
    case = case_memory_service.get_case(case_id)
    if not case:
        if case_id == "CASE-1024":
            case = _seed_hero_case()
        else:
            raise CaseNotFoundException(case_id)
    return _format_case_for_frontend(case)


@router.get("/cases/{case_id}/investigation")
async def get_case_investigation(case_id: str):
    """
    Retrieves evidence and graph investigation details for a case.
    Matches frontend contract: GET /api/cases/{caseId}/investigation.
    """
    return await get_case_by_id(case_id)


@router.get("/cases/{case_id}/recommendation")
async def get_case_recommendation(case_id: str):
    """
    Retrieves latest action recommendation and policy basis for a case.
    Matches frontend contract: GET /api/cases/{caseId}/recommendation.
    """
    formatted = await get_case_by_id(case_id)
    return formatted["recommendation"]


class EvidenceRequestPayload(BaseModel):
    evidence_type: str = Field(default="CUSTOMER_TRANSACTION_CONFIRMATION")


@router.post("/cases/{case_id}/evidence-request")
async def request_case_evidence(case_id: str, body: Optional[EvidenceRequestPayload] = None):
    """
    Dispatches evidence collection request (e.g. customer verification).
    Updates case state to WAITING_FOR_EVIDENCE and appends timeline event.
    Matches frontend contract: POST /api/cases/{caseId}/evidence-request.
    """
    case = case_memory_service.get_case(case_id)
    if not case:
        if case_id == "CASE-1024":
            case = _seed_hero_case()
        else:
            raise CaseNotFoundException(case_id)

    case.status = CaseStatus.WAITING_FOR_EVIDENCE
    case.updated_at = int(time.time())
    case.timeline.append(TimelineEvent(
        stage="WAITING_FOR_EVIDENCE",
        title="Verification Requested",
        description="Customer confirmation and device verification requested under policy.",
        actor="AGENT",
    ))
    case_memory_service.save_case(case)
    formatted = _format_case_for_frontend(case)
    return {
        "case_id": case_id,
        "status": case.status.value if isinstance(case.status, CaseStatus) else str(case.status),
        "requested": formatted["missing_evidence"],
    }


class EvidenceSubmissionPayload(BaseModel):
    type: str = Field(default="CUSTOMER_CONFIRMATION")
    source: str = Field(default="Controlled customer verification")
    summary: str = Field(..., description="Customer response narrative")
    related_entities: Optional[List[str]] = Field(default_factory=list)


@router.post("/cases/{case_id}/evidence")
async def add_case_evidence(case_id: str, body: EvidenceSubmissionPayload):
    """
    Ingests customer response or external evidence item.
    Enforces Security Baseline: Ingested as OBSERVATION with untrusted_data_flag=True (never arbitrary FACT).
    Updates risk, uncertainty, NBA recommendations, and timeline.
    Matches frontend contract: POST /api/cases/{caseId}/evidence.
    """
    case = case_memory_service.get_case(case_id)
    if not case:
        if case_id == "CASE-1024":
            case = _seed_hero_case()
        else:
            raise CaseNotFoundException(case_id)

    # Ingest untrusted customer response as OBSERVATION (never FACT)
    ev_item = EvidenceItem(
        evidence_id=f"EV-{uuid.uuid4().hex[:4].upper()}",
        source=body.source,
        evidence_type=body.type,
        description=body.summary,
        claim=body.summary,
        confidence=0.99,
        untrusted_data_flag=True,
        fact_level="OBSERVATION",
        is_direct=True,
        entity_ids=body.related_entities or ([case.customer_id, case.transaction_id] if case.customer_id else [case.transaction_id]),
    )
    case.evidence.append(ev_item)

    is_denial = any(w in body.summary.lower() for w in ("not recognize", "unrecognized", "fraud", "denied", "did not", "never"))
    now_ts = int(time.time())
    case.updated_at = now_ts

    if is_denial:
        case.confidence = 0.96
        case.risk_score = max(case.risk_score or 0.85, 0.95)
        case.status = CaseStatus.ACTION_READY
        case.recommendation = ActionRecommendation(
            action="BLOCK_TRANSACTION · FREEZE_ACCOUNT",
            priority=1,
            reason="Customer denied transaction. Strong evidence of unauthorized activity warrants protective action.",
            confidence=0.96,
            approval_required=True,
            policy_basis="POL-FRD-12 · Confirmed unauthorized transaction with high-risk connected entities",
            route="L1",
        )
        case.approval_request = ApprovalRequest(
            case_id=case_id,
            action="DECLINE_TRANSACTION",
            target_resource=case.transaction_id,
            amount=case.exposure_usd or 8420.0,
            approval_level=ApprovalLevel.L1_SUPERVISOR,
            status=ApprovalStatus.PENDING,
        )
    else:
        case.confidence = 0.95
        case.risk_score = 0.05
        case.status = CaseStatus.ACTION_READY
        case.recommendation = ActionRecommendation(
            action="ALLOW_TRANSACTION",
            priority=1,
            reason="Customer confirmed transaction as legitimate.",
            confidence=0.95,
            approval_required=False,
            policy_basis="POL-FRD-03 · Customer confirmation of legitimate transaction",
            route="auto",
        )

    case.timeline.append(TimelineEvent(
        stage="EVIDENCE_INGESTION",
        title="Customer Response Received",
        description=f"Customer stated: “{body.summary}”",
        actor="CUSTOMER",
    ))
    case.timeline.append(TimelineEvent(
        stage="RISK_UPDATE",
        title="Risk Updated",
        description=f"Confidence updated to {case.confidence*100:.0f}% after customer response.",
        actor="AGENT",
    ))
    case.timeline.append(TimelineEvent(
        stage="NBA_UPDATE",
        title="Action Recommended",
        description=f"Recommended action '{case.recommendation.action}': {case.recommendation.reason}",
        actor="AGENT",
    ))
    case_memory_service.save_case(case)
    return _format_case_for_frontend(case)


# ------------------------------------------------------------------------------
# Stage 6 Execution & Case Persistence Endpoints
# ------------------------------------------------------------------------------

class CaseActionRequest(BaseModel):
    """Payload for frontend action dispatch (matches frontend/services/api.ts)."""
    action: str = Field(..., description="Action to execute")
    approved: bool = Field(default=False, description="Client-claimed approval flag (strictly unvetted)")
    approver_id: Optional[str] = Field(default=None, description="Optional approver identifier")
    notes: Optional[str] = Field(default=None, description="Optional operational notes")


@router.post("/cases/{case_id}/action", status_code=status.HTTP_200_OK)
async def take_case_action(case_id: str, body: CaseActionRequest):
    """
    Executes a remediation action for a case under strict server-side authorization gating.
    Matches frontend service contract: POST /api/cases/{case_id}/action.
    CRITICAL: Does NOT blindly trust client-provided `approved: true`.
    """
    case = case_memory_service.get_case(case_id)
    if not case:
        if case_id == "CASE-1024":
            case = _seed_hero_case()
        else:
            raise CaseNotFoundException(case_id)

    target_action = body.action.strip()
    norm_action_str = target_action.split("·")[0].strip() if "·" in target_action else target_action

    # Determine evaluated exposure from case
    exposure = case.exposure_usd or (case.amount if hasattr(case, "amount") else 0.0)

    # Server-side policy evaluation
    policy_assessment = policy_evaluator.evaluate(
        action=norm_action_str,
        exposure_usd=exposure,
        facts={
            "case_id": case_id,
            "risk_score": case.risk_score or 0.0,
            "confidence": case.confidence or 1.0,
        },
    )

    # Server-side authorization check: Auto vs L1/L2
    if policy_assessment.approval_level == ApprovalLevel.AUTO:
        if not policy_assessment.permitted:
            raise InvalidApprovalException(
                f"Action '{target_action}' is prohibited by policy: {policy_assessment.explanation}",
                details={"case_id": case_id, "violated_rules": policy_assessment.violated_rules}
            )
    else:
        # Requires human approval (L1 or L2)
        if case.approval_request and case.approval_request.status == ApprovalStatus.APPROVED:
            pass
        elif body.approver_id and policy_evaluator.verify_approver_authority(body.approver_id, policy_assessment.approval_level):
            if not case.approval_request:
                case.approval_request = ApprovalRequest(
                    case_id=case_id,
                    action=norm_action_str,
                    target_resource=case.transaction_id,
                    amount=exposure,
                    approval_level=policy_assessment.approval_level,
                    status=ApprovalStatus.APPROVED,
                    approver_id=body.approver_id,
                )
            else:
                case.approval_request.status = ApprovalStatus.APPROVED
                case.approval_request.approver_id = body.approver_id
        else:
            raise InvalidApprovalException(
                f"Action '{target_action}' requires {policy_assessment.approval_level.value} supervisory approval. "
                "Client-asserted approval is rejected: server-side approval record is missing or not approved.",
                details={"case_id": case_id, "required_level": policy_assessment.approval_level.value}
            )

    # Resolve target resource
    act_norm = norm_action_str.upper()
    if act_norm in ("BLOCK_CARD", "MONITOR_CARD"):
        target_res = case.connected_card_ids[0] if case.connected_card_ids else f"CARD-{case.customer_id or case.transaction_id}"
    elif act_norm in ("BLOCK_ALL_CARDS", "MONITOR_CONNECTED_CARDS"):
        target_res = case.customer_id or f"C-{case.transaction_id}"
    elif act_norm in ("DECLINE_TRANSACTION", "ALLOW_TRANSACTION", "BLOCK_TRANSACTION", "STEP_UP_AUTH"):
        target_res = case.transaction_id
    elif act_norm in ("WARN_CUSTOMER", "VERIFY_WITH_CUSTOMER"):
        target_res = case.customer_id or f"C-{case.transaction_id}"
    else:
        target_res = case.transaction_id or case_id

    # Execute action via ActionExecutionService
    exec_res = action_executor.execute(
        action=norm_action_str,
        case_id=case_id,
        target_resource=target_res,
        policy_assessment=policy_assessment,
        approval_request=case.approval_request,
        approver_id=body.approver_id or (case.approval_request.approver_id if case.approval_request else None),
        actor="API_CASE_ACTION",
    )

    if exec_res.status not in (ExecutionStatus.EXECUTED, ExecutionStatus.ALREADY_EXECUTED):
        raise InvalidApprovalException(
            f"Action execution could not be completed: {exec_res.message}",
            details={"status": exec_res.status.value, "details": exec_res.details}
        )

    # Update case state
    case.status = CaseStatus.RESOLVED
    case.updated_at = int(time.time())
    case.timeline.append(TimelineEvent(
        stage="EXECUTION",
        title=f"Action Executed: {exec_res.action.value}",
        description=exec_res.message,
        actor="SYSTEM",
    ))

    # Commit to TigerGraph case memory via adapter
    case_memory_adapter.persist_case(
        case=case,
        execution_results=[exec_res],
        actor="API_CASE_ACTION",
    )
    case_memory_service.save_case(case)

    return _format_case_for_frontend(case)


class ExecuteInvestigationRequest(BaseModel):
    """Optional payload for automated investigation execution."""
    trigger: Optional[Dict[str, Any]] = Field(default=None)
    action_override: Optional[str] = Field(default=None)
    approver_id: Optional[str] = Field(default=None)


@router.post("/investigations/{transaction_id}/execute", status_code=status.HTTP_200_OK)
async def execute_investigation(
    transaction_id: str,
    body: Optional[ExecuteInvestigationRequest] = None,
):
    """
    Automated investigation lifecycle execution endpoint:
    Runs investigation -> risk assessment -> NBA -> policy compliance -> action execution (if auto-approved).
    If human approval is required, stops at AWAITING_APPROVAL and returns pending approval request.
    """
    trigger = body.trigger if body else None
    action_override = body.action_override if body else None
    approver_id = body.approver_id if body else None

    # Step 1: Run Stage 2 Investigation
    investigation = investigation_engine.investigate(transaction_id=transaction_id, trigger=trigger)

    # Step 2: Run Stage 3 Risk & Uncertainty
    risk = risk_uncertainty_service.assess(investigation)

    # Step 3: Run Stage 4 NBA
    nba_res = nba_service.assess(risk=risk, investigation=investigation)
    target_action = action_override or (nba_res.primary_action.action if nba_res.primary_action else "ALLOW_TRANSACTION")

    # Step 4: Run Stage 5 Policy Evaluation
    policy_res = policy_evaluator.evaluate(
        action=target_action,
        investigation=investigation,
        risk=risk,
    )

    case_id = investigation.case_id
    cust_id = investigation.customer.get("customer_id") if investigation.customer else None

    # Resolve target resource
    act_norm = target_action.upper()
    if act_norm in ("BLOCK_CARD", "MONITOR_CARD"):
        cards = investigation.customer.get("linked_cards", []) if investigation.customer else []
        target_res = cards[0] if cards else f"CARD-{transaction_id[-6:]}"
    elif act_norm in ("BLOCK_ALL_CARDS", "MONITOR_CONNECTED_CARDS"):
        target_res = cust_id or f"C-{transaction_id}"
    elif act_norm in ("DECLINE_TRANSACTION", "ALLOW_TRANSACTION", "BLOCK_TRANSACTION", "STEP_UP_AUTH"):
        target_res = transaction_id
    elif act_norm in ("WARN_CUSTOMER", "VERIFY_WITH_CUSTOMER"):
        target_res = cust_id or f"C-{transaction_id}"
    else:
        target_res = transaction_id

    # Create Case record
    case_obj = InvestigationCase(
        case_id=case_id,
        transaction_id=transaction_id,
        customer_id=cust_id,
        risk_score=risk.fraud_probability,
        confidence=risk.confidence,
        uncertainty=risk.uncertainty,
        exposure_usd=policy_res.exposure_usd,
        evidence=investigation.evidence,
        fraud_patterns=investigation.fraud_pattern_evidence,
    )

    # If action is prohibited by policy, return blocked state
    if not policy_res.permitted or policy_res.hitl_status in (HITLStatus.POLICY_BLOCKED, HITLStatus.POLICY_INDETERMINATE):
        case_obj.status = CaseStatus.RESOLVED
        case_memory_service.save_case(case_obj)
        return {
            "case_id": case_id,
            "transaction_id": transaction_id,
            "status": "POLICY_BLOCKED",
            "action": target_action,
            "approval_required": False,
            "approval_level": policy_res.approval_level.value,
            "approval_request": None,
            "execution_result": None,
            "message": f"Action '{target_action}' is prohibited by policy: {policy_res.explanation}",
            "violated_rules": policy_res.violated_rules,
        }

    # If action requires approval, return awaiting approval state
    if policy_res.approval_required:
        case_obj.status = CaseStatus.AWAITING_APPROVAL
        now = int(time.time())
        expires_at = now + 3600
        token = policy_evaluator.generate_approval_token(
            case_id=case_id,
            action=target_action,
            target_resource=target_res,
            amount=policy_res.exposure_usd,
            approval_level=policy_res.approval_level.value,
            expires_at=expires_at,
        )
        case_obj.approval_request = ApprovalRequest(
            case_id=case_id,
            action=target_action,
            target_resource=target_res,
            amount=policy_res.exposure_usd,
            approval_level=policy_res.approval_level,
            approval_token=token,
            requested_at=now,
            expires_at=expires_at,
            status=ApprovalStatus.PENDING,
        )
        case_memory_service.save_case(case_obj)
        return {
            "case_id": case_id,
            "transaction_id": transaction_id,
            "status": "AWAITING_APPROVAL",
            "action": target_action,
            "approval_required": True,
            "approval_level": policy_res.approval_level.value,
            "approval_request": case_obj.approval_request.model_dump(),
            "execution_result": None,
            "message": f"Action '{target_action}' requires {policy_res.approval_level.value} approval prior to execution.",
        }

    # Action is auto-approved: execute
    exec_res = action_executor.execute(
        action=target_action,
        case_id=case_id,
        target_resource=target_res,
        policy_assessment=policy_res,
        approver_id=approver_id,
        actor="API_AUTO_EXECUTION",
    )

    case_obj.status = CaseStatus.RESOLVED
    case_obj.timeline.append(TimelineEvent(
        stage="EXECUTION",
        title=f"Action Executed: {exec_res.action.value}",
        description=exec_res.message,
    ))

    # Persist to TigerGraph case memory
    persist_receipt = case_memory_adapter.persist_case(
        case=case_obj,
        execution_results=[exec_res],
        actor="API_AUTO_PERSISTENCE",
    )
    case_memory_service.save_case(case_obj)

    return {
        "case_id": case_id,
        "transaction_id": transaction_id,
        "status": "RESOLVED",
        "action": target_action,
        "approval_required": False,
        "execution_result": exec_res.model_dump(),
        "case_persistence": persist_receipt,
        "message": exec_res.message,
    }


@router.post("/investigate/{transaction_id}/execute", status_code=status.HTTP_200_OK)
async def investigate_transaction_execute(
    transaction_id: str,
    body: Optional[ExecuteInvestigationRequest] = None,
):
    """Alias route for investigation lifecycle execution."""
    return await execute_investigation(transaction_id=transaction_id, body=body)
