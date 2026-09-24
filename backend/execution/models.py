# ==============================================================================
# FraudGraph AI - Execution Engine Models
# Workstream: Person 1 (Brain) - Stage 6 Execution & Case Memory
# ==============================================================================

import time
import uuid
from enum import Enum
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

from backend.models.domain import ActionType


class ExecutionStatus(str, Enum):
    """Lifecycle statuses for remediation action execution."""
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    ALREADY_EXECUTED = "ALREADY_EXECUTED"
    NOT_AUTHORIZED = "NOT_AUTHORIZED"


class ExecutionResult(BaseModel):
    """
    Immutable structured record of a remediation action execution.
    Enforces deterministic simulation metadata and idempotency references.
    """
    execution_id: str = Field(
        default_factory=lambda: f"EXEC-{uuid.uuid4().hex[:8].upper()}",
        description="Unique execution run identifier"
    )
    case_id: str = Field(..., description="Associated case identifier")
    action: ActionType = Field(..., description="Canonical action executed")
    target_resource: str = Field(..., description="Target card, account, or transaction identifier")
    status: ExecutionStatus = Field(..., description="Outcome status of execution")
    executed_at: int = Field(
        default_factory=lambda: int(time.time()),
        description="Epoch timestamp when action was executed"
    )
    simulated: bool = Field(
        default=True,
        description="Strictly True: all hackathon execution is simulated"
    )
    idempotency_key: str = Field(
        ...,
        description="Idempotency composite key: f'{case_id}:{action.value}:{target_resource}'"
    )
    approval_reference: Optional[str] = Field(
        default=None,
        description="Approval ID or token granting execution authority"
    )
    message: str = Field(
        ...,
        description="Human-readable execution outcome narrative"
    )
    audit_event_id: Optional[str] = Field(
        default=None,
        description="Audit event ID corresponding to this execution"
    )
    details: Dict[str, Any] = Field(
        default_factory=dict,
        description="Detailed execution metadata and parameters"
    )
