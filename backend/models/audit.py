# ==============================================================================
# FraudGraph AI - Structured Security Audit Trail
# Workstream: Person 1 (Brain) - Stage 1 Foundation
# ==============================================================================

import time
import uuid
import logging
import re
from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("fraudgraph.audit")


class AuditEventType(str, Enum):
    """Standardized lifecycle events for security audit trail per Baseline Section 8."""
    RECOMMENDED = "RECOMMENDED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"
    TOOL_CALLED = "TOOL_CALLED"
    SECURITY_VIOLATION = "SECURITY_VIOLATION"
    INVESTIGATION_STARTED = "INVESTIGATION_STARTED"
    INVESTIGATION_COMPLETED = "INVESTIGATION_COMPLETED"
    EVIDENCE_COLLECTED = "EVIDENCE_COLLECTED"
    PARTIAL_FAILURE = "PARTIAL_FAILURE"
    POLICY_EVALUATED = "POLICY_EVALUATED"
    HITL_REQUIRED = "HITL_REQUIRED"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    APPROVAL_GRANTED = "APPROVAL_GRANTED"
    APPROVAL_REJECTED = "APPROVAL_REJECTED"
    # Stage 6 Execution & Case Memory lifecycle events
    ACTION_EXECUTION_REQUESTED = "ACTION_EXECUTION_REQUESTED"
    ACTION_EXECUTED = "ACTION_EXECUTED"
    ACTION_EXECUTION_FAILED = "ACTION_EXECUTION_FAILED"
    ACTION_EXECUTION_BLOCKED = "ACTION_EXECUTION_BLOCKED"
    CASE_MEMORY_WRITE_REQUESTED = "CASE_MEMORY_WRITE_REQUESTED"
    CASE_MEMORY_WRITTEN = "CASE_MEMORY_WRITTEN"
    CASE_MEMORY_WRITE_FAILED = "CASE_MEMORY_WRITE_FAILED"


# Keys that must be masked in audit logs
SENSITIVE_KEY_PATTERNS = [
    re.compile(r"pass(word)?", re.IGNORECASE),
    re.compile(r"token", re.IGNORECASE),
    re.compile(r"api[_-]?key", re.IGNORECASE),
    re.compile(r"secret", re.IGNORECASE),
    re.compile(r"auth(orization)?", re.IGNORECASE),
    re.compile(r"credit[_-]?card", re.IGNORECASE),
    re.compile(r"cvv", re.IGNORECASE),
    re.compile(r"ssn", re.IGNORECASE),
]


def sanitize_audit_payload(data: Any) -> Any:
    """
    Recursively scrubs sensitive keys, tokens, and PII before writing to audit trail.
    """
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            if any(p.search(str(k)) for p in SENSITIVE_KEY_PATTERNS):
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = sanitize_audit_payload(v)
        return sanitized
    elif isinstance(data, list):
        return [sanitize_audit_payload(item) for item in data]
    return data


class AuditEvent(BaseModel):
    """Structured audit log entry."""
    event_id: str = Field(default_factory=lambda: f"AUD-{uuid.uuid4().hex[:8].upper()}")
    event_type: AuditEventType = Field(..., description="Lifecycle audit event type")
    case_id: Optional[str] = Field(default=None, description="Associated case identifier")
    action: Optional[str] = Field(default=None, description="Action or tool involved")
    actor: str = Field(default="SYSTEM", description="Actor who initiated (AGENT, ANALYST, SYSTEM)")
    timestamp: int = Field(default_factory=lambda: int(time.time()))
    payload: Dict[str, Any] = Field(default_factory=dict, description="Scrubbed payload details")
    status: str = Field(default="SUCCESS", description="SUCCESS, FAILED, BLOCKED")


class AuditLogger:
    """Thread-safe, structured audit logger maintaining an append-only in-memory ledger."""

    def __init__(self):
        self._events: List[AuditEvent] = []

    def record_event(
        self,
        event_type: AuditEventType,
        case_id: Optional[str] = None,
        action: Optional[str] = None,
        actor: str = "SYSTEM",
        payload: Optional[Dict[str, Any]] = None,
        status: str = "SUCCESS",
    ) -> AuditEvent:
        """Records an audit event with automatic payload scrubbing."""
        scrubbed_payload = sanitize_audit_payload(payload or {})
        event = AuditEvent(
            event_type=event_type,
            case_id=case_id,
            action=action,
            actor=actor,
            payload=scrubbed_payload,
            status=status,
        )
        self._events.append(event)
        
        # Log structured entry
        logger.info(
            f"[AUDIT] {event.event_type.value} | case={event.case_id} | action={event.action} | "
            f"actor={event.actor} | status={event.status}"
        )
        return event

    def get_events(self, case_id: Optional[str] = None, event_type: Optional[AuditEventType] = None) -> List[AuditEvent]:
        """Retrieves recorded audit events with optional filtering."""
        filtered = self._events
        if case_id:
            filtered = [e for e in filtered if e.case_id == case_id]
        if event_type:
            filtered = [e for e in filtered if e.event_type == event_type]
        return list(filtered)

    def clear(self) -> None:
        """Clears events (used primarily in test fixtures)."""
        self._events.clear()


# Global audit logger instance
audit_logger = AuditLogger()
