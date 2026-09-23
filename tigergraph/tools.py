# ==============================================================================
# FraudGraph AI - TigerGraph Tools Contract Implementation
# Workstream: Person 2 (Graph)
#
# Exposes clean Python tool functions with Pydantic response models matching
# Section 7 of the Integration Specification exactly.
# Consumed by Person 1 (LangGraph Agent) & Person 3 (Frontend / Backend).
# ==============================================================================

import logging
from typing import Dict, Any, List, Optional, Callable, Union
from pydantic import BaseModel, Field
from tigergraph import config
from tigergraph.mock_provider import mock_provider, GraphError

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------------------
# Pydantic Response Models matching Section 7 & Section 5 Specification
# ------------------------------------------------------------------------------

class TransactionDetailResponse(BaseModel):
    transaction_id: str
    customer_id: str
    account_id: str
    amount: float
    currency: str = "USD"
    timestamp: int
    risk_score: float
    channel: str
    card_network: str
    merchant_name: str
    device_id: str
    ip_str: str
    dist1: Optional[float] = None
    dist2: Optional[float] = None
    c1: Optional[int] = None
    c2: Optional[int] = None
    c3: Optional[int] = None
    c4: Optional[int] = None
    c5: Optional[int] = None
    c6: Optional[int] = None
    c7: Optional[int] = None
    c8: Optional[int] = None
    c9: Optional[int] = None
    c10: Optional[int] = None
    c11: Optional[int] = None
    c12: Optional[int] = None
    c13: Optional[int] = None
    c14: Optional[int] = None


class CustomerDetailResponse(BaseModel):
    customer_id: str
    name: str
    risk_tier: str
    created_at: int
    accounts: List[str] = Field(default_factory=list)
    linked_cards: List[str] = Field(default_factory=list)
    email: str
    risk_score: float


class TransactionHistoryItem(BaseModel):
    transaction_id: str
    amount: float
    timestamp: int
    merchant_name: str
    risk_score: float
    channel: str


class TransactionHistorySummary(BaseModel):
    total_transactions: int
    avg_amount: float
    max_amount: float
    velocity_30d: int
    risk_distribution: Dict[str, int] = Field(default_factory=dict)


class TransactionHistoryResponse(BaseModel):
    transactions: List[TransactionHistoryItem] = Field(default_factory=list)
    summary: TransactionHistorySummary


class GraphNode(BaseModel):
    id: str
    label: str
    type: str
    risk_score: float


class GraphEdge(BaseModel):
    source: str
    target: str
    type: str


class ConnectedEntitiesResponse(BaseModel):
    nodes: List[GraphNode] = Field(default_factory=list)
    edges: List[GraphEdge] = Field(default_factory=list)


class SharedDeviceItem(BaseModel):
    device_id: str
    linked_accounts: int
    risk_score: float
    associated_account_ids: Optional[List[str]] = None


class SharedDevicesResponse(BaseModel):
    devices: List[SharedDeviceItem] = Field(default_factory=list)


class FraudPatternItem(BaseModel):
    pattern_id: str
    name: str
    description: str
    evidence_refs: List[str] = Field(default_factory=list)
    confidence: float


class DetectFraudPatternsResponse(BaseModel):
    patterns: List[FraudPatternItem] = Field(default_factory=list)


class SimilarCaseItem(BaseModel):
    case_id: str
    similarity_score: float
    status: str
    risk_score: float
    outcome: str
    matched_patterns: List[str] = Field(default_factory=list)
    key_findings: Optional[str] = None


class SimilarCasesResponse(BaseModel):
    similar_cases: List[SimilarCaseItem] = Field(default_factory=list)


class PolicyContextResponse(BaseModel):
    policy_id: str
    policy_basis: str
    approval_required: bool
    sar_required: bool
    confidence_threshold: float
    allowed_actions: List[str] = Field(default_factory=list)
    escalation_notes: Optional[str] = None


class WriteCaseResponse(BaseModel):
    status: str
    case_id: str
    graph_ids: List[str] = Field(default_factory=list)
    nodes_written: int
    edges_written: int
    message: str


# ------------------------------------------------------------------------------
# 9 Clean Python Tool Functions matching Section 7 Tool Contract
# ------------------------------------------------------------------------------

def get_transaction(transaction_id: str) -> Union[TransactionDetailResponse, Dict[str, Any]]:
    """
    Tool 1: get_transaction
    Input: transaction_id (string)
    Output: Transaction details including amount, risk score, merchant, device, and card network.
            Returns Section 9 error dictionary on failure or unknown ID.
    """
    try:
        raw_data = mock_provider.get_transaction(transaction_id=transaction_id)
        return TransactionDetailResponse(**raw_data)
    except GraphError as ge:
        return ge.to_dict()
    except Exception as e:
        return {
            "error": {
                "code": "GRAPH_QUERY_FAILED",
                "message": str(e),
                "details": {"transaction_id": transaction_id}
            }
        }


def get_customer(customer_id: str) -> Union[CustomerDetailResponse, Dict[str, Any]]:
    """
    Tool 2: get_customer
    Input: customer_id (string)
    Output: Customer details including profile, risk tier, linked accounts, and card tokens.
            Returns Section 9 error dictionary on failure or unknown ID.
    """
    try:
        raw_data = mock_provider.get_customer(customer_id=customer_id)
        return CustomerDetailResponse(**raw_data)
    except GraphError as ge:
        return ge.to_dict()
    except Exception as e:
        return {
            "error": {
                "code": "GRAPH_QUERY_FAILED",
                "message": str(e),
                "details": {"customer_id": customer_id}
            }
        }


def get_transaction_history(
    entity_id: Optional[str] = None,
    customer_id: Optional[str] = None,
    account_id: Optional[str] = None,
    limit: int = 10
) -> Union[TransactionHistoryResponse, Dict[str, Any]]:
    """
    Tool 3: get_transaction_history
    Input: customer/account id (string)
    Output: Transaction list + behavioral profile summary (velocity, average amount, risk distribution).
            Returns Section 9 error dictionary on failure.
    """
    target_id = entity_id or customer_id or account_id or ""
    try:
        raw_data = mock_provider.get_transaction_history(entity_id=target_id, limit=limit)
        return TransactionHistoryResponse(**raw_data)
    except GraphError as ge:
        return ge.to_dict()
    except Exception as e:
        return {
            "error": {
                "code": "GRAPH_QUERY_FAILED",
                "message": str(e),
                "details": {"entity_id": target_id}
            }
        }


def get_connected_entities(entity_id: str, depth: int = 1) -> Union[ConnectedEntitiesResponse, Dict[str, Any]]:
    """
    Tool 4: get_connected_entities
    Input: entity_id (string), depth (int)
    Output: Subgraph nodes + edges for investigative network visualization.
            Returns Section 9 error dictionary on failure.
    """
    try:
        raw_data = mock_provider.get_connected_entities(entity_id=entity_id, depth=depth)
        return ConnectedEntitiesResponse(**raw_data)
    except GraphError as ge:
        return ge.to_dict()
    except Exception as e:
        return {
            "error": {
                "code": "GRAPH_QUERY_FAILED",
                "message": str(e),
                "details": {"entity_id": entity_id}
            }
        }


def find_shared_devices(
    entity_id: Optional[str] = None,
    customer_id: Optional[str] = None,
    account_id: Optional[str] = None,
    device_id: Optional[str] = None
) -> Union[SharedDevicesResponse, Dict[str, Any]]:
    """
    Tool 5: find_shared_devices
    Input: customer/account/device id (string)
    Output: Connected devices and linked account counts indicating syndicate or device hopping rings.
            Returns Section 9 error dictionary on failure.
    """
    target_id = entity_id or device_id or customer_id or account_id or ""
    try:
        raw_data = mock_provider.find_shared_devices(entity_id=target_id)
        return SharedDevicesResponse(**raw_data)
    except GraphError as ge:
        return ge.to_dict()
    except Exception as e:
        return {
            "error": {
                "code": "GRAPH_QUERY_FAILED",
                "message": str(e),
                "details": {"entity_id": target_id}
            }
        }


def detect_fraud_patterns(
    case_context: Optional[str] = None,
    entity_id: Optional[str] = None,
    transaction_id: Optional[str] = None
) -> Union[DetectFraudPatternsResponse, Dict[str, Any]]:
    """
    Tool 6: detect_fraud_patterns
    Input: case/entity context (string)
    Output: Detected fraud patterns and linked evidence references.
            Returns Section 9 error dictionary on failure.
    """
    target_id = case_context or entity_id or transaction_id or ""
    try:
        raw_data = mock_provider.detect_fraud_patterns(entity_id=target_id)
        return DetectFraudPatternsResponse(**raw_data)
    except GraphError as ge:
        return ge.to_dict()
    except Exception as e:
        return {
            "error": {
                "code": "GRAPH_QUERY_FAILED",
                "message": str(e),
                "details": {"entity_id": target_id}
            }
        }


def find_similar_cases(
    case_context: Optional[str] = None,
    case_id: Optional[str] = None
) -> Union[SimilarCasesResponse, Dict[str, Any]]:
    """
    Tool 7: find_similar_cases
    Input: case context (string)
    Output: Similar historical cases, matched patterns, and historical outcomes.
            Returns Section 9 error dictionary on failure.
    """
    target_ctx = case_context or case_id or ""
    try:
        raw_data = mock_provider.find_similar_cases(case_context=target_ctx)
        return SimilarCasesResponse(**raw_data)
    except GraphError as ge:
        return ge.to_dict()
    except Exception as e:
        return {
            "error": {
                "code": "GRAPH_QUERY_FAILED",
                "message": str(e),
                "details": {"case_context": target_ctx}
            }
        }


def get_policy_context(
    action: Optional[str] = None,
    pattern_id: Optional[str] = None,
    amount: Optional[float] = None,
    case_context: Optional[str] = None
) -> Union[PolicyContextResponse, Dict[str, Any]]:
    """
    Tool 8: get_policy_context
    Input: case/pattern/action (strings, optional amount)
    Output: Relevant policy context, SAR filing obligations, and approval requirements.
            Returns Section 9 error dictionary on failure.
    """
    target_action = action or case_context or "MONITOR"
    try:
        raw_data = mock_provider.get_policy_context(
            action=target_action,
            pattern_id=pattern_id,
            amount=amount
        )
        return PolicyContextResponse(**raw_data)
    except GraphError as ge:
        return ge.to_dict()
    except Exception as e:
        return {
            "error": {
                "code": "GRAPH_QUERY_FAILED",
                "message": str(e),
                "details": {"action": target_action}
            }
        }


def write_case_to_graph(case_payload: Optional[Dict[str, Any]] = None, **kwargs) -> Union[WriteCaseResponse, Dict[str, Any]]:
    """
    Tool 9: write_case_to_graph
    Input: case payload matching Case schema (dict)
    Output: Write status, graph IDs, and node/edge commit counts in TigerGraph case memory.
            Returns Section 9 error dictionary on failure.
    """
    payload = case_payload if case_payload is not None else kwargs
    if not payload.get("case_id"):
        return {
            "error": {
                "code": "CASE_NOT_FOUND",
                "message": "Case payload missing required 'case_id' field.",
                "details": {"received_payload": payload}
            }
        }
    try:
        if not getattr(config, "USE_MOCK_GRAPH", True):
            try:
                from tigergraph.client import live_client
                raw_data = live_client.write_case_to_graph(case_payload=payload)
                return WriteCaseResponse(**raw_data)
            except Exception as live_err:
                logger.warning("Live graph write failed, falling back to mock provider: %s", live_err)
        raw_data = mock_provider.write_case_to_graph(case_payload=payload)
        return WriteCaseResponse(**raw_data)
    except GraphError as ge:
        return ge.to_dict()
    except Exception as e:
        return {
            "error": {
                "code": "GRAPH_QUERY_FAILED",
                "message": str(e),
                "details": {"case_id": payload.get("case_id", "unknown")}
            }
        }


# ------------------------------------------------------------------------------
# Single Import Point for Agent Tool Registry
# ------------------------------------------------------------------------------

def get_graph_tools() -> Dict[str, Callable]:
    """
    Single import point returning the complete suite of 9 graph tools.
    Usage:
        from tigergraph.tools import get_graph_tools
        tools = get_graph_tools()
        txn = tools["get_transaction"]("TXN-104829")
    """
    return {
        "get_transaction": get_transaction,
        "get_customer": get_customer,
        "get_transaction_history": get_transaction_history,
        "get_connected_entities": get_connected_entities,
        "find_shared_devices": find_shared_devices,
        "detect_fraud_patterns": detect_fraud_patterns,
        "find_similar_cases": find_similar_cases,
        "get_policy_context": get_policy_context,
        "write_case_to_graph": write_case_to_graph,
    }


__all__ = [
    "get_graph_tools",
    "get_transaction",
    "get_customer",
    "get_transaction_history",
    "get_connected_entities",
    "find_shared_devices",
    "detect_fraud_patterns",
    "find_similar_cases",
    "get_policy_context",
    "write_case_to_graph",
    "TransactionDetailResponse",
    "CustomerDetailResponse",
    "TransactionHistoryResponse",
    "ConnectedEntitiesResponse",
    "SharedDevicesResponse",
    "DetectFraudPatternsResponse",
    "SimilarCasesResponse",
    "PolicyContextResponse",
    "WriteCaseResponse",
    "GraphError"
]
