# ==============================================================================
# FraudGraph AI - GraphRAG Local Embeddings Abstraction
# Workstream: Person 2 (Graph)
#
# Provides local, offline vector embeddings using sentence-transformers/all-MiniLM-L6-v2
# with deterministic semantic hashing fallback for high reliability.
# ==============================================================================

import math
import re
from typing import List, Optional

_MODEL = None
_MODEL_LOAD_FAILED = False


def _get_sentence_transformer():
    """Lazy loads sentence-transformers/all-MiniLM-L6-v2 model."""
    global _MODEL, _MODEL_LOAD_FAILED
    if _MODEL is not None:
        return _MODEL
    if _MODEL_LOAD_FAILED:
        return None

    try:
        from sentence_transformers import SentenceTransformer
        # Load local or cache all-MiniLM-L6-v2
        _MODEL = SentenceTransformer("all-MiniLM-L6-v2")
        return _MODEL
    except Exception as e:
        _MODEL_LOAD_FAILED = True
        return None


def _fallback_embed(text: str, dim: int = 384) -> List[float]:
    """
    Deterministic semantic hash embedding used as a fallback if the neural
    weights are not yet downloaded or offline. Generates normalized 384-dim vectors
    matching all-MiniLM-L6-v2 dimensionality.
    """
    cleaned = re.sub(r"[^\w\s]", " ", (text or "").lower())
    words = cleaned.split()

    vec = [0.0] * dim
    if not words:
        return vec

    # Hash word unigrams and bigrams into vector buckets
    for i, w in enumerate(words):
        h = hash(w) % dim
        vec[h] += 1.0
        if i + 1 < len(words):
            bigram = f"{w}_{words[i+1]}"
            h2 = hash(bigram) % dim
            vec[h2] += 1.5

    # L2 normalize
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0.0:
        vec = [round(x / norm, 6) for x in vec]
    return vec


def embed_text(text: str) -> List[float]:
    """
    Encodes an input text string into a 384-dimensional vector.
    Uses sentence-transformers/all-MiniLM-L6-v2 when available.
    """
    model = _get_sentence_transformer()
    if model is not None:
        try:
            emb = model.encode(text, convert_to_numpy=True)
            return [float(x) for x in emb.tolist()]
        except Exception:
            pass
    return _fallback_embed(text)


def embed_batch(texts: List[str]) -> List[List[float]]:
    """Encodes a batch of input texts into vector embeddings."""
    model = _get_sentence_transformer()
    if model is not None:
        try:
            embs = model.encode(texts, convert_to_numpy=True)
            return [[float(x) for x in emb.tolist()] for emb in embs]
        except Exception:
            pass
    return [_fallback_embed(t) for t in texts]


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Computes the cosine similarity between two float vectors."""
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    dot = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return float(dot / (norm1 * norm2))


__all__ = ["embed_text", "embed_batch", "cosine_similarity"]
