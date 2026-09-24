# ==============================================================================
# FraudGraph AI - Action Executor Interface
# Workstream: Person 1 (Brain) - Stage 6 Execution & Case Memory
# ==============================================================================

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from backend.models.domain import ActionType
from backend.execution.models import ExecutionResult


class ActionExecutorInterface(ABC):
    """Abstract interface defining the execution protocol for remediation actions."""

    @abstractmethod
    def validate_target(self, action: ActionType, target_resource: str) -> bool:
        """
        Validates whether target_resource matches the expected identifier format
        for the given canonical action.
        """
        pass

    @abstractmethod
    def execute(
        self,
        action: ActionType,
        case_id: str,
        target_resource: str,
        params: Optional[Dict[str, Any]] = None,
        approval_reference: Optional[str] = None,
    ) -> ExecutionResult:
        """
        Executes a remediation action in simulated mode, producing an ExecutionResult.
        """
        pass
