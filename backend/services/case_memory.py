# ==============================================================================
# FraudGraph AI - Case Memory Service
# Workstream: Person 1 (Brain) - Stage 1 Foundation
# ==============================================================================

import time
from typing import Dict, Any, List, Optional

from backend.models.domain import InvestigationCase
from backend.services.interface import CaseMemoryInterface


class InMemoryCaseMemoryService(CaseMemoryInterface):
    """
    In-memory case memory repository for development, staging, and Stage 1 foundation.
    Stores and retrieves active and historical investigation cases.
    """

    def __init__(self):
        self._cases: Dict[str, InvestigationCase] = {}

    def save_case(self, case: InvestigationCase) -> bool:
        case.updated_at = int(time.time())
        self._cases[case.case_id] = case
        return True

    def get_case(self, case_id: str) -> Optional[InvestigationCase]:
        return self._cases.get(case_id)

    def list_cases(self, limit: int = 50) -> List[InvestigationCase]:
        # Return sorted by updated_at descending
        sorted_cases = sorted(self._cases.values(), key=lambda c: c.updated_at, reverse=True)
        return sorted_cases[:limit]

    def search_similar_cases(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        # Lightweight similarity matching across stored cases
        results = []
        q_lower = query.lower()
        for case in self._cases.values():
            score = 0.5
            if case.transaction_id.lower() in q_lower or (case.customer_id and case.customer_id.lower() in q_lower):
                score = 0.9
            results.append({
                "case_id": case.case_id,
                "transaction_id": case.transaction_id,
                "status": case.status.value,
                "risk_score": case.risk_score,
                "similarity_score": score,
            })
        return sorted(results, key=lambda x: x["similarity_score"], reverse=True)[:limit]

    def clear(self) -> None:
        self._cases.clear()


# Singleton instance
case_memory_service = InMemoryCaseMemoryService()
