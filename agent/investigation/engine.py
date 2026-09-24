# ==============================================================================
# FraudGraph AI - Investigation Engine
# Workstream: Person 1 (Brain) - Stage 2 Investigation Engine
# ==============================================================================

import time
import uuid
import logging
from typing import Dict, Any, Optional, List

from backend.errors import (
    ValidationError,
    TransactionNotFoundException,
    CustomerNotFoundException,
    GraphQueryFailedException,
    UnauthorizedToolError,
)
from backend.models.domain import (
    InvestigationResult,
    InvestigationStatus,
    EvidenceItem,
    TimelineEvent,
)
from backend.models.audit import audit_logger, AuditEventType
from agent.tools.security import VALID_ID_PATTERN
from agent.tools.graph_adapter import graph_adapter, Person2GraphAdapter
from agent.investigation.evidence_processor import evidence_processor, EvidenceProcessor

logger = logging.getLogger("fraudgraph.investigation_engine")


class InvestigationEngine:
    """
    Stage 2 Investigation Engine for FraudGraph AI.
    Systematically gathers, validates, normalizes, deduplicates, and structures
    evidence using Person 2's TigerGraph and GraphRAG layer.

    Strict Boundary:
    Answers: "WHAT EVIDENCE DO WE HAVE?"
    Does NOT answer: "HOW RISKY IS THIS?", "WHAT SHOULD WE DO?", "ARE WE ALLOWED TO DO IT?"
    """

    def __init__(
        self,
        adapter: Optional[Person2GraphAdapter] = None,
        processor: Optional[EvidenceProcessor] = None,
    ):
        self._adapter = adapter or graph_adapter
        self._evidence_processor = processor or evidence_processor

    def investigate(
        self,
        transaction_id: str,
        trigger: Optional[Dict[str, Any]] = None,
    ) -> InvestigationResult:
        """
        Executes end-to-end evidence gathering and structuring for a transaction.
        Handles partial component failures gracefully without data fabrication.
        """
        # 1. Input sanitization & validation (fail-closed against injections)
        if not transaction_id or not isinstance(transaction_id, str):
            raise ValidationError(
                message="Transaction ID must be a non-empty string.",
                details={"transaction_id": transaction_id},
            )

        clean_txn_id = transaction_id.strip()
        if not VALID_ID_PATTERN.match(clean_txn_id):
            audit_logger.record_event(
                event_type=AuditEventType.SECURITY_VIOLATION,
                action="INVESTIGATE_INPUT_VALIDATION",
                actor="INVESTIGATION_ENGINE",
                payload={"transaction_id": clean_txn_id, "reason": "Disallowed characters in identifier"},
            )
            raise ValidationError(
                message=f"Invalid transaction ID format: '{clean_txn_id}'. Identifiers must be alphanumeric with hyphens, underscores, dots, or colons.",
                details={"transaction_id": clean_txn_id},
            )

        case_id = f"CASE-{uuid.uuid4().hex[:8].upper()}"
        start_time = int(time.time())
        warnings: List[str] = []
        timeline: List[Dict[str, Any]] = []

        def add_event(stage: str, title: str, description: str = ""):
            timeline.append({
                "event_id": f"EVT-{uuid.uuid4().hex[:8].upper()}",
                "timestamp": int(time.time()),
                "stage": stage,
                "title": title,
                "description": description,
                "actor": "INVESTIGATION_ENGINE",
                "metadata": {},
            })

        # 2. Record start audit event
        audit_logger.record_event(
            event_type=AuditEventType.INVESTIGATION_STARTED,
            action="START_INVESTIGATION",
            actor="INVESTIGATION_ENGINE",
            payload={"case_id": case_id, "transaction_id": clean_txn_id, "trigger": trigger},
        )
        add_event("TRIGGERED", "Investigation Triggered", f"Triggered investigation for transaction {clean_txn_id}")

        # 3. Transaction Enrichment (Mandatory primary step)
        try:
            txn_data = self._adapter.get_transaction(clean_txn_id)
            add_event("ENRICHMENT", "Transaction Profile Loaded", f"Retrieved {txn_data.get('amount')} {txn_data.get('currency', 'USD')} transaction")
        except TransactionNotFoundException:
            audit_logger.record_event(
                event_type=AuditEventType.FAILED,
                action="GET_TRANSACTION",
                actor="INVESTIGATION_ENGINE",
                payload={"case_id": case_id, "transaction_id": clean_txn_id, "error": "Transaction not found"},
            )
            raise
        except Exception as e:
            audit_logger.record_event(
                event_type=AuditEventType.FAILED,
                action="GET_TRANSACTION",
                actor="INVESTIGATION_ENGINE",
                payload={"case_id": case_id, "transaction_id": clean_txn_id, "error": str(e)},
            )
            raise GraphQueryFailedException("get_transaction", details={"transaction_id": clean_txn_id, "error": str(e)})

        # 4. Customer Enrichment & Bounded Transaction History
        customer_id = txn_data.get("customer_id")
        cust_data: Optional[Dict[str, Any]] = None
        txn_history: List[Dict[str, Any]] = []

        if customer_id:
            try:
                cust_data = self._adapter.get_customer(customer_id)
                add_event("ENRICHMENT", "Customer Profile Loaded", f"Resolved customer {customer_id} ({cust_data.get('name')})")
            except Exception as e:
                msg = f"Failed to retrieve customer {customer_id}: {e}"
                logger.warning(msg)
                warnings.append(msg)
                audit_logger.record_event(
                    event_type=AuditEventType.PARTIAL_FAILURE,
                    action="GET_CUSTOMER",
                    actor="INVESTIGATION_ENGINE",
                    payload={"customer_id": customer_id, "error": str(e)},
                )

            try:
                history_res = self._adapter.get_transaction_history(customer_id, limit=50)
                raw_history = history_res.get("transactions", [])
                # Enforce hard upper bound of 50 records
                txn_history = raw_history[:50]
                add_event("ENRICHMENT", "Transaction History Retrieved", f"Loaded {len(txn_history)} historical records")
            except Exception as e:
                msg = f"Failed to retrieve transaction history for {customer_id}: {e}"
                logger.warning(msg)
                warnings.append(msg)
                audit_logger.record_event(
                    event_type=AuditEventType.PARTIAL_FAILURE,
                    action="GET_TRANSACTION_HISTORY",
                    actor="INVESTIGATION_ENGINE",
                    payload={"customer_id": customer_id, "error": str(e)},
                )

        # 5. Graph Analytics (Multi-Hop Neighborhood, Shared Devices, Fraud Patterns)
        connected_entities: Dict[str, Any] = {}
        shared_devices: Dict[str, Any] = {}
        fraud_patterns: List[Dict[str, Any]] = []
        similar_cases: List[Dict[str, Any]] = []

        try:
            connected_entities = self._adapter.get_connected_entities(clean_txn_id, depth=2)
            add_event("GRAPH_ANALYTICS", "Connected Entities Traversed", f"Traversed depth 2 graph neighborhood: {connected_entities.get('total_connections', 0)} connections")
        except Exception as e:
            msg = f"Graph traversal failed for {clean_txn_id}: {e}"
            logger.warning(msg)
            warnings.append(msg)
            audit_logger.record_event(
                event_type=AuditEventType.PARTIAL_FAILURE,
                action="GET_CONNECTED_ENTITIES",
                actor="INVESTIGATION_ENGINE",
                payload={"transaction_id": clean_txn_id, "error": str(e)},
            )

        device_id = txn_data.get("device_id")
        if device_id and device_id != "UNKNOWN_DEVICE":
            try:
                shared_devices = self._adapter.find_shared_devices(device_id)
                add_event("GRAPH_ANALYTICS", "Shared Devices Analyzed", f"Evaluated device sharing for {device_id}")
            except Exception as e:
                msg = f"Shared device analysis failed for {device_id}: {e}"
                logger.warning(msg)
                warnings.append(msg)
                audit_logger.record_event(
                    event_type=AuditEventType.PARTIAL_FAILURE,
                    action="FIND_SHARED_DEVICES",
                    actor="INVESTIGATION_ENGINE",
                    payload={"device_id": device_id, "error": str(e)},
                )

        try:
            patterns_res = self._adapter.detect_fraud_patterns(clean_txn_id)
            fraud_patterns = patterns_res.get("patterns", [])
            add_event("GRAPH_ANALYTICS", "Fraud Typologies Evaluated", f"Identified {len(fraud_patterns)} topology pattern(s)")
        except Exception as e:
            msg = f"Fraud pattern detection failed for {clean_txn_id}: {e}"
            logger.warning(msg)
            warnings.append(msg)
            audit_logger.record_event(
                event_type=AuditEventType.PARTIAL_FAILURE,
                action="DETECT_FRAUD_PATTERNS",
                actor="INVESTIGATION_ENGINE",
                payload={"transaction_id": clean_txn_id, "error": str(e)},
            )

        try:
            cases_res = self._adapter.find_similar_cases(case_description=clean_txn_id, top_k=3)
            similar_cases = cases_res.get("similar_cases", [])
            add_event("GRAPH_ANALYTICS", "Historical Case Precedents Retrieved", f"Found {len(similar_cases)} similar case(s)")
        except Exception as e:
            msg = f"Similar case retrieval failed for {clean_txn_id}: {e}"
            logger.warning(msg)
            warnings.append(msg)
            audit_logger.record_event(
                event_type=AuditEventType.PARTIAL_FAILURE,
                action="FIND_SIMILAR_CASES",
                actor="INVESTIGATION_ENGINE",
                payload={"transaction_id": clean_txn_id, "error": str(e)},
            )

        # 6. GraphRAG Context Retrieval
        graphrag_context: Dict[str, Any] = {}
        try:
            graphrag_context = self._adapter.retrieve_investigation_context(
                transaction_id=clean_txn_id,
                customer_id=customer_id,
            )
            add_event("GRAPHRAG_CONTEXT", "GraphRAG Context Formatted", "Retrieved governing policies and structured case memory")
        except Exception as e:
            msg = f"GraphRAG retrieval failed for {clean_txn_id}: {e}"
            logger.warning(msg)
            warnings.append(msg)
            audit_logger.record_event(
                event_type=AuditEventType.PARTIAL_FAILURE,
                action="RETRIEVE_INVESTIGATION_CONTEXT",
                actor="INVESTIGATION_ENGINE",
                payload={"transaction_id": clean_txn_id, "error": str(e)},
            )

        # 7. Evidence Processing & Deterministic Deduplication
        evidence_items = self._evidence_processor.process_all(
            transaction_data=txn_data,
            customer_data=cust_data,
            transaction_history=txn_history,
            connected_entities=connected_entities,
            shared_devices=shared_devices,
            fraud_patterns=fraud_patterns,
            similar_cases=similar_cases,
            graphrag_context=graphrag_context,
            trigger_data=trigger,
        )

        audit_logger.record_event(
            event_type=AuditEventType.EVIDENCE_COLLECTED,
            action="EVIDENCE_PROCESSED",
            actor="INVESTIGATION_ENGINE",
            payload={
                "case_id": case_id,
                "evidence_count": len(evidence_items),
                "fact_count": sum(1 for e in evidence_items if e.fact_level == "FACT"),
                "observation_count": sum(1 for e in evidence_items if e.fact_level == "OBSERVATION"),
                "inference_count": sum(1 for e in evidence_items if e.fact_level == "INFERENCE"),
            },
        )
        add_event("EVIDENCE_PROCESSING", "Evidence Normalized & Deduplicated", f"Structured {len(evidence_items)} canonical evidence items")

        # 8. Investigation Status determination
        status = InvestigationStatus.PARTIAL if warnings else InvestigationStatus.COMPLETE
        end_time = int(time.time())

        add_event("INVESTIGATION_COMPLETE", f"Investigation {status.value}", f"Completed investigation with status {status.value}")

        audit_logger.record_event(
            event_type=AuditEventType.INVESTIGATION_COMPLETED,
            action="COMPLETE_INVESTIGATION",
            actor="INVESTIGATION_ENGINE",
            payload={"case_id": case_id, "transaction_id": clean_txn_id, "status": status.value, "warnings_count": len(warnings)},
        )

        # 9. Return typed InvestigationResult
        return InvestigationResult(
            case_id=case_id,
            transaction_id=clean_txn_id,
            status=status,
            transaction=txn_data,
            customer=cust_data,
            transaction_history=txn_history,
            connected_entities=connected_entities,
            graph_findings=[connected_entities] if connected_entities else [],
            fraud_pattern_evidence=fraud_patterns,
            similar_cases=similar_cases,
            graphrag_context=graphrag_context,
            evidence=evidence_items,
            warnings=warnings,
            timeline=timeline,
            created_at=start_time,
            completed_at=end_time,
        )


# Global singleton instance
investigation_engine = InvestigationEngine()
