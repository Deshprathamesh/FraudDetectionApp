# ==============================================================================
# FraudGraph AI - GraphRAG Similar Case Retrieval Engine
# Workstream: Person 2 (Graph)
#
# Hybrid retrieval matching semantic embeddings over historical closed investigations
# and graph pattern typology signatures. Conforms to Section 7 find_similar_cases.
# ==============================================================================

import os
import json
from typing import Dict, Any, List, Optional
from tigergraph.tools import SimilarCasesResponse, SimilarCaseItem
from graphrag.embeddings.embedder import embed_text, cosine_similarity

CASES_FILE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "documents", "cases", "historical_cases.json"
)

_HISTORICAL_CASES: Optional[List[Dict[str, Any]]] = None


def _load_historical_cases() -> List[Dict[str, Any]]:
    """Loads historical cases and computes vector embeddings for each."""
    global _HISTORICAL_CASES
    if _HISTORICAL_CASES is not None:
        return _HISTORICAL_CASES

    cases: List[Dict[str, Any]] = []
    if os.path.exists(CASES_FILE_PATH):
        try:
            with open(CASES_FILE_PATH, "r", encoding="utf-8") as f:
                cases = json.load(f)
        except Exception:
            cases = []

    # Pre-embed searchable case representation
    for c in cases:
        pattern_names = " ".join([p.get("name", "") for p in c.get("fraud_patterns", [])])
        pattern_ids = " ".join([p.get("pattern_id", "") for p in c.get("fraud_patterns", [])])
        evidence_summaries = " ".join([e.get("summary", "") for e in c.get("evidence", [])])
        searchable_text = (
            f"Case {c.get('case_id')}: Outcome {c.get('outcome')} Risk {c.get('risk_score')}. "
            f"Patterns: {pattern_ids} {pattern_names}. "
            f"Evidence: {evidence_summaries}. "
            f"Rationale: {c.get('investigator_rationale', '')}. "
            f"Findings: {c.get('key_findings', '')}"
        )
        c["_embedding"] = embed_text(searchable_text)
        c["_pattern_ids"] = [p.get("pattern_id", "") for p in c.get("fraud_patterns", [])]

    _HISTORICAL_CASES = cases
    return _HISTORICAL_CASES


def find_similar_cases(case_context: str, top_k: int = 3) -> SimilarCasesResponse:
    """
    Performs hybrid similarity retrieval over historical case precedents.
    Combines embedding semantic distance with graph pattern typology matching.
    """
    cases = _load_historical_cases()
    if not cases:
        return SimilarCasesResponse(similar_cases=[])

    query_str = (case_context or "").lower()
    q_emb = embed_text(case_context or "")

    scored_cases: List[Dict[str, Any]] = []

    for c in cases:
        emb_sim = cosine_similarity(q_emb, c.get("_embedding", []))

        # Typology & keyword matching boost
        typology_boost = 0.0
        for pid in c.get("_pattern_ids", []):
            if pid.lower() in query_str:
                typology_boost += 0.25

        if "device" in query_str and "FP-01" in c.get("_pattern_ids", []):
            typology_boost += 0.20
        if ("velocity" in query_str or "burst" in query_str) and "FP-02" in c.get("_pattern_ids", []):
            typology_boost += 0.20
        if ("mule" in query_str or "wire" in query_str or "crypto" in query_str) and "FP-03" in c.get("_pattern_ids", []):
            typology_boost += 0.25
        if ("proxy" in query_str or "tor" in query_str or "geo" in query_str) and "FP-04" in c.get("_pattern_ids", []):
            typology_boost += 0.20
        if ("synthetic" in query_str or "card test" in query_str) and "FP-05" in c.get("_pattern_ids", []):
            typology_boost += 0.20

        # Hybrid composite score bounded [0.0, 0.99]
        composite_score = round(min(0.99, max(0.15, 0.65 * emb_sim + typology_boost)), 2)

        scored_cases.append({
            "case_id": c.get("case_id", "CASE-UNKNOWN"),
            "similarity_score": composite_score,
            "status": c.get("status", "RESOLVED"),
            "risk_score": float(c.get("risk_score", 0.5)),
            "outcome": c.get("outcome", "UNKNOWN"),
            "matched_patterns": c.get("_pattern_ids", []),
            "key_findings": c.get("key_findings", c.get("investigator_rationale", "")),
        })

    # Sort descending by composite similarity score
    scored_cases.sort(key=lambda x: x["similarity_score"], reverse=True)

    items = [SimilarCaseItem(**sc) for sc in scored_cases[:top_k]]
    return SimilarCasesResponse(similar_cases=items)


__all__ = ["find_similar_cases"]
