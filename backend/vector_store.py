"""ChromaDB-backed chunk indexing and semantic retrieval."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .embeddings import embed_text


class ChromaVectorStore:
    """Persistent local Chroma index with an optional graceful fallback state."""

    def __init__(self, path: Path, collection_name: str = "intelligraph_chunks"):
        self.path = path
        self.collection_name = collection_name
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
            try:
                self.collection = client.get_or_create_collection(
                    name=self.collection_name,
                    configuration={"hnsw": {"space": "cosine"}},
                )
            except (TypeError, ValueError):
                # Compatibility with older Chroma releases that use metadata.
                self.collection = client.get_or_create_collection(
                    name=self.collection_name,
                    metadata={"hnsw:space": "cosine"},
                )
        except Exception as exc:  # pragma: no cover - environment dependent
            self.error = str(exc)
            self.client = None
            self.collection = None

    def upsert_document(self, document: dict[str, Any]) -> None:
        collection = self.collection
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
            embeddings=[embed_text(chunk["text"]) for chunk in chunks],
        )

    def delete_document(self, document_id: str) -> None:
        collection = self.collection
        if collection is not None:
            collection.delete(where={"document_id": document_id})

    def query(self, question: str, top_k: int = 5) -> list[dict[str, Any]]:
        collection = self.collection
        if collection is None or collection.count() == 0:
            return []
        result = collection.query(
            query_embeddings=[embed_text(question)],
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
        return {
            "provider": "chroma",
            "enabled": True,
            "available": self.available,
            "path": str(self.path),
            "collection": self.collection_name,
            "records": collection.count() if collection is not None else 0,
            "error": self.error,
        }
