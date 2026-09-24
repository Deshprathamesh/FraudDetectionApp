# ==============================================================================
# FraudGraph AI - Evidence Processor & Deduplication Engine
# Workstream: Person 1 (Brain) - Stage 2 Investigation Engine
# ==============================================================================

import logging
from typing import Dict, Any, List, Optional, Tuple, Set
from backend.models.domain import EvidenceItem

logger = logging.getLogger("fraudgraph.evidence_processor")


class EvidenceProcessor:
    """
    Evidence Processor and Normalization Engine.
    Transforms raw heterogeneous data streams (transaction data, customer profiles,
    multi-hop graph neighborhoods, fraud typologies, and GraphRAG precedents)
    into structured, categorized, and deterministically deduplicated EvidenceItems.

    Epistemic Taxonomy:
    - FACT: Direct ground-truth attributes from core entity/transaction records.
    - OBSERVATION: Topological graph relationships, multi-hop traversals, shared hardware.
    - INFERENCE: Historical similarity precedents, statistical comparisons, model outputs.
    """

    def __init__(self):
        pass

    def process_transaction(self, txn: Dict[str, Any]) -> List[EvidenceItem]:
        """Extracts direct factual evidence from the target transaction profile."""
        if not txn:
            return []

        items: List[EvidenceItem] = []
        txn_id = txn.get("transaction_id", "UNKNOWN")
        cust_id = txn.get("customer_id")
        amount = txn.get("amount")
        currency = txn.get("currency", "USD")
        channel = txn.get("channel", "UNKNOWN")
        card_network = txn.get("card_network", "UNKNOWN")
        merchant = txn.get("merchant_name", "Unknown Merchant")
        device_id = txn.get("device_id")
        ip_str = txn.get("ip_str")
        raw_risk_score = txn.get("risk_score")

        # 1. Core financial fact
        items.append(
            EvidenceItem(
                source="ENRICHMENT",
                evidence_type="FINANCIAL_ATTRIBUTES",
                fact_level="FACT",
                is_direct=True,
                related_transaction=txn_id,
                related_entity=cust_id,
                entity_ids=[x for x in [txn_id, cust_id, txn.get("account_id")] if x],
                claim=f"Transaction {txn_id} of amount {amount} {currency} executed via {channel} on {card_network} at {merchant}.",
                description=f"Direct financial transaction attributes: {amount} {currency}, merchant={merchant}, channel={channel}.",
                confidence=1.0,
                untrusted_data_flag=False,
                provenance_sources=["tigergraph.get_transaction"],
                details={
                    "amount": amount,
                    "currency": currency,
                    "channel": channel,
                    "card_network": card_network,
                    "merchant_name": merchant,
                    "account_id": txn.get("account_id"),
                },
            )
        )

        # 2. Digital channel & hardware footprint
        items.append(
            EvidenceItem(
                source="ENRICHMENT",
                evidence_type="DEVICE_NETWORK_FOOTPRINT",
                fact_level="FACT",
                is_direct=True,
                related_transaction=txn_id,
                related_entity=device_id,
                entity_ids=[x for x in [device_id, ip_str] if x and x != "UNKNOWN_DEVICE"],
                claim=f"Transaction originated from device {device_id} and IP {ip_str}.",
                description=f"Originating hardware fingerprint {device_id} and network IP {ip_str}.",
                confidence=1.0,
                untrusted_data_flag=False,
                provenance_sources=["tigergraph.get_transaction"],
                details={"device_id": device_id, "ip_str": ip_str},
            )
        )

        # 3. Upstream raw detection risk score (observational feature, NOT final risk score)
        if raw_risk_score is not None:
            items.append(
                EvidenceItem(
                    source="ENRICHMENT",
                    evidence_type="UPSTREAM_DETECTION_SCORE",
                    fact_level="OBSERVATION",
                    is_direct=False,
                    related_transaction=txn_id,
                    related_entity=cust_id,
                    entity_ids=[txn_id],
                    claim=f"Upstream ingest system recorded raw detection risk score of {raw_risk_score:.4f}.",
                    description=f"Incoming raw anomaly detection signal: {raw_risk_score:.4f}.",
                    confidence=1.0,
                    untrusted_data_flag=False,
                    provenance_sources=["tigergraph.get_transaction"],
                    details={"raw_risk_score": raw_risk_score},
                )
            )

        return items

    def process_customer(self, cust: Dict[str, Any]) -> List[EvidenceItem]:
        """Extracts direct factual evidence from customer profile."""
        if not cust:
            return []

        cust_id = cust.get("customer_id", "UNKNOWN")
        name = cust.get("name", "Unknown")
        risk_tier = cust.get("risk_tier", "LOW")
        accounts = cust.get("accounts", [])
        linked_cards = cust.get("linked_cards", [])

        return [
            EvidenceItem(
                source="ENRICHMENT",
                evidence_type="CUSTOMER_PROFILE",
                fact_level="FACT",
                is_direct=True,
                related_entity=cust_id,
                entity_ids=[cust_id] + accounts + linked_cards,
                claim=f"Customer {cust_id} ({name}) holds risk tier {risk_tier} with {len(accounts)} accounts and {len(linked_cards)} linked cards.",
                description=f"Customer identity verification: {name}, tier={risk_tier}, linked accounts={len(accounts)}, cards={len(linked_cards)}.",
                confidence=1.0,
                untrusted_data_flag=False,
                provenance_sources=["tigergraph.get_customer"],
                details={
                    "customer_id": cust_id,
                    "name": name,
                    "risk_tier": risk_tier,
                    "accounts_count": len(accounts),
                    "cards_count": len(linked_cards),
                },
            )
        ]

    def process_transaction_history(
        self,
        history: List[Dict[str, Any]],
        primary_txn_id: str,
        customer_id: Optional[str] = None,
    ) -> List[EvidenceItem]:
        """Analyzes historical transactions for velocity and frequency observations."""
        if not history:
            return []

        # Bound history to maximum 50 records
        bounded_history = history[:50]
        total_txns = len(bounded_history)
        total_volume = sum(float(t.get("amount", 0.0)) for t in bounded_history)
        avg_volume = total_volume / total_txns if total_txns > 0 else 0.0

        return [
            EvidenceItem(
                source="GRAPH",
                evidence_type="TRANSACTION_HISTORY_VELOCITY",
                fact_level="OBSERVATION",
                is_direct=False,
                related_transaction=primary_txn_id,
                related_entity=customer_id,
                entity_ids=[t.get("transaction_id") for t in bounded_history if t.get("transaction_id")][:10],
                claim=f"Historical window retrieved {total_txns} prior transactions with cumulative volume ${total_volume:,.2f} USD (avg ${avg_volume:,.2f} USD).",
                description=f"Transaction velocity and baseline history: {total_txns} records evaluated.",
                confidence=0.95,
                untrusted_data_flag=False,
                provenance_sources=["tigergraph.get_transaction_history"],
                details={
                    "history_count": total_txns,
                    "total_volume_usd": round(total_volume, 2),
                    "avg_amount_usd": round(avg_volume, 2),
                },
            )
        ]

    def process_connected_entities(
        self,
        entities: Dict[str, Any],
        primary_txn_id: str,
    ) -> List[EvidenceItem]:
        """Extracts graph topological observations across multi-hop entity neighborhoods."""
        if not entities:
            return []

        depth = entities.get("depth", 2)

        # Support both Person 2 ConnectedEntitiesResponse ({nodes, edges}) and direct field dicts
        if "nodes" in entities:
            nodes = entities.get("nodes", [])
            accounts = [n["id"] for n in nodes if n.get("type") == "Account"]
            cards = [n["id"] for n in nodes if n.get("type") in ("Card", "connected_cards")]
            devices = [n["id"] for n in nodes if n.get("type") == "Device"]
            merchants = [n["id"] for n in nodes if n.get("type") == "Merchant"]
            total_conns = len(nodes)
        else:
            accounts = entities.get("connected_accounts", [])
            cards = entities.get("connected_cards", [])
            devices = entities.get("connected_devices", [])
            merchants = entities.get("connected_merchants", [])
            total_conns = entities.get("total_connections", len(accounts) + len(cards) + len(devices) + len(merchants))

        return [
            EvidenceItem(
                source="GRAPH",
                evidence_type="GRAPH_NEIGHBORHOOD_TOPOLOGY",
                fact_level="OBSERVATION",
                is_direct=False,
                related_transaction=primary_txn_id,
                entity_ids=cards + accounts + devices,
                claim=f"Multi-hop graph traversal at depth {depth} revealed {total_conns} connected entities: {len(accounts)} accounts, {len(cards)} cards, {len(devices)} devices, {len(merchants)} merchants.",
                description=f"Graph neighborhood depth {depth}: {len(cards)} linked cards, {len(devices)} devices, {len(accounts)} accounts.",
                confidence=0.90,
                untrusted_data_flag=False,
                provenance_sources=["tigergraph.get_connected_entities"],
                details={
                    "depth": depth,
                    "connected_cards_count": len(cards),
                    "connected_accounts_count": len(accounts),
                    "connected_devices_count": len(devices),
                    "connected_merchants_count": len(merchants),
                    "total_connections": total_conns,
                },
            )
        ]

    def process_shared_devices(
        self,
        shared_devices: Dict[str, Any],
        device_id: str,
        primary_txn_id: Optional[str] = None,
    ) -> List[EvidenceItem]:
        """Analyzes shared hardware devices for syndicate or account take-over indicators."""
        if not shared_devices:
            return []

        # Support Person 2 SharedDevicesResponse format: {"devices": [...]}
        if "devices" in shared_devices:
            dev_items: List[EvidenceItem] = []
            for dev in shared_devices.get("devices", []):
                d_id = dev.get("device_id", device_id)
                linked_accs = dev.get("associated_account_ids") or []
                linked_count = dev.get("linked_accounts", len(linked_accs))
                risk = float(dev.get("risk_score", 0.8))

                if linked_count > 1 or risk >= 0.7:
                    dev_items.append(
                        EvidenceItem(
                            source="GRAPH",
                            evidence_type="DEVICE_SHARING",
                            fact_level="OBSERVATION",
                            is_direct=False,
                            related_transaction=primary_txn_id,
                            related_entity=d_id,
                            entity_ids=[d_id] + linked_accs,
                            claim=f"Device {d_id} is shared across {linked_count} linked accounts (risk score: {risk:.2f}).",
                            description=f"Hardware fingerprint {d_id} shared across {linked_count} accounts.",
                            confidence=risk,
                            untrusted_data_flag=False,
                            provenance_sources=["tigergraph.find_shared_devices"],
                            details={
                                "device_id": d_id,
                                "linked_accounts": linked_count,
                                "risk_score": risk,
                                "associated_account_ids": linked_accs,
                            },
                        )
                    )
            return dev_items

        dev_id = shared_devices.get("device_id", device_id)
        assoc_accs = shared_devices.get("associated_accounts", [])
        assoc_custs = shared_devices.get("associated_customers", [])
        risk_flag = shared_devices.get("risk_flag", False)

        if not assoc_accs and not assoc_custs and not risk_flag:
            return []

        return [
            EvidenceItem(
                source="GRAPH",
                evidence_type="DEVICE_SHARING",
                fact_level="OBSERVATION",
                is_direct=False,
                related_transaction=primary_txn_id,
                related_entity=dev_id,
                entity_ids=[dev_id] + assoc_accs + assoc_custs,
                claim=f"Device {dev_id} is shared across {len(assoc_custs)} customer(s) and {len(assoc_accs)} account(s) (risk_flag={risk_flag}).",
                description=f"Device sharing observation: device {dev_id} associated with multiple customer entities.",
                confidence=0.92,
                untrusted_data_flag=False,
                provenance_sources=["tigergraph.find_shared_devices"],
                details={
                    "device_id": dev_id,
                    "associated_customers_count": len(assoc_custs),
                    "associated_accounts_count": len(assoc_accs),
                    "risk_flag": risk_flag,
                },
            )
        ]

    def process_fraud_patterns(
        self,
        patterns: List[Dict[str, Any]],
        primary_txn_id: str,
    ) -> List[EvidenceItem]:
        """Translates detected graph topology fraud patterns into structured observations."""
        if not patterns:
            return []

        items: List[EvidenceItem] = []
        for p in patterns:
            pat_id = p.get("pattern_id", "FP-UNKNOWN")
            name = p.get("name", "Unknown Pattern")
            desc = p.get("description", "")
            severity = p.get("severity", "HIGH")
            conf = float(p.get("confidence", 0.85))
            matched_entities = p.get("matched_entities", [])

            items.append(
                EvidenceItem(
                    source="GRAPH",
                    evidence_type="FRAUD_TYPOLOGY_MATCH",
                    fact_level="OBSERVATION",
                    is_direct=False,
                    related_transaction=primary_txn_id,
                    related_entity=pat_id,
                    entity_ids=[primary_txn_id] + matched_entities,
                    claim=f"Graph typology match: '{name}' ({pat_id}) with severity {severity} (confidence: {conf:.2f}).",
                    description=desc or f"Topology pattern {name} detected in graph.",
                    confidence=conf,
                    untrusted_data_flag=False,
                    provenance_sources=["tigergraph.detect_fraud_patterns"],
                    details={
                        "pattern_id": pat_id,
                        "name": name,
                        "severity": severity,
                        "matched_entities": matched_entities,
                    },
                )
            )
        return items

    def process_similar_cases(
        self,
        similar_cases: List[Dict[str, Any]],
        primary_txn_id: str,
    ) -> List[EvidenceItem]:
        """Translates historical similar case precedents into categorized inference evidence."""
        if not similar_cases:
            return []

        items: List[EvidenceItem] = []
        for c in similar_cases[:3]: # Cap at top 3 precedents
            case_id = c.get("case_id", "CASE-UNKNOWN")
            sim_score = float(c.get("similarity_score", 0.0))
            outcome = c.get("outcome", "UNKNOWN")
            hist_risk = float(c.get("risk_score", 0.0))
            findings = c.get("key_findings", "")
            matched_pats = c.get("matched_patterns", [])

            items.append(
                EvidenceItem(
                    source="GRAPHRAG",
                    evidence_type="CASE_PRECEDENT",
                    fact_level="INFERENCE",
                    is_direct=False,
                    related_transaction=primary_txn_id,
                    related_entity=case_id,
                    entity_ids=[case_id],
                    claim=f"Prior case {case_id} exhibited {int(sim_score * 100)}% similarity; historical resolution: {outcome} (historical risk: {hist_risk:.2f}).",
                    description=f"Historical precedent: {case_id}, similarity={sim_score:.2f}, outcome={outcome}. {findings}",
                    confidence=sim_score,
                    untrusted_data_flag=True, # Historical narrative and retrieval flagged untrusted
                    provenance_sources=["graphrag.find_similar_cases"],
                    details={
                        "case_id": case_id,
                        "similarity_score": sim_score,
                        "outcome": outcome,
                        "historical_risk": hist_risk,
                        "matched_patterns": matched_pats,
                    },
                )
            )
        return items

    def process_graphrag_context(
        self,
        graphrag_context: Dict[str, Any],
        primary_txn_id: str,
    ) -> List[EvidenceItem]:
        """Processes composite GraphRAG retrieval including policy constraints."""
        if not graphrag_context:
            return []

        items: List[EvidenceItem] = []

        # Policy context model
        policy = graphrag_context.get("policy", {})
        if policy:
            policy_id = policy.get("policy_id", "POL-DEFAULT")
            policy_basis = policy.get("policy_basis", "")
            approval_req = policy.get("approval_required", False)
            sar_req = policy.get("sar_required", False)
            conf_thresh = float(policy.get("confidence_threshold", 0.80))
            allowed = policy.get("allowed_actions", [])

            items.append(
                EvidenceItem(
                    source="GRAPHRAG",
                    evidence_type="GOVERNING_POLICY",
                    fact_level="FACT",
                    is_direct=True,
                    related_transaction=primary_txn_id,
                    related_entity=policy_id,
                    entity_ids=[policy_id],
                    claim=f"Governing policy clause {policy_id}: Human approval={approval_req}, SAR required={sar_req}, required confidence threshold={conf_thresh:.2f}.",
                    description=f"Policy constraints from {policy_id}: {policy_basis}",
                    confidence=1.0,
                    untrusted_data_flag=False,
                    provenance_sources=["graphrag.get_policy_context"],
                    details={
                        "policy_id": policy_id,
                        "policy_basis": policy_basis,
                        "approval_required": approval_req,
                        "sar_required": sar_req,
                        "confidence_threshold": conf_thresh,
                        "allowed_actions": allowed,
                    },
                )
            )

        # Raw prompt context tagged strictly as UNTRUSTED evidence artifact
        prompt_context = graphrag_context.get("prompt_context", "")
        if prompt_context:
            items.append(
                EvidenceItem(
                    source="GRAPHRAG",
                    evidence_type="SYNTHESIZED_PROMPT_CONTEXT",
                    fact_level="INFERENCE",
                    is_direct=False,
                    related_transaction=primary_txn_id,
                    entity_ids=[primary_txn_id],
                    claim="Synthesized GraphRAG context generated for LLM reasoning.",
                    description=prompt_context[:300] + "..." if len(prompt_context) > 300 else prompt_context,
                    confidence=0.85,
                    untrusted_data_flag=True, # Explicit security requirement
                    provenance_sources=["graphrag.pipeline.retrieve_context"],
                    details={"context_length": len(prompt_context)},
                )
            )

        return items

    def deduplicate_evidence(self, items: List[EvidenceItem]) -> List[EvidenceItem]:
        """
        Deterministically deduplicates a list of EvidenceItems.
        Combines duplicate evidence asserting the same factual/observational claim
        by merging entity IDs and provenance sources without LLM evaluation.
        """
        dedup_map: Dict[Tuple[str, str, str, str], EvidenceItem] = {}

        for item in items:
            # Deterministic unique signature:
            # (source, evidence_type, primary_entity, normalized_claim_or_desc_prefix)
            primary_entity = item.related_entity or item.related_transaction or ""
            fact_prefix = (item.claim or item.description)[:60].strip().lower()
            key = (item.source, item.evidence_type, primary_entity, fact_prefix)

            if key in dedup_map:
                existing = dedup_map[key]
                # Merge entity_ids maintaining order and uniqueness
                combined_entities: List[str] = list(existing.entity_ids)
                for eid in item.entity_ids:
                    if eid not in combined_entities:
                        combined_entities.append(eid)
                existing.entity_ids = combined_entities

                # Merge provenance sources
                combined_prov: List[str] = list(existing.provenance_sources)
                for prov in item.provenance_sources:
                    if prov not in combined_prov:
                        combined_prov.append(prov)
                existing.provenance_sources = combined_prov

                # Keep higher confidence
                existing.confidence = max(existing.confidence, item.confidence)
                # Keep untrusted flag true if any source is untrusted
                existing.untrusted_data_flag = existing.untrusted_data_flag or item.untrusted_data_flag
            else:
                dedup_map[key] = item

        return list(dedup_map.values())

    @staticmethod
    def _sanitize_trigger_text(text: str) -> str:
        """Sanitizes trigger narrative against control characters and length bounds."""
        if not text:
            return ""
        cleaned = "".join(ch for ch in text if ch.isprintable() or ch in (" ", "\t", "\n"))
        cleaned = " ".join(cleaned.split())
        if len(cleaned) > 500:
            cleaned = cleaned[:497] + "..."
        return cleaned

    def process_trigger(
        self,
        trigger: Optional[Dict[str, Any]],
        primary_txn_id: str,
        customer_id: Optional[str] = None,
        card_id: Optional[str] = None,
    ) -> List[EvidenceItem]:
        """
        Transforms inbound case trigger context (customer report, risk score alert, analyst request)
        into structured, typed EvidenceItem(s) with explicit provenance, epistemic OBSERVATION level,
        and untrusted data tagging.
        """
        if not trigger or not isinstance(trigger, dict):
            return []

        trigger_type = str(trigger.get("trigger_type") or "").strip().lower()
        trigger_text = str(trigger.get("trigger_text") or "").strip()

        # If there is neither type nor text, nothing to process
        if not trigger_type and not trigger_text:
            return []

        # Sanitize narrative text against prompt injection / control characters
        clean_text = self._sanitize_trigger_text(trigger_text) if trigger_text else f"{trigger_type} trigger alert"

        # Resolve entity references
        effective_cust_id = trigger.get("customer_id") or customer_id
        effective_card_id = trigger.get("card_id") or card_id
        effective_txn_id = trigger.get("flagged_txn_id") or trigger.get("transaction_id") or primary_txn_id

        entity_ids = [x for x in [effective_txn_id, effective_cust_id, effective_card_id] if x and str(x) != "UNKNOWN"]

        items: List[EvidenceItem] = []

        if trigger_type == "customer_report":
            # Epistemic classification: OBSERVATION (unverified customer report, NOT confirmed fraud)
            # Provenance: CASE_TRIGGER (explicitly distinct from graph/enrichment)
            text_lower = clean_text.lower()
            if any(w in text_lower for w in ("never made", "not make", "unauthorized", "stolen", "denied", "fraud", "did not", "dispute")):
                claim_str = f"Customer reports unauthorized transaction: {clean_text}"
                resp_str = f"unauthorized: {clean_text}"
            elif any(w in text_lower for w in ("authorized", "i made this", "valid", "legitimate", "confirmed")):
                claim_str = f"Customer confirmed transaction: {clean_text}"
                resp_str = f"authorized: {clean_text}"
            else:
                claim_str = f"Customer dispute statement: {clean_text}"
                resp_str = clean_text

            items.append(
                EvidenceItem(
                    source="CASE_TRIGGER",
                    evidence_type="CUSTOMER_VERIFICATION",
                    fact_level="OBSERVATION",
                    is_direct=True,
                    related_transaction=effective_txn_id,
                    related_entity=effective_cust_id or effective_card_id,
                    entity_ids=entity_ids,
                    claim=claim_str,
                    description=f"Customer dispute report received via case trigger: {clean_text}",
                    confidence=0.85,
                    untrusted_data_flag=True,  # External untrusted narrative
                    provenance_sources=["case_trigger", "case_trigger.customer_report"],
                    details={
                        "trigger_type": "customer_report",
                        "response": resp_str,
                        "trigger_text": clean_text,
                        "customer_id": effective_cust_id,
                        "card_id": effective_card_id,
                    },
                )
            )
        elif trigger_type == "risk_score":
            # Epistemic classification: OBSERVATION (incoming detection alert context)
            score_val = trigger.get("risk_score")
            items.append(
                EvidenceItem(
                    source="CASE_TRIGGER",
                    evidence_type="TRIGGER_CONTEXT",
                    fact_level="OBSERVATION",
                    is_direct=True,
                    related_transaction=effective_txn_id,
                    related_entity=effective_cust_id or effective_card_id,
                    entity_ids=entity_ids,
                    claim=f"Trigger context from detection alert: {clean_text}",
                    description=f"Case opened with detection trigger context: {clean_text}",
                    confidence=0.80,
                    untrusted_data_flag=True,
                    provenance_sources=["case_trigger", "case_trigger.risk_score"],
                    details={
                        "trigger_type": "risk_score",
                        "trigger_text": clean_text,
                        "risk_score": score_val,
                        "direction": "NEUTRAL",  # Strictly neutral context; upstream score handled separately
                    },
                )
            )
        elif trigger_type == "analyst_request":
            # Epistemic classification: OBSERVATION (analyst directive, not a fraud verdict)
            items.append(
                EvidenceItem(
                    source="CASE_TRIGGER",
                    evidence_type="ANALYST_DIRECTIVE",
                    fact_level="OBSERVATION",
                    is_direct=True,
                    related_transaction=effective_txn_id,
                    related_entity=effective_cust_id or effective_card_id,
                    entity_ids=entity_ids,
                    claim=f"Analyst investigation request: {clean_text}",
                    description=f"Case opened via analyst request: {clean_text}",
                    confidence=0.85,
                    untrusted_data_flag=True,
                    provenance_sources=["case_trigger", "case_trigger.analyst_request"],
                    details={
                        "trigger_type": "analyst_request",
                        "trigger_text": clean_text,
                        "direction": "NEUTRAL",  # Investigation request is neutral context until evidence found
                    },
                )
            )
        else:
            # Fallback for generic or custom trigger types
            items.append(
                EvidenceItem(
                    source="CASE_TRIGGER",
                    evidence_type="TRIGGER_CONTEXT",
                    fact_level="OBSERVATION",
                    is_direct=True,
                    related_transaction=effective_txn_id,
                    related_entity=effective_cust_id or effective_card_id,
                    entity_ids=entity_ids,
                    claim=f"Inbound case trigger: {clean_text}",
                    description=f"Trigger context ({trigger_type or 'general'}): {clean_text}",
                    confidence=0.80,
                    untrusted_data_flag=True,
                    provenance_sources=["case_trigger"],
                    details={
                        "trigger_type": trigger_type or "general",
                        "trigger_text": clean_text,
                        "direction": "NEUTRAL",
                    },
                )
            )

        return items

    def process_all(
        self,
        transaction_data: Optional[Dict[str, Any]] = None,
        customer_data: Optional[Dict[str, Any]] = None,
        transaction_history: Optional[List[Dict[str, Any]]] = None,
        connected_entities: Optional[Dict[str, Any]] = None,
        shared_devices: Optional[Dict[str, Any]] = None,
        fraud_patterns: Optional[List[Dict[str, Any]]] = None,
        similar_cases: Optional[List[Dict[str, Any]]] = None,
        graphrag_context: Optional[Dict[str, Any]] = None,
        trigger_data: Optional[Dict[str, Any]] = None,
    ) -> List[EvidenceItem]:
        """Collects, normalizes, categorizes, and deduplicates all evidence streams."""
        raw_items: List[EvidenceItem] = []
        txn_id = transaction_data.get("transaction_id", "UNKNOWN") if transaction_data else "UNKNOWN"
        cust_id = customer_data.get("customer_id") if customer_data else (transaction_data.get("customer_id") if transaction_data else None)
        dev_id = transaction_data.get("device_id") if transaction_data else None

        if txn_id == "UNKNOWN" and trigger_data:
            txn_id = trigger_data.get("flagged_txn_id") or trigger_data.get("transaction_id") or "UNKNOWN"
        if not cust_id and trigger_data:
            cust_id = trigger_data.get("customer_id")
        card_id = (trigger_data.get("card_id") if trigger_data else None) or (transaction_data.get("card_id") if transaction_data else None)

        if transaction_data:
            raw_items.extend(self.process_transaction(transaction_data))
        if customer_data:
            raw_items.extend(self.process_customer(customer_data))
        if transaction_history:
            raw_items.extend(self.process_transaction_history(transaction_history, primary_txn_id=txn_id, customer_id=cust_id))
        if connected_entities:
            raw_items.extend(self.process_connected_entities(connected_entities, primary_txn_id=txn_id))
        if shared_devices and dev_id:
            raw_items.extend(self.process_shared_devices(shared_devices, device_id=dev_id, primary_txn_id=txn_id))
        if fraud_patterns:
            raw_items.extend(self.process_fraud_patterns(fraud_patterns, primary_txn_id=txn_id))
        if similar_cases:
            raw_items.extend(self.process_similar_cases(similar_cases, primary_txn_id=txn_id))
        if graphrag_context:
            raw_items.extend(self.process_graphrag_context(graphrag_context, primary_txn_id=txn_id))
        if trigger_data:
            raw_items.extend(self.process_trigger(trigger_data, primary_txn_id=txn_id, customer_id=cust_id, card_id=card_id))

        return self.deduplicate_evidence(raw_items)


# Global singleton instance
evidence_processor = EvidenceProcessor()
