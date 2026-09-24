# ==============================================================================
# FraudGraph AI - Mock Remediation Action Service
# Workstream: Person 1 (Brain) - Stage 1 Foundation
# ==============================================================================

import time
from typing import Dict, Any, Optional

from backend.models.domain import ActionResult, ActionType
from backend.models.audit import audit_logger, AuditEventType
from backend.services.interface import ActionExecutionInterface
from backend.errors import ValidationError


class MockActionService(ActionExecutionInterface):
    """
    Mock remediation action execution service.
    Simulates remediation side-effects, enforces action naming constraints,
    and produces structured audit records.
    """

    SUPPORTED_ACTIONS = {item.value for item in ActionType}

    def is_supported_action(self, action: str) -> bool:
        return action.upper() in self.SUPPORTED_ACTIONS

    def execute_action(
        self,
        action: str,
        case_id: str,
        target_resource: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> ActionResult:
        action_clean = action.strip().upper()
        if not self.is_supported_action(action_clean):
            audit_logger.record_event(
                event_type=AuditEventType.FAILED,
                case_id=case_id,
                action=action,
                actor="MOCK_ACTION_SERVICE",
                payload={"target_resource": target_resource, "reason": "UNSUPPORTED_ACTION"},
                status="FAILED",
            )
            raise ValidationError(
                f"Action '{action}' is not a recognized or supported action.",
                details={"action": action, "supported_actions": list(sorted(self.SUPPORTED_ACTIONS))},
            )

        payload = params or {}
        
        # Record execution in audit trail
        audit_logger.record_event(
            event_type=AuditEventType.EXECUTED,
            case_id=case_id,
            action=action_clean,
            actor="MOCK_ACTION_SERVICE",
            payload={"target_resource": target_resource, "params": payload},
            status="SUCCESS",
        )

        return ActionResult(
            success=True,
            action=action_clean,
            case_id=case_id,
            target_resource=target_resource,
            message=f"Simulated action '{action_clean}' successfully applied to '{target_resource}'.",
            timestamp=int(time.time()),
            details=payload,
        )


# Singleton instance
mock_action_service = MockActionService()
