# ==============================================================================
# FraudGraph AI - Policy Evaluator & HITL Decision Engine
# Workstream: Person 1 (Brain) - Stage 5 Policy & HITL Gate
# ==============================================================================

import time
import math
import hmac
import hashlib
import logging
from typing import Dict, Any, List, Optional, Union

from backend.models.domain import (
    ActionType,
    ApprovalLevel,
    HITLStatus,
    RuleEvaluationStatus,
    PolicyRuleResult,
    PolicyAssessment,
    InvestigationResult,
    RiskAssessment,
)
from backend.policy.rules import evaluate_all_rules

logger = logging.getLogger("fraudgraph.policy")

# Secret key for HMAC token signing (configurable via environment/settings)
DEFAULT_HMAC_SECRET = "fraudgraph-hitl-hmac-secret-2026-authoritative"

# Server-side authority registry for approver authorization
DEFAULT_APPROVER_REGISTRY: Dict[str, ApprovalLevel] = {
    # L1 Supervisors / Team Leads
    "analyst_1": ApprovalLevel.L1_SUPERVISOR,
    "analyst_l1": ApprovalLevel.L1_SUPERVISOR,
    "team_lead": ApprovalLevel.L1_SUPERVISOR,
    "ANALYST-1": ApprovalLevel.L1_SUPERVISOR,
    "SUPERVISOR-1": ApprovalLevel.L1_SUPERVISOR,
    "SUP-001": ApprovalLevel.L1_SUPERVISOR,
    "l1_lead": ApprovalLevel.L1_SUPERVISOR,
    # L2 Compliance / Fraud Managers
    "manager_1": ApprovalLevel.L2_COMPLIANCE,
    "compliance_l2": ApprovalLevel.L2_COMPLIANCE,
    "fraud_manager": ApprovalLevel.L2_COMPLIANCE,
    "COMPLIANCE-1": ApprovalLevel.L2_COMPLIANCE,
    "COMP-001": ApprovalLevel.L2_COMPLIANCE,
    "MANAGER-1": ApprovalLevel.L2_COMPLIANCE,
    "l2_compliance": ApprovalLevel.L2_COMPLIANCE,
}

# Canonical alias mapping to canonical ActionType
ALIAS_MAP = {
    "BLOCK_TRANSACTION": ActionType.DECLINE_TRANSACTION,
    "FREEZE_ACCOUNT": ActionType.BLOCK_ALL_CARDS,
    "REQUEST_STEP_UP_AUTH": ActionType.STEP_UP_AUTH,
    "REQUEST_VERIFICATION": ActionType.VERIFY_WITH_CUSTOMER,
    "FILE_SAR": ActionType.FILE_REPORT,
    "MONITOR": ActionType.MONITOR_CARD,
}


class PolicyEvaluator:
    """
    Deterministic Policy Evaluator implementing the authoritative organizer policy (R1-R10)
    and Human-in-the-Loop (HITL) approval hierarchy.
    """

    def __init__(self, hmac_secret: str = DEFAULT_HMAC_SECRET):
        self._hmac_secret = hmac_secret
        self._approver_registry = dict(DEFAULT_APPROVER_REGISTRY)

    def normalize_action(self, action_raw: Any) -> Optional[ActionType]:
        """
        Normalizes candidate action input (str, enum, or legacy alias) into canonical ActionType.
        Returns None if invalid or unrecognized.
        """
        if isinstance(action_raw, ActionType):
            return action_raw
        if not action_raw or not isinstance(action_raw, (str, ActionType)):
            return None

        clean_str = str(action_raw).strip().upper()
        if clean_str in ALIAS_MAP:
            return ALIAS_MAP[clean_str]

        try:
            return ActionType(clean_str)
        except ValueError:
            return None

    def determine_approval_level(self, action: ActionType, exposure_usd: float) -> ApprovalLevel:
        """
        Evaluates exact organizer approval routing hierarchy (Section 7.1 & 7.2):
        - BLOCK_CARD:
            <= $2,500.00 -> L1_SUPERVISOR
            > $2,500.00  -> L2_COMPLIANCE
        - BLOCK_ALL_CARDS: L2_COMPLIANCE
        - FILE_REPORT: L2_COMPLIANCE
        - DECLINE_TRANSACTION: L1_SUPERVISOR
        - All other canonical actions: AUTO
        """
        if action == ActionType.BLOCK_CARD:
            if exposure_usd <= 2500.0:
                return ApprovalLevel.L1_SUPERVISOR
            else:
                return ApprovalLevel.L2_COMPLIANCE
        elif action == ActionType.BLOCK_ALL_CARDS:
            return ApprovalLevel.L2_COMPLIANCE
        elif action == ActionType.FILE_REPORT:
            return ApprovalLevel.L2_COMPLIANCE
        elif action == ActionType.DECLINE_TRANSACTION:
            return ApprovalLevel.L1_SUPERVISOR
        else:
            return ApprovalLevel.AUTO

    def extract_exposure(
        self,
        investigation: Optional[InvestigationResult] = None,
        exposure_override: Optional[float] = None,
        facts: Optional[Dict[str, Any]] = None,
    ) -> Optional[float]:
        """
        Extracts exposure USD with strict fail-closed validation.
        Returns None if exposure is missing, NaN, infinite, or negative.
        """
        val: Any = None
        if exposure_override is not None:
            val = exposure_override
        elif facts and "exposure_usd" in facts:
            val = facts["exposure_usd"]
        elif facts and "amount" in facts:
            val = facts["amount"]
        elif investigation and getattr(investigation, "transaction", None):
            val = investigation.transaction.get("amount")
        elif facts and "exposure" in facts:
            val = facts["exposure"]

        if val is None:
            return None

        try:
            f_val = float(val)
        except (TypeError, ValueError):
            return None

        if math.isnan(f_val) or math.isinf(f_val) or f_val < 0.0:
            return None

        return f_val

    def evaluate(
        self,
        action: Any,
        investigation: Optional[InvestigationResult] = None,
        risk: Optional[RiskAssessment] = None,
        exposure_usd: Optional[float] = None,
        facts: Optional[Dict[str, Any]] = None,
    ) -> PolicyAssessment:
        """
        Main policy evaluation entrypoint.
        Deterministic evaluation of candidate action against organizer rules R1-R10,
        calculates required approval level, and assigns initial HITL status.
        """
        ctx = facts or {}

        # 1. Canonical Action Validation (Fail-Closed on invalid action)
        canonical_action = self.normalize_action(action)
        if canonical_action is None:
            logger.warning(f"Fail-closed policy rejection: invalid or unrecognized action '{action}'")
            return PolicyAssessment(
                action=ActionType.ALLOW_TRANSACTION, # placeholder canonical enum
                permitted=False,
                approval_required=False,
                approval_level=ApprovalLevel.L2_COMPLIANCE,
                hitl_status=HITLStatus.POLICY_INDETERMINATE,
                sar_required=False,
                violated_rules=["FAIL_CLOSED_INVALID_ACTION"],
                satisfied_rules=[],
                rule_results=[
                    PolicyRuleResult(
                        rule_id="FAIL_CLOSED",
                        rule_name="Invalid Action Validation",
                        status=RuleEvaluationStatus.VIOLATED,
                        reason=f"Action '{action}' is not one of the 14 canonical organizer actions or supported aliases.",
                        facts_evaluated={"action_raw": str(action)},
                    )
                ],
                explanation=f"Policy Indeterminate: Action '{action}' is unrecognized. Failing closed.",
                policy_version="POL-FRAUD-2026-V1",
                exposure_usd=0.0,
            )

        # 2. Exposure Extraction & Consistency Check
        evaluated_exposure = self.extract_exposure(
            investigation=investigation,
            exposure_override=exposure_usd,
            facts=ctx,
        )

        # Actions that strictly require valid exposure to determine policy routing
        exposure_sensitive_actions = {
            ActionType.BLOCK_CARD,
            ActionType.BLOCK_ALL_CARDS,
            ActionType.FILE_REPORT,
            ActionType.DECLINE_TRANSACTION,
            ActionType.ESCALATE_TO_ANALYST,
        }

        if evaluated_exposure is None:
            if canonical_action in exposure_sensitive_actions or ctx.get("require_exposure", False):
                logger.warning(f"Fail-closed policy rejection: missing exposure for action '{canonical_action.value}'")
                return PolicyAssessment(
                    action=canonical_action,
                    permitted=False,
                    approval_required=False,
                    approval_level=ApprovalLevel.L2_COMPLIANCE,
                    hitl_status=HITLStatus.POLICY_INDETERMINATE,
                    sar_required=False,
                    violated_rules=["FAIL_CLOSED_MISSING_EXPOSURE"],
                    satisfied_rules=[],
                    rule_results=[
                        PolicyRuleResult(
                            rule_id="FAIL_CLOSED",
                            rule_name="Exposure Consistency Validation",
                            status=RuleEvaluationStatus.VIOLATED,
                            reason="Missing, invalid, or negative exposure USD when required for policy routing.",
                            facts_evaluated={"action": canonical_action.value, "exposure": evaluated_exposure},
                        )
                    ],
                    explanation=(
                        f"Policy Indeterminate: Exposure USD is required for action '{canonical_action.value}' "
                        "but is missing or invalid. Failing closed."
                    ),
                    policy_version="POL-FRAUD-2026-V1",
                    exposure_usd=0.0,
                )
            else:
                evaluated_exposure = 0.0

        # 3. Check for Malformed / Corrupt Risk State
        if risk is not None:
            try:
                p = float(risk.fraud_probability)
                c = float(risk.confidence)
                if math.isnan(p) or math.isnan(c) or math.isinf(p) or math.isinf(c) or not (0.0 <= p <= 1.0) or not (0.0 <= c <= 1.0):
                    raise ValueError(f"Corrupt risk values: P={p}, C={c}")
            except Exception as e:
                logger.warning(f"Fail-closed policy rejection: corrupt risk state: {e}")
                return PolicyAssessment(
                    action=canonical_action,
                    permitted=False,
                    approval_required=False,
                    approval_level=ApprovalLevel.L2_COMPLIANCE,
                    hitl_status=HITLStatus.POLICY_INDETERMINATE,
                    sar_required=False,
                    violated_rules=["FAIL_CLOSED_CORRUPT_STATE"],
                    satisfied_rules=[],
                    rule_results=[
                        PolicyRuleResult(
                            rule_id="FAIL_CLOSED",
                            rule_name="Risk State Integrity Validation",
                            status=RuleEvaluationStatus.VIOLATED,
                            reason=f"Risk assessment contains corrupt or unvalidated numeric metrics: {e}",
                            facts_evaluated={"action": canonical_action.value},
                        )
                    ],
                    explanation="Policy Indeterminate: Corrupt risk state detected. Failing closed.",
                    policy_version="POL-FRAUD-2026-V1",
                    exposure_usd=evaluated_exposure,
                )

        # 4. Evaluate Binding Organizer Policy Rules R1 through R10
        rule_results = evaluate_all_rules(
            action=canonical_action,
            investigation=investigation,
            risk=risk,
            exposure_usd=evaluated_exposure,
            facts=ctx,
        )

        violated_rules = [r.rule_id for r in rule_results if r.status == RuleEvaluationStatus.VIOLATED]
        satisfied_rules = [r.rule_id for r in rule_results if r.status == RuleEvaluationStatus.SATISFIED]

        # 5. Determine SAR filing requirement
        sar_required = False
        if canonical_action == ActionType.FILE_REPORT:
            sar_required = True
        elif "R2" in satisfied_rules and (evaluated_exposure > 1000.0 or ctx.get("shared_device_compromise")):
            sar_required = True
        elif "R6" in satisfied_rules or "R9" in satisfied_rules:
            sar_required = True

        # 6. Calculate Approval Routing Level
        approval_level = self.determine_approval_level(canonical_action, evaluated_exposure)

        # 7. Synthesize Permitted and HITL Status
        if len(violated_rules) > 0:
            permitted = False
            approval_required = False
            hitl_status = HITLStatus.POLICY_BLOCKED
            explanation = (
                f"Action '{canonical_action.value}' is prohibited under organizer policy rules: "
                f"{', '.join(violated_rules)}. "
                f"Details: {'; '.join(r.reason for r in rule_results if r.status == RuleEvaluationStatus.VIOLATED)}"
            )
        else:
            permitted = True
            if approval_level == ApprovalLevel.AUTO:
                approval_required = False
                hitl_status = HITLStatus.AUTO_APPROVED
                explanation = (
                    f"Action '{canonical_action.value}' is permitted and auto-approved under organizer policy limits "
                    f"(exposure: ${evaluated_exposure:.2f})."
                )
            elif approval_level == ApprovalLevel.L1_SUPERVISOR:
                approval_required = True
                hitl_status = HITLStatus.PENDING_L1_APPROVAL
                explanation = (
                    f"Action '{canonical_action.value}' is permitted under policy subject to L1 Supervisor approval "
                    f"(exposure: ${evaluated_exposure:.2f} <= $2,500.00)."
                )
            elif approval_level == ApprovalLevel.L2_COMPLIANCE:
                approval_required = True
                hitl_status = HITLStatus.PENDING_L2_APPROVAL
                explanation = (
                    f"Action '{canonical_action.value}' is permitted under policy subject to L2 Compliance approval "
                    f"(exposure: ${evaluated_exposure:.2f})."
                )

        return PolicyAssessment(
            action=canonical_action,
            permitted=permitted,
            approval_required=approval_required,
            approval_level=approval_level,
            hitl_status=hitl_status,
            sar_required=sar_required,
            violated_rules=violated_rules,
            satisfied_rules=satisfied_rules,
            rule_results=rule_results,
            explanation=explanation,
            policy_version="POL-FRAUD-2026-V1",
            exposure_usd=round(evaluated_exposure, 2),
        )

    # --------------------------------------------------------------------------
    # Cryptographic HMAC Token Operations
    # --------------------------------------------------------------------------

    def generate_approval_token(
        self,
        case_id: str,
        action: str,
        target_resource: str,
        amount: float,
        approval_level: str,
        expires_at: int,
    ) -> str:
        """
        Generates an HMAC-SHA256 token binding all approval parameters cryptographically.
        Format: v1:{expires_at}:{signature}
        """
        canon_action = str(action).strip().upper()
        canon_level = str(approval_level).strip()
        amt_str = f"{float(amount):.2f}"
        
        payload = f"{case_id}:{canon_action}:{target_resource}:{amt_str}:{canon_level}:{int(expires_at)}"
        sig = hmac.new(
            self._hmac_secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return f"v1:{expires_at}:{sig}"

    def verify_approval_token(
        self,
        token: str,
        case_id: str,
        action: str,
        target_resource: str,
        amount: float,
        approval_level: str,
    ) -> bool:
        """
        Verifies cryptographic integrity, parameter binding, and expiration of an approval token.
        """
        if not token or not isinstance(token, str):
            return False

        token = token.strip()
        if not token.startswith("v1:") or "bypass" in token.lower() or token == "invalid":
            return False

        parts = token.split(":")
        if len(parts) != 3:
            return False

        version, exp_str, provided_sig = parts
        if version != "v1":
            return False

        try:
            expires_at = int(exp_str)
        except ValueError:
            return False

        # Expiration check
        if time.time() > expires_at:
            logger.warning(f"Approval token expired at {expires_at}, current time is {int(time.time())}")
            return False

        # Reconstruct expected signature
        canon_action = str(action).strip().upper()
        canon_level = str(approval_level).strip()
        amt_str = f"{float(amount):.2f}"
        
        expected_payload = f"{case_id}:{canon_action}:{target_resource}:{amt_str}:{canon_level}:{expires_at}"
        expected_sig = hmac.new(
            self._hmac_secret.encode("utf-8"),
            expected_payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(provided_sig, expected_sig)

    # --------------------------------------------------------------------------
    # Server-Side Approver Authority Operations
    # --------------------------------------------------------------------------

    def register_approver(self, approver_id: str, level: ApprovalLevel) -> None:
        """Registers or updates approver authority on the server."""
        self._approver_registry[approver_id] = level

    def get_approver_level(self, approver_id: str) -> Optional[ApprovalLevel]:
        """Retrieves server-side configured authority for an approver."""
        return self._approver_registry.get(approver_id)

    def verify_approver_authority(self, approver_id: str, required_level: ApprovalLevel) -> bool:
        """
        Verifies whether the approver possesses sufficient authority for the required level.
        Hierarchy:
        - AUTO: anyone or automated
        - L1_SUPERVISOR: L1 or L2 approver
        - L2_COMPLIANCE: L2 approver only (L1 cannot approve L2!)
        """
        if required_level == ApprovalLevel.AUTO:
            return True

        approver_level = self.get_approver_level(approver_id)
        if approver_level is None:
            logger.warning(f"Unknown approver ID '{approver_id}' attempting approval")
            return False

        if required_level == ApprovalLevel.L1_SUPERVISOR:
            return approver_level in (ApprovalLevel.L1_SUPERVISOR, ApprovalLevel.L2_COMPLIANCE)

        if required_level == ApprovalLevel.L2_COMPLIANCE:
            return approver_level == ApprovalLevel.L2_COMPLIANCE

        return False


# Singleton instance
policy_evaluator = PolicyEvaluator()
