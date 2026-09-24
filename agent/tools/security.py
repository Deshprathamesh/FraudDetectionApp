# ==============================================================================
# FraudGraph AI - Tool Security & Least Privilege Manager
# Workstream: Person 1 (Brain) - Stage 1 Foundation
# ==============================================================================

import re
from enum import Enum
from typing import Dict, Any, List, Set, Optional
from pydantic import BaseModel, Field

from backend.errors import UnauthorizedToolError
from backend.models.audit import audit_logger, AuditEventType


class ToolSecurityLevel(str, Enum):
    """Categorization of tool capability per Least Privilege principles."""
    READ = "READ"
    WRITE = "WRITE"


class ToolMetadata(BaseModel):
    """Explicit security and parameter metadata per tool."""
    name: str
    security_level: ToolSecurityLevel
    description: str
    allowed_params: Set[str]
    timeout_seconds: int = 15
    requires_authorization: bool = False


# SQL/GSQL Injection & Raw Command Patterns
DISALLOWED_INJECTION_PATTERNS = [
    re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|INTERPRET|GSQL|RUN\s+QUERY)\b", re.IGNORECASE),
    re.compile(r"[;]{1,}"), # Statement chaining
    re.compile(r"(--|/\*|\*/)"), # Comment injections
    re.compile(r"(\.\./|\.\.\\)"), # Path traversal
]

# Strict Identifier Pattern (Alphanumeric with hyphens, underscores, dots, or colons)
VALID_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:\-]+$")


class ToolSecurityManager:
    """
    Enforces application-level access control, least privilege, and input sanitization
    for all tool invocations made by the agent.
    """

    def __init__(self):
        self._registry: Dict[str, ToolMetadata] = {}
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """Registers the frozen Person 2 tool specifications."""
        tools = [
            ToolMetadata(
                name="get_transaction",
                security_level=ToolSecurityLevel.READ,
                description="Fetches transaction details by transaction_id",
                allowed_params={"transaction_id", "id"},
            ),
            ToolMetadata(
                name="get_customer",
                security_level=ToolSecurityLevel.READ,
                description="Fetches customer profile by customer_id",
                allowed_params={"customer_id", "id"},
            ),
            ToolMetadata(
                name="get_transaction_history",
                security_level=ToolSecurityLevel.READ,
                description="Retrieves historical transactions for customer or account",
                allowed_params={"customer_id", "account_id", "entity_id", "limit"},
            ),
            ToolMetadata(
                name="get_connected_entities",
                security_level=ToolSecurityLevel.READ,
                description="Traverses multi-hop entity graph neighborhood",
                allowed_params={"entity_id", "target_id", "depth", "limit"},
            ),
            ToolMetadata(
                name="find_shared_devices",
                security_level=ToolSecurityLevel.READ,
                description="Detects shared device accounts and syndicates",
                allowed_params={"device_id", "target_id", "entity_id"},
            ),
            ToolMetadata(
                name="detect_fraud_patterns",
                security_level=ToolSecurityLevel.READ,
                description="Evaluates graph topology for known fraud patterns",
                allowed_params={"transaction_id", "customer_id", "entity_id", "target_id"},
            ),
            ToolMetadata(
                name="find_similar_cases",
                security_level=ToolSecurityLevel.READ,
                description="Retrieves similar historical cases from memory",
                allowed_params={"case_description", "case_context", "query", "top_k", "limit"},
            ),
            ToolMetadata(
                name="get_policy_context",
                security_level=ToolSecurityLevel.READ,
                description="Retrieves governing fraud policy constraints",
                allowed_params={"action", "amount", "case_context", "pattern_id", "proposed_action", "query", "top_k"},
            ),
            ToolMetadata(
                name="retrieve_investigation_context",
                security_level=ToolSecurityLevel.READ,
                description="GraphRAG composite context retrieval",
                allowed_params={"transaction_id", "customer_id", "case_context", "pattern_id", "proposed_action", "amount"},
            ),
            ToolMetadata(
                name="write_case_to_graph",
                security_level=ToolSecurityLevel.WRITE,
                description="Commits investigation case and evidence to TigerGraph",
                allowed_params={"case_data", "payload"},
                requires_authorization=False, # Authorized in workflow state
            ),
        ]
        for t in tools:
            self._registry[t.name] = t

    def is_tool_registered(self, tool_name: str) -> bool:
        return tool_name in self._registry

    def get_tool_metadata(self, tool_name: str) -> Optional[ToolMetadata]:
        return self._registry.get(tool_name)

    def validate_tool_call(self, tool_name: str, kwargs: Dict[str, Any]) -> None:
        """
        Validates tool invocation against registered schema and security policies.
        Raises UnauthorizedToolError on any violation (fail-closed).
        """
        if tool_name not in self._registry:
            audit_logger.record_event(
                event_type=AuditEventType.SECURITY_VIOLATION,
                action=tool_name,
                payload={"reason": "UNREGISTERED_TOOL", "args": list(kwargs.keys())},
                status="BLOCKED",
            )
            raise UnauthorizedToolError(
                tool_name=tool_name,
                reason=f"Tool '{tool_name}' is not in the authorized tool registry.",
            )

        meta = self._registry[tool_name]

        # Verify parameter names against allowed params
        for param_key in kwargs:
            if param_key not in meta.allowed_params:
                audit_logger.record_event(
                    event_type=AuditEventType.SECURITY_VIOLATION,
                    action=tool_name,
                    payload={"reason": "DISALLOWED_PARAMETER", "param": param_key},
                    status="BLOCKED",
                )
                raise UnauthorizedToolError(
                    tool_name=tool_name,
                    reason=f"Parameter '{param_key}' is not allowed for tool '{tool_name}'. Allowed: {sorted(meta.allowed_params)}",
                )

        # Inspect parameter values for injection and malicious syntax
        for k, v in kwargs.items():
            if isinstance(v, str):
                # Check for raw GSQL or SQL injection signatures
                for pattern in DISALLOWED_INJECTION_PATTERNS:
                    if pattern.search(v):
                        audit_logger.record_event(
                            event_type=AuditEventType.SECURITY_VIOLATION,
                            action=tool_name,
                            payload={"reason": "INJECTION_ATTEMPT_DETECTED", "param": k},
                            status="BLOCKED",
                        )
                        raise UnauthorizedToolError(
                            tool_name=tool_name,
                            reason=f"Input for parameter '{k}' failed security validation (forbidden token or command syntax detected).",
                        )

                # For identifier parameters, enforce strict ID character set
                if "id" in k.lower() and not VALID_ID_PATTERN.match(v):
                    audit_logger.record_event(
                        event_type=AuditEventType.SECURITY_VIOLATION,
                        action=tool_name,
                        payload={"reason": "INVALID_IDENTIFIER_FORMAT", "param": k, "value": v},
                        status="BLOCKED",
                    )
                    raise UnauthorizedToolError(
                        tool_name=tool_name,
                        reason=f"Identifier parameter '{k}' contains invalid characters. Must be alphanumeric with standard delimiters.",
                    )


# Global tool security manager
tool_security_manager = ToolSecurityManager()
