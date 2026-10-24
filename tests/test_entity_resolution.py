from backend.entity_resolution import resolve_entities_and_triples
from backend.llm_extractor import ExtractedEntity, ExtractedTriple


def test_aliases_merge_when_types_match():
    entities = [
        ExtractedEntity(name="Type 2 Diabetes", type="Condition"),
        ExtractedEntity(name="type 2 diabetes mellitus", type="Condition"),
    ]
    resolved, triples = resolve_entities_and_triples(entities, [])
    assert len(resolved) == 1
    assert "type 2 diabetes mellitus" in resolved[0]["aliases"]
    assert triples == []


def test_incompatible_entity_types_do_not_merge():
    entities = [
        ExtractedEntity(name="Mercury", type="Location"),
        ExtractedEntity(name="Mercury", type="Technology"),
    ]
    resolved, _ = resolve_entities_and_triples(entities, [])
    assert len(resolved) == 2
