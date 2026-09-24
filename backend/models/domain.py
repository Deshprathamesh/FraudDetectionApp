# ==============================================================================
# FraudGraph AI - Core Domain Models
# Workstream: Person 1 (Brain) - Stage 1 Foundation
# ==============================================================================

import math
import time
import uuid
from enum import Enum
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field, field_validator


class ActionType(str, Enum):
    """Canonical action types across FraudGraph AI."""
    # Challenge 14 canonical actions
    ALLOW_TRANSACTION = "ALLOW_TRANSACTION"
    DECLINE_TRANSACTION = "DECLINE_TRANSACTION"
    MONITOR_CARD = "MONITOR_CARD"
    MONITOR_CONNECTED_CARDS = "MONITOR_CONNECTED_CARDS"
    WARN_CUSTOMER = "WARN_CUSTOMER"
    VERIFY_WITH_CUSTOMER = "VERIFY_WITH_CUSTOMER"
    STEP_UP_AUTH = "STEP_UP_AUTH"
    BLOCK_CARD = "BLOCK_CARD"
    BLOCK_ALL_CARDS = "BLOCK_ALL_CARDS"
    GENERATE_REPORT = "GENERATE_REPORT"
    CREATE_CASE = "CREATE_CASE"
    FILE_REPORT = "FILE_REPORT"
    ESCALATE_TO_ANALYST = "ESCALATE_TO_ANALYST"
    CLOSE_NO_FRAUD = "CLOSE_NO_FRAUD"

    # Common operational aliases supported seamlessly
    BLOCK_TRANSACTION = "BLOCK_TRANSACTION"
    FREEZE_ACCOUNT = "FREEZE_ACCOUNT"
    FILE_SAR = "FILE_SAR"
    REQUEST_STEP_UP_AUTH = "REQUEST_STEP_UP_AUTH"
    REQUEST_VERIFICATION = "REQUEST_VERIFICATION"
    MONITOR = "MONITOR"


CANONICAL_ACTION_NAMES = {
    ActionType.ALLOW_TRANSACTION.value,
    ActionType.DECLINE_TRANSACTION.value,
    ActionType.MONITOR_CARD.value,
    ActionType.MONITOR_CONNECTED_CARDS.value,
    ActionType.WARN_CUSTOMER.value,
    ActionType.VERIFY_WITH_CUSTOMER.value,
    ActionType.STEP_UP_AUTH.value,
    ActionType.BLOCK_CARD.value,
    ActionType.BLOCK_ALL_CARDS.value,
    ActionType.GENERATE_REPORT.value,
    ActionType.CREATE_CASE.value,
    ActionType.FILE_REPORT.value,
    ActionType.ESCALATE_TO_ANALYST.value,
    ActionType.CLOSE_NO_FRAUD.value,
}


class CaseStatus(str, Enum):
    """Lifecycle statuses for fraud investigation cases."""
    TRIGGERED = "TRIGGERED"
    INVESTIGATING = "INVESTIGATING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"
    FAILED = "FAILED"
    CLOSED = "CLOSED"
    WAITING_FOR_EVIDENCE = "WAITING_FOR_EVIDENCE"
    ACTION_READY = "ACTION_READY"


class ApprovalStatus(str, Enum):
    """Statuses for human-in-the-loop approvals."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    NOT_REQUIRED = "NOT_REQUIRED"


class ApprovalLevel(str, Enum):
    """Canonical approval routing levels defined by organizer policy."""
    AUTO = "auto"
    L1_SUPERVISOR = "L1"
    L2_COMPLIANCE = "L2"


class HITLStatus(str, Enum):
    """Canonical lifecycle states for Human-in-the-Loop decisioning."""
    AUTO_APPROVED = "AUTO_APPROVED"
    PENDING_L1_APPROVAL = "PENDING_L1_APPROVAL"
    PENDING_L2_APPROVAL = "PENDING_L2_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    POLICY_INDETERMINATE = "POLICY_INDETERMINATE"


class RuleEvaluationStatus(str, Enum):
    """Evaluation status for individual organizer policy rules."""
    SATISFIED = "SATISFIED"
    VIOLATED = "VIOLATED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class RiskLevel(str, Enum):
    """Categorical risk tiers."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Transaction(BaseModel):
    """Core transaction domain model."""
    transaction_id: str = Field(..., description="Canonical transaction identifier (e.g. TXN-104829)")
    customer_id: str = Field(..., description="Associated customer ID (e.g. C-45821)")
    account_id: str = Field(..., description="Associated account identifier")
    amount: float = Field(..., gt=0, description="Transaction amount in USD")
    currency: str = Field(default="USD", description="Currency code, strictly USD")
    timestamp: int = Field(default_factory=lambda: int(time.time()), description="Epoch timestamp")
    channel: str = Field(default="POS", description="Channel (POS, ONLINE, ATM, WIRE)")
    card_network: str = Field(default="VISA", description="Card network (VISA, MASTERCARD, AMEX)")
    merchant_name: str = Field(default="Unknown Merchant", description="Merchant name")
    device_id: str = Field(default="UNKNOWN_DEVICE", description="Device hardware fingerprint")
    ip_str: str = Field(default="127.0.0.1", description="Client IP address")
    risk_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Base risk score (0.0 to 1.0)")
    is_proxy: bool = Field(default=False, description="Whether transaction originated from VPN/Tor/Proxy")

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        if v.upper() != "USD":
            raise ValueError(f"Currency must be USD, got: {v}")
        return "USD"


class Customer(BaseModel):
    """Customer profile domain model."""
    customer_id: str = Field(..., description="Canonical customer identifier")
    name: str = Field(..., description="Customer full name")
    email: str = Field(default="unknown@example.com", description="Customer email")
    risk_tier: RiskLevel = Field(default=RiskLevel.LOW, description="Customer risk tier")
    created_at: int = Field(default_factory=lambda: int(time.time()), description="Account creation timestamp")
    accounts: List[str] = Field(default_factory=list, description="List of linked account IDs")
    linked_cards: List[str] = Field(default_factory=list, description="List of linked card IDs")
    risk_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Customer risk score")


class EvidenceItem(BaseModel):
    """Individual evidence artifact captured during an investigation."""
    evidence_id: str = Field(default_factory=lambda: f"EVID-{uuid.uuid4().hex[:8].upper()}")
    source: str = Field(..., description="Origin of evidence (GRAPH, GRAPHRAG, ENRICHMENT, RULE)")
    evidence_type: str = Field(default="GENERAL", description="Categorical type (DEVICE_SHARING, VELOCITY, PROXY, PRECEDENT)")
    description: str = Field(default="", description="Detailed description of the evidence")
    claim: Optional[str] = Field(default=None, description="Factual claim asserted by evidence")
    ref: Optional[str] = Field(default=None, description="Query reference or source pointer")
    entity_ids: List[str] = Field(default_factory=list, description="Associated entities")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence in this evidence item")
    untrusted_data_flag: bool = Field(default=False, description="Flag indicating external untrusted content")
    timestamp: int = Field(default_factory=lambda: int(time.time()))
    details: Dict[str, Any] = Field(default_factory=dict)
    
    # Stage 2 Evidence Taxonomy Enhancements
    related_entity: Optional[str] = Field(default=None, description="Primary entity this evidence relates to")
    related_transaction: Optional[str] = Field(default=None, description="Transaction ID this evidence directly references")
    fact_level: str = Field(default="FACT", description="Epistemic level: FACT, OBSERVATION, INFERENCE")
    is_direct: bool = Field(default=True, description="True for direct observation, False for derived relationship")
    provenance_sources: List[str] = Field(default_factory=list, description="List of source systems/queries contributing to this item")

    @field_validator("fact_level")
    @classmethod
    def validate_fact_level(cls, v: str) -> str:
        valid_levels = {"FACT", "OBSERVATION", "INFERENCE"}
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"fact_level must be one of {valid_levels}, got: {v}")
        return v_upper


class InvestigationStatus(str, Enum):
    """Investigation lifecycle statuses for Stage 2 Investigation Engine."""
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class InvestigationStartRequest(BaseModel):
    """Payload to trigger an investigation via REST API."""
    transaction_id: str = Field(..., description="Canonical transaction identifier")
    trigger: Optional[Dict[str, Any]] = Field(default=None, description="Optional trigger metadata")

    @field_validator("transaction_id")
    @classmethod
    def validate_transaction_id(cls, v: str) -> str:
        v_stripped = v.strip()
        if not v_stripped:
            raise ValueError("transaction_id cannot be empty")
        return v_stripped


class InvestigationResult(BaseModel):
    """
    Stage 2 Investigation Engine output.
    Structures all validated, normalized, and deduplicated evidence without premature verdicts.
    """
    case_id: str = Field(default_factory=lambda: f"CASE-{uuid.uuid4().hex[:8].upper()}")
    transaction_id: str = Field(..., description="Target transaction ID")
    status: InvestigationStatus = Field(default=InvestigationStatus.COMPLETE)
    transaction: Optional[Dict[str, Any]] = Field(default=None, description="Transaction details")
    customer: Optional[Dict[str, Any]] = Field(default=None, description="Customer profile")
    transaction_history: List[Dict[str, Any]] = Field(default_factory=list, description="Historical transactions (bounded)")
    connected_entities: Dict[str, Any] = Field(default_factory=dict, description="Multi-hop entity graph")
    graph_findings: List[Dict[str, Any]] = Field(default_factory=list, description="Graph topology findings")
    fraud_pattern_evidence: List[Dict[str, Any]] = Field(default_factory=list, description="Detected fraud patterns")
    similar_cases: List[Dict[str, Any]] = Field(default_factory=list, description="Similar precedent cases")
    graphrag_context: Dict[str, Any] = Field(default_factory=dict, description="Retrieved GraphRAG policy and precedent context")
    evidence: List[EvidenceItem] = Field(default_factory=list, description="Deduplicated structured evidence items")
    warnings: List[str] = Field(default_factory=list, description="Warnings or partial failure notices")
    timeline: List[Dict[str, Any]] = Field(default_factory=list, description="Investigation timeline events")
    created_at: int = Field(default_factory=lambda: int(time.time()))
    completed_at: Optional[int] = Field(default=None)
    risk_score: Optional[float] = Field(default=None, description="Assessed fraud risk score")


class FraudPattern(BaseModel):
    """Detected fraud pattern or syndicate typology."""
    pattern_id: str = Field(..., description="Pattern identifier (e.g. FP-01)")
    name: str = Field(..., description="Pattern typology name")
    description: str = Field(..., description="Description of the pattern match")
    severity: RiskLevel = Field(default=RiskLevel.HIGH)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    evidence_refs: List[str] = Field(default_factory=list, description="Referenced evidence IDs")
    matched_entities: List[str] = Field(default_factory=list, description="Entities involved in the pattern")


class SignalDirection(str, Enum):
    """Direction of evidentiary indication."""
    SUPPORTS_FRAUD = "SUPPORTS_FRAUD"
    SUPPORTS_LEGITIMATE = "SUPPORTS_LEGITIMATE"
    NEUTRAL = "NEUTRAL"


class IndependenceGroup(str, Enum):
    """Independent evidence categories preventing double-counting."""
    TRANSACTION_ATTRIBUTES = "TRANSACTION_ATTRIBUTES"
    CUSTOMER_PROFILE = "CUSTOMER_PROFILE"
    TRANSACTION_HISTORY = "TRANSACTION_HISTORY"
    GRAPH_TOPOLOGY = "GRAPH_TOPOLOGY"
    DEVICE_SHARING = "DEVICE_SHARING"
    FRAUD_PATTERN = "FRAUD_PATTERN"
    HISTORICAL_CASE = "HISTORICAL_CASE"
    POLICY_DIRECTIVE = "POLICY_DIRECTIVE"
    CUSTOMER_VERIFICATION = "CUSTOMER_VERIFICATION"


class StoppingStatus(str, Enum):
    """Organizer-defined investigation stopping decisions."""
    SUFFICIENT_EVIDENCE = "SUFFICIENT_EVIDENCE"
    MORE_EVIDENCE_REQUIRED = "MORE_EVIDENCE_REQUIRED"
    INCONCLUSIVE = "INCONCLUSIVE"
    INVESTIGATION_BLOCKED = "INVESTIGATION_BLOCKED"


class RiskSignal(BaseModel):
    """Individual typed evidentiary risk signal extracted from Stage 2 evidence."""
    signal_id: str = Field(default_factory=lambda: f"SIG-{uuid.uuid4().hex[:8].upper()}")
    category: str = Field(default="GENERAL", description="Signal category (e.g. velocity, device, pattern)")
    name: Optional[str] = Field(default=None, description="Short descriptive name of the signal")
    description: str = Field(default="", description="Explainable description of the signal")
    direction: SignalDirection = Field(..., description="Evidentiary direction")
    strength: float = Field(default=0.5, description="Raw strength of the signal [0.0, 1.0]")
    weight: float = Field(default=0.5, description="Effective weight considering evidence quality [0.0, 1.0]")
    source: str = Field(default="STAGE2_EVIDENCE", description="Originating tool or evidence source")
    evidence_ids: List[str] = Field(default_factory=list, description="Referenced EvidenceItem IDs")
    evidence_refs: List[str] = Field(default_factory=list, description="Referenced EvidenceItem IDs (alias)")
    provenance: List[str] = Field(default_factory=list, description="Query/pipeline provenance pointers")
    independence_group: IndependenceGroup = Field(..., description="Independent grouping to prevent double-counting")

    def model_post_init(self, __context: Any) -> None:
        if not self.description and self.name:
            self.description = self.name
        if not self.name and self.description:
            self.name = self.description[:50]
        if self.evidence_refs and not self.evidence_ids:
            self.evidence_ids = list(self.evidence_refs)
        elif self.evidence_ids and not self.evidence_refs:
            self.evidence_refs = list(self.evidence_ids)

    @field_validator("strength", "weight", mode="before")
    @classmethod
    def validate_signal_floats(cls, v: Any) -> float:
        try:
            val = float(v)
        except (TypeError, ValueError):
            raise ValueError(f"Expected float, got {v}")
        if math.isnan(val) or math.isinf(val):
            raise ValueError("Numeric value cannot be NaN or infinite")
        return max(0.0, min(1.0, val))


class InformationGap(BaseModel):
    """Identified evidentiary or context gap in the investigation."""
    gap_id: str = Field(default_factory=lambda: f"GAP-{uuid.uuid4().hex[:8].upper()}")
    gap_type: Optional[str] = Field(default=None, description="Category or taxonomy of the gap")
    description: str = Field(..., description="Nature of the missing information")
    affected_conclusion: str = Field(default="", description="How this gap impacts the fraud or legitimacy assessment")
    severity: str = Field(default="MEDIUM", description="Severity of the gap: LOW, MEDIUM, HIGH, CRITICAL")
    evidence_currently_available: str = Field(default="", description="Summary of evidence currently present")
    material_impact: bool = Field(default=True, description="Whether obtaining this info could materially change the decision")
    impact_score: float = Field(default=0.5, description="Relative impact score [0.0, 1.0]")


class StoppingDecision(BaseModel):
    """Organizer-defined stopping decision evaluation."""
    status: StoppingStatus = Field(..., description="Stopping status")
    reason: str = Field(..., description="Factual justification for stopping or continuing")
    fraud_probability: float = Field(default=0.0, description="Assessed fraud probability")
    confidence: float = Field(default=0.0, description="Assessed confidence level")
    independent_evidence_count: int = Field(default=0, description="Count of independent supporting evidence groups")
    condition_met: Optional[str] = Field(default=None, description="Organizer condition satisfied if stopped")
    missing_information: List[str] = Field(default_factory=list, description="Information gaps preventing conclusive decision")
    recommended_next_query: Optional[str] = Field(default=None, description="Recommended next evidence gathering step")

    @property
    def rationale(self) -> str:
        return self.reason

    @field_validator("fraud_probability", "confidence", mode="before")
    @classmethod
    def validate_stopping_floats(cls, v: Any) -> float:
        try:
            val = float(v)
        except (TypeError, ValueError):
            raise ValueError(f"Expected float, got {v}")
        if math.isnan(val) or math.isinf(val):
            raise ValueError("Numeric value cannot be NaN or infinite")
        if not (0.0 <= val <= 1.0):
            raise ValueError(f"Value must be between 0.0 and 1.0, got {val}")
        return val


class RiskAssessment(BaseModel):
    """
    Stage 3 Comprehensive Risk & Uncertainty Assessment.
    Consumes Stage 2 evidence and produces explainable probability and confidence metrics.
    """
    fraud_probability: float = Field(default=0.0, ge=0.0, le=1.0, description="Heuristic fraud probability [0.0, 1.0]")
    risk_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Input detection score or unified risk index")
    risk_level: RiskLevel = Field(default=RiskLevel.LOW, description="Categorical risk rating")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Evidence corroboration confidence [0.0, 1.0]")
    uncertainty: float = Field(default=0.0, ge=0.0, le=1.0, description="Epistemic uncertainty (1.0 - confidence)")
    evidence_count: int = Field(default=0, description="Total count of evaluated evidence items")
    independent_evidence_count: int = Field(default=0, description="Count of distinct independent evidence groups")
    supporting_signals: List[Union[RiskSignal, str]] = Field(default_factory=list, description="Signals supporting fraud")
    contradicting_signals: List[Union[RiskSignal, str]] = Field(default_factory=list, description="Signals supporting legitimacy")
    neutral_signals: List[Union[RiskSignal, str]] = Field(default_factory=list, description="Neutral contextual signals")
    signal_breakdown: Dict[str, Any] = Field(default_factory=dict, description="Summary counts and weights by group")
    stopping_decision: Optional[StoppingDecision] = Field(default=None, description="Organizer stopping evaluation")
    information_gaps: List[InformationGap] = Field(default_factory=list, description="Identified evidence gaps")
    reasoning_summary: str = Field(default="", description="Traceable, evidence-grounded reasoning narrative")
    methodology: str = Field(default="heuristic_probability_estimate", description="Explicit methodology tag")
    factors: List[str] = Field(default_factory=list, description="Salient risk drivers for backward compatibility")
    timestamp: int = Field(default_factory=lambda: int(time.time()))

    @property
    def epistemic_uncertainty(self) -> float:
        """Alias for uncertainty."""
        return self.uncertainty

    @property
    def epistemic_confidence(self) -> float:
        """Alias for confidence."""
        return self.confidence

    @field_validator("fraud_probability", "risk_score", "confidence", "uncertainty", mode="before")
    @classmethod
    def validate_risk_floats(cls, v: Any) -> float:
        try:
            val = float(v)
        except (TypeError, ValueError):
            raise ValueError(f"Expected float, got {v}")
        if math.isnan(val) or math.isinf(val):
            raise ValueError("Numeric value cannot be NaN or infinite")
        if not (0.0 <= val <= 1.0):
            raise ValueError(f"Value must be between 0.0 and 1.0 inclusive, got {val}")
        return val


class UncertaintyAssessment(BaseModel):
    """Assessment of epistemic uncertainty and confidence."""
    confidence: float = Field(..., ge=0.0, le=1.0, description="Evidence corroboration level (0.0 to 1.0)")
    uncertainty: float = Field(..., ge=0.0, le=1.0, description="Epistemic uncertainty (1.0 - confidence)")
    uncertainty_sources: List[str] = Field(default_factory=list, description="Identified sources of uncertainty")
    missing_information: List[str] = Field(default_factory=list, description="Information gaps")


class ActionRecommendation(BaseModel):
    """Recommended next-best action from the reasoning engine."""
    action: str = Field(..., description="Canonical action name")
    priority: int = Field(default=1, description="Priority ranking (1 is highest)")
    reason: str = Field(..., description="Actionable rationale for recommendation")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in recommendation")
    evidence_ids: List[str] = Field(default_factory=list, description="Supporting evidence IDs")
    approval_required: bool = Field(default=False, description="Whether human approval is required")
    policy_basis: str = Field(default="", description="Governing policy clause")
    alternative_actions: List[str] = Field(default_factory=list, description="Ranked alternative actions")
    route: str = Field(default="auto", description="Approval route: auto, L1, L2")


class ActionRouteItem(BaseModel):
    """Action recommendation item with explicit routing per organizer specification."""
    action: str = Field(..., description="Canonical action name")
    route: str = Field(default="auto", description="Approval routing: auto, L1, L2")
    reason: str = Field(default="", description="Governing rule citation or justification")


class NextBestActionItem(BaseModel):
    """Specific next-best-action recommendation item generated by Stage 4 NBA engine."""
    action: str = Field(..., description="Canonical action name from the 14 organizer actions")
    rationale: str = Field(..., description="Evidence-grounded rationale for this action")
    priority: int = Field(default=1, ge=1, le=10, description="Priority rank (1 is highest)")
    supporting_evidence: List[str] = Field(default_factory=list, description="Supporting evidence references or IDs")
    triggering_gaps: List[str] = Field(default_factory=list, description="Information gaps or conditions prompting this action")

    @field_validator("action")
    @classmethod
    def validate_canonical_action(cls, v: str) -> str:
        action_str = v.strip().upper() if isinstance(v, str) else str(v).upper()
        if action_str not in CANONICAL_ACTION_NAMES:
            # Canonical alias normalization for legacy callers
            alias_map = {
                "BLOCK_TRANSACTION": ActionType.DECLINE_TRANSACTION.value,
                "FREEZE_ACCOUNT": ActionType.BLOCK_ALL_CARDS.value,
                "REQUEST_STEP_UP_AUTH": ActionType.STEP_UP_AUTH.value,
                "REQUEST_VERIFICATION": ActionType.VERIFY_WITH_CUSTOMER.value,
                "FILE_SAR": ActionType.FILE_REPORT.value,
                "MONITOR": ActionType.MONITOR_CARD.value,
            }
            if action_str in alias_map:
                action_str = alias_map[action_str]
            else:
                raise ValueError(
                    f"Action '{v}' is not one of the 14 canonical actions: {sorted(CANONICAL_ACTION_NAMES)}"
                )
        return action_str

    @property
    def reason(self) -> str:
        """Compatibility alias for rationale expected by legacy/frontend callers."""
        return self.rationale


class NBAWhatChanged(BaseModel):
    """Factual explanation of differences between initial and final next best action sets."""
    explanation: str = Field(..., description="Factual explanation of what changed between initial and final recommendations")
    before_fraud_probability: Optional[float] = Field(default=None, description="Initial heuristic fraud probability estimate")
    after_fraud_probability: Optional[float] = Field(default=None, description="Final heuristic fraud probability estimate")
    before_uncertainty: Optional[float] = Field(default=None, description="Initial epistemic uncertainty")
    after_uncertainty: Optional[float] = Field(default=None, description="Final epistemic uncertainty")
    resolved_gaps: List[str] = Field(default_factory=list, description="Information gaps resolved by subsequent evidence")
    evidence_added: List[str] = Field(default_factory=list, description="New evidence items that triggered update")


class NextBestActionAssessment(BaseModel):
    """
    Stage 4 output model for Next Best Action decisioning.
    Captures initial recommendations, final recommendations (if updated), and explainability.
    Does NOT execute actions, route approvals, or evaluate Stage 5 policy.
    """
    initial: List[NextBestActionItem] = Field(default_factory=list, description="Ranked initial next best actions")
    final: List[NextBestActionItem] = Field(default_factory=list, description="Ranked final next best actions after evidence")
    what_changed: Optional[Union[NBAWhatChanged, str]] = Field(default=None, description="Explanation of what changed between initial and final")
    rationale: str = Field(default="", description="High-level narrative rationale")
    methodology: str = Field(default="deterministic_evidentiary_nba", description="Deterministic rule-based evidentiary methodology")

    @property
    def primary_action(self) -> Optional[NextBestActionItem]:
        """Primary action: top final action if present, else top initial action."""
        if self.final:
            return self.final[0]
        return self.initial[0] if self.initial else None

    @property
    def alternative_actions(self) -> List[NextBestActionItem]:
        """Ranked alternative actions excluding the primary action."""
        if self.final:
            return self.final[1:]
        return self.initial[1:] if len(self.initial) > 1 else []


class NextBestActions(BaseModel):
    """Container for Next Best Action decisioning supporting organizer answer schema."""
    initial: List[ActionRouteItem] = Field(default_factory=list, description="Initial NBA recommendations prior to evidence")
    final: List[ActionRouteItem] = Field(default_factory=list, description="Final NBA recommendations following evidence")
    what_changed: Optional[str] = Field(default=None, description="Explanation of how additional evidence updated actions")
    primary_action: Optional[ActionRecommendation] = None
    alternative_actions: List[ActionRecommendation] = Field(default_factory=list)
    rationale: str = Field(default="")
    escalation_path: str = Field(default="auto") # auto, L1, L2


class EvidenceRequest(BaseModel):
    """Evidence request submitted by agent during investigation per organizer specification."""
    type: str = Field(..., description="Validation inquiry type (e.g. customer_validation, merchant_inquiry)")
    asked_after_step: int = Field(default=1, description="Investigation step number when inquiry was raised")
    assumed_response: Optional[str] = Field(default=None, description="Response from customer or analyst")


class SARReport(BaseModel):
    """Suspicious Activity Report (SAR) domain model for regulatory filing."""
    sar_id: str = Field(default_factory=lambda: f"SAR-{uuid.uuid4().hex[:8].upper()}")
    case_id: str = Field(default="", description="Associated case identifier")
    subject_id: str = Field(default="", description="Primary subject (customer_id or entity_id)")
    amount: float = Field(default=0.0, ge=0, description="Suspicious transaction amount in USD")
    narrative: str = Field(default="", description="Factual narrative detailing suspicious indicators")
    status: str = Field(default="DRAFT", description="Status (DRAFT, FILED, REJECTED)")
    file: bool = Field(default=True, description="Whether SAR filing is required")
    reason: Optional[str] = Field(default=None, description="Policy rule justification for SAR")
    subjects: List[str] = Field(default_factory=list, description="Subject IDs reported to FinCEN")
    total_amount_usd: Optional[float] = Field(default=None, description="Aggregated exposure amount in USD")
    activity_dates: List[str] = Field(default_factory=list, description="Activity dates [start, end]")
    created_at: int = Field(default_factory=lambda: int(time.time()))


class ApprovalSubmission(BaseModel):
    """Payload for human analyst submitting approval or rejection."""
    approver_id: str = Field(..., description="Analyst or supervisor identifier")
    decision: str = Field(..., description="Approval decision: APPROVED or REJECTED")
    approval_token: Optional[str] = Field(default=None, description="Cryptographic HMAC approval token")
    notes: Optional[str] = Field(default=None, description="Decision rationale or audit notes")


class PolicyRuleResult(BaseModel):
    """Result of evaluating a single organizer policy rule (R1-R10)."""
    rule_id: str = Field(..., description="Canonical rule ID (e.g. R1, R2)")
    rule_name: str = Field(..., description="Descriptive name of the policy rule")
    status: RuleEvaluationStatus = Field(..., description="Evaluation status: SATISFIED, VIOLATED, NOT_APPLICABLE")
    reason: str = Field(default="", description="Explainable justification for the rule outcome")
    facts_evaluated: Dict[str, Any] = Field(default_factory=dict, description="Factual state parameters evaluated")


class PolicyAssessment(BaseModel):
    """
    Stage 5 Policy Compliance and Human-in-the-Loop Assessment.
    Consumes Stage 2 investigation, Stage 3 risk, and Stage 4 NBA recommendation.
    Answers: IS THE RECOMMENDED ACTION PERMITTED UNDER ORGANIZER POLICY, AND WHO MUST APPROVE IT?
    """
    action: ActionType = Field(..., description="Canonical ActionType evaluated")
    permitted: bool = Field(..., description="Whether action is permitted under bank/organizer policy")
    approval_required: bool = Field(..., description="Whether human approval is required prior to execution")
    approval_level: ApprovalLevel = Field(..., description="Required approval level: AUTO, L1_SUPERVISOR, L2_COMPLIANCE")
    hitl_status: HITLStatus = Field(..., description="Initial HITL lifecycle status")
    sar_required: bool = Field(default=False, description="Whether SAR regulatory filing is required")
    violated_rules: List[str] = Field(default_factory=list, description="Rule IDs violated by action")
    satisfied_rules: List[str] = Field(default_factory=list, description="Rule IDs satisfied / permitting action")
    rule_results: List[PolicyRuleResult] = Field(default_factory=list, description="Detailed per-rule evaluation results")
    explanation: str = Field(default="", description="Explainable audit-ready policy summary")
    policy_version: str = Field(default="POL-FRAUD-2026-V1", description="Policy version identifier")
    exposure_usd: float = Field(default=0.0, ge=0.0, description="Evaluated exposure in USD")

    @field_validator("action", mode="before")
    @classmethod
    def validate_action_enum(cls, v: Any) -> ActionType:
        if isinstance(v, ActionType):
            return v
        v_str = str(v).strip().upper()
        alias_map = {
            "BLOCK_TRANSACTION": ActionType.DECLINE_TRANSACTION,
            "FREEZE_ACCOUNT": ActionType.BLOCK_ALL_CARDS,
            "REQUEST_STEP_UP_AUTH": ActionType.STEP_UP_AUTH,
            "REQUEST_VERIFICATION": ActionType.VERIFY_WITH_CUSTOMER,
            "FILE_SAR": ActionType.FILE_REPORT,
            "MONITOR": ActionType.MONITOR_CARD,
        }
        if v_str in alias_map:
            return alias_map[v_str]
        try:
            return ActionType(v_str)
        except ValueError:
            raise ValueError(f"Action '{v}' is not a valid canonical ActionType or recognized alias.")


class ApprovalRequest(BaseModel):
    """Human-in-the-loop approval request specification."""
    approval_id: str = Field(default_factory=lambda: f"APPR-{uuid.uuid4().hex[:8].upper()}")
    case_id: str = Field(..., description="Associated case identifier")
    action: str = Field(..., description="Action awaiting approval")
    target_resource: str = Field(..., description="Target card/account/transaction identifier")
    amount: float = Field(default=0.0, ge=0.0, description="Associated amount in USD")
    requested_at: int = Field(default_factory=lambda: int(time.time()))
    expires_at: int = Field(default_factory=lambda: int(time.time()) + 3600)
    status: ApprovalStatus = Field(default=ApprovalStatus.PENDING)
    approval_level: ApprovalLevel = Field(default=ApprovalLevel.L1_SUPERVISOR, description="Required approval level")
    approval_token: Optional[str] = Field(default=None, description="Cryptographic token for validation")
    approver_id: Optional[str] = Field(default=None, description="ID of analyst who approved/rejected")


class ActionResult(BaseModel):
    """Result of an executed remediation action."""
    success: bool = Field(..., description="Whether action executed successfully")
    action: str = Field(..., description="Executed action name")
    case_id: str = Field(..., description="Associated case identifier")
    target_resource: str = Field(..., description="Target entity ID")
    message: str = Field(..., description="Status summary message")
    timestamp: int = Field(default_factory=lambda: int(time.time()))
    details: Dict[str, Any] = Field(default_factory=dict)


class TimelineEvent(BaseModel):
    """Timeline entry tracking progress across the investigation."""
    event_id: str = Field(default_factory=lambda: f"EVT-{uuid.uuid4().hex[:8].upper()}")
    timestamp: int = Field(default_factory=lambda: int(time.time()))
    stage: str = Field(..., description="Workflow stage (e.g. TRIGGERED, ENRICHMENT, HITL_GATE)")
    title: str = Field(..., description="Brief headline of the event")
    description: str = Field(default="", description="Detailed narrative of the event")
    actor: str = Field(default="SYSTEM", description="Actor (AGENT, HUMAN_SUPERVISOR, POLICY_ENGINE)")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class InvestigationCase(BaseModel):
    """Comprehensive investigation case record supporting organizer evaluation schema."""
    case_id: str = Field(default_factory=lambda: f"CASE-{uuid.uuid4().hex[:8].upper()}")
    transaction_id: str = Field(..., description="Investigated transaction ID")
    customer_id: Optional[str] = Field(default=None, description="Customer ID")
    status: CaseStatus = Field(default=CaseStatus.TRIGGERED)
    verdict: Optional[str] = Field(default=None, description="Verdict: fraud, non_fraud, cleared")
    fraud_probability: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    pattern: Optional[str] = Field(default=None, description="Canonical fraud pattern identifier")
    pattern_description: Optional[str] = Field(default=None, description="Typology description")
    risk_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    uncertainty: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    exposure_usd: Optional[float] = Field(default=None, description="Exposure amount in USD")
    affected_txn_ids: List[str] = Field(default_factory=list)
    connected_card_ids: List[str] = Field(default_factory=list)
    connected_device_profiles: List[str] = Field(default_factory=list)
    evidence_requests: List[EvidenceRequest] = Field(default_factory=list)
    recommendation: Optional[ActionRecommendation] = Field(default=None)
    next_best_actions: Optional[NextBestActions] = Field(default=None)
    approval_request: Optional[ApprovalRequest] = Field(default=None)
    evidence: List[EvidenceItem] = Field(default_factory=list)
    fraud_patterns: List[FraudPattern] = Field(default_factory=list)
    similar_prior_cases: List[str] = Field(default_factory=list)
    summary: Optional[str] = Field(default=None, description="Factual investigation summary")
    written_to_graph: bool = Field(default=False)
    graph_case_id: Optional[str] = Field(default=None)
    stop_reason: Optional[str] = Field(default=None)
    timeline: List[TimelineEvent] = Field(default_factory=list)
    created_at: int = Field(default_factory=lambda: int(time.time()))
    updated_at: int = Field(default_factory=lambda: int(time.time()))
