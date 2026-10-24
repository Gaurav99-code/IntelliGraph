"""Document parsing, structured extraction, caching, and chunk aggregation."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock
from typing import Any

from .entity_resolution import resolve_chunk_results
from .llm_client import JSONGenerator, LLMClient
from .llm_extractor import ChunkExtraction, ExtractedEntity, ExtractedTriple, extract_chunk

logger = logging.getLogger(__name__)

STOPWORDS = {
    "about", "after", "again", "also", "among", "because", "before", "being",
    "between", "could", "does", "during", "from", "have", "into", "more",
    "most", "other", "over", "same", "some", "such", "than", "that", "their",
    "there", "these", "they", "this", "those", "through", "under", "using",
    "very", "what", "when", "where", "which", "while", "with", "would", "your",
    "and", "are", "but", "for", "has", "how", "its", "not", "our", "the", "was",
    "were", "will", "you", "can", "all", "any", "out", "who", "why", "too",
    "question", "questions", "document", "documents", "section", "overview", "purpose",
}

GENERIC_ENTITY_TERMS = {
    "get", "post", "put", "delete", "patch", "run", "api", "frontend", "backend",
    "json", "pdf", "readme", "scripts", "source", "code", "file", "files", "the api",
    "purpose", "overview", "risk factors", "symptoms", "screening", "connections for the knowledge graph",
    "synthetic educational sample for intelligraph testing",
    "early", "detection", "synthetic", "intelligraph", "purpose", "common", "limited",
    "social", "risk", "factors", "symptoms", "screening", "research", "evidence",
    "overview", "framework", "community", "clinical", "nutrition", "exercise", "prevention",
    "treatment", "treatments", "medication", "medications", "study", "studies", "outcomes",
}

RELATION_WORDS = (
    "increases risk of", "associated with", "connected to", "measured by", "influenced by",
    "used to", "compared with", "depends on", "relates to", "connects to", "increases",
    "reduces", "improves", "supports", "enables", "includes", "contains", "builds", "maps",
    "answers", "extracts", "groups", "retrieves", "requires", "treats", "causes", "affects",
    "is", "are",
)

DEFAULT_CACHE_PATH = Path(__file__).resolve().parents[1] / "data" / "extraction_cache.json"
CACHE_LOCK = Lock()


def decode_document(filename: str, content: bytes) -> str:
    """Decode a text or PDF upload into normalized plain text."""

    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:  # pragma: no cover
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
    """Split text into readable, overlapping retrieval chunks."""

    if not text:
        return []
    paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n", text) if paragraph.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if current and len(candidate) > max_chars:
            chunks.append(current)
            current = f"{current[-overlap:]} {paragraph}".strip()
        else:
            current = candidate
    if current:
        chunks.append(current)

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
    return [token.lower() for token in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text) if token.lower() not in STOPWORDS]


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:80]


def extract_topics(text: str, limit: int = 8) -> list[dict[str, Any]]:
    """Return frequency-based topic labels for the current baseline."""

    counts = Counter(_tokens(text))
    return [{"id": f"topic:{_slug(term)}", "label": term, "score": count} for term, count in counts.most_common(limit)]


def extract_entities(text: str, topics: list[dict[str, Any]]) -> list[str]:
    """Extract candidate entity phrases for the heuristic fallback."""

    candidates: list[str] = []
    body = "\n".join(text.splitlines()[2:]) if len(text.splitlines()) > 2 else text
    for match in re.findall(r"\b(?:[A-Z][A-Za-z0-9_-]*|\d+)(?:[ \t]+(?:[A-Z][A-Za-z0-9_-]*|\d+)){0,3}\b", body):
        if match.casefold() not in STOPWORDS and match.casefold() not in GENERIC_ENTITY_TERMS:
            candidates.append(match.strip())
    for match in re.findall(r"\b(?:type 2 diabetes(?: mellitus)?|insulin resistance|glucose monitoring|weight reduction)\b", body, re.I):
        if match.casefold() not in GENERIC_ENTITY_TERMS:
            candidates.append(match.strip())
    candidates.extend(topic["label"] for topic in topics[:5])
    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = candidate.casefold()
        if key not in seen and len(candidate) >= 3 and key not in GENERIC_ENTITY_TERMS:
            deduped.append(candidate)
            seen.add(key)
    return deduped[:40]


def _heuristic_type(name: str, text: str) -> str:
    lower = name.lower()
    if any(term in lower for term in ("diabetes", "obesity", "insulin resistance", "hypertension")):
        return "Condition"
    if any(term in lower for term in ("metformin", "semaglutide", "insulin")):
        return "Medication"
    if any(term in lower for term in ("hba1c", "biomarker", "glucose monitoring", "blood pressure")):
        return "Biomarker"
    if any(term in lower for term in ("program", "trial", "study")):
        return "Study"
    if any(term in lower for term in ("intervention", "therapy", "treatment", "exercise")):
        return "Treatment"
    if any(term in lower for term in ("university", "organization", "agency", "company", "inc")):
        return "Organization"
    return "Concept"


def extract_relationships(text: str, entities: list[str], doc_id: str = "", chunk_id: str = "") -> list[dict[str, str]]:
    """Extract explicit heuristic relationships with source trace metadata."""

    relationships: list[dict[str, str]] = []
    sentences = [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+|\n+", text) if sentence.strip()]
    entity_lookup = {entity.casefold(): entity for entity in entities}
    for sentence in sentences:
        found = [entity_lookup[key] for key in entity_lookup if re.search(rf"\b{re.escape(key)}\b", sentence, re.I)]
        if len(found) < 2:
            continue
        relation = next(
            (candidate for candidate in sorted(RELATION_WORDS, key=len, reverse=True)
             if re.search(rf"\b{re.escape(candidate)}\b", sentence.lower())),
            "related to",
        )
        for left, right in zip(found, found[1:]):
            if left.casefold() != right.casefold():
                relationships.append({
                    "subject": left,
                    "relation": relation,
                    "object": right,
                    "source": left,
                    "target": right,
                    "evidence": sentence[:500],
                    "doc_id": doc_id,
                    "chunk_id": chunk_id,
                })
    unique: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for relationship in relationships:
        key = (relationship["subject"].casefold(), relationship["relation"], relationship["object"].casefold())
        if key not in seen:
            unique.append(relationship)
            seen.add(key)
    return unique[:100]


def heuristic_extract_chunk(text: str, doc_id: str, chunk_id: str) -> dict[str, Any]:
    """Extract typed, traceable fallback data without an LLM."""

    topics = extract_topics(text)
    names = extract_entities(text, topics)
    entities = [
        {"name": name, "type": _heuristic_type(name, text), "description": "Heuristically extracted concept or phrase."}
        for name in names
    ]
    triples = extract_relationships(text, names, doc_id, chunk_id)
    return {"entities": entities, "triples": triples}


def _load_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_cache(path: Path, cache: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _strip_trace(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "entities": result.get("entities", []),
        "triples": [
            {key: triple.get(key, "") for key in ("subject", "relation", "object", "evidence")}
            for triple in result.get("triples", [])
        ],
    }


def _apply_trace(result: dict[str, Any], doc_id: str, chunk_id: str) -> dict[str, Any]:
    triples = []
    for triple in result.get("triples", []):
        triple = {**triple, "doc_id": doc_id, "chunk_id": chunk_id}
        triple.setdefault("source", triple.get("subject", ""))
        triple.setdefault("target", triple.get("object", ""))
        triples.append(triple)
    return {"entities": result.get("entities", []), "triples": triples}


def process_document(
    document_id: str,
    filename: str,
    content: bytes,
    llm_client: JSONGenerator | None = None,
    cache_path: Path | None = None,
) -> dict[str, Any]:
    """Process one upload with parallel cached LLM extraction and safe fallback."""

    text = decode_document(filename, content)
    if len(text) < 10:
        raise ValueError("The document does not contain enough readable text")
    chunks = split_into_chunks(text)
    client = llm_client or LLMClient.from_env()
    cache_file = cache_path or DEFAULT_CACHE_PATH
    cache = _load_cache(cache_file)
    cache_updates: dict[str, Any] = {}
    llm_allowed = client.enabled and bool(client.api_key)

    def process_chunk(index: int, chunk: str) -> tuple[int, dict[str, Any], str]:
        chunk_id = f"{document_id}:chunk:{index}"
        cache_key = hashlib.sha256(chunk.encode("utf-8")).hexdigest()
        cached = cache.get(cache_key)
        if cached and isinstance(cached, dict) and "result" in cached:
            cached_method = cached.get("extraction_method", "heuristic")
            # A later LLM-enabled run must be allowed to upgrade an older
            # heuristic cache entry; successful LLM entries remain cache hits.
            if not (llm_allowed and cached_method == "heuristic"):
                return index, _apply_trace(cached["result"], document_id, chunk_id), cached_method
        method = "heuristic"
        try:
            if llm_allowed:
                extracted = extract_chunk(chunk, document_id, chunk_id, client)
                result = extracted.model_dump()
                method = "llm"
            else:
                result = heuristic_extract_chunk(chunk, document_id, chunk_id)
        except Exception as exc:  # one bad chunk must not fail the document
            logger.warning("Chunk extraction failed for %s: %s", chunk_id, exc)
            result = heuristic_extract_chunk(chunk, document_id, chunk_id)
        cache_updates[cache_key] = {"result": _strip_trace(result), "extraction_method": method}
        return index, _apply_trace(result, document_id, chunk_id), method

    processed: list[tuple[int, dict[str, Any], str]] = []
    with ThreadPoolExecutor(max_workers=min(5, max(1, len(chunks)))) as executor:
        futures = [executor.submit(process_chunk, index, chunk) for index, chunk in enumerate(chunks)]
        for future in as_completed(futures):
            processed.append(future.result())
    processed.sort(key=lambda item: item[0])

    with CACHE_LOCK:
        cache.update(cache_updates)
        _save_cache(cache_file, cache)

    chunk_results = [result for _, result, _ in processed]
    entities, triples = resolve_chunk_results(chunk_results)
    method_counts = Counter(method for _, _, method in processed)
    method = "mixed" if len(method_counts) > 1 else next(iter(method_counts), "heuristic")
    stored_chunks = [
        {
            "id": f"{document_id}:chunk:{index}",
            "index": index,
            "text": chunk,
            "extraction_method": processed[index][2],
        }
        for index, chunk in enumerate(chunks)
    ]
    relationships = [
        {**triple, "source": triple["subject"], "target": triple["object"]}
        for triple in triples
    ]
    return {
        "id": document_id,
        "name": filename,
        "text": text,
        "chunks": stored_chunks,
        "topics": extract_topics(text),
        "entities": entities,
        "relationships": relationships,
        "extraction_method": method,
        "extraction_method_counts": dict(method_counts),
    }
