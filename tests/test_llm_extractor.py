import pytest

from backend.llm_client import LLMClient, LLMError
from backend.llm_extractor import ChunkExtraction, extract_chunk


class FakeLLM:
    enabled = True
    api_key: str | None = "test"

    def generate_json(self, system_prompt, user_prompt, schema):
        return """```json
        {"entities":[{"name":"Metformin","type":"Medication","description":"a medication"}],
        "triples":[{"subject":"Metformin","relation":"treats","object":"Type 2 Diabetes","evidence":"Metformin treats Type 2 Diabetes."}]}
        ```"""


def test_extractor_returns_valid_typed_json():
    result = extract_chunk("Metformin treats Type 2 Diabetes.", "doc-1", "chunk-1", FakeLLM())
    assert isinstance(result, ChunkExtraction)
    assert result.entities[0].type == "Medication"
    assert result.triples[0].doc_id == "doc-1"
    assert result.triples[0].chunk_id == "chunk-1"


def test_fenced_and_embedded_json_is_repaired():
    parsed = LLMClient.parse_json("prefix\n```json\n{\"entities\": [], \"triples\": []}\n```\nsuffix")
    assert parsed == {"entities": [], "triples": []}


def test_malformed_json_is_rejected_for_safe_fallback():
    with pytest.raises(LLMError):
        LLMClient.parse_json("not json")
