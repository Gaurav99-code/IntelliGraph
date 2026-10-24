"""Embedding compatibility helpers.

This keeps Phase 1 self-contained and avoids downloading a model during first
startup. The interface is intentionally isolated so a hosted or local semantic
embedding provider can replace it in a later phase without changing Chroma
integration or the API contract.
"""

from __future__ import annotations

import hashlib
import math
import re


EMBEDDING_DIMENSION = 256


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9][a-z0-9_-]{2,}", text.lower())


def hash_embed_text(text: str) -> list[float]:
    """Create a normalized feature-hash embedding for a text string."""

    vector = [0.0] * EMBEDDING_DIMENSION
    tokens = _tokens(text)
    if not tokens:
        return vector

    features = tokens + [f"{a}_{b}" for a, b in zip(tokens, tokens[1:])]
    for feature in features:
        digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
        bucket = int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSION
        sign = 1.0 if digest[4] % 2 else -1.0
        vector[bucket] += sign

    norm = math.sqrt(sum(value * value for value in vector))
    return [value / norm for value in vector] if norm else vector


def embed_text(text: str) -> list[float]:
    """Backward-compatible hash embedding helper.

    New code should use ``backend.embedding_service.get_embedding_service``.
    """

    return hash_embed_text(text)


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """Compute cosine similarity for fallback/entity-resolution vectors."""

    if len(left) != len(right) or not left:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0
