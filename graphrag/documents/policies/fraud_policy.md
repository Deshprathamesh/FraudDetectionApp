# Global Bank - Enterprise Fraud Mitigation & Risk Policy
**Document Reference**: POL-FRAUD-2026-V1  
**Effective Date**: January 1, 2026  
**Governing Bodies**: BSA / FinCEN, CFPB (Regulation E), OCC Risk Governance

---

## 1. Scope & Objective
This policy governs automated and agentic fraud intervention, transaction decisioning, regulatory reporting, and customer escalation protocols across all retail, commercial, and card payment networks.

---

## 2. Action Thresholds & Decision Matrix

Automated and analyst-assisted fraud actions must adhere to the following confidence and risk thresholds:

### 2.1 Action Matrix
* **ALLOW_TRANSACTION**:
  - *Criteria*: Transaction risk score `< 0.30` with no adverse entity links (clean device, clean IP, no velocity deviations).
  - *Execution*: Instant automated execution. No analyst approval required.
* **REQUEST_STEP_UP_AUTH / REQUEST_VERIFICATION**:
  - *Criteria*: Transaction risk score between `0.30` and `0.70`, OR high uncertainty (confidence `< 0.70`), OR first-time transaction from a new device/geolocation.
  - *Execution*: Pre-decision challenge (SMS OTP, biometric prompt, or push authentication).
  - *Policy Rule*: Auto-allowed without supervisor sign-off.
* **BLOCK_TRANSACTION**:
  - *Criteria*: Transaction risk score `≥ 0.70` with corroborated evidence (e.g., syndicate ring, velocity burst, known stolen credential).
  - *Execution*:
    - If transaction amount is `< $5,000`: Automated block permitted with immediate customer notification.
    - If transaction amount is `≥ $5,000`: Mandatory L2 human analyst approval required prior to irreversible account lockdown.
* **FREEZE_ACCOUNT**:
  - *Criteria*: Multi-account takeover indicators, distributed mule account behavior, or severe device sharing rings.
  - *Execution*: High-impact action. Requires secondary supervisor approval regardless of amount.
* **ESCALATE_TO_ANALYST**:
  - *Criteria*: High transaction value (`≥ $5,000`), or conflicting signals (e.g., high risk score but VIP customer profile).

---

## 3. High-Value Transaction Approvals

### 3.1 Secondary Approval Threshold
* **Threshold**: Any transaction or cumulative daily debit activity exceeding **$5,000.00 USD** flagged as suspicious (`risk_score ≥ 0.70`).
* **Governance Rule**: Automated agents are strictly prohibited from unilateral permanent fund forfeiture or unilateral unrestricted account closures exceeding $5,000 without documented secondary human-in-the-loop (HITL) approval.
* **Approval Routing**: Route to Fraud Investigation Team Tier-2 (Supervisory Queue).

---

## 4. Suspicious Activity Reporting (SAR) Obligations

Under the Bank Secrecy Act (BSA) and FinCEN regulations (31 CFR § 1020.320):

### 4.1 Mandatory SAR Filing Triggers
1. **Identified Subject Threshold**: Any suspicious transaction, series of transactions, or suspected fraud pattern aggregating **$5,000 or more** where a suspect or beneficiary entity has been identified.
2. **Unidentified Subject Threshold**: Any suspicious transaction aggregating **$25,000 or more** where no subject can be identified (e.g., automated card testing or anonymous botnet attacks).
3. **Structuring & Mule Networks**: Any transaction designed to evade BSA reporting thresholds ($10,000 CTR) or rapid pass-through mule account distribution must be submitted for SAR review within 30 calendar days.

### 4.2 SAR Filing Protocol
* The automated agent must flag `sar_required = true` on the investigation case record.
* The agent must compile a draft SAR narrative including:
  - Subject customer ID and account details.
  - Device fingerprint, IP address, and proxy indicator.
  - Subgraph typology (e.g., shared device ring, mule chain).
  - Chronological transaction timeline.

---

## 5. Customer Contact Policy & Regulation E Compliance

### 5.1 Customer Notification Guidelines
* **Proactive Contact**: Within 15 minutes of an automated transaction block or step-up challenge, an automated notification (SMS, email, in-app push) must be dispatched to the customer's registered contact handles.
* **Communication Standards**: Notifications must specify the card ending in the last 4 digits, merchant name, and dollar amount. Notifications must never ask for passwords or full account credentials.

### 5.2 Regulation E (12 CFR Part 1005) Dispute Management
* **Unauthorized Transfers**: When a customer disputes a transaction under Regulation E:
  - The bank must investigate and provide provisional credit within 10 business days if the investigation is ongoing.
  - The investigation record, graph evidence, and device authentication logs must be preserved as defensible audit records.
  - If fraud is confirmed as third-party compromise, the account must be re-secured and customer funds restored within statutory limits ($50 maximum liability if reported within 2 business days).
