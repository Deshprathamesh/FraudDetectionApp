# Bank Fraud Typologies & Known Patterns Reference Guide
**Document Reference**: TYP-PATTERNS-2026-V1  
**Target Architecture**: TigerGraph Knowledge Graph & GraphRAG Pipeline

This document defines the 5 primary fraud patterns recognized by the bank's fraud detection models, their graph signatures, observable indicators, and prescribed next-best actions.

---

### [FP-01] Shared Device Syndicate Ring
* **Name**: Shared Device Syndicate Ring / Account Takeover Ring
* **Category**: Device & Network Fraud
* **Severity**: High (0.85)
* **Graph Topology**: Multiple distinct `Customer` / `Account` nodes connecting to a single `Device` hardware fingerprint or shared UUID within a rolling 48-hour window.
* **Observable Indicators**:
  - `Device.linked_accounts ≥ 3` across unrelated names/SSNs.
  - Rapid sequential login attempts from the same browser/OS profile.
  - Alternating credit card numbers across different billing addresses on the same device.
* **Prescribed Next-Best Actions**:
  - `BLOCK_TRANSACTION`: Block pending checkout authorization.
  - `FREEZE_ACCOUNT`: Restrict all linked accounts on the device ring pending manual investigation.
  - Request step-up biometric re-authentication for affected legitimate account holders.

---

### [FP-02] Card Testing & Rapid Velocity Burst
* **Name**: Card Testing & Rapid Velocity Burst
* **Category**: Automated Bot & Velocity Fraud
* **Severity**: High (0.80)
* **Graph Topology**: Single `Account` or `CreditCard` issuing high-frequency transaction edges (`c1`..`c14` counters elevated) within a compressed time frame.
* **Observable Indicators**:
  - Burst of 3+ micro-transactions (< $5.00) at digital merchants/gas stations followed immediately by high-value (> $500.00) purchases.
  - Transaction frequency exceeds 3 standard deviations above customer 30-day baseline velocity.
  - Repeated CVV/expiration mismatches prior to successful authorization.
* **Prescribed Next-Best Actions**:
  - `BLOCK_TRANSACTION`: Prevent high-value cash-out attempt.
  - Place temporary transaction velocity throttle on the card token.
  - Send SMS verification challenge to customer mobile device.

---

### [FP-03] Mule Account Daisy-Chain & Capital Flight
* **Name**: Mule Account Daisy-Chain & Rapid Funneling
* **Category**: AML / Money Laundering
* **Severity**: Critical (0.95)
* **Graph Topology**: Linear daisy-chain or fan-out fund routing: rapid inbound transfer followed by immediate outbound transfer to high-risk beneficiary nodes (crypto exchanges, offshore wire).
* **Observable Indicators**:
  - Account age `< 30 days` receiving sudden high-value deposit followed within minutes by full balance withdrawal.
  - Minimal retail purchasing history; 95%+ of volume comprises peer-to-peer or wire transfers.
  - Overlapping IP address subnets across sending and receiving parties.
* **Prescribed Next-Best Actions**:
  - `FREEZE_ACCOUNT`: Immediately place administrative debit freeze on intermediate mule accounts.
  - `FILE_SAR`: Suspicious Activity Report (SAR) filing mandatory under FinCEN BSA rules for fund transfers aggregating ≥ $5,000.
  - Escalate to AML Financial Intelligence Unit (FIU).

---

### [FP-04] Geo-Velocity & Proxy Churning
* **Name**: Geo-Velocity Anomaly & Anonymized Proxy Churning
* **Category**: Cyber / Identity Masking
* **Severity**: High (0.90)
* **Graph Topology**: Consecutive `Transaction` nodes linked to `IPAddress` vertices in disparate geographic jurisdictions with impossible physical travel times, or IP flagged as Tor/VPN.
* **Observable Indicators**:
  - Physical distance between successive transactions > 500 miles within < 1 hour (`dist1`, `dist2` anomalies).
  - Connection originating from known commercial datacenter, Tor exit node, or residential proxy network.
  - Timezone mismatch between device locale and geolocation IP.
* **Prescribed Next-Best Actions**:
  - `REQUEST_STEP_UP_AUTH`: Require out-of-band push authentication or mobile authenticator verification.
  - If transaction > $5,000 or customer does not respond: `BLOCK_TRANSACTION`.
  - Add proxy IP subnet to risk monitoring watchlist.

---

### [FP-05] Synthetic Identity Overlap & Credential Stuffing
* **Name**: Synthetic Identity Profile Overlap
* **Category**: Identity Fraud
* **Severity**: Medium-High (0.75)
* **Graph Topology**: Tangled bipartite graph where multiple `Customer` entities share overlapping `Email`, phone numbers, or physical addresses, paired with fragmented SSN records.
* **Observable Indicators**:
  - Disposable or temporary email domain (`is_disposable = true`).
  - Credit file with thin credit history coupled with high initial credit line request.
  - Shared billing address across 5+ applicants within 60 days.
* **Prescribed Next-Best Actions**:
  - `REQUEST_VERIFICATION`: Demand primary government ID and utility bill proof of address.
  - Restrict credit line expansion and hold pending disbursements.
  - Escalate case to Senior Fraud Analyst.
