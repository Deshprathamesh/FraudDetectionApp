# ==============================================================================
# FraudGraph AI - Centralized Error System
# Workstream: Person 1 (Brain) - Stage 1 Foundation
# ==============================================================================

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """Section 9 standardized error detail payload."""
    code: str = Field(..., description="Machine-readable uppercase error code")
    message: str = Field(..., description="Human-readable error description")
    details: Dict[str, Any] = Field(default_factory=dict, description="Contextual error details")


class ErrorResponse(BaseModel):
    """Canonical Section 9 error envelope."""
    error: ErrorDetail

    @classmethod
    def create(cls, code: str, message: str, details: Optional[Dict[str, Any]] = None) -> "ErrorResponse":
        return cls(
            error=ErrorDetail(
                code=code,
                message=message,
                details=details or {}
            )
        )


class FraudGraphException(Exception):
    """Base exception for all FraudGraph AI errors conforming to Section 9."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """Returns the canonical Section 9 error dictionary."""
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            }
        }

    def to_response(self) -> ErrorResponse:
        return ErrorResponse.create(
            code=self.code,
            message=self.message,
            details=self.details,
        )


# Specific Typed Exceptions

class TransactionNotFoundException(FraudGraphException):
    def __init__(self, transaction_id: str, message: Optional[str] = None):
        super().__init__(
            code="TRANSACTION_NOT_FOUND",
            message=message or f"Transaction '{transaction_id}' was not found in graph database.",
            status_code=404,
            details={"transaction_id": transaction_id},
        )


class CustomerNotFoundException(FraudGraphException):
    def __init__(self, customer_id: str, message: Optional[str] = None):
        super().__init__(
            code="CUSTOMER_NOT_FOUND",
            message=message or f"Customer '{customer_id}' was not found in graph database.",
            status_code=404,
            details={"customer_id": customer_id},
        )


class CaseNotFoundException(FraudGraphException):
    def __init__(self, case_id: str, message: Optional[str] = None):
        super().__init__(
            code="CASE_NOT_FOUND",
            message=message or f"Case '{case_id}' was not found.",
            status_code=404,
            details={"case_id": case_id},
        )


class GraphQueryFailedException(FraudGraphException):
    def __init__(self, query_name: str, message: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        d = {"query_name": query_name}
        if details:
            d.update(details)
        super().__init__(
            code="GRAPH_QUERY_FAILED",
            message=message or f"Graph query '{query_name}' failed to execute.",
            status_code=502,
            details=d,
        )


class PolicyViolationException(FraudGraphException):
    def __init__(self, reason: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code="POLICY_VIOLATION",
            message=reason,
            status_code=403,
            details=details or {},
        )


class ApprovalRequiredException(FraudGraphException):
    def __init__(self, action: str, case_id: str, approval_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        d = {"action": action, "case_id": case_id}
        if approval_id:
            d["approval_id"] = approval_id
        if details:
            d.update(details)
        super().__init__(
            code="APPROVAL_REQUIRED",
            message=f"Action '{action}' requires supervisor approval before execution.",
            status_code=403,
            details=d,
        )


class InvalidApprovalException(FraudGraphException):
    def __init__(self, reason: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code="INVALID_APPROVAL",
            message=reason,
            status_code=403,
            details=details or {},
        )


class UnauthorizedToolError(FraudGraphException):
    def __init__(self, tool_name: str, reason: str, details: Optional[Dict[str, Any]] = None):
        d = {"tool_name": tool_name, "reason": reason}
        if details:
            d.update(details)
        super().__init__(
            code="UNAUTHORIZED_TOOL_CALL",
            message=f"Unauthorized tool invocation: '{tool_name}'. {reason}",
            status_code=403,
            details=d,
        )


class AgentTimeoutException(FraudGraphException):
    def __init__(self, stage: str, timeout_seconds: int):
        super().__init__(
            code="AGENT_TIMEOUT",
            message=f"Agent investigation exceeded timeout of {timeout_seconds}s at stage '{stage}'.",
            status_code=504,
            details={"stage": stage, "timeout_seconds": timeout_seconds},
        )


class WorkflowLoopLimitExceeded(FraudGraphException):
    def __init__(self, iteration_count: int, max_iterations: int):
        super().__init__(
            code="WORKFLOW_LOOP_LIMIT_EXCEEDED",
            message=f"Workflow exceeded maximum iteration limit of {max_iterations} (reached {iteration_count}).",
            status_code=500,
            details={"iteration_count": iteration_count, "max_iterations": max_iterations},
        )


class ValidationError(FraudGraphException):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code="VALIDATION_ERROR",
            message=message,
            status_code=422,
            details=details or {},
        )


class InternalServerError(FraudGraphException):
    def __init__(self, message: str = "An unexpected internal server error occurred."):
        super().__init__(
            code="INTERNAL_SERVER_ERROR",
            message=message,
            status_code=500,
            details={},
        )
