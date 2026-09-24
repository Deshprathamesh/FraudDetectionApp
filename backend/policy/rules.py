# ==============================================================================
# FraudGraph AI - Organizer Policy Rules (R1 - R10)
# Workstream: Person 1 (Brain) - Stage 5 Policy & HITL Gate
# ==============================================================================

from typing import Dict, Any, List, Optional
from backend.models.domain import (
    ActionType,
    RuleEvaluationStatus,
    PolicyRuleResult,
    InvestigationResult,
    RiskAssessment,
    StoppingStatus,
)


def evaluate_r1(
    action: ActionType,
    investigation: Optional[InvestigationResult] = None,
    risk: Optional[RiskAssessment] = None,
    exposure_usd: float = 0.0,
    facts: Optional[Dict[str, Any]] = None,
) -> PolicyRuleResult:
    """
    Rule R1 (Verify before block on weak signal):
    If investigation rests on a single signal and assessed fraud probability < 0.70,
    recommend VERIFY_WITH_CUSTOMER or STEP_UP_AUTH before any block.
    Blocking on a single weak signal is a policy violation.
    """
    ctx = facts or {}
    
    # Determine independent signal count
    if "signals_count" in ctx:
        signals_count = int(ctx["signals_count"])
    elif risk and hasattr(risk, "independent_evidence_count") and risk.independent_evidence_count > 0:
        signals_count = risk.independent_evidence_count
    elif risk and hasattr(risk, "supporting_signals"):
        signals_count = len(risk.supporting_signals)
    elif investigation and hasattr(investigation, "evidence"):
        signals_count = len(investigation.evidence)
    else:
        signals_count = ctx.get("evidence_count", 1)

    # Determine fraud probability
    if "fraud_probability" in ctx:
        fraud_prob = float(ctx["fraud_probability"])
    elif risk and hasattr(risk, "fraud_probability"):
        fraud_prob = float(risk.fraud_probability)
    else:
        fraud_prob = 0.0

    facts_eval = {
        "signals_count": signals_count,
        "fraud_probability": round(fraud_prob, 4),
        "action": action.value,
    }

    # If confirmed credential compromise or multiple card fraud exists, R1 weak signal rule is not applicable
    if ctx.get("credentials_compromised") or ctx.get("account_takeover") or int(ctx.get("confirmed_fraud_cards_count", 0)) >= 2:
        return PolicyRuleResult(
            rule_id="R1",
            rule_name="Verify before block on weak signal",
            status=RuleEvaluationStatus.NOT_APPLICABLE,
            reason="R1 not triggered: confirmed credential compromise or multiple card fraud present.",
            facts_evaluated=facts_eval,
        )

    # Condition: single signal and P(fraud) < 0.70
    is_weak_signal = (signals_count <= 1) and (fraud_prob < 0.70)

    if not is_weak_signal:
        return PolicyRuleResult(
            rule_id="R1",
            rule_name="Verify before block on weak signal",
            status=RuleEvaluationStatus.NOT_APPLICABLE,
            reason="R1 not triggered: multiple signals or fraud probability >= 0.70.",
            facts_evaluated=facts_eval,
        )

    # Triggered: check action
    if action in (ActionType.BLOCK_CARD, ActionType.BLOCK_ALL_CARDS):
        return PolicyRuleResult(
            rule_id="R1",
            rule_name="Verify before block on weak signal",
            status=RuleEvaluationStatus.VIOLATED,
            reason=(
                f"R1 Violation: Investigation rests on a single signal ({signals_count}) "
                f"with fraud probability {fraud_prob:.2f} < 0.70. "
                "Blocking card is prohibited before customer verification or step-up auth."
            ),
            facts_evaluated=facts_eval,
        )
    elif action in (ActionType.VERIFY_WITH_CUSTOMER, ActionType.STEP_UP_AUTH):
        return PolicyRuleResult(
            rule_id="R1",
            rule_name="Verify before block on weak signal",
            status=RuleEvaluationStatus.SATISFIED,
            reason="R1 Satisfied: Weak signal correctly routed to customer verification or step-up auth.",
            facts_evaluated=facts_eval,
        )

    return PolicyRuleResult(
        rule_id="R1",
        rule_name="Verify before block on weak signal",
        status=RuleEvaluationStatus.NOT_APPLICABLE,
        reason=f"R1: Weak signal detected but action '{action.value}' is neither a block nor a verification.",
        facts_evaluated=facts_eval,
    )


def evaluate_r2(
    action: ActionType,
    investigation: Optional[InvestigationResult] = None,
    risk: Optional[RiskAssessment] = None,
    exposure_usd: float = 0.0,
    facts: Optional[Dict[str, Any]] = None,
) -> PolicyRuleResult:
    """
    Rule R2 (Customer denies transaction):
    Recommend BLOCK_CARD and CREATE_CASE. Add FILE_REPORT if exposure > $1,000.00
    or case connects to a shared device profile or another card's fraud.
    """
    ctx = facts or {}
    
    # Check if customer denied transaction
    denied = (
        ctx.get("customer_response") in ("denies", "denied", "fraud")
        or ctx.get("customer_denied") is True
        or ctx.get("customer_dispute") is True
    )

    if not denied and investigation:
        for req in investigation.evidence_requests if hasattr(investigation, "evidence_requests") else []:
            resp = getattr(req, "assumed_response", "") or ""
            if any(w in resp.lower() for w in ("not make", "deni", "fraud", "unauthorized", "did not")):
                denied = True
                break

    facts_eval = {
        "customer_denied": denied,
        "exposure_usd": exposure_usd,
        "action": action.value,
    }

    if not denied:
        return PolicyRuleResult(
            rule_id="R2",
            rule_name="Customer denies transaction",
            status=RuleEvaluationStatus.NOT_APPLICABLE,
            reason="R2 not triggered: customer has not denied the transaction.",
            facts_evaluated=facts_eval,
        )

    # Triggered: customer denied
    has_shared_link = (
        ctx.get("shared_device_compromise", False)
        or ctx.get("connected_fraud_card", False)
        or (investigation and len(getattr(investigation, "connected_entities", {}).get("shared_cards", [])) > 0)
    )

    if action in (ActionType.ALLOW_TRANSACTION, ActionType.CLOSE_NO_FRAUD):
        return PolicyRuleResult(
            rule_id="R2",
            rule_name="Customer denies transaction",
            status=RuleEvaluationStatus.VIOLATED,
            reason=f"R2 Violation: Customer explicitly denied transaction. Action '{action.value}' is prohibited.",
            facts_evaluated=facts_eval,
        )
    elif action in (ActionType.BLOCK_CARD, ActionType.CREATE_CASE):
        return PolicyRuleResult(
            rule_id="R2",
            rule_name="Customer denies transaction",
            status=RuleEvaluationStatus.SATISFIED,
            reason="R2 Satisfied: Customer denied transaction; BLOCK_CARD and CREATE_CASE are permitted.",
            facts_evaluated=facts_eval,
        )
    elif action == ActionType.FILE_REPORT:
        if exposure_usd > 1000.0 or has_shared_link:
            return PolicyRuleResult(
                rule_id="R2",
                rule_name="Customer denies transaction",
                status=RuleEvaluationStatus.SATISFIED,
                reason="R2 Satisfied: Customer denial with exposure > $1,000 or shared link permits and requires FILE_REPORT.",
                facts_evaluated=facts_eval,
            )
        return PolicyRuleResult(
            rule_id="R2",
            rule_name="Customer denies transaction",
            status=RuleEvaluationStatus.SATISFIED,
            reason="R2 Satisfied: Customer denial permits FILE_REPORT.",
            facts_evaluated=facts_eval,
        )

    return PolicyRuleResult(
        rule_id="R2",
        rule_name="Customer denies transaction",
        status=RuleEvaluationStatus.NOT_APPLICABLE,
        reason=f"R2: Customer denied transaction; action '{action.value}' is not directly governed by R2.",
        facts_evaluated=facts_eval,
    )


def evaluate_r3(
    action: ActionType,
    investigation: Optional[InvestigationResult] = None,
    risk: Optional[RiskAssessment] = None,
    exposure_usd: float = 0.0,
    facts: Optional[Dict[str, Any]] = None,
) -> PolicyRuleResult:
    """
    Rule R3 (Customer confirms transaction):
    Recommend CLOSE_NO_FRAUD and record confirmation in case notes.
    Prohibits BLOCK_CARD, BLOCK_ALL_CARDS, DECLINE_TRANSACTION.
    """
    ctx = facts or {}
    
    confirmed = (
        ctx.get("customer_response") in ("confirms", "confirmed", "legitimate")
        or ctx.get("customer_confirmed") is True
    )

    if not confirmed and investigation:
        for req in investigation.evidence_requests if hasattr(investigation, "evidence_requests") else []:
            resp = getattr(req, "assumed_response", "") or ""
            if any(w in resp.lower() for w in ("confirm", "made purchase", "legitimate", "authorized")):
                confirmed = True
                break

    facts_eval = {
        "customer_confirmed": confirmed,
        "action": action.value,
    }

    if not confirmed:
        return PolicyRuleResult(
            rule_id="R3",
            rule_name="Customer confirms transaction",
            status=RuleEvaluationStatus.NOT_APPLICABLE,
            reason="R3 not triggered: customer has not confirmed the transaction.",
            facts_evaluated=facts_eval,
        )

    # Customer confirmed
    if action in (ActionType.BLOCK_CARD, ActionType.BLOCK_ALL_CARDS, ActionType.DECLINE_TRANSACTION):
        return PolicyRuleResult(
            rule_id="R3",
            rule_name="Customer confirms transaction",
            status=RuleEvaluationStatus.VIOLATED,
            reason=f"R3 Violation: Customer confirmed transaction as legitimate. Action '{action.value}' is strictly prohibited.",
            facts_evaluated=facts_eval,
        )
    elif action in (ActionType.CLOSE_NO_FRAUD, ActionType.ALLOW_TRANSACTION):
        return PolicyRuleResult(
            rule_id="R3",
            rule_name="Customer confirms transaction",
            status=RuleEvaluationStatus.SATISFIED,
            reason="R3 Satisfied: Customer confirmed transaction; CLOSE_NO_FRAUD or ALLOW_TRANSACTION is permitted.",
            facts_evaluated=facts_eval,
        )

    return PolicyRuleResult(
        rule_id="R3",
        rule_name="Customer confirms transaction",
        status=RuleEvaluationStatus.NOT_APPLICABLE,
        reason=f"R3: Customer confirmed transaction; action '{action.value}' is unaffected.",
        facts_evaluated=facts_eval,
    )


def evaluate_r4(
    action: ActionType,
    investigation: Optional[InvestigationResult] = None,
    risk: Optional[RiskAssessment] = None,
    exposure_usd: float = 0.0,
    facts: Optional[Dict[str, Any]] = None,
) -> PolicyRuleResult:
    """
    Rule R4 (No reply within 24 hours):
    Recommend MONITOR_CARD and DECLINE_TRANSACTION for pending authorizations.
    Escalate if exposure > $500.00.
    """
    ctx = facts or {}
    unresponsive = (
        ctx.get("unresponsive_24h") is True
        or ctx.get("customer_response") in ("no_reply_24h", "unresponsive", "timeout")
        or (ctx.get("hours_since_inquiry", 0) >= 24 and not ctx.get("customer_response"))
    )

    facts_eval = {
        "unresponsive_24h": unresponsive,
        "exposure_usd": exposure_usd,
        "action": action.value,
    }

    if not unresponsive:
        return PolicyRuleResult(
            rule_id="R4",
            rule_name="No reply within 24 hours",
            status=RuleEvaluationStatus.NOT_APPLICABLE,
            reason="R4 not triggered: inquiry is not 24h unresponsive.",
            facts_evaluated=facts_eval,
        )

    if action in (ActionType.MONITOR_CARD, ActionType.DECLINE_TRANSACTION):
        return PolicyRuleResult(
            rule_id="R4",
            rule_name="No reply within 24 hours",
            status=RuleEvaluationStatus.SATISFIED,
            reason="R4 Satisfied: Customer unresponsive after 24h; monitoring card and declining pending transactions permitted.",
            facts_evaluated=facts_eval,
        )
    elif action == ActionType.ESCALATE_TO_ANALYST:
        if exposure_usd > 500.0:
            return PolicyRuleResult(
                rule_id="R4",
                rule_name="No reply within 24 hours",
                status=RuleEvaluationStatus.SATISFIED,
                reason="R4 Satisfied: Unresponsive customer with exposure > $500 requires ESCALATE_TO_ANALYST.",
                facts_evaluated=facts_eval,
            )
        return PolicyRuleResult(
            rule_id="R4",
            rule_name="No reply within 24 hours",
            status=RuleEvaluationStatus.SATISFIED,
            reason="R4 Satisfied: Escalation to analyst permitted.",
            facts_evaluated=facts_eval,
        )

    return PolicyRuleResult(
        rule_id="R4",
        rule_name="No reply within 24 hours",
        status=RuleEvaluationStatus.NOT_APPLICABLE,
        reason=f"R4: Customer unresponsive 24h; action '{action.value}' not specified by R4.",
        facts_evaluated=facts_eval,
    )


def evaluate_r5(
    action: ActionType,
    investigation: Optional[InvestigationResult] = None,
    risk: Optional[RiskAssessment] = None,
    exposure_usd: float = 0.0,
    facts: Optional[Dict[str, Any]] = None,
) -> PolicyRuleResult:
    """
    Rule R5 (Card testing):
    3+ small online authorizations within an hour followed by a larger purchase
    -> recommend DECLINE_TRANSACTION and STEP_UP_AUTH.
    If purchase cleared > $100.00 -> recommend BLOCK_CARD.
    """
    ctx = facts or {}
    
    is_card_testing = (
        ctx.get("pattern") == "card_testing"
        or ctx.get("card_testing_sequence") is True
        or ctx.get("is_card_testing") is True
        or ctx.get("card_testing") is True
    )

    if not is_card_testing and investigation:
        for p in getattr(investigation, "fraud_pattern_evidence", []):
            p_name = p.get("name", "") if isinstance(p, dict) else getattr(p, "name", "")
            p_id = p.get("pattern_id", "") if isinstance(p, dict) else getattr(p, "pattern_id", "")
            if "testing" in p_name.lower() or p_id in ("FP-02", "FP-05"):
                is_card_testing = True
                break

    cleared_over_100 = (
        ctx.get("cleared_over_100", False) is True
        or float(ctx.get("cleared_amount", 0.0)) > 100.0
        or (ctx.get("transaction_cleared", False) is True and exposure_usd > 100.0)
    )

    facts_eval = {
        "card_testing": is_card_testing,
        "cleared_over_100": cleared_over_100,
        "exposure_usd": exposure_usd,
        "action": action.value,
    }

    if not is_card_testing:
        return PolicyRuleResult(
            rule_id="R5",
            rule_name="Card testing sequence",
            status=RuleEvaluationStatus.NOT_APPLICABLE,
            reason="R5 not triggered: card testing sequence not observed.",
            facts_evaluated=facts_eval,
        )

    if action in (ActionType.DECLINE_TRANSACTION, ActionType.STEP_UP_AUTH):
        return PolicyRuleResult(
            rule_id="R5",
            rule_name="Card testing sequence",
            status=RuleEvaluationStatus.SATISFIED,
            reason="R5 Satisfied: Card testing sequence observed; DECLINE_TRANSACTION and STEP_UP_AUTH permitted.",
            facts_evaluated=facts_eval,
        )
    elif action == ActionType.BLOCK_CARD:
        if cleared_over_100:
            return PolicyRuleResult(
                rule_id="R5",
                rule_name="Card testing sequence",
                status=RuleEvaluationStatus.SATISFIED,
                reason="R5 Satisfied: Card testing with cleared purchase > $100.00 permits BLOCK_CARD.",
                facts_evaluated=facts_eval,
            )
        else:
            return PolicyRuleResult(
                rule_id="R5",
                rule_name="Card testing sequence",
                status=RuleEvaluationStatus.VIOLATED,
                reason="R5 Violation: Card testing without cleared purchase > $100.00 prohibits BLOCK_CARD; must DECLINE_TRANSACTION and STEP_UP_AUTH.",
                facts_evaluated=facts_eval,
            )

    return PolicyRuleResult(
        rule_id="R5",
        rule_name="Card testing sequence",
        status=RuleEvaluationStatus.NOT_APPLICABLE,
        reason=f"R5: Card testing sequence active; action '{action.value}' not directly governed by R5.",
        facts_evaluated=facts_eval,
    )


def evaluate_r6(
    action: ActionType,
    investigation: Optional[InvestigationResult] = None,
    risk: Optional[RiskAssessment] = None,
    exposure_usd: float = 0.0,
    facts: Optional[Dict[str, Any]] = None,
) -> PolicyRuleResult:
    """
    Rule R6 (Shared origin):
    Multiple cards showing fraud from the same device profile, billing region,
    or recipient email in one window -> recommend CREATE_CASE, FILE_REPORT, and MONITOR_CONNECTED_CARDS.
    """
    ctx = facts or {}
    shared_origin = (
        ctx.get("shared_origin") is True
        or ctx.get("syndicate_ring") is True
        or ctx.get("multiple_cards_fraud") is True
        or (investigation and len(getattr(investigation, "connected_entities", {}).get("connected_cards", [])) > 1)
    )

    facts_eval = {
        "shared_origin": shared_origin,
        "action": action.value,
    }

    if not shared_origin:
        return PolicyRuleResult(
            rule_id="R6",
            rule_name="Shared origin across cards",
            status=RuleEvaluationStatus.NOT_APPLICABLE,
            reason="R6 not triggered: multiple cards from shared origin not detected.",
            facts_evaluated=facts_eval,
        )

    if action in (ActionType.CREATE_CASE, ActionType.FILE_REPORT, ActionType.MONITOR_CONNECTED_CARDS):
        return PolicyRuleResult(
            rule_id="R6",
            rule_name="Shared origin across cards",
            status=RuleEvaluationStatus.SATISFIED,
            reason="R6 Satisfied: Shared origin syndicate detected; CREATE_CASE, FILE_REPORT, and MONITOR_CONNECTED_CARDS permitted.",
            facts_evaluated=facts_eval,
        )

    return PolicyRuleResult(
        rule_id="R6",
        rule_name="Shared origin across cards",
        status=RuleEvaluationStatus.NOT_APPLICABLE,
        reason=f"R6: Shared origin detected; action '{action.value}' not directly governed by R6.",
        facts_evaluated=facts_eval,
    )


def evaluate_r7(
    action: ActionType,
    investigation: Optional[InvestigationResult] = None,
    risk: Optional[RiskAssessment] = None,
    exposure_usd: float = 0.0,
    facts: Optional[Dict[str, Any]] = None,
) -> PolicyRuleResult:
    """
    Rule R7 (Disputed recurring charge):
    Customer disputes recurring charge matching historical pattern
    -> recommend CREATE_CASE, VERIFY_WITH_CUSTOMER, WARN_CUSTOMER. Do NOT block.
    """
    ctx = facts or {}
    disputed_recurring = (
        ctx.get("disputed_recurring_charge") is True
        or ctx.get("is_recurring_dispute") is True
        or ctx.get("recurring_dispute") is True
        or ctx.get("disputed_recurring") is True
    )

    facts_eval = {
        "disputed_recurring": disputed_recurring,
        "action": action.value,
    }

    if not disputed_recurring:
        return PolicyRuleResult(
            rule_id="R7",
            rule_name="Disputed recurring charge",
            status=RuleEvaluationStatus.NOT_APPLICABLE,
            reason="R7 not triggered: transaction is not a disputed recurring charge.",
            facts_evaluated=facts_eval,
        )

    # R7 forbids blocking
    if action in (ActionType.BLOCK_CARD, ActionType.BLOCK_ALL_CARDS):
        return PolicyRuleResult(
            rule_id="R7",
            rule_name="Disputed recurring charge",
            status=RuleEvaluationStatus.VIOLATED,
            reason="R7 Violation: Customer disputes recurring charge matching historical pattern. Card blocking is strictly prohibited.",
            facts_evaluated=facts_eval,
        )
    elif action in (ActionType.CREATE_CASE, ActionType.VERIFY_WITH_CUSTOMER, ActionType.WARN_CUSTOMER):
        return PolicyRuleResult(
            rule_id="R7",
            rule_name="Disputed recurring charge",
            status=RuleEvaluationStatus.SATISFIED,
            reason="R7 Satisfied: Disputed recurring charge appropriately handled with case creation, verification, or warning.",
            facts_evaluated=facts_eval,
        )

    return PolicyRuleResult(
        rule_id="R7",
        rule_name="Disputed recurring charge",
        status=RuleEvaluationStatus.NOT_APPLICABLE,
        reason=f"R7: Disputed recurring charge active; action '{action.value}' not directly governed by R7.",
        facts_evaluated=facts_eval,
    )


def evaluate_r8(
    action: ActionType,
    investigation: Optional[InvestigationResult] = None,
    risk: Optional[RiskAssessment] = None,
    exposure_usd: float = 0.0,
    facts: Optional[Dict[str, Any]] = None,
) -> PolicyRuleResult:
    """
    Rule R8 (Escalate when uncertain and exposed):
    If verdict is uncertain and exposure > $500.00, or evidence conflicts
    -> recommend ESCALATE_TO_ANALYST.
    """
    ctx = facts or {}
    
    is_uncertain = (
        ctx.get("verdict") == "uncertain"
        or ctx.get("is_uncertain") is True
        or (risk and risk.confidence < 0.70)
        or (risk and risk.uncertainty > 0.30)
        or (risk and risk.stopping_decision and risk.stopping_decision.status in (StoppingStatus.INCONCLUSIVE, StoppingStatus.MORE_EVIDENCE_REQUIRED))
    )
    conflicting = ctx.get("conflicting_evidence", False) is True
    high_exposure = exposure_usd > 500.0

    condition_met = (is_uncertain and high_exposure) or conflicting

    facts_eval = {
        "uncertain": is_uncertain,
        "conflicting_evidence": conflicting,
        "exposure_usd": exposure_usd,
        "action": action.value,
    }

    if not condition_met:
        return PolicyRuleResult(
            rule_id="R8",
            rule_name="Escalate when uncertain and exposed",
            status=RuleEvaluationStatus.NOT_APPLICABLE,
            reason="R8 not triggered: evidence is not uncertain/conflicting or exposure <= $500.",
            facts_evaluated=facts_eval,
        )

    if action == ActionType.ESCALATE_TO_ANALYST:
        return PolicyRuleResult(
            rule_id="R8",
            rule_name="Escalate when uncertain and exposed",
            status=RuleEvaluationStatus.SATISFIED,
            reason="R8 Satisfied: Uncertain verdict with exposure > $500 or conflicting evidence requires ESCALATE_TO_ANALYST.",
            facts_evaluated=facts_eval,
        )

    return PolicyRuleResult(
        rule_id="R8",
        rule_name="Escalate when uncertain and exposed",
        status=RuleEvaluationStatus.NOT_APPLICABLE,
        reason=f"R8: Escalation recommended for uncertain exposure > $500; proposed action is '{action.value}'.",
        facts_evaluated=facts_eval,
    )


def evaluate_r9(
    action: ActionType,
    investigation: Optional[InvestigationResult] = None,
    risk: Optional[RiskAssessment] = None,
    exposure_usd: float = 0.0,
    facts: Optional[Dict[str, Any]] = None,
) -> PolicyRuleResult:
    """
    Rule R9 (Undocumented patterns):
    Coordinated abuse fitting no known pattern
    -> recommend CREATE_CASE, FILE_REPORT, and ESCALATE_TO_ANALYST. Describe pattern in analyst notes.
    """
    ctx = facts or {}
    is_undocumented = (
        ctx.get("pattern") == "undocumented"
        or ctx.get("is_undocumented") is True
        or ctx.get("unknown_pattern") is True
    )

    if not is_undocumented and investigation:
        for p in getattr(investigation, "fraud_pattern_evidence", []):
            p_name = p.get("name", "") if isinstance(p, dict) else getattr(p, "name", "")
            p_id = p.get("pattern_id", "") if isinstance(p, dict) else getattr(p, "pattern_id", "")
            if "undocumented" in p_name.lower() or p_id == "FP-03":
                is_undocumented = True
                break

    facts_eval = {
        "undocumented_pattern": is_undocumented,
        "action": action.value,
    }

    if not is_undocumented:
        return PolicyRuleResult(
            rule_id="R9",
            rule_name="Undocumented patterns",
            status=RuleEvaluationStatus.NOT_APPLICABLE,
            reason="R9 not triggered: pattern is documented or known.",
            facts_evaluated=facts_eval,
        )

    if action in (ActionType.CREATE_CASE, ActionType.FILE_REPORT, ActionType.ESCALATE_TO_ANALYST):
        return PolicyRuleResult(
            rule_id="R9",
            rule_name="Undocumented patterns",
            status=RuleEvaluationStatus.SATISFIED,
            reason="R9 Satisfied: Undocumented pattern; CREATE_CASE, FILE_REPORT, and ESCALATE_TO_ANALYST permitted.",
            facts_evaluated=facts_eval,
        )

    return PolicyRuleResult(
        rule_id="R9",
        rule_name="Undocumented patterns",
        status=RuleEvaluationStatus.NOT_APPLICABLE,
        reason=f"R9: Undocumented pattern active; action '{action.value}' not directly governed by R9.",
        facts_evaluated=facts_eval,
    )


def evaluate_r10(
    action: ActionType,
    investigation: Optional[InvestigationResult] = None,
    risk: Optional[RiskAssessment] = None,
    exposure_usd: float = 0.0,
    facts: Optional[Dict[str, Any]] = None,
) -> PolicyRuleResult:
    """
    Rule R10 (Constraint on BLOCK_ALL_CARDS):
    NEVER recommend BLOCK_ALL_CARDS unless >= 2 customer cards show confirmed fraud
    or customer credentials are confirmed compromised.
    """
    ctx = facts or {}
    
    # R10 only constrains BLOCK_ALL_CARDS
    if action != ActionType.BLOCK_ALL_CARDS:
        return PolicyRuleResult(
            rule_id="R10",
            rule_name="Constraint on BLOCK_ALL_CARDS",
            status=RuleEvaluationStatus.NOT_APPLICABLE,
            reason=f"R10 not triggered: action is '{action.value}', not BLOCK_ALL_CARDS.",
            facts_evaluated={"action": action.value},
        )

    confirmed_fraud_cards = int(ctx.get("confirmed_fraud_cards_count", 0))
    if not confirmed_fraud_cards and investigation:
        shared = getattr(investigation, "connected_entities", {}).get("connected_cards", [])
        if len(shared) >= 2 and ctx.get("customer_denied"):
            confirmed_fraud_cards = len(shared)

    credentials_compromised = (
        ctx.get("credentials_compromised", False) is True
        or ctx.get("account_takeover", False) is True
        or ctx.get("pattern") == "account_takeover"
    )

    meets_criteria = (confirmed_fraud_cards >= 2) or credentials_compromised

    facts_eval = {
        "action": action.value,
        "confirmed_fraud_cards_count": confirmed_fraud_cards,
        "credentials_compromised": credentials_compromised,
        "criteria_met": meets_criteria,
    }

    if meets_criteria:
        return PolicyRuleResult(
            rule_id="R10",
            rule_name="Constraint on BLOCK_ALL_CARDS",
            status=RuleEvaluationStatus.SATISFIED,
            reason="R10 Satisfied: >= 2 cards show confirmed fraud or credentials compromised. BLOCK_ALL_CARDS permitted.",
            facts_evaluated=facts_eval,
        )
    else:
        return PolicyRuleResult(
            rule_id="R10",
            rule_name="Constraint on BLOCK_ALL_CARDS",
            status=RuleEvaluationStatus.VIOLATED,
            reason="R10 Violation: Prohibited to BLOCK_ALL_CARDS unless >= 2 customer cards show confirmed fraud or customer credentials are confirmed compromised.",
            facts_evaluated=facts_eval,
        )


ALL_RULES = [
    evaluate_r1,
    evaluate_r2,
    evaluate_r3,
    evaluate_r4,
    evaluate_r5,
    evaluate_r6,
    evaluate_r7,
    evaluate_r8,
    evaluate_r9,
    evaluate_r10,
]


def evaluate_all_rules(
    action: ActionType,
    investigation: Optional[InvestigationResult] = None,
    risk: Optional[RiskAssessment] = None,
    exposure_usd: float = 0.0,
    facts: Optional[Dict[str, Any]] = None,
) -> List[PolicyRuleResult]:
    """
    Evaluates all 10 binding organizer rules deterministically against candidate action and facts.
    """
    results: List[PolicyRuleResult] = []
    for rule_fn in ALL_RULES:
        res = rule_fn(
            action=action,
            investigation=investigation,
            risk=risk,
            exposure_usd=exposure_usd,
            facts=facts,
        )
        results.append(res)
    return results
