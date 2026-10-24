"""ChromaDB-backed chunk indexing and semantic retrieval."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .embedding_service import EmbeddingService, get_embedding_service


class ChromaVectorStore:
    """Persistent local Chroma index with an optional graceful fallback state."""

    def __init__(self, path: Path, collection_name: str = "intelligraph_chunks"):
        self.path = path
        self.collection_name = collection_name
        self.embedding_service: EmbeddingService = get_embedding_service()
        self.client: Any | None = None
        self.collection: Any | None = None
        self.error: str | None = None
        self._connect()

    @property
    def available(self) -> bool:
        return self.collection is not None

    def _connect(self) -> None:
        try:
            import chromadb

            self.path.mkdir(parents=True, exist_ok=True)
            client: Any = chromadb.PersistentClient(path=str(self.path))
            self.client = client
            self.collection = self._get_or_create_collection(client, self.embedding_service.requested_model)
        except Exception as exc:  # pragma: no cover - environment dependent
            self.error = str(exc)
            self.client = None
            self.collection = None

    def _get_or_create_collection(self, client: Any, model_name: str) -> Any:
        """Create a cosine collection and rebuild it when its model changes."""

        try:
            collection = client.get_collection(name=self.collection_name)
            metadata = collection.metadata or {}
            stored_model = metadata.get("embedding_model")
            if stored_model and stored_model != model_name:
                client.delete_collection(name=self.collection_name)
                collection = None
        except Exception:
            collection = None
        if collection is not None:
            return collection
        try:
            return client.get_or_create_collection(
                name=self.collection_name,
                configuration={"hnsw": {"space": "cosine"}},
                metadata={"embedding_model": model_name},
            )
        except (TypeError, ValueError):
            return client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine", "embedding_model": model_name},
            )

    def _ensure_active_collection(self) -> Any | None:
        """Load embeddings and align collection metadata with the active model."""

        collection = self.collection
        if self.client is None:
            return collection
        # Loading happens here, not during API import, so startup remains fast.
        self.embedding_service.encode(["__intelligraph_model_probe__"])
        active_model = self.embedding_service.active_model
        metadata = collection.metadata if collection is not None else {}
        if collection is None or metadata.get("embedding_model") != active_model:
            if collection is not None:
                self.client.delete_collection(name=self.collection_name)
            self.collection = self._get_or_create_collection(self.client, active_model)
        return self.collection

    def upsert_document(self, document: dict[str, Any]) -> None:
        collection = self._ensure_active_collection()
        if collection is None:
            return
        chunks = document.get("chunks", [])
        if not chunks:
            return
        collection.upsert(
            ids=[chunk["id"] for chunk in chunks],
            documents=[chunk["text"] for chunk in chunks],
            metadatas=[
                {
                    "document_id": document["id"],
                    "document_name": document["name"],
                    "chunk_id": chunk["id"],
                    "chunk_index": chunk["index"],
                }
                for chunk in chunks
            ],
            embeddings=self.embedding_service.encode([chunk["text"] for chunk in chunks]),
        )

    def delete_document(self, document_id: str) -> None:
        collection = self.collection
        if collection is not None:
            collection.delete(where={"document_id": document_id})

    def query(self, question: str, top_k: int = 5) -> list[dict[str, Any]]:
        collection = self._ensure_active_collection()
        if collection is None or collection.count() == 0:
            return []
        result = collection.query(
            query_embeddings=self.embedding_service.encode([question]),
            n_results=max(1, min(top_k, 20)),
            include=["documents", "metadatas", "distances"],
        )
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        matches: list[dict[str, Any]] = []
        for text, metadata, distance in zip(documents, metadatas, distances):
            matches.append(
                {
                    "document_id": metadata["document_id"],
                    "document_name": metadata["document_name"],
                    "chunk_id": metadata.get("chunk_id"),
                    "chunk_index": metadata["chunk_index"],
                    "text": text,
                    "score": round(max(0.0, 1.0 - float(distance)), 4),
                    "matched_terms": [],
                }
            )
        return matches

    def status(self) -> dict[str, Any]:
        collection = self.collection
        embedding_status = self.embedding_service.status()
        return {
            "provider": "chroma",
            "enabled": True,
            "available": self.available,
            "path": str(self.path),
            "collection": self.collection_name,
            "records": collection.count() if collection is not None else 0,
            "error": self.error,
            **embedding_status,
        }
