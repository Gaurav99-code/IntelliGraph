"""Local persistence and hybrid lexical/graph retrieval for IntelliGraph."""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any


QUERY_STOPWORDS = {
    "about", "after", "again", "also", "are", "because", "before", "being",
    "between", "could", "does", "during", "from", "have", "how", "into", "is",
    "its", "main", "more", "most", "other", "over", "same", "some", "such",
    "than", "that", "the", "their", "there", "these", "they", "this", "those",
    "through", "under", "was", "were", "what", "when", "where", "which", "while",
    "who", "why", "will", "with", "would", "you", "your", "and", "but", "for",
    "not", "our", "can", "all", "any", "out", "too",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _terms(value: str) -> set[str]:
    return {
        token.lower()
        for token in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", value)
        if token.lower() not in QUERY_STOPWORDS
    }


class KnowledgeStore:
    """A small JSON-backed store that works locally without external services.

    The file format is intentionally straightforward.  It keeps the prototype
    usable on a laptop and leaves a clean seam for replacing persistence with
    Neo4j + ChromaDB later.
    """

    def __init__(self, path: Path, vector_store: Any | None = None, graph_store: Any | None = None):
        self.path = path
        self._lock = Lock()
        self.documents: dict[str, dict[str, Any]] = {}
        self.vector_store = vector_store
        self.graph_store = graph_store
        self.last_sync_errors: list[str] = []
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            self.documents = payload.get("documents", {})
        except (OSError, json.JSONDecodeError):
            # A broken local cache should not prevent the API from starting.
            self.documents = {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": 1, "updated_at": _now(), "documents": self.documents}
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def add_document(self, document: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            document = {**document, "created_at": _now()}
            self.documents[document["id"]] = document
            self._save()
            self._sync_document(document)
            return document

    def delete_document(self, document_id: str) -> bool:
        with self._lock:
            existed = document_id in self.documents
            if existed:
                self._delete_from_backends(document_id)
                del self.documents[document_id]
                self._save()
            return existed

    def _sync_document(self, document: dict[str, Any]) -> None:
        self.last_sync_errors = []
        for backend, operation in (
            (self.vector_store, "upsert_document"),
            (self.graph_store, "sync_document"),
        ):
            if backend is None:
                continue
            try:
                getattr(backend, operation)(document)
            except Exception as exc:  # pragma: no cover - service dependent
                self.last_sync_errors.append(f"{backend.__class__.__name__}: {exc}")

    def _delete_from_backends(self, document_id: str) -> None:
        self.last_sync_errors = []
        for backend in (self.vector_store, self.graph_store):
            if backend is None:
                continue
            try:
                backend.delete_document(document_id)
            except Exception as exc:  # pragma: no cover - service dependent
                self.last_sync_errors.append(f"{backend.__class__.__name__}: {exc}")

    def reindex_backends(self) -> dict[str, Any]:
        """Mirror JSON documents into configured vector and graph backends."""

        errors: list[str] = []
        for document in self.documents.values():
            self._sync_document(document)
            errors.extend(self.last_sync_errors)
        return {"documents": len(self.documents), "errors": errors}

    def backend_status(self) -> dict[str, Any]:
        return {
            "vector": self.vector_store.status() if self.vector_store else {"available": False, "provider": "none"},
            "graph": self.graph_store.status() if self.graph_store else {"available": False, "provider": "none"},
            "sync_errors": self.last_sync_errors,
        }

    def extraction_method_counts(self) -> dict[str, int]:
        """Count processed chunks by extraction method across stored documents."""

        counts: Counter[str] = Counter()
        for document in self.documents.values():
            counts.update(document.get("extraction_method_counts", {}))
        return dict(counts)

    def list_documents(self) -> list[dict[str, Any]]:
        return [self._document_summary(document) for document in self.documents.values()]

    def get_document(self, document_id: str) -> dict[str, Any] | None:
        return self.documents.get(document_id)

    @staticmethod
    def _document_summary(document: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": document["id"],
            "name": document["name"],
            "created_at": document.get("created_at"),
            "characters": len(document.get("text", "")),
            "chunks": len(document.get("chunks", [])),
            "topics": [topic["label"] for topic in document.get("topics", [])],
            "entities": len(document.get("entities", [])),
            "extraction_method": document.get("extraction_method", "heuristic"),
            "extraction_method_counts": document.get("extraction_method_counts", {}),
        }

    def graph(self, document_id: str | None = None) -> dict[str, list[dict[str, Any]]]:
        if self.graph_store is not None and getattr(self.graph_store, "available", False):
            try:
                graph = self.graph_store.graph(document_id=document_id)
                if graph["nodes"] or graph["edges"]:
                    return graph
            except Exception as exc:  # pragma: no cover - service dependent
                self.last_sync_errors.append(f"{self.graph_store.__class__.__name__}: {exc}")
        documents = [self.documents[document_id]] if document_id and document_id in self.documents else list(self.documents.values())
        nodes: dict[str, dict[str, Any]] = {}
        edges: dict[str, dict[str, Any]] = {}

        def add_node(node_id: str, label: str, node_type: str, **extra: Any) -> None:
            node = nodes.setdefault(node_id, {"id": node_id, "label": label, "type": node_type, "weight": 0})
            node["weight"] += 1
            node.update(extra)

        def add_edge(source: str, target: str, relation: str) -> None:
            edge_id = f"{source}|{relation}|{target}"
            edge = edges.setdefault(
                edge_id,
                {"id": edge_id, "source": source, "target": target, "label": relation, "weight": 0},
            )
            edge["weight"] += 1

        for document in documents:
            document_node = f"document:{document['id']}"
            add_node(document_node, document["name"], "document", extraction_method=document.get("extraction_method", "heuristic"))
            for topic in document.get("topics", []):
                add_node(topic["id"], topic["label"], "topic", score=topic.get("score", 1))
                add_edge(document_node, topic["id"], "has topic")
            entity_ids: dict[str, str] = {}
            for entity in document.get("entities", []):
                entity_name = entity["name"] if isinstance(entity, dict) else entity
                entity_id = f"entity:{re.sub(r'[^a-z0-9]+', '-', entity_name.lower()).strip('-')}"
                entity_ids[entity_name.casefold()] = entity_id
                add_node(
                    entity_id,
                    entity_name,
                    "entity",
                    entity_type=entity.get("type", "Other") if isinstance(entity, dict) else "Other",
                    description=entity.get("description", "") if isinstance(entity, dict) else "",
                    aliases=entity.get("aliases", []) if isinstance(entity, dict) else [],
                    extraction_method=document.get("extraction_method", "heuristic"),
                )
                add_edge(document_node, entity_id, "mentions")
            for relationship in document.get("relationships", []):
                source_name = relationship.get("source", relationship.get("subject", ""))
                target_name = relationship.get("target", relationship.get("object", ""))
                source = entity_ids.get(source_name.casefold())
                target = entity_ids.get(target_name.casefold())
                if source and target:
                    edge_id = f"{source}|{relationship['relation']}|{target}|{relationship.get('chunk_id', '')}"
                    edge = edges.setdefault(
                        edge_id,
                        {
                            "id": edge_id,
                            "source": source,
                            "target": target,
                            "label": relationship["relation"],
                            "weight": 0,
                            "evidence": relationship.get("evidence", ""),
                            "document_id": relationship.get("doc_id", document["id"]),
                            "chunk_id": relationship.get("chunk_id", ""),
                            "extraction_method": document.get("extraction_method", "heuristic"),
                        },
                    )
                    edge["weight"] += 1

        return {"nodes": list(nodes.values()), "edges": list(edges.values())}

    def node_details(self, node_id: str) -> dict[str, Any] | None:
        graph = self.graph()
        node = next((item for item in graph["nodes"] if item["id"] == node_id), None)
        if not node:
            return None
        connected_edges = [edge for edge in graph["edges"] if edge["source"] == node_id or edge["target"] == node_id]
        return {"node": node, "edges": connected_edges}

    def search(self, question: str, top_k: int = 5) -> dict[str, Any]:
        query_terms = _terms(question)
        if not query_terms:
            return {"route": "factual", "matches": [], "topics": [], "paths": []}

        thematic_markers = {"theme", "themes", "topic", "topics", "main", "overall", "across", "summarize", "summary"}
        route = "thematic" if query_terms.intersection(thematic_markers) else "factual"
        matches: list[dict[str, Any]] = []

        if self.vector_store is not None and getattr(self.vector_store, "available", False):
            try:
                matches = self.vector_store.query(question, top_k)
                for match in matches:
                    match["matched_terms"] = sorted(query_terms & _terms(match["text"]))
            except Exception as exc:  # pragma: no cover - service dependent
                self.last_sync_errors.append(f"{self.vector_store.__class__.__name__}: {exc}")

        if not matches:
            for document in self.documents.values():
                for chunk in document.get("chunks", []):
                    chunk_terms = _terms(chunk["text"])
                    overlap = len(query_terms & chunk_terms)
                    if overlap == 0:
                        continue
                    # A mild length normalization favors focused chunks over long ones.
                    score = overlap / math.sqrt(max(len(chunk_terms), 1))
                    matches.append({
                        "document_id": document["id"],
                        "document_name": document["name"],
                        "chunk_id": chunk["id"],
                        "chunk_index": chunk["index"],
                        "text": chunk["text"],
                        "score": round(score, 4),
                        "matched_terms": sorted(query_terms & chunk_terms),
                    })

        matches.sort(key=lambda match: match["score"], reverse=True)
        matches = matches[: max(1, min(top_k, 20))]

        topic_scores: Counter[str] = Counter()
        matched_document_ids = {match["document_id"] for match in matches}
        for document in self.documents.values():
            if document["id"] not in matched_document_ids:
                continue
            for topic in document.get("topics", []):
                if topic["label"].lower() in query_terms or not matches:
                    topic_scores[topic["label"]] += topic.get("score", 1)
                elif _terms(topic["label"]) & query_terms:
                    topic_scores[topic["label"]] += topic.get("score", 1)

        if route == "thematic" and not topic_scores:
            for document in self.documents.values():
                for topic in document.get("topics", []):
                    topic_scores[topic["label"]] += topic.get("score", 1)

        topics = [{"label": label, "score": score} for label, score in topic_scores.most_common(8)]
        paths = self._supporting_paths(matches)
        return {"route": route, "matches": matches, "topics": topics, "paths": paths}

    def _supporting_paths(self, matches: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
        graph = self.graph()
        labels = {node["id"]: node["label"] for node in graph["nodes"]}
        paths: list[list[dict[str, Any]]] = []
        for match in matches[:5]:
            document_node = f"document:{match['document_id']}"
            direct = [edge for edge in graph["edges"] if edge["source"] == document_node]
            matched_terms = set(match.get("matched_terms", []))
            relevant = [
                edge
                for edge in direct
                if _terms(labels.get(edge["target"], "")) & matched_terms
            ]
            if relevant:
                paths.append(relevant[:6])
            elif direct:
                paths.append(direct[:6])
        return paths

    def answer(self, question: str, top_k: int = 5) -> dict[str, Any]:
        result = self.search(question, top_k)
        matches = result["matches"]
        if not self.documents:
            answer = "Upload one or more documents before asking a question."
        elif not matches and result["route"] == "thematic":
            answer = "I could not find a direct match, so there is not enough grounded evidence for a theme summary."
        elif not matches:
            answer = "I could not find a grounded answer in the uploaded documents."
        elif result["route"] == "thematic":
            topic_text = ", ".join(topic["label"] for topic in result["topics"][:6])
            answer = f"The strongest themes across the matching documents are: {topic_text or 'the matched passages'}."
        else:
            best = matches[0]
            sentences = [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", best["text"]) if sentence.strip()]
            sentence = max(
                sentences,
                key=lambda candidate: len(_terms(candidate) & set(best["matched_terms"])),
                default=best["text"],
            )
            answer = sentence or best["text"]

        return {
            "question": question,
            "answer": answer,
            "route": result["route"],
            "sources": [
                {
                    "document_id": match["document_id"],
                    "document_name": match["document_name"],
                    "chunk_id": match["chunk_id"],
                    "chunk_index": match["chunk_index"],
                    "score": match["score"],
                    "text": match["text"],
                }
                for match in matches
            ],
            "topics": result["topics"],
            "graph_paths": result["paths"],
        }
