"""Canonical entity resolution for typed extraction results."""

from __future__ import annotations

import re
from typing import Any

from rapidfuzz.fuzz import ratio

from .embedding_service import cosine_similarity, get_embedding_service
from .llm_extractor import ExtractedEntity, ExtractedTriple


GENERIC_TYPES = {"Other", "Concept"}


def normalize_name(value: str) -> str:
    """Normalize an entity label for comparison without changing display text."""

    normalized = re.sub(r"[^a-z0-9\s]+", " ", value.lower())
    normalized = re.sub(r"^the\s+", "", normalized)
    return " ".join(normalized.split())


def compatible_types(left: str, right: str) -> bool:
    """Return whether two typed entities can safely share a canonical node."""

    return left == right or (left in GENERIC_TYPES and right in GENERIC_TYPES)


def _is_alias(left: ExtractedEntity, right: ExtractedEntity) -> bool:
    if not compatible_types(left.type, right.type):
        return False
    a, b = normalize_name(left.name), normalize_name(right.name)
    if not a or not b:
        return False
    if a == b or ratio(a, b) >= 90:
        return True
    shorter, longer = sorted((a, b), key=len)
    if shorter in longer and len(shorter.split()) >= 2:
        return True
    vectors = get_embedding_service().encode([a, b])
    return cosine_similarity(vectors[0], vectors[1]) >= 0.88


def resolve_entities_and_triples(
    entities: list[ExtractedEntity],
    triples: list[ExtractedTriple],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Merge aliases, preserve typed metadata, and rewrite triples canonically."""

    canonical: list[dict[str, Any]] = []
    lookup: dict[str, str] = {}

    for entity in entities:
        existing = next((item for item in canonical if _is_alias(entity, ExtractedEntity(**item))), None)
        if existing is None:
            item = {
                "name": entity.name.strip(),
                "type": entity.type,
                "description": entity.description.strip(),
                "aliases": [],
            }
            canonical.append(item)
            existing = item
        elif normalize_name(entity.name) != normalize_name(existing["name"]):
            existing["aliases"].append(entity.name.strip())
        if not existing["description"] and entity.description:
            existing["description"] = entity.description.strip()
        lookup[normalize_name(entity.name)] = existing["name"]
        lookup[normalize_name(existing["name"])] = existing["name"]
        for alias in existing["aliases"]:
            lookup[normalize_name(alias)] = existing["name"]

    resolved_triples: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    for triple in triples:
        subject = lookup.get(normalize_name(triple.subject), triple.subject.strip())
        object_name = lookup.get(normalize_name(triple.object), triple.object.strip())
        if normalize_name(subject) == normalize_name(object_name):
            continue
        key = (normalize_name(subject), triple.relation, normalize_name(object_name), triple.doc_id, triple.chunk_id)
        if key in seen:
            continue
        seen.add(key)
        resolved_triples.append({
            "subject": subject,
            "relation": triple.relation,
            "object": object_name,
            "evidence": triple.evidence,
            "doc_id": triple.doc_id,
            "chunk_id": triple.chunk_id,
        })
    return canonical, resolved_triples


def resolve_chunk_results(results: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Resolve serialized chunk extraction results across one document."""

    entities: list[ExtractedEntity] = []
    triples: list[ExtractedTriple] = []
    for result in results:
        entities.extend(ExtractedEntity.model_validate(entity) for entity in result.get("entities", []))
        triples.extend(ExtractedTriple.model_validate(triple) for triple in result.get("triples", []))
    return resolve_entities_and_triples(entities, triples)
