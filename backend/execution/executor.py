# ==============================================================================
# FraudGraph AI - Action Execution Service
# Workstream: Person 1 (Brain) - Stage 6 Execution & Case Memory
# ==============================================================================

import time
import logging
from typing import Dict, Any, List, Optional, Union

from backend.models.domain import (
    ActionType,
    ApprovalLevel,
    ApprovalStatus,
    ApprovalRequest,
    CANONICAL_ACTION_NAMES,
    HITLStatus,
    PolicyAssessment,
)
from backend.models.audit import audit_logger, AuditEventType
from backend.policy.evaluator import policy_evaluator
from backend.execution.models import ExecutionStatus, ExecutionResult
from backend.execution.interface import ActionExecutorInterface
from backend.execution.mock_executor import mock_action_executor

logger = logging.getLogger("fraudgraph.execution")


class ActionExecutionService:
    """
    Central orchestration service for remediation action execution.
    Enforces the 7 independent authorization checks (A-G), execution idempotency,
    and structured audit logging.
    """

    def __init__(self, executor: Optional[ActionExecutorInterface] = None):
        self.executor = executor or mock_action_executor
        self._registry: Dict[str, ExecutionResult] = {}

    def get_idempotency_key(self, case_id: str, action: Union[ActionType, str], target_resource: str) -> str:
        act_str = action.value if isinstance(action, ActionType) else str(action).upper()
        return f"{case_id.strip()}:{act_str}:{target_resource.strip()}"

    def get_execution(self, case_id: str, action: Union[ActionType, str], target_resource: str) -> Optional[ExecutionResult]:
        key = self.get_idempotency_key(case_id, action, target_resource)
        return self._registry.get(key)

    def get_executions_for_case(self, case_id: str) -> List[ExecutionResult]:
        prefix = f"{case_id.strip()}:"
        return [res for key, res in self._registry.items() if key.startswith(prefix)]

    def clear(self) -> None:
        """Clears the execution registry (used primarily in test fixtures)."""
        self._registry.clear()

    def execute(
        self,
        action: Union[ActionType, str],
        case_id: str,
        target_resource: str,
        policy_assessment: Optional[PolicyAssessment] = None,
        approval_request: Optional[ApprovalRequest] = None,
        params: Optional[Dict[str, Any]] = None,
        approver_id: Optional[str] = None,
        actor: str = "EXECUTION_SERVICE",
    ) -> ExecutionResult:
        """
        Executes a remediation action under strict 7-point authorization gating.
        """
        clean_case_id = (case_id or "").strip()
        clean_target = (target_resource or "").strip()

        # ----------------------------------------------------------------------
        # Check A: Case context exists and is valid
        # ----------------------------------------------------------------------
        if not clean_case_id:
            logger.warning("[EXECUTION BLOCKED] Check A failed: Missing case_id.")
            audit_logger.record_event(
                event_type=AuditEventType.ACTION_EXECUTION_BLOCKED,
                case_id="UNKNOWN",
                action=str(action),
                actor=actor,
                payload={"reason": "CHECK_A_MISSING_CASE_ID", "target_resource": clean_target},
                status="BLOCKED",
            )
            return ExecutionResult(
                case_id="UNKNOWN",
                action=ActionType.ALLOW_TRANSACTION,
                target_resource=clean_target,
                status=ExecutionStatus.BLOCKED,
                idempotency_key=f"UNKNOWN:{action}:{clean_target}",
                message="Execution blocked: Investigation case context or case_id is missing.",
            )

        # ----------------------------------------------------------------------
        # Check B: Canonical Action Normalization
        # ----------------------------------------------------------------------
        action_enum = self._normalize_action(action)
        if action_enum is None:
            logger.warning(f"[EXECUTION BLOCKED] Check B failed: Unsupported action '{action}'.")
            audit_logger.record_event(
                event_type=AuditEventType.ACTION_EXECUTION_BLOCKED,
                case_id=clean_case_id,
                action=str(action),
                actor=actor,
                payload={"reason": "CHECK_B_UNSUPPORTED_ACTION", "action_provided": str(action)},
                status="BLOCKED",
            )
            return ExecutionResult(
                case_id=clean_case_id,
                action=ActionType.ALLOW_TRANSACTION,
                target_resource=clean_target,
                status=ExecutionStatus.NOT_AUTHORIZED,
                idempotency_key=f"{clean_case_id}:{action}:{clean_target}",
                message=f"Execution rejected: '{action}' is not a recognized canonical ActionType.",
            )

        idempotency_key = self.get_idempotency_key(clean_case_id, action_enum, clean_target)

        # ----------------------------------------------------------------------
        # Check F: Idempotency Verification (Prevent duplicate execution early)
        # ----------------------------------------------------------------------
        if idempotency_key in self._registry:
            existing = self._registry[idempotency_key]
            logger.info(f"[EXECUTION IDEMPOTENT] Action '{action_enum.value}' already executed for case '{clean_case_id}'.")
            return ExecutionResult(
                execution_id=existing.execution_id,
                case_id=clean_case_id,
                action=action_enum,
                target_resource=clean_target,
                status=ExecutionStatus.ALREADY_EXECUTED,
                executed_at=existing.executed_at,
                simulated=existing.simulated,
                idempotency_key=idempotency_key,
                approval_reference=existing.approval_reference,
                message=f"Action '{action_enum.value}' on '{clean_target}' has already been executed for case '{clean_case_id}'. Duplicate execution prevented.",
                audit_event_id=existing.audit_event_id,
                details=existing.details,
            )

        # ----------------------------------------------------------------------
        # Check G: Target Resource Validation
        # ----------------------------------------------------------------------
        if not self.executor.validate_target(action_enum, clean_target):
            logger.warning(f"[EXECUTION BLOCKED] Check G failed: Invalid target '{clean_target}' for action '{action_enum.value}'.")
            audit_logger.record_event(
                event_type=AuditEventType.ACTION_EXECUTION_BLOCKED,
                case_id=clean_case_id,
                action=action_enum.value,
                actor=actor,
                payload={"reason": "CHECK_G_INVALID_TARGET_RESOURCE", "target_resource": clean_target},
                status="BLOCKED",
            )
            return ExecutionResult(
                case_id=clean_case_id,
                action=action_enum,
                target_resource=clean_target,
                status=ExecutionStatus.BLOCKED,
                idempotency_key=idempotency_key,
                message=f"Execution blocked: Target resource '{clean_target}' is invalid for action '{action_enum.value}'.",
            )

        # ----------------------------------------------------------------------
        # Check C: Policy Assessment Exists and Permits Action
        # ----------------------------------------------------------------------
        if policy_assessment is None:
            logger.warning(f"[EXECUTION BLOCKED] Check C failed: Missing PolicyAssessment for case '{clean_case_id}'.")
            audit_logger.record_event(
                event_type=AuditEventType.ACTION_EXECUTION_BLOCKED,
                case_id=clean_case_id,
                action=action_enum.value,
                actor=actor,
                payload={"reason": "CHECK_C_MISSING_POLICY_ASSESSMENT"},
                status="BLOCKED",
            )
            return ExecutionResult(
                case_id=clean_case_id,
                action=action_enum,
                target_resource=clean_target,
                status=ExecutionStatus.BLOCKED,
                idempotency_key=idempotency_key,
                message="Execution blocked: Policy assessment is missing. Unvetted actions cannot be executed.",
            )

        if not policy_assessment.permitted or policy_assessment.hitl_status in (HITLStatus.POLICY_BLOCKED, HITLStatus.POLICY_INDETERMINATE):
            logger.warning(f"[EXECUTION BLOCKED] Check C failed: Action '{action_enum.value}' blocked by policy for case '{clean_case_id}'.")
            audit_logger.record_event(
                event_type=AuditEventType.ACTION_EXECUTION_BLOCKED,
                case_id=clean_case_id,
                action=action_enum.value,
                actor=actor,
                payload={
                    "reason": "CHECK_C_POLICY_PROHIBITED",
                    "hitl_status": policy_assessment.hitl_status.value,
                    "violated_rules": policy_assessment.violated_rules,
                },
                status="BLOCKED",
            )
            return ExecutionResult(
                case_id=clean_case_id,
                action=action_enum,
                target_resource=clean_target,
                status=ExecutionStatus.BLOCKED,
                idempotency_key=idempotency_key,
                message=f"Execution blocked by policy: {policy_assessment.explanation}",
                details={"violated_rules": policy_assessment.violated_rules},
            )

        # ----------------------------------------------------------------------
        # Check D & E: Approval Level Satisfaction & Approver Authority
        # ----------------------------------------------------------------------
        req_level = policy_assessment.approval_level
        approval_ref: Optional[str] = None

        if req_level == ApprovalLevel.AUTO:
            # Auto-approved: No human approval record required
            approval_ref = "AUTO_APPROVED"
        else:
            # Human approval (L1 or L2) required
            if approval_request is None:
                logger.warning(f"[EXECUTION BLOCKED] Check D failed: Action requires {req_level.value} approval, but no request exists.")
                audit_logger.record_event(
                    event_type=AuditEventType.ACTION_EXECUTION_BLOCKED,
                    case_id=clean_case_id,
                    action=action_enum.value,
                    actor=actor,
                    payload={"reason": "CHECK_D_MISSING_APPROVAL_REQUEST", "required_level": req_level.value},
                    status="BLOCKED",
                )
                return ExecutionResult(
                    case_id=clean_case_id,
                    action=action_enum,
                    target_resource=clean_target,
                    status=ExecutionStatus.NOT_AUTHORIZED,
                    idempotency_key=idempotency_key,
                    message=f"Execution not authorized: Action requires {req_level.value} human approval, but no approval request was found.",
                )

            if approval_request.status != ApprovalStatus.APPROVED:
                logger.warning(f"[EXECUTION BLOCKED] Check D failed: Approval status is '{approval_request.status.value}'.")
                audit_logger.record_event(
                    event_type=AuditEventType.ACTION_EXECUTION_BLOCKED,
                    case_id=clean_case_id,
                    action=action_enum.value,
                    actor=actor,
                    payload={"reason": "CHECK_D_APPROVAL_NOT_GRANTED", "status": approval_request.status.value},
                    status="BLOCKED",
                )
                return ExecutionResult(
                    case_id=clean_case_id,
                    action=action_enum,
                    target_resource=clean_target,
                    status=ExecutionStatus.NOT_AUTHORIZED,
                    idempotency_key=idempotency_key,
                    message=f"Execution not authorized: Approval request status is '{approval_request.status.value}', expected 'APPROVED'.",
                )

            # Check E: Approver authority verification
            effective_approver = approver_id or approval_request.approver_id
            if not effective_approver:
                logger.warning("[EXECUTION BLOCKED] Check E failed: Approver ID missing.")
                audit_logger.record_event(
                    event_type=AuditEventType.ACTION_EXECUTION_BLOCKED,
                    case_id=clean_case_id,
                    action=action_enum.value,
                    actor=actor,
                    payload={"reason": "CHECK_E_MISSING_APPROVER_ID"},
                    status="BLOCKED",
                )
                return ExecutionResult(
                    case_id=clean_case_id,
                    action=action_enum,
                    target_resource=clean_target,
                    status=ExecutionStatus.NOT_AUTHORIZED,
                    idempotency_key=idempotency_key,
                    message="Execution not authorized: Approver ID is missing from approval record.",
                )

            has_authority = policy_evaluator.verify_approver_authority(effective_approver, req_level)
            if not has_authority:
                logger.warning(f"[EXECUTION BLOCKED] Check E failed: Approver '{effective_approver}' has insufficient authority for {req_level.value}.")
                audit_logger.record_event(
                    event_type=AuditEventType.ACTION_EXECUTION_BLOCKED,
                    case_id=clean_case_id,
                    action=action_enum.value,
                    actor=actor,
                    payload={
                        "reason": "CHECK_E_INSUFFICIENT_AUTHORITY",
                        "approver_id": effective_approver,
                        "required_level": req_level.value,
                    },
                    status="BLOCKED",
                )
                return ExecutionResult(
                    case_id=clean_case_id,
                    action=action_enum,
                    target_resource=clean_target,
                    status=ExecutionStatus.NOT_AUTHORIZED,
                    idempotency_key=idempotency_key,
                    message=f"Execution not authorized: Approver '{effective_approver}' has insufficient authority for level '{req_level.value}'.",
                )

            approval_ref = approval_request.approval_id

        # ----------------------------------------------------------------------
        # Authorization Passed: Dispatch Execution
        # ----------------------------------------------------------------------
        req_audit = audit_logger.record_event(
            event_type=AuditEventType.ACTION_EXECUTION_REQUESTED,
            case_id=clean_case_id,
            action=action_enum.value,
            actor=actor,
            payload={
                "target_resource": clean_target,
                "approval_reference": approval_ref,
                "approval_level": req_level.value,
                "params": params or {},
            },
        )

        try:
            exec_res = self.executor.execute(
                action=action_enum,
                case_id=clean_case_id,
                target_resource=clean_target,
                params=params,
                approval_reference=approval_ref,
            )

            # Record success in audit trail
            success_audit = audit_logger.record_event(
                event_type=AuditEventType.ACTION_EXECUTED,
                case_id=clean_case_id,
                action=action_enum.value,
                actor=actor,
                payload={
                    "execution_id": exec_res.execution_id,
                    "target_resource": clean_target,
                    "simulated": exec_res.simulated,
                    "approval_reference": approval_ref,
                },
                status="SUCCESS",
            )
            exec_res.audit_event_id = success_audit.event_id

            # Save in idempotency registry
            self._registry[idempotency_key] = exec_res
            return exec_res

        except Exception as ex:
            logger.error(f"[EXECUTION FAILED] Action '{action_enum.value}' failed during execution: {ex}", exc_info=True)
            failed_audit = audit_logger.record_event(
                event_type=AuditEventType.ACTION_EXECUTION_FAILED,
                case_id=clean_case_id,
                action=action_enum.value,
                actor=actor,
                payload={"target_resource": clean_target, "error": str(ex)},
                status="FAILED",
            )
            return ExecutionResult(
                case_id=clean_case_id,
                action=action_enum,
                target_resource=clean_target,
                status=ExecutionStatus.FAILED,
                idempotency_key=idempotency_key,
                approval_reference=approval_ref,
                message=f"Action execution failed: {str(ex)}",
                audit_event_id=failed_audit.event_id,
                details={"error": str(ex)},
            )

    def _normalize_action(self, action: Union[ActionType, str]) -> Optional[ActionType]:
        if isinstance(action, ActionType):
            return action

        act_clean = str(action).strip().upper()
        alias_map = {
            "BLOCK_TRANSACTION": ActionType.DECLINE_TRANSACTION,
            "FREEZE_ACCOUNT": ActionType.BLOCK_ALL_CARDS,
            "REQUEST_STEP_UP_AUTH": ActionType.STEP_UP_AUTH,
            "REQUEST_VERIFICATION": ActionType.VERIFY_WITH_CUSTOMER,
            "FILE_SAR": ActionType.FILE_REPORT,
            "MONITOR": ActionType.MONITOR_CARD,
        }
        if act_clean in alias_map:
            return alias_map[act_clean]

        try:
            return ActionType(act_clean)
        except ValueError:
            return None


# Global singleton execution service
action_executor = ActionExecutionService()
