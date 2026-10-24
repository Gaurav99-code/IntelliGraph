from typing import Any

from backend.answer_generator import generate_grounded_answer


SOURCES = [
    {
        "document_id": "doc-1",
        "document_name": "diabetes.txt",
        "chunk_id": "chunk-1",
        "score": 0.9,
        "text": "Metformin improves insulin sensitivity and reduces glucose production.",
    },
    {
        "document_id": "doc-2",
        "document_name": "other.txt",
        "chunk_id": "chunk-2",
        "score": 0.3,
        "text": "Insulin resistance can affect glucose control.",
    },
]


class FakeLLM:
    enabled = True

    def __init__(self, response: Any = None, error: Exception | None = None):
        self.response = response
        self.error = error
        self.calls: list[tuple[str, str, dict]] = []

    def generate_json(self, system_prompt, user_prompt, schema):
        self.calls.append((system_prompt, user_prompt, schema))
        if self.error:
            raise self.error
        return self.response


def test_valid_grounded_answer_has_valid_citation_and_evidence_prompt():
    llm = FakeLLM({
        "answer": "Metformin improves insulin sensitivity.",
        "citation_ids": ["source-0"],
        "confidence": 0.86,
        "insufficient_evidence": False,
    })

    result = generate_grounded_answer(
        "What does metformin do?",
        SOURCES,
        [[{
            "source": "entity:metformin",
            "target": "entity:insulin-sensitivity",
            "label": "improves",
            "document_id": "doc-1",
            "chunk_id": "chunk-1",
            "evidence": "Metformin improves insulin sensitivity.",
        }]],
        [{"label": "diabetes", "score": 1}],
        llm,
    )

    assert result == {
        "answer": "Metformin improves insulin sensitivity.",
        "citation_ids": ["source-0"],
        "confidence": 0.86,
        "insufficient_evidence": False,
        "answer_method": "llm",
    }
    assert "Answer only from the supplied evidence" in llm.calls[0][0]
    assert '"source_id": "source-0"' in llm.calls[0][1]
    assert '"supporting_source_ids": [\n        "source-0"\n      ]' in llm.calls[0][1]


def test_llm_can_report_insufficient_evidence():
    llm = FakeLLM({
        "answer": "The supplied evidence is insufficient.",
        "citation_ids": [],
        "confidence": 0.1,
        "insufficient_evidence": True,
    })

    result = generate_grounded_answer("Unknown question", SOURCES, [], [], llm)

    assert result["answer_method"] == "llm"
    assert result["insufficient_evidence"] is True
    assert result["citation_ids"] == []


def test_malformed_llm_response_uses_extractive_fallback():
    result = generate_grounded_answer(
        "What does metformin do?",
        SOURCES,
        [],
        [],
        FakeLLM("not valid json"),
    )

    assert result == {
        "answer": "Metformin improves insulin sensitivity and reduces glucose production.",
        "citation_ids": ["source-0"],
        "confidence": 0.5,
        "insufficient_evidence": False,
        "answer_method": "extractive",
    }


def test_llm_failure_uses_best_source_fallback():
    result = generate_grounded_answer(
        "What does metformin do?",
        SOURCES,
        [],
        [],
        FakeLLM(error=TimeoutError("Ollama timed out")),
    )

    assert result["answer_method"] == "extractive"
    assert result["citation_ids"] == ["source-0"]
    assert result["answer"].startswith("Metformin improves")


def test_no_sources_returns_insufficient_evidence_without_calling_llm():
    llm = FakeLLM(error=AssertionError("LLM should not be called without sources"))

    result = generate_grounded_answer("What does metformin do?", [], [], [], llm)

    assert result == {
        "answer": "I could not find enough grounded evidence in the uploaded documents to answer this question.",
        "citation_ids": [],
        "confidence": 0.0,
        "insufficient_evidence": True,
        "answer_method": "extractive",
    }
