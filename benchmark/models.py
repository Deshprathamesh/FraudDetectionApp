# ==============================================================================
# FraudGraph AI - Benchmark Data Models
# Workstream: Benchmark Evaluation Harness
# ==============================================================================

from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class FailureCategory(str, Enum):
    """Failure classifications strictly adhering to Section 18."""
    INPUT_ERROR = "INPUT_ERROR"
    INVESTIGATION_FAILURE = "INVESTIGATION_FAILURE"
    RISK_FAILURE = "RISK_FAILURE"
    NBA_FAILURE = "NBA_FAILURE"
    POLICY_FAILURE = "POLICY_FAILURE"
    APPROVAL_FAILURE = "APPROVAL_FAILURE"
    EXECUTION_FAILURE = "EXECUTION_FAILURE"
    CASE_MEMORY_FAILURE = "CASE_MEMORY_FAILURE"
    INTEGRATION_FAILURE = "INTEGRATION_FAILURE"
    UNKNOWN = "UNKNOWN"


class BenchmarkCase(BaseModel):
    """
    Typed benchmark case representation matching the authoritative
    organizer case_pack.csv schema.
    """
    case_id: str = Field(description="Unique case identifier (e.g., HHG-001)")
    opened_at: str = Field(description="Opening timestamp string")
    trigger_type: str = Field(description="Trigger category (risk_score, customer_report, analyst_request)")
    trigger_text: str = Field(description="Detailed narrative trigger description")
    flagged_txn_id: str = Field(description="Target transaction identifier")
    card_id: str = Field(description="Card token or identifier")
    customer_id: str = Field(description="Customer identifier")
    risk_score: Optional[float] = Field(default=None, description="Input detection model score (if provided)")

    # Ground-truth placeholders - never fabricated
    expected_pattern: str = Field(default="NOT PROVIDED", description="Ground truth pattern from benchmark source")
    expected_action: str = Field(default="NOT PROVIDED", description="Ground truth action from benchmark source")
    expected_outcome: str = Field(default="NOT PROVIDED", description="Ground truth outcome from benchmark source")

    def to_trigger_dict(self) -> Dict[str, Any]:
        """Convert case metadata into standard workflow trigger dictionary."""
        return {
            "case_id": self.case_id,
            "opened_at": self.opened_at,
            "trigger_type": self.trigger_type,
            "trigger_text": self.trigger_text,
            "card_id": self.card_id,
            "customer_id": self.customer_id,
            "risk_score": self.risk_score,
        }


class BenchmarkCaseResult(BaseModel):
    """
    Structured benchmark evaluation result per case capturing all
    Section 7, 8, 9, 10, and 16 requirements.
    """
    benchmark_case_id: str
    transaction_id: str

    investigation_status: str = Field(default="NOT_RUN", description="COMPLETED, FAILED, PARTIAL")

    fraud_probability: Optional[float] = None
    confidence: Optional[float] = None
    uncertainty: Optional[float] = None

    detected_pattern: Optional[str] = None
    expected_pattern: str = "NOT PROVIDED"
    pattern_match: str = "NOT PROVIDED"

    affected_transaction_ids: List[str] = Field(default_factory=list)
    connected_card_ids: List[str] = Field(default_factory=list)
    exposure_usd: float = 0.0

    evidence_count: int = 0
    evidence_items: List[Dict[str, Any]] = Field(default_factory=list)

    initial_nba: Optional[str] = None
    final_nba: Optional[str] = None
    expected_action: str = "NOT PROVIDED"
    action_match: str = "NOT PROVIDED"
    what_changed: Optional[str] = None

    policy_permitted: Optional[bool] = None
    policy_violated_rules: List[str] = Field(default_factory=list)
    approval_level: Optional[str] = None
    hitl_status: Optional[str] = None

    execution_status: Optional[str] = None
    execution_id: Optional[str] = None
    simulated: bool = True

    case_memory_status: Optional[str] = None
    final_workflow_state: Optional[str] = None

    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    failure_category: Optional[str] = None

    provenance: Dict[str, Any] = Field(
        default_factory=dict,
        description="Lineage explaining where outputs originated (Section 8)"
    )
