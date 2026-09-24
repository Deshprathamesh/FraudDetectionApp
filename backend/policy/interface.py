# ==============================================================================
# FraudGraph AI - Policy & Approval Interfaces
# Workstream: Person 1 (Brain) - Stage 1 Foundation
# ==============================================================================

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from backend.models.domain import ApprovalRequest


class PolicyDecision(BaseModel):
    """Result of evaluating policy rules against a proposed action and transaction."""
    allowed: bool = Field(..., description="Whether the action is permitted under bank policy")
    approval_required: bool = Field(default=False, description="Whether human approval is required")
    sar_required: bool = Field(default=False, description="Whether a Suspicious Activity Report is required")
    reason: str = Field(default="", description="Policy basis or justification")
    policy_id: str = Field(default="POL-FRAUD-2026-V1")
    matched_rules: List[str] = Field(default_factory=list, description="IDs of matched rules")
    confidence_threshold: float = Field(default=0.8, description="Minimum confidence required for automated action")
    constraints: Dict[str, Any] = Field(default_factory=dict, description="Operational constraints")


class PolicyEngineInterface(ABC):
    """Abstract interface for the governing policy engine (Stage 5 implementation target)."""

    @abstractmethod
    def evaluate(
        self,
        transaction: Dict[str, Any],
        risk_score: float,
        confidence: float,
        recommended_action: str,
        policy_context: Optional[Dict[str, Any]] = None,
    ) -> PolicyDecision:
        """Evaluates policy constraints for a candidate action."""
        pass

    @abstractmethod
    def generate_approval_token(
        self,
        case_id: str,
        action: str,
        target_resource: str,
        amount: float,
        expires_at: int,
    ) -> str:
        """Generates an HMAC-signed approval token bound to case and action parameters."""
        pass

    @abstractmethod
    def verify_approval_token(
        self,
        token: str,
        case_id: str,
        action: str,
        target_resource: str,
        amount: float,
    ) -> bool:
        """Verifies approval token authenticity, expiration, and parameter binding."""
        pass


class ApprovalServiceInterface(ABC):
    """Abstract interface for Human-in-the-Loop approval workflows."""

    @abstractmethod
    def create_approval_request(
        self,
        case_id: str,
        action: str,
        target_resource: str,
        amount: float,
    ) -> ApprovalRequest:
        """Creates and stores a pending approval request."""
        pass

    @abstractmethod
    def submit_approval(
        self,
        case_id: str,
        approval_id: str,
        approver_id: str,
        decision: str, # "APPROVED" or "REJECTED"
        token: str,
        notes: Optional[str] = None,
    ) -> ApprovalRequest:
        """Processes an approval decision from a human analyst."""
        pass
