# ==============================================================================
# FraudGraph AI - Services Interfaces
# Workstream: Person 1 (Brain) - Stage 1 Foundation
# ==============================================================================

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

from backend.models.domain import ActionResult, InvestigationCase


class ActionExecutionInterface(ABC):
    """Abstract interface for simulated/real remediation action execution."""

    @abstractmethod
    def execute_action(
        self,
        action: str,
        case_id: str,
        target_resource: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> ActionResult:
        """Executes the specified action and records audit evidence."""
        pass

    @abstractmethod
    def is_supported_action(self, action: str) -> bool:
        """Checks if the action is supported by the executor."""
        pass


class CaseMemoryInterface(ABC):
    """Abstract interface for case persistence and case memory retrieval."""

    @abstractmethod
    def save_case(self, case: InvestigationCase) -> bool:
        """Persists or updates an investigation case."""
        pass

    @abstractmethod
    def get_case(self, case_id: str) -> Optional[InvestigationCase]:
        """Retrieves a case by unique case ID."""
        pass

    @abstractmethod
    def list_cases(self, limit: int = 50) -> List[InvestigationCase]:
        """Lists recent investigation cases."""
        pass

    @abstractmethod
    def search_similar_cases(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Searches historical case memory for similar precedents."""
        pass
