# ==============================================================================
# FraudGraph AI - Case Memory Persistence Adapter
# Workstream: Person 1 (Brain) - Stage 6 Execution & Case Memory
# ==============================================================================

import time
import logging
from typing import Dict, Any, List, Optional, Union

from backend.models.domain import (
    InvestigationCase,
    EvidenceItem,
    FraudPattern,
    ActionType,
)
from backend.models.audit import audit_logger, AuditEventType
from backend.execution.models import ExecutionResult
from agent.tools.graph_adapter import graph_adapter

logger = logging.getLogger("fraudgraph.case_memory")


class CaseMemoryAdapter:
    """
    Adapter responsible for persisting completed fraud investigation cases,
    their evidentiary topology, and execution records into TigerGraph case memory.
    Implements fault isolation: case write failures do NOT crash remediation actions.
    """

    def __init__(self, adapter=None):
        self._graph_adapter = adapter or graph_adapter

    def persist_case(
        self,
        case: Union[InvestigationCase, Dict[str, Any]],
        execution_results: Optional[List[Union[ExecutionResult, Dict[str, Any]]]] = None,
        actor: str = "CASE_PERSISTENCE_SERVICE",
    ) -> Dict[str, Any]:
        """
        Normalizes, validates, and commits an investigation case into TigerGraph.
        Returns a structured persistence receipt.
        """
        payload = self._build_case_payload(case, execution_results)
        case_id = payload.get("case_id", "UNKNOWN")

        # 1. Record write requested audit event
        audit_logger.record_event(
            event_type=AuditEventType.CASE_MEMORY_WRITE_REQUESTED,
            case_id=case_id,
            action="write_case_to_graph",
            actor=actor,
            payload={
                "transaction_id": payload.get("transaction_id"),
                "evidence_count": len(payload.get("evidence", [])),
                "pattern_count": len(payload.get("fraud_patterns", [])),
                "action_count": len(payload.get("action_records", [])),
            },
        )

        try:
            # 2. Invoke Person 2's graph write via adapter
            res = self._graph_adapter.write_case_to_graph(payload)

            graph_ids = res.get("graph_ids", [])
            nodes_written = res.get("nodes_written", 0)
            edges_written = res.get("edges_written", 0)
            graph_case_id = graph_ids[0] if graph_ids else f"vertex_fraudcase_{case_id}"

            # 3. Update case object if provided
            if isinstance(case, InvestigationCase):
                case.written_to_graph = True
                case.graph_case_id = graph_case_id

            # 4. Record write succeeded audit event
            audit_logger.record_event(
                event_type=AuditEventType.CASE_MEMORY_WRITTEN,
                case_id=case_id,
                action="write_case_to_graph",
                actor=actor,
                payload={
                    "graph_case_id": graph_case_id,
                    "nodes_written": nodes_written,
                    "edges_written": edges_written,
                    "status": "SUCCESS",
                },
                status="SUCCESS",
            )

            logger.info(f"Successfully persisted case '{case_id}' to TigerGraph case memory.")
            return {
                "success": True,
                "case_id": case_id,
                "graph_case_id": graph_case_id,
                "graph_ids": graph_ids,
                "nodes_written": nodes_written,
                "edges_written": edges_written,
                "message": res.get("message", f"Case '{case_id}' committed to TigerGraph."),
            }

        except Exception as e:
            # Fault isolation: TigerGraph write failure does NOT mark remediation failed
            logger.error(f"Failed to persist case '{case_id}' to TigerGraph case memory: {e}", exc_info=False)

            if isinstance(case, InvestigationCase):
                case.written_to_graph = False

            audit_logger.record_event(
                event_type=AuditEventType.CASE_MEMORY_WRITE_FAILED,
                case_id=case_id,
                action="write_case_to_graph",
                actor=actor,
                payload={"error": str(e), "status": "FAILED"},
                status="FAILED",
            )

            return {
                "success": False,
                "case_id": case_id,
                "graph_case_id": None,
                "graph_ids": [],
                "nodes_written": 0,
                "edges_written": 0,
                "error": str(e),
                "message": f"Case memory write failed: {str(e)}",
            }

    def _build_case_payload(
        self,
        case: Union[InvestigationCase, Dict[str, Any]],
        execution_results: Optional[List[Union[ExecutionResult, Dict[str, Any]]]] = None,
    ) -> Dict[str, Any]:
        """Normalizes heterogeneous case models into the Person 2 graph write schema."""
        if isinstance(case, InvestigationCase):
            case_id = case.case_id
            transaction_id = case.transaction_id
            customer_id = case.customer_id or "UNKNOWN"
            status = case.status.value if hasattr(case.status, "value") else str(case.status)
            risk_score = case.risk_score or 0.0
            confidence = case.confidence or 1.0

            evidence_list = []
            for ev in case.evidence:
                if isinstance(ev, EvidenceItem):
                    evidence_list.append(ev.model_dump())
                elif isinstance(ev, dict):
                    evidence_list.append(dict(ev))

            pattern_list = []
            for fp in case.fraud_patterns:
                if isinstance(fp, FraudPattern):
                    pattern_list.append(fp.model_dump())
                elif isinstance(fp, dict):
                    pattern_list.append(dict(fp))

        elif isinstance(case, dict):
            case_id = case.get("case_id", "CASE-UNKNOWN")
            transaction_id = case.get("transaction_id", "TXN-UNKNOWN")
            customer_id = case.get("customer_id") or "UNKNOWN"
            status = case.get("status", "RESOLVED")
            risk_score = case.get("risk_score", 0.0)
            confidence = case.get("confidence", 1.0)
            evidence_list = list(case.get("evidence", []))
            pattern_list = list(case.get("fraud_patterns", []))
        else:
            raise ValueError(f"Unsupported case type: {type(case)}")

        # Normalize action records
        action_records = []
        if execution_results:
            for er in execution_results:
                if isinstance(er, ExecutionResult):
                    action_records.append({
                        "action_id": er.execution_id,
                        "action_type": er.action.value if isinstance(er.action, ActionType) else str(er.action),
                        "status": er.status.value if hasattr(er.status, "value") else str(er.status),
                        "target_resource": er.target_resource,
                        "executed_at": er.executed_at,
                        "simulated": er.simulated,
                    })
                elif isinstance(er, dict):
                    action_records.append(dict(er))

        return {
            "case_id": case_id,
            "transaction_id": transaction_id,
            "customer_id": customer_id,
            "status": status,
            "risk_score": risk_score,
            "confidence": confidence,
            "evidence": evidence_list,
            "fraud_patterns": pattern_list,
            "action_records": action_records,
            "updated_at": int(time.time()),
        }


# Global singleton instance
case_memory_adapter = CaseMemoryAdapter()
