# ==============================================================================
# FraudGraph AI - Agent Reasoning Interfaces
# Workstream: Person 1 (Brain) - Stage 1 Foundation
# ==============================================================================

from abc import ABC, abstractmethod
from typing import Dict, Any

from backend.models.domain import (
    RiskAssessment,
    UncertaintyAssessment,
    ActionRecommendation,
)


class RiskEngineInterface(ABC):
    """Abstract interface for fraud risk probability assessment."""

    @abstractmethod
    def assess_risk(self, state: Dict[str, Any]) -> RiskAssessment:
        """Computes fraud risk score and factors from current state evidence."""
        pass


class UncertaintyEngineInterface(ABC):
    """Abstract interface for epistemic uncertainty and confidence evaluation."""

    @abstractmethod
    def assess_uncertainty(self, state: Dict[str, Any]) -> UncertaintyAssessment:
        """Evaluates confidence and uncertainty gaps given available evidence."""
        pass


class NextBestActionEngineInterface(ABC):
    """Abstract interface for Next Best Action (NBA) reasoning."""

    @abstractmethod
    def recommend_action(self, state: Dict[str, Any]) -> ActionRecommendation:
        """Determines the prioritized action recommendation based on risk, uncertainty, and policy."""
        pass
