"""Cached sentence-transformer embeddings with a deterministic fallback."""

from __future__ import annotations

import logging
import math
import os
from typing import Any

from .embeddings import hash_embed_text

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Load one embedding model per process and batch encode text."""

    def __init__(self, model_name: str | None = None, fallback_model: str | None = None):
        self.requested_model = model_name or os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
        self.fallback_model = fallback_model or os.getenv("EMBEDDING_FALLBACK_MODEL", "all-MiniLM-L6-v2")
        self._model: Any | None = None
        self.active_model = "hash-fallback"
        self.error: str | None = None

    def _load(self) -> None:
        if self._model is not None or self.active_model == "hash-fallback" and self.error is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer

            try:
                self._model = SentenceTransformer(self.requested_model)
                self.active_model = self.requested_model
            except Exception as first_error:
                logger.warning("Embedding model %s could not load; trying fallback %s: %s", self.requested_model, self.fallback_model, first_error)
                self._model = SentenceTransformer(self.fallback_model)
                self.active_model = self.fallback_model
        except Exception as exc:  # pragma: no cover - dependency/model environment dependent
            self.error = str(exc)
            self.active_model = "hash-fallback"
            logger.warning("Sentence-transformers unavailable; using hash embeddings: %s", exc)

    def encode(self, texts: list[str]) -> list[list[float]]:
        """Encode a batch, preserving input order."""

        if not texts:
            return []
        self._load()
        if self._model is None:
            return [hash_embed_text(text) for text in texts]
        vectors = self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return [list(map(float, vector)) for vector in vectors]

    def encode_one(self, text: str) -> list[float]:
        """Encode one string."""

        return self.encode([text])[0]

    def status(self) -> dict[str, Any]:
        """Return model state without exposing private configuration."""

        return {
            "embedding_model": self.active_model if self._model is not None else self.requested_model,
            "embedding_requested_model": self.requested_model,
            "embedding_fallback_model": self.fallback_model,
            "embedding_backend": "sentence-transformers" if self._model is not None else "lazy/unloaded",
            "embedding_error": self.error,
        }


_SERVICE: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    """Return the process-wide embedding service."""

    global _SERVICE
    if _SERVICE is None:
        _SERVICE = EmbeddingService()
    return _SERVICE


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """Compute cosine similarity for equal-length vectors."""

    if len(left) != len(right) or not left:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0
