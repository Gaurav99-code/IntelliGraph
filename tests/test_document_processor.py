from pathlib import Path

from backend.document_processor import process_document


class CountingLLM:
    enabled = True
    api_key: str | None = "test"

    def __init__(self, fail=False):
        self.calls = 0
        self.fail = fail

    def generate_json(self, system_prompt, user_prompt, schema):
        self.calls += 1
        if self.fail:
            raise RuntimeError("simulated provider failure")
        return {
            "entities": [
                {"name": "Metformin", "type": "Medication", "description": "a medication"},
                {"name": "insulin sensitivity", "type": "Concept", "description": "a metabolic concept"},
            ],
            "triples": [{
                "subject": "Metformin",
                "relation": "improves",
                "object": "insulin sensitivity",
                "evidence": "Metformin improves insulin sensitivity.",
            }],
        }


def test_cache_hit_skips_llm_call(tmp_path: Path):
    cache = tmp_path / "extraction_cache.json"
    first = CountingLLM()
    process_document("doc-1", "a.txt", b"Metformin improves insulin sensitivity.", first, cache)
    second = CountingLLM()
    document = process_document("doc-2", "a.txt", b"Metformin improves insulin sensitivity.", second, cache)
    assert first.calls == 1
    assert second.calls == 0
    assert document["extraction_method"] == "llm"


def test_llm_enabled_run_upgrades_heuristic_cache(tmp_path: Path):
    cache = tmp_path / "extraction_cache.json"
    process_document("doc-1", "a.txt", b"Metformin improves insulin sensitivity.", CountingLLM(fail=True), cache)
    successful = CountingLLM()
    document = process_document("doc-2", "a.txt", b"Metformin improves insulin sensitivity.", successful, cache)
    assert successful.calls == 1
    assert document["extraction_method"] == "llm"


def test_llm_failure_falls_back_without_failing_upload(tmp_path: Path):
    document = process_document(
        "doc-1",
        "a.txt",
        b"Metformin improves insulin sensitivity and glucose control.",
        CountingLLM(fail=True),
        tmp_path / "extraction_cache.json",
    )
    assert document["extraction_method"] == "heuristic"
    assert document["chunks"][0]["extraction_method"] == "heuristic"
    assert document["entities"]
