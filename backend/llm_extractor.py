"""Structured entity and relationship extraction for document chunks."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .llm_client import JSONGenerator, LLMClient


EntityType = Literal[
    "Person", "Organization", "Concept", "Condition", "Medication", "Treatment",
    "Biomarker", "Study", "Technology", "Location", "Other",
]


class ExtractedEntity(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = Field(min_length=1, max_length=120)
    type: EntityType = "Other"
    description: str = Field(default="", max_length=500)


class ExtractedTriple(BaseModel):
    model_config = ConfigDict(extra="ignore")

    subject: str = Field(min_length=1, max_length=120)
    relation: str = Field(min_length=1, max_length=80)
    object: str = Field(min_length=1, max_length=120)
    evidence: str = Field(min_length=1, max_length=500)
    doc_id: str = ""
    chunk_id: str = ""

    @field_validator("relation")
    @classmethod
    def normalize_relation(cls, value: str) -> str:
        return " ".join(value.lower().strip().split())


class ChunkExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    entities: list[ExtractedEntity] = Field(default_factory=list, max_length=15)
    triples: list[ExtractedTriple] = Field(default_factory=list, max_length=20)


SYSTEM_PROMPT = """You extract a clean knowledge graph from one document chunk.
Extract ONLY facts explicitly stated in the chunk. Do not infer, speculate, or
use outside knowledge. Skip generic words, headings, boilerplate, file/API/UI
terms, and process words such as GET, POST, Run, API, frontend, and backend.
Use only these entity types: Person, Organization, Concept, Condition,
Medication, Treatment, Biomarker, Study, Technology, Location, Other.
Relations must be short lowercase verb phrases such as 'treats', 'increases
risk of', or 'measured by'. Return at most 15 entities and 20 triples.

Few-shot examples:
Chunk: 'Metformin is a medication used to improve insulin sensitivity.'
JSON: {"entities":[{"name":"Metformin","type":"Medication","description":"a medication"},{"name":"insulin sensitivity","type":"Concept","description":"a glucose-regulation concept"}],"triples":[{"subject":"Metformin","relation":"improves","object":"insulin sensitivity","evidence":"Metformin is a medication used to improve insulin sensitivity."}]}

Chunk: 'The Diabetes Prevention Program compared intensive lifestyle intervention with metformin.'
JSON: {"entities":[{"name":"Diabetes Prevention Program","type":"Study","description":"a prevention study"},{"name":"intensive lifestyle intervention","type":"Treatment","description":"a lifestyle intervention"},{"name":"Metformin","type":"Medication","description":"a medication"}],"triples":[{"subject":"Diabetes Prevention Program","relation":"compared","object":"Metformin","evidence":"The Diabetes Prevention Program compared intensive lifestyle intervention with metformin."}]}
"""


def extraction_schema() -> dict[str, Any]:
    """Return the JSON schema sent to the configured LLM."""

    return ChunkExtraction.model_json_schema()


def extract_chunk(text: str, doc_id: str, chunk_id: str, client: JSONGenerator) -> ChunkExtraction:
    """Extract typed entities and traceable triples from one chunk."""

    payload = client.generate_json(
        SYSTEM_PROMPT,
        f"Document id: {doc_id}\nChunk id: {chunk_id}\n\nChunk text:\n{text}",
        extraction_schema(),
    )
    if isinstance(payload, str):
        payload = LLMClient.parse_json(payload)
    result = ChunkExtraction.model_validate(payload)
    for triple in result.triples:
        triple.doc_id = doc_id
        triple.chunk_id = chunk_id
    return result
