"""Document parsing and lightweight knowledge-graph extraction.

The project can run without a hosted LLM or external graph/vector database.  This
module deliberately uses deterministic heuristics as a local baseline so the
frontend has a real ingestion and retrieval flow from day one.  The extraction
functions are isolated so they can later be replaced with an LLM/Neo4j/Chroma
implementation without changing the HTTP contract.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any


STOPWORDS = {
    "about", "after", "again", "also", "among", "because", "before", "being",
    "between", "could", "does", "during", "from", "have", "into", "more",
    "most", "other", "over", "same", "some", "such", "than", "that", "their",
    "there", "these", "they", "this", "those", "through", "under", "using",
    "very", "what", "when", "where", "which", "while", "with", "would", "your",
    "and", "are", "but", "for", "has", "how", "its", "not", "our", "the", "was",
    "were", "will", "you", "can", "all", "any", "out", "who", "why", "too",
    "question", "questions",
}

RELATION_WORDS = (
    "is", "are", "uses", "supports", "improves", "enables", "includes",
    "relates to", "connects to", "depends on", "contains", "builds", "maps",
    "answers", "extracts", "groups", "retrieves", "requires",
)


def decode_document(filename: str, content: bytes) -> str:
    """Decode a text or PDF upload into plain text.

    PDF support is optional at runtime.  ``pypdf`` is listed in requirements,
    but the clear error here also makes a missing optional install actionable.
    """

    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise ValueError("PDF support requires the 'pypdf' package") from exc

        from io import BytesIO

        reader = PdfReader(BytesIO(content))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    else:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("latin-1")

    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def split_into_chunks(text: str, max_chars: int = 1400, overlap: int = 180) -> list[str]:
    """Split text into readable retrieval chunks while preserving context."""

    if not text:
        return []

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if current and len(candidate) > max_chars:
            chunks.append(current)
            prefix = current[-overlap:] if overlap else ""
            current = f"{prefix} {paragraph}".strip()
        else:
            current = candidate
    if current:
        chunks.append(current)

    # A single long paragraph still needs splitting.
    final: list[str] = []
    for chunk in chunks:
        if len(chunk) <= max_chars:
            final.append(chunk)
            continue
        start = 0
        while start < len(chunk):
            end = min(start + max_chars, len(chunk))
            final.append(chunk[start:end].strip())
            if end == len(chunk):
                break
            start = max(0, end - overlap)
    return [chunk for chunk in final if chunk]


def _tokens(text: str) -> list[str]:
    return [
        token.lower()
        for token in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text)
        if token.lower() not in STOPWORDS
    ]


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:80]


def extract_topics(text: str, limit: int = 8) -> list[dict[str, Any]]:
    """Return frequency-based topics suitable for a local baseline."""

    counts = Counter(_tokens(text))
    return [
        {"id": f"topic:{_slug(term)}", "label": term, "score": count}
        for term, count in counts.most_common(limit)
    ]


def extract_entities(text: str, topics: list[dict[str, Any]]) -> list[str]:
    """Extract named phrases and useful domain terms without an NLP dependency."""

    candidates: list[str] = []
    for match in re.findall(r"\b(?:[A-Z][A-Za-z0-9_-]*)(?:\s+[A-Z][A-Za-z0-9_-]*){0,3}\b", text):
        if len(match) > 2 and match.lower() not in STOPWORDS:
            candidates.append(match.strip())

    # Topic terms are also graph entities; this makes lower-case technical
    # concepts visible in the graph (for example, "vector search").
    candidates.extend(topic["label"] for topic in topics[:5])
    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = candidate.casefold()
        if key not in seen and len(candidate) >= 3:
            deduped.append(candidate)
            seen.add(key)
    return deduped[:40]


def extract_relationships(text: str, entities: list[str]) -> list[dict[str, str]]:
    """Extract explicit sentence relationships and co-occurrence links."""

    relationships: list[dict[str, str]] = []
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]
    entity_lookup = {entity.casefold(): entity for entity in entities}

    for sentence in sentences:
        found = [entity_lookup[key] for key in entity_lookup if re.search(rf"\b{re.escape(key)}\b", sentence, re.I)]
        if len(found) < 2:
            continue

        matched_relation = next((relation for relation in RELATION_WORDS if relation in sentence.lower()), "related to")
        if matched_relation != "related to" and len(found) >= 2:
            relationships.append({"source": found[0], "relation": matched_relation, "target": found[1]})
        for left, right in zip(found, found[1:]):
            relationships.append({"source": left, "relation": "related to", "target": right})

    unique: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for relationship in relationships:
        key = (
            relationship["source"].casefold(),
            relationship["relation"].casefold(),
            relationship["target"].casefold(),
        )
        if key not in seen and key[0] != key[2]:
            unique.append(relationship)
            seen.add(key)
    return unique[:100]


def process_document(document_id: str, filename: str, content: bytes) -> dict[str, Any]:
    """Build the normalized document payload persisted by the store."""

    text = decode_document(filename, content)
    if len(text) < 10:
        raise ValueError("The document does not contain enough readable text")

    chunks = split_into_chunks(text)
    topics = extract_topics(text)
    entities = extract_entities(text, topics)
    relationships = extract_relationships(text, entities)
    return {
        "id": document_id,
        "name": filename,
        "text": text,
        "chunks": [
            {"id": f"{document_id}:chunk:{index}", "index": index, "text": chunk}
            for index, chunk in enumerate(chunks)
        ],
        "topics": topics,
        "entities": entities,
        "relationships": relationships,
    }
