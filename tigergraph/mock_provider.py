# ==============================================================================
# FraudGraph AI - TigerGraph Mock Provider
# Workstream: Person 2 (Graph)
#
# ==============================================================================
# PLACEHOLDER DATA - FOR TESTING AND AGENT INTEGRATION ONLY
# ==============================================================================
# This mock provider simulates TigerGraph queries and graph intelligence
# operations using deterministic, pre-seeded graph fixtures.
# This data serves as a functional mock contract for Person 1 (Brain/Agent)
# and Person 3 (Product/Frontend) during early integration.
# It will be replaced once the full HHGOA_IEEE benchmark dataset is loaded.
# ==============================================================================

from typing import Dict, Any, List, Optional
import time

# ------------------------------------------------------------------------------
# Standard Error Exception matching Section 9 Error Contract
# ------------------------------------------------------------------------------

class GraphError(Exception):
    """Exception class strictly adhering to Section 9 standard error shape."""
    def __init__(self, code: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            }
        }


# ------------------------------------------------------------------------------
# In-Memory Graph Fixtures (PLACEHOLDER DATA)
# ------------------------------------------------------------------------------

MOCK_TRANSACTIONS: Dict[str, Dict[str, Any]] = {
    "TXN-104829": {
        "transaction_id": "TXN-104829",
        "customer_id": "C-45821",
        "account_id": "ACC-90124",
        "amount": 1249.50,
        "currency": "USD",
        "timestamp": 1718002000,
        "risk_score": 0.87,
        "channel": "W",
        "card_network": "visa",
        "merchant_name": "Electronics Hub Online",
        "device_id": "D-421",
        "ip_str": "198.51.100.42",
        "dist1": 14.0,
        "dist2": 0.0,
        "c1": 4,
        "c2": 3,
        "c3": 0,
        "c4": 1,
        "c5": 0,
        "c6": 2,
        "c7": 0,
        "c8": 1,
        "c9": 0,
        "c10": 1,
        "c11": 2,
        "c12": 0,
        "c13": 3,
        "c14": 1,
    },
    "TXN-209144": {
        "transaction_id": "TXN-209144",
        "customer_id": "C-77109",
        "account_id": "ACC-33109",
        "amount": 48.00,
        "currency": "USD",
        "timestamp": 1718005400,
        "risk_score": 0.12,
        "channel": "R",
        "card_network": "mastercard",
        "merchant_name": "Daily Groceries Express",
        "device_id": "D-119",
        "ip_str": "203.0.113.15",
        "dist1": 2.5,
        "dist2": 0.0,
        "c1": 1,
        "c2": 1,
        "c3": 0,
        "c4": 0,
        "c5": 0,
        "c6": 1,
        "c7": 0,
        "c8": 0,
        "c9": 0,
        "c10": 0,
        "c11": 1,
        "c12": 0,
        "c13": 1,
        "c14": 1,
    },
    "TXN-301855": {
        "transaction_id": "TXN-301855",
        "customer_id": "C-10294",
        "account_id": "ACC-55210",
        "amount": 8450.00,
        "currency": "USD",
        "timestamp": 1718011200,
        "risk_score": 0.94,
        "channel": "W",
        "card_network": "visa",
        "merchant_name": "Global Wire & Crypto Swap",
        "device_id": "D-884",
        "ip_str": "185.220.101.5",
        "dist1": 850.0,
        "dist2": 120.0,
        "c1": 12,
        "c2": 8,
        "c3": 0,
        "c4": 5,
        "c5": 0,
        "c6": 9,
        "c7": 0,
        "c8": 4,
        "c9": 0,
        "c10": 3,
        "c11": 7,
        "c12": 0,
        "c13": 10,
        "c14": 6,
    },
    "TXN-405112": {
        "transaction_id": "TXN-405112",
        "customer_id": "C-99321",
        "account_id": "ACC-67123",
        "amount": 310.00,
        "currency": "USD",
        "timestamp": 1718014500,
        "risk_score": 0.65,
        "channel": "M",
        "card_network": "discover",
        "merchant_name": "Luxury App Direct",
        "device_id": "D-302",
        "ip_str": "192.0.2.88",
        "dist1": 45.0,
        "dist2": 0.0,
        "c1": 2,
        "c2": 2,
        "c3": 0,
        "c4": 1,
        "c5": 0,
        "c6": 1,
        "c7": 0,
        "c8": 1,
        "c9": 0,
        "c10": 1,
        "c11": 1,
        "c12": 0,
        "c13": 2,
        "c14": 1,
    }
}

MOCK_CUSTOMERS: Dict[str, Dict[str, Any]] = {
    "C-45821": {
        "customer_id": "C-45821",
        "name": "Alex Mercer",
        "risk_tier": "HIGH",
        "created_at": 1690000000,
        "accounts": ["ACC-90124"],
        "linked_cards": ["CARD-4029-XXXX-1102"],
        "email": "alex.mercer@mockmail.io",
        "risk_score": 0.84,
    },
    "C-77109": {
        "customer_id": "C-77109",
        "name": "Sarah Jenkins",
        "risk_tier": "LOW",
        "created_at": 1675000000,
        "accounts": ["ACC-33109"],
        "linked_cards": ["CARD-5100-XXXX-8921"],
        "email": "sarah.j@legitbank.com",
        "risk_score": 0.08,
    },
    "C-10294": {
        "customer_id": "C-10294",
        "name": "Dmitri Volkov",
        "risk_tier": "CRITICAL",
        "created_at": 1715000000,
        "accounts": ["ACC-55210"],
        "linked_cards": ["CARD-4111-XXXX-9940"],
        "email": "dvolk_temp92@fasttemp.org",
        "risk_score": 0.93,
    },
    "C-99321": {
        "customer_id": "C-99321",
        "name": "Jordan Lee",
        "risk_tier": "MEDIUM",
        "created_at": 1705000000,
        "accounts": ["ACC-67123"],
        "linked_cards": ["CARD-6011-XXXX-3341"],
        "email": "jordan.lee@domain.net",
        "risk_score": 0.58,
    }
}

MOCK_DEVICE_RINGS: Dict[str, Dict[str, Any]] = {
    "D-421": {
        "device_id": "D-421",
        "linked_accounts": 4,
        "risk_score": 0.81,
        "associated_account_ids": ["ACC-90124", "ACC-88310", "ACC-12093", "ACC-77402"],
    },
    "D-119": {
        "device_id": "D-119",
        "linked_accounts": 1,
        "risk_score": 0.05,
        "associated_account_ids": ["ACC-33109"],
    },
    "D-884": {
        "device_id": "D-884",
        "linked_accounts": 3,
        "risk_score": 0.92,
        "associated_account_ids": ["ACC-55210", "ACC-44910", "ACC-19033"],
    },
    "D-302": {
        "device_id": "D-302",
        "linked_accounts": 2,
        "risk_score": 0.55,
        "associated_account_ids": ["ACC-67123", "ACC-99214"],
    }
}

MOCK_FRAUD_PATTERNS: Dict[str, List[Dict[str, Any]]] = {
    "TXN-104829": [
        {
            "pattern_id": "FP-01",
            "name": "Shared Device Syndicate Ring",
            "description": "Hardware fingerprint D-421 is linked across 4 distinct customer accounts with rapid credential alternation.",
            "evidence_refs": ["EVID-GRAPH-001", "EVID-DEV-421"],
            "confidence": 0.88,
        },
        {
            "pattern_id": "FP-02",
            "name": "Rapid Velocity Burst",
            "description": "Customer purchase velocity spiked by 4.2x above established 30-day baseline within a 3-hour window.",
            "evidence_refs": ["EVID-HIST-90124"],
            "confidence": 0.79,
        }
    ],
    "TXN-209144": [],
    "TXN-301855": [
        {
            "pattern_id": "FP-04",
            "name": "Geo-Velocity & Proxy Churning",
            "description": "Transaction executed via Tor exit node (185.220.101.5) with geographic displacement exceeding physical travel limits.",
            "evidence_refs": ["EVID-IP-884", "EVID-TOR-01"],
            "confidence": 0.95,
        },
        {
            "pattern_id": "FP-03",
            "name": "Mule Account Daisy-Chain",
            "description": "Newly funded account exhibiting high-volume outbound capital flight to high-risk merchant / crypto exchange.",
            "evidence_refs": ["EVID-FLOW-55210"],
            "confidence": 0.91,
        }
    ],
    "TXN-405112": [
        {
            "pattern_id": "FP-05",
            "name": "Card Testing Micro-Spurt",
            "description": "Repeated authorization attempts with varying CVVs and amounts prior to approval.",
            "evidence_refs": ["EVID-AUTH-302"],
            "confidence": 0.62,
        }
    ]
}

MOCK_SIMILAR_CASES: List[Dict[str, Any]] = [
    {
        "case_id": "CASE-0842",
        "similarity_score": 0.91,
        "status": "RESOLVED",
        "risk_score": 0.89,
        "outcome": "CONFIRMED_FRAUD",
        "matched_patterns": ["FP-01", "FP-02"],
        "key_findings": "Device sharing syndicate operating automated checkout scripts. Account blocked, funds recovered.",
    },
    {
        "case_id": "CASE-0773",
        "similarity_score": 0.88,
        "status": "RESOLVED",
        "risk_score": 0.96,
        "outcome": "CONFIRMED_FRAUD",
        "matched_patterns": ["FP-03", "FP-04"],
        "key_findings": "Mule network off-ramping stolen card balances via overseas crypto platforms. SAR filed.",
    },
    {
        "case_id": "CASE-0915",
        "similarity_score": 0.72,
        "status": "RESOLVED",
        "risk_score": 0.64,
        "outcome": "CLEARED",
        "matched_patterns": ["FP-04"],
        "key_findings": "False positive triggered by legitimate executive roaming travel. Verified via step-up authentication.",
    },
    {
        "case_id": "CASE-0620",
        "similarity_score": 0.68,
        "status": "RESOLVED",
        "risk_score": 0.78,
        "outcome": "CONFIRMED_FRAUD",
        "matched_patterns": ["FP-05"],
        "key_findings": "Automated BIN attack and credential stuffing. Card blocked and replaced.",
    }
]

# In-memory Case Store for case-memory write/read operations
MOCK_WRITTEN_CASES: Dict[str, Dict[str, Any]] = {}


# ------------------------------------------------------------------------------
# Mock Provider Implementation Class
# ------------------------------------------------------------------------------

class TigerGraphMockProvider:
    """
    Deterministic implementation of all 9 TigerGraph Agent Tool contracts.
    Matches Section 7 and Section 5 of the Integration Specification.
    """

    def get_transaction(self, transaction_id: str) -> Dict[str, Any]:
        """Tool 1: get_transaction(transaction_id) -> transaction details"""
        if not transaction_id or transaction_id not in MOCK_TRANSACTIONS:
            raise GraphError(
                code="TRANSACTION_NOT_FOUND",
                message=f"Transaction '{transaction_id}' was not found in graph database.",
                details={"transaction_id": transaction_id}
            )
        return MOCK_TRANSACTIONS[transaction_id]

    def get_customer(self, customer_id: str) -> Dict[str, Any]:
        """Tool 2: get_customer(customer_id) -> customer details"""
        if not customer_id or customer_id not in MOCK_CUSTOMERS:
            raise GraphError(
                code="CUSTOMER_NOT_FOUND",
                message=f"Customer '{customer_id}' was not found in graph database.",
                details={"customer_id": customer_id}
            )
        return MOCK_CUSTOMERS[customer_id]

    def get_transaction_history(self, entity_id: str, limit: int = 10) -> Dict[str, Any]:
        """Tool 3: get_transaction_history(customer/account id) -> transaction list + summary"""
        # Resolve customer or account id
        cust = None
        if entity_id in MOCK_CUSTOMERS:
            cust = MOCK_CUSTOMERS[entity_id]
        else:
            for c in MOCK_CUSTOMERS.values():
                if entity_id in c.get("accounts", []):
                    cust = c
                    break

        # Collect matching transactions
        matched_txns: List[Dict[str, Any]] = []
        for txn in MOCK_TRANSACTIONS.values():
            if cust and (txn["customer_id"] == cust["customer_id"] or txn["account_id"] in cust["accounts"]):
                matched_txns.append({
                    "transaction_id": txn["transaction_id"],
                    "amount": txn["amount"],
                    "timestamp": txn["timestamp"],
                    "merchant_name": txn["merchant_name"],
                    "risk_score": txn["risk_score"],
                    "channel": txn["channel"]
                })

        # If no customer match, return empty history with zero summary
        if not matched_txns:
            return {
                "transactions": [],
                "summary": {
                    "total_transactions": 0,
                    "avg_amount": 0.0,
                    "max_amount": 0.0,
                    "velocity_30d": 0,
                    "risk_distribution": {"low": 0, "medium": 0, "high": 0}
                }
            }

        matched_txns = sorted(matched_txns, key=lambda x: x["timestamp"], reverse=True)[:limit]
        total_txns = len(matched_txns)
        avg_amt = sum(t["amount"] for t in matched_txns) / total_txns if total_txns > 0 else 0.0
        max_amt = max(t["amount"] for t in matched_txns) if total_txns > 0 else 0.0

        low_count = sum(1 for t in matched_txns if t["risk_score"] < 0.3)
        med_count = sum(1 for t in matched_txns if 0.3 <= t["risk_score"] < 0.7)
        high_count = sum(1 for t in matched_txns if t["risk_score"] >= 0.7)

        return {
            "transactions": matched_txns,
            "summary": {
                "total_transactions": total_txns,
                "avg_amount": round(avg_amt, 2),
                "max_amount": round(max_amt, 2),
                "velocity_30d": total_txns * 3,  # simulated 30d baseline
                "risk_distribution": {
                    "low": low_count,
                    "medium": med_count,
                    "high": high_count
                }
            }
        }

    def get_connected_entities(self, entity_id: str, depth: int = 1) -> Dict[str, Any]:
        """Tool 4: get_connected_entities(entity_id, depth) -> nodes + edges"""
        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []
        visited = set()

        def add_node(nid: str, label: str, ntype: str, risk: float):
            if nid not in visited:
                visited.add(nid)
                nodes.append({
                    "id": nid,
                    "label": label,
                    "type": ntype,
                    "risk_score": risk
                })

        # Check if entity is transaction
        if entity_id in MOCK_TRANSACTIONS:
            t = MOCK_TRANSACTIONS[entity_id]
            add_node(t["transaction_id"], f"Txn ${t['amount']}", "Transaction", t["risk_score"])
            add_node(t["customer_id"], f"Customer {t['customer_id']}", "Customer", 0.75)
            add_node(t["device_id"], f"Device {t['device_id']}", "Device", 0.81)
            add_node(t["ip_str"], f"IP {t['ip_str']}", "IPAddress", 0.65)
            add_node(t["merchant_name"], t["merchant_name"], "Merchant", 0.20)

            edges.append({"source": t["customer_id"], "target": t["transaction_id"], "type": "PERFORMED_TRANSACTION"})
            edges.append({"source": t["transaction_id"], "target": t["device_id"], "type": "USED_DEVICE"})
            edges.append({"source": t["transaction_id"], "target": t["ip_str"], "type": "ASSOCIATED_IP"})
            edges.append({"source": t["transaction_id"], "target": t["merchant_name"], "type": "TARGETS_MERCHANT"})

            # If depth > 1, expand connected device ring
            if depth > 1 and t["device_id"] in MOCK_DEVICE_RINGS:
                ring = MOCK_DEVICE_RINGS[t["device_id"]]
                for acc_id in ring["associated_account_ids"]:
                    add_node(acc_id, f"Account {acc_id}", "Account", ring["risk_score"])
                    edges.append({"source": acc_id, "target": t["device_id"], "type": "USED_DEVICE"})

        # Check if entity is customer
        elif entity_id in MOCK_CUSTOMERS:
            c = MOCK_CUSTOMERS[entity_id]
            add_node(c["customer_id"], c["name"], "Customer", c["risk_score"])
            for acc in c["accounts"]:
                add_node(acc, f"Account {acc}", "Account", c["risk_score"])
                edges.append({"source": c["customer_id"], "target": acc, "type": "HAS_ACCOUNT"})

        # Check if entity is device
        elif entity_id in MOCK_DEVICE_RINGS:
            d = MOCK_DEVICE_RINGS[entity_id]
            add_node(d["device_id"], f"Device {d['device_id']}", "Device", d["risk_score"])
            for acc in d["associated_account_ids"]:
                add_node(acc, f"Account {acc}", "Account", d["risk_score"])
                edges.append({"source": acc, "target": d["device_id"], "type": "USED_DEVICE"})
        # Check if entity is case / FraudCase
        elif entity_id in MOCK_WRITTEN_CASES or entity_id.startswith("CASE-"):
            case_data = MOCK_WRITTEN_CASES.get(entity_id, {})
            if not case_data:
                for sc in MOCK_SIMILAR_CASES:
                    if sc.get("case_id") == entity_id:
                        case_data = sc
                        break
            risk = float(case_data.get("risk_score", 0.85))
            add_node(entity_id, f"FraudCase {entity_id}", "FraudCase", risk)
            txn_id = case_data.get("transaction_id")
            if txn_id:
                add_node(txn_id, f"Txn {txn_id}", "Transaction", risk)
                edges.append({"source": entity_id, "target": txn_id, "type": "INVOLVED_IN_CASE"})
            cust_id = case_data.get("customer_id")
            if cust_id:
                add_node(cust_id, f"Customer {cust_id}", "Customer", 0.75)
                edges.append({"source": entity_id, "target": cust_id, "type": "LINKED_CUSTOMER"})
            for ev in case_data.get("evidence", []):
                ev_id = ev.get("evidence_id") or ev.get("id")
                if ev_id:
                    add_node(ev_id, f"Evidence {ev_id}", "Evidence", float(ev.get("confidence", 0.9)))
                    edges.append({"source": entity_id, "target": ev_id, "type": "HAS_EVIDENCE"})
            for pat in case_data.get("fraud_patterns", []):
                pat_id = pat.get("pattern_id") or pat.get("id") if isinstance(pat, dict) else pat
                if isinstance(pat_id, str):
                    add_node(pat_id, f"Pattern {pat_id}", "FraudPattern", 0.85)
                    edges.append({"source": entity_id, "target": pat_id, "type": "DETECTED_PATTERN"})
        else:
            add_node(entity_id, f"Entity {entity_id}", "Unknown", 0.50)

        return {"nodes": nodes, "edges": edges}

    def find_shared_devices(self, entity_id: str) -> Dict[str, Any]:
        """Tool 5: find_shared_devices(customer/account/device id) -> connected devices/accounts"""
        target_device = None

        # Direct device ID match
        if entity_id in MOCK_DEVICE_RINGS:
            target_device = MOCK_DEVICE_RINGS[entity_id]
        # Transaction ID match
        elif entity_id in MOCK_TRANSACTIONS:
            dev_id = MOCK_TRANSACTIONS[entity_id]["device_id"]
            target_device = MOCK_DEVICE_RINGS.get(dev_id)
        # Customer ID match
        elif entity_id in MOCK_CUSTOMERS:
            # Check transactions belonging to this customer
            for t in MOCK_TRANSACTIONS.values():
                if t["customer_id"] == entity_id:
                    dev_id = t["device_id"]
                    target_device = MOCK_DEVICE_RINGS.get(dev_id)
                    if target_device:
                        break

        if not target_device:
            # Fallback default empty representation
            return {"devices": []}

        return {
            "devices": [
                {
                    "device_id": target_device["device_id"],
                    "linked_accounts": target_device["linked_accounts"],
                    "risk_score": target_device["risk_score"],
                    "associated_account_ids": target_device.get("associated_account_ids", []),
                }
            ]
        }

    def detect_fraud_patterns(self, entity_id: str) -> Dict[str, Any]:
        """Tool 6: detect_fraud_patterns(case/entity context) -> patterns + evidence references"""
        # Lookup patterns mapped to transaction or default
        patterns = MOCK_FRAUD_PATTERNS.get(entity_id, [])

        if not patterns and entity_id in MOCK_CUSTOMERS:
            # Retrieve patterns from customer's transactions
            for txn_id, txn in MOCK_TRANSACTIONS.items():
                if txn["customer_id"] == entity_id and txn_id in MOCK_FRAUD_PATTERNS:
                    patterns.extend(MOCK_FRAUD_PATTERNS[txn_id])

        return {"patterns": patterns}

    def find_similar_cases(self, case_context: str) -> Dict[str, Any]:
        """Tool 7: find_similar_cases(case context) -> similar cases + outcomes"""
        # Return top matches from historical closed investigations
        # If context specifies high-value wire or mule, prioritize CASE-0773
        results = list(MOCK_SIMILAR_CASES)

        if "301855" in case_context or "wire" in case_context.lower() or "tor" in case_context.lower():
            results.sort(key=lambda c: 0.99 if "FP-03" in c.get("matched_patterns", []) else 0.5, reverse=True)
        elif "104829" in case_context or "device" in case_context.lower():
            results.sort(key=lambda c: 0.99 if "FP-01" in c.get("matched_patterns", []) else 0.5, reverse=True)

        return {"similar_cases": results[:3]}

    def get_policy_context(
        self,
        action: str,
        pattern_id: Optional[str] = None,
        amount: Optional[float] = None
    ) -> Dict[str, Any]:
        """Tool 8: get_policy_context(case/pattern/action) -> relevant policy context"""
        clean_action = (action or "").strip().upper()

        approval_required = False
        sar_required = False
        basis = "Standard automated risk mitigation tier."
        confidence_threshold = 0.75
        allowed_actions = ["MONITOR", "REQUEST_VERIFICATION", "BLOCK_TRANSACTION"]

        if clean_action in ["FREEZE_ACCOUNT", "BLOCK_TRANSACTION"]:
            if amount and amount >= 5000.0:
                approval_required = True
                sar_required = True
                basis = "Bank Policy POL-804: Actions affecting balances over $5,000 require L2 Human-in-the-Loop approval and FinCEN SAR filing evaluation."
                confidence_threshold = 0.85
            else:
                basis = "Bank Policy POL-402: Automated block permitted for confirmed syndicate or velocity violations exceeding risk score 0.80."
                confidence_threshold = 0.80
        elif clean_action in ["REQUEST_STEP_UP_AUTH", "REQUEST_VERIFICATION"]:
            approval_required = False
            basis = "Bank Policy POL-201: Pre-decision step-up authentication permitted when uncertainty is elevated (confidence < 0.70)."
            confidence_threshold = 0.50
        elif clean_action == "ALLOW_TRANSACTION":
            basis = "Bank Policy POL-101: Low risk score (<0.30) with no suspicious device or syndicate linkages."
            confidence_threshold = 0.70

        return {
            "policy_id": "POL-FRAUD-2026-V1",
            "policy_basis": basis,
            "approval_required": approval_required,
            "sar_required": sar_required,
            "confidence_threshold": confidence_threshold,
            "allowed_actions": allowed_actions,
            "escalation_notes": "Tier-2 compliance review mandatory if customer disputes or SAR threshold triggered."
        }

    def write_case_to_graph(self, case_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Tool 9: write_case_to_graph(case payload) -> write status + graph ids"""
        case_id = case_payload.get("case_id")
        if not case_id:
            raise GraphError(
                code="CASE_NOT_FOUND",
                message="Case payload missing required 'case_id' field.",
                details={"received_payload": case_payload}
            )

        # Store in-memory with normalized evidence_type and action_type
        stored_payload = dict(case_payload)
        normalized_evidence = []
        for ev in case_payload.get("evidence", []):
            ev_copy = dict(ev)
            if "evidence_type" not in ev_copy and "type" in ev_copy:
                ev_copy["evidence_type"] = ev_copy["type"]
            elif "type" not in ev_copy and "evidence_type" in ev_copy:
                ev_copy["type"] = ev_copy["evidence_type"]
            normalized_evidence.append(ev_copy)
        stored_payload["evidence"] = normalized_evidence

        normalized_actions = []
        for act in case_payload.get("action_records", case_payload.get("actions", [])):
            act_copy = dict(act)
            if "action_type" not in act_copy and "type" in act_copy:
                act_copy["action_type"] = act_copy["type"]
            elif "type" not in act_copy and "action_type" in act_copy:
                act_copy["type"] = act_copy["action_type"]
            normalized_actions.append(act_copy)
        if normalized_actions:
            stored_payload["action_records"] = normalized_actions

        stored_payload["updated_at"] = int(time.time())
        MOCK_WRITTEN_CASES[case_id] = stored_payload

        generated_graph_ids = [
            f"vertex_fraudcase_{case_id}",
            f"edge_involved_{case_payload.get('transaction_id', 'unknown')}",
            f"edge_customer_{case_payload.get('customer_id', 'unknown')}"
        ]

        for ev in normalized_evidence:
            ev_id = ev.get("evidence_id") or ev.get("id")
            if ev_id:
                generated_graph_ids.append(f"vertex_evidence_{ev_id}")
                generated_graph_ids.append(f"edge_has_evidence_{ev_id}")

        for act in normalized_actions:
            act_id = act.get("action_id") or act.get("id")
            if act_id:
                generated_graph_ids.append(f"vertex_actionrecord_{act_id}")
                generated_graph_ids.append(f"edge_executed_action_{act_id}")

        return {
            "status": "SUCCESS",
            "case_id": case_id,
            "graph_ids": generated_graph_ids,
            "nodes_written": 1 + len(normalized_evidence) + len(case_payload.get("fraud_patterns", [])) + len(normalized_actions),
            "edges_written": 2 + len(normalized_evidence) + len(normalized_actions),
            "message": f"Case '{case_id}' successfully committed to TigerGraph case memory."
        }


# Global singleton mock instance
mock_provider = TigerGraphMockProvider()
