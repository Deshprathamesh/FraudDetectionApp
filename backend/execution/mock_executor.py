# ==============================================================================
# FraudGraph AI - Mock Remediation Action Executor
# Workstream: Person 1 (Brain) - Stage 6 Execution & Case Memory
# ==============================================================================

import time
import re
from typing import Dict, Any, Optional

from backend.models.domain import ActionType
from backend.execution.models import ExecutionStatus, ExecutionResult
from backend.execution.interface import ActionExecutorInterface
from backend.errors import ValidationError


class MockActionExecutor(ActionExecutorInterface):
    """
    Deterministic mock action executor simulating remediation side-effects for
    all 14 canonical organizer actions.
    Enforces target resource syntax validation and guarantees simulated = True.
    """

    CARD_PATTERN = re.compile(r"^(CARD|CC|PAN)[\-_]?", re.IGNORECASE)
    CUSTOMER_PATTERN = re.compile(r"^(CUST|CUSTOMER)[\-_]?|^C[\-_]\d+", re.IGNORECASE)
    ACCOUNT_PATTERN = re.compile(r"^(ACC|ACCT|ACCOUNT)[\-_]?", re.IGNORECASE)
    TRANSACTION_PATTERN = re.compile(r"^(TXN|TX|TRANSACTION)[\-_]?", re.IGNORECASE)
    CASE_PATTERN = re.compile(r"^(CASE)[\-_]?", re.IGNORECASE)

    def validate_target(self, action: ActionType, target_resource: str) -> bool:
        """
        Validates whether target_resource is appropriate for the action type.
        """
        if not target_resource or not target_resource.strip():
            return False

        target = target_resource.strip()

        if action in (ActionType.BLOCK_CARD, ActionType.MONITOR_CARD):
            # Target should be a card identifier (e.g. CARD-4111-XXXX-9940 or similar)
            return bool(self.CARD_PATTERN.search(target)) or "CARD" in target.upper()

        if action in (ActionType.BLOCK_ALL_CARDS, ActionType.MONITOR_CONNECTED_CARDS):
            # Target should be customer or account identifier
            if self.CARD_PATTERN.search(target):
                return False
            return (
                bool(self.CUSTOMER_PATTERN.search(target))
                or bool(self.ACCOUNT_PATTERN.search(target))
                or "CUST" in target.upper()
                or "ACC" in target.upper()
                or (target.upper().startswith("C-") and not target.upper().startswith("CARD"))
            )

        if action in (ActionType.DECLINE_TRANSACTION, ActionType.ALLOW_TRANSACTION, ActionType.STEP_UP_AUTH):
            # Target should be transaction (or customer/phone for step-up)
            return (
                bool(self.TRANSACTION_PATTERN.search(target))
                or bool(self.CUSTOMER_PATTERN.search(target))
                or target.startswith("TXN-")
                or target.startswith("C-")
            )

        if action in (ActionType.WARN_CUSTOMER, ActionType.VERIFY_WITH_CUSTOMER):
            # Target should be customer identifier (strictly not card or transaction)
            if self.CARD_PATTERN.search(target) or self.TRANSACTION_PATTERN.search(target):
                return False
            return bool(self.CUSTOMER_PATTERN.search(target)) or (target.upper().startswith("C-") and not target.upper().startswith("CARD"))

        if action in (
            ActionType.GENERATE_REPORT,
            ActionType.CREATE_CASE,
            ActionType.FILE_REPORT,
            ActionType.ESCALATE_TO_ANALYST,
            ActionType.CLOSE_NO_FRAUD,
        ):
            # Target can be case, customer, or transaction identifier
            return len(target) > 0

        return True

    def execute(
        self,
        action: ActionType,
        case_id: str,
        target_resource: str,
        params: Optional[Dict[str, Any]] = None,
        approval_reference: Optional[str] = None,
    ) -> ExecutionResult:
        """
        Simulates the execution of a canonical remediation action.
        """
        clean_target = target_resource.strip()
        if not self.validate_target(action, clean_target):
            raise ValidationError(
                f"Target resource '{clean_target}' is invalid for action '{action.value}'.",
                details={
                    "action": action.value,
                    "target_resource": clean_target,
                    "required_type": self._get_expected_target_type(action),
                }
            )

        details = dict(params or {})
        now = int(time.time())
        idempotency_key = f"{case_id}:{action.value}:{clean_target}"

        message = self._generate_simulated_narrative(action, clean_target, details)

        return ExecutionResult(
            case_id=case_id,
            action=action,
            target_resource=clean_target,
            status=ExecutionStatus.EXECUTED,
            executed_at=now,
            simulated=True,
            idempotency_key=idempotency_key,
            approval_reference=approval_reference,
            message=message,
            details=details,
        )

    def _get_expected_target_type(self, action: ActionType) -> str:
        if action in (ActionType.BLOCK_CARD, ActionType.MONITOR_CARD):
            return "CARD identifier (e.g. CARD-xxxx)"
        if action in (ActionType.BLOCK_ALL_CARDS, ActionType.MONITOR_CONNECTED_CARDS):
            return "CUSTOMER or ACCOUNT identifier (e.g. C-xxxx, ACC-xxxx)"
        if action in (ActionType.DECLINE_TRANSACTION, ActionType.ALLOW_TRANSACTION):
            return "TRANSACTION identifier (e.g. TXN-xxxx)"
        if action in (ActionType.WARN_CUSTOMER, ActionType.VERIFY_WITH_CUSTOMER):
            return "CUSTOMER identifier (e.g. C-xxxx)"
        return "RESOURCE identifier (e.g. CASE-xxxx, TXN-xxxx, C-xxxx)"

    def _generate_simulated_narrative(
        self,
        action: ActionType,
        target: str,
        details: Dict[str, Any],
    ) -> str:
        """Generates clear, deterministic, simulation-labeled outcome narrative."""
        amount = details.get("amount")
        amt_str = f" [amount=${amount:.2f}]" if amount is not None else ""

        narratives = {
            ActionType.ALLOW_TRANSACTION: f"[SIMULATED] Transaction '{target}' allowed to clear without hold.",
            ActionType.DECLINE_TRANSACTION: f"[SIMULATED] Transaction '{target}' declined at authorization switch{amt_str}.",
            ActionType.MONITOR_CARD: f"[SIMULATED] Enhanced telemetry and velocity rule monitoring activated for card '{target}'.",
            ActionType.MONITOR_CONNECTED_CARDS: f"[SIMULATED] Fleet monitoring triggered across all associated payment instruments for '{target}'.",
            ActionType.WARN_CUSTOMER: f"[SIMULATED] Out-of-band security advisory notification dispatched to customer '{target}'.",
            ActionType.VERIFY_WITH_CUSTOMER: f"[SIMULATED] Interactive confirmation dispatch (SMS/Push) initiated for customer '{target}'.",
            ActionType.STEP_UP_AUTH: f"[SIMULATED] Step-up 2FA cryptographic challenge triggered for transaction '{target}'.",
            ActionType.BLOCK_CARD: f"[SIMULATED] Card '{target}' placed in permanent restricted block status on card issuer switch.",
            ActionType.BLOCK_ALL_CARDS: f"[SIMULATED] Complete account suspension executed: all cards linked to '{target}' blocked.",
            ActionType.GENERATE_REPORT: f"[SIMULATED] Regulatory audit documentation and factual evidence dossier generated for '{target}'.",
            ActionType.CREATE_CASE: f"[SIMULATED] Formal investigative fraud dossier opened for tracking target '{target}'.",
            ActionType.FILE_REPORT: f"[SIMULATED] Suspicious Activity Report (SAR) draft filed with compliance repository for '{target}'.",
            ActionType.ESCALATE_TO_ANALYST: f"[SIMULATED] High-priority tier-2 fraud analyst work-queue ticket dispatched for '{target}'.",
            ActionType.CLOSE_NO_FRAUD: f"[SIMULATED] Case closed as false positive; clear legitimacy disposition recorded for '{target}'.",
        }
        return narratives.get(action, f"[SIMULATED] Action '{action.value}' applied to '{target}'.")


# Singleton instance
mock_action_executor = MockActionExecutor()
