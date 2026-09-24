# ==============================================================================
# FraudGraph AI - Person 2 Graph & GraphRAG Adapter Layer
# Workstream: Person 1 (Brain) - Stage 1 Foundation
# ==============================================================================

import logging
from typing import Dict, Any, Optional

from tigergraph.tools import get_graph_tools
from graphrag.pipeline import pipeline as graphrag_pipeline
from backend.errors import (
    TransactionNotFoundException,
    CustomerNotFoundException,
    CaseNotFoundException,
    GraphQueryFailedException,
    UnauthorizedToolError,
)
from backend.models.audit import audit_logger, AuditEventType
from agent.tools.security import tool_security_manager

logger = logging.getLogger("fraudgraph.graph_adapter")


class Person2GraphAdapter:
    """
    Adapter layer encapsulating all interactions with Person 2's TigerGraph tools
    and GraphRAG pipeline. Enforces parameter security, least-privilege tool checks,
    audit event logging, and Section 9 exception translation.
    """

    def __init__(self):
        self._tools = get_graph_tools()
        self._graphrag = graphrag_pipeline

    def get_transaction(self, transaction_id: str) -> Dict[str, Any]:
        """Fetches transaction details from TigerGraph."""
        tool_security_manager.validate_tool_call("get_transaction", {"transaction_id": transaction_id})
        audit_logger.record_event(
            event_type=AuditEventType.TOOL_CALLED,
            action="get_transaction",
            actor="AGENT",
            payload={"transaction_id": transaction_id},
        )
        try:
            res = self._tools["get_transaction"](transaction_id)
            if isinstance(res, dict) and "error" in res:
                raise TransactionNotFoundException(
                    transaction_id=transaction_id,
                    message=res["error"].get("message"),
                )
            return res.model_dump() if hasattr(res, "model_dump") else dict(res)
        except (TransactionNotFoundException, UnauthorizedToolError):
            raise
        except Exception as e:
            logger.error(f"Error calling get_transaction({transaction_id}): {e}", exc_info=False)
            raise GraphQueryFailedException("get_transaction", details={"transaction_id": transaction_id})

    def get_customer(self, customer_id: str) -> Dict[str, Any]:
        """Fetches customer details from TigerGraph."""
        tool_security_manager.validate_tool_call("get_customer", {"customer_id": customer_id})
        audit_logger.record_event(
            event_type=AuditEventType.TOOL_CALLED,
            action="get_customer",
            actor="AGENT",
            payload={"customer_id": customer_id},
        )
        try:
            res = self._tools["get_customer"](customer_id)
            if isinstance(res, dict) and "error" in res:
                raise CustomerNotFoundException(
                    customer_id=customer_id,
                    message=res["error"].get("message"),
                )
            return res.model_dump() if hasattr(res, "model_dump") else dict(res)
        except (CustomerNotFoundException, UnauthorizedToolError):
            raise
        except Exception as e:
            logger.error(f"Error calling get_customer({customer_id}): {e}", exc_info=False)
            raise GraphQueryFailedException("get_customer", details={"customer_id": customer_id})

    def get_transaction_history(self, customer_id: str, limit: int = 50) -> Dict[str, Any]:
        """Retrieves transaction history for a customer."""
        tool_security_manager.validate_tool_call("get_transaction_history", {"customer_id": customer_id, "limit": limit})
        audit_logger.record_event(
            event_type=AuditEventType.TOOL_CALLED,
            action="get_transaction_history",
            actor="AGENT",
            payload={"customer_id": customer_id, "limit": limit},
        )
        try:
            res = self._tools["get_transaction_history"](customer_id=customer_id)
            return res.model_dump() if hasattr(res, "model_dump") else dict(res)
        except UnauthorizedToolError:
            raise
        except Exception as e:
            logger.error(f"Error calling get_transaction_history({customer_id}): {e}", exc_info=False)
            raise GraphQueryFailedException("get_transaction_history", details={"customer_id": customer_id})

    def get_connected_entities(self, entity_id: str, depth: int = 2) -> Dict[str, Any]:
        """Traverses multi-hop connected graph topology for an entity."""
        tool_security_manager.validate_tool_call("get_connected_entities", {"entity_id": entity_id, "depth": depth})
        audit_logger.record_event(
            event_type=AuditEventType.TOOL_CALLED,
            action="get_connected_entities",
            actor="AGENT",
            payload={"entity_id": entity_id, "depth": depth},
        )
        try:
            res = self._tools["get_connected_entities"](entity_id, depth=depth)
            return res.model_dump() if hasattr(res, "model_dump") else dict(res)
        except UnauthorizedToolError:
            raise
        except Exception as e:
            logger.error(f"Error calling get_connected_entities({entity_id}): {e}", exc_info=False)
            raise GraphQueryFailedException("get_connected_entities", details={"entity_id": entity_id})

    def find_shared_devices(self, device_id: str) -> Dict[str, Any]:
        """Detects shared device accounts and syndicate linkages."""
        tool_security_manager.validate_tool_call("find_shared_devices", {"device_id": device_id})
        audit_logger.record_event(
            event_type=AuditEventType.TOOL_CALLED,
            action="find_shared_devices",
            actor="AGENT",
            payload={"device_id": device_id},
        )
        try:
            res = self._tools["find_shared_devices"](device_id)
            return res.model_dump() if hasattr(res, "model_dump") else dict(res)
        except UnauthorizedToolError:
            raise
        except Exception as e:
            logger.error(f"Error calling find_shared_devices({device_id}): {e}", exc_info=False)
            raise GraphQueryFailedException("find_shared_devices", details={"device_id": device_id})

    def detect_fraud_patterns(self, transaction_id: str) -> Dict[str, Any]:
        """Evaluates graph topology for known fraud patterns."""
        tool_security_manager.validate_tool_call("detect_fraud_patterns", {"transaction_id": transaction_id})
        audit_logger.record_event(
            event_type=AuditEventType.TOOL_CALLED,
            action="detect_fraud_patterns",
            actor="AGENT",
            payload={"transaction_id": transaction_id},
        )
        try:
            res = self._tools["detect_fraud_patterns"](transaction_id)
            return res.model_dump() if hasattr(res, "model_dump") else dict(res)
        except UnauthorizedToolError:
            raise
        except Exception as e:
            logger.error(f"Error calling detect_fraud_patterns({transaction_id}): {e}", exc_info=False)
            raise GraphQueryFailedException("detect_fraud_patterns", details={"transaction_id": transaction_id})

    def find_similar_cases(self, case_description: str, top_k: int = 3) -> Dict[str, Any]:
        """Retrieves similar historical cases from memory."""
        tool_security_manager.validate_tool_call("find_similar_cases", {"case_description": case_description, "top_k": top_k})
        audit_logger.record_event(
            event_type=AuditEventType.TOOL_CALLED,
            action="find_similar_cases",
            actor="AGENT",
            payload={"case_description": case_description, "top_k": top_k},
        )
        try:
            res = self._tools["find_similar_cases"](case_description)
            return res.model_dump() if hasattr(res, "model_dump") else dict(res)
        except UnauthorizedToolError:
            raise
        except Exception as e:
            logger.error(f"Error calling find_similar_cases: {e}", exc_info=False)
            raise GraphQueryFailedException("find_similar_cases")

    def get_policy_context(self, action: str, amount: float = 0.0) -> Dict[str, Any]:
        """Retrieves governing fraud policy constraints."""
        tool_security_manager.validate_tool_call("get_policy_context", {"action": action, "amount": amount})
        audit_logger.record_event(
            event_type=AuditEventType.TOOL_CALLED,
            action="get_policy_context",
            actor="AGENT",
            payload={"action": action, "amount": amount},
        )
        try:
            res = self._tools["get_policy_context"](action=action, amount=amount)
            return res.model_dump() if hasattr(res, "model_dump") else dict(res)
        except UnauthorizedToolError:
            raise
        except Exception as e:
            logger.error(f"Error calling get_policy_context({action}, {amount}): {e}", exc_info=False)
            raise GraphQueryFailedException("get_policy_context")

    def retrieve_investigation_context(
        self,
        transaction_id: str,
        customer_id: Optional[str] = None,
        pattern_id: Optional[str] = None,
        proposed_action: Optional[str] = None,
        amount: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Retrieves composite GraphRAG context (grounded policy + case precedent)
        and returns both prompt prose and structured models.
        """
        call_params = {"transaction_id": transaction_id}
        if customer_id:
            call_params["customer_id"] = customer_id
        if pattern_id:
            call_params["pattern_id"] = pattern_id
        if proposed_action:
            call_params["proposed_action"] = proposed_action
        if amount is not None:
            call_params["amount"] = amount

        tool_security_manager.validate_tool_call("retrieve_investigation_context", call_params)
        audit_logger.record_event(
            event_type=AuditEventType.TOOL_CALLED,
            action="retrieve_investigation_context",
            actor="AGENT",
            payload=call_params,
        )
        try:
            structured = self._graphrag.get_structured_context(
                case_context=transaction_id,
                pattern_id=pattern_id,
                proposed_action=proposed_action,
                amount=amount,
            )
            return {
                "prompt_context": structured["prompt_context"],
                "policy": structured["policy"].model_dump() if hasattr(structured["policy"], "model_dump") else structured["policy"],
                "similar_cases": structured["similar_cases"].model_dump() if hasattr(structured["similar_cases"], "model_dump") else structured["similar_cases"],
            }
        except UnauthorizedToolError:
            raise
        except Exception as e:
            logger.error(f"Error calling retrieve_investigation_context({transaction_id}): {e}", exc_info=False)
            raise GraphQueryFailedException("retrieve_investigation_context", details={"transaction_id": transaction_id})

    def write_case_to_graph(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        """Writes case record and evidence links to TigerGraph."""
        tool_security_manager.validate_tool_call("write_case_to_graph", {"case_data": case_data})
        audit_logger.record_event(
            event_type=AuditEventType.TOOL_CALLED,
            action="write_case_to_graph",
            actor="AGENT",
            payload={"case_id": case_data.get("case_id")},
        )
        try:
            res = self._tools["write_case_to_graph"](case_data)
            if isinstance(res, dict) and "error" in res:
                raise CaseNotFoundException(
                    case_id=case_data.get("case_id", "UNKNOWN"),
                    message=res["error"].get("message"),
                )
            return res.model_dump() if hasattr(res, "model_dump") else dict(res)
        except (CaseNotFoundException, UnauthorizedToolError):
            raise
        except Exception as e:
            logger.error(f"Error calling write_case_to_graph: {e}", exc_info=False)
            raise GraphQueryFailedException("write_case_to_graph", details={"case_id": case_data.get("case_id")})


# Global adapter instance
graph_adapter = Person2GraphAdapter()
