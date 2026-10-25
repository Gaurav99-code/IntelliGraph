from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from backend import main
from backend.llm_client import LLMClient
from backend.store import KnowledgeStore


class FakeAnswerLLM:
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


def _store_with_document(tmp_path: Path) -> KnowledgeStore:
    store = KnowledgeStore(tmp_path / "knowledge.json")
    store.add_document({
        "id": "doc-1",
        "name": "diabetes.txt",
        "text": "Metformin improves insulin sensitivity and reduces glucose production.",
        "chunks": [{
            "id": "doc-1:chunk:0",
            "index": 0,
            "text": "Metformin improves insulin sensitivity and reduces glucose production.",
        }],
        "topics": [{"id": "topic:diabetes", "label": "diabetes", "score": 1}],
        "entities": [
            {"name": "Metformin", "type": "Medication", "description": "a medication"},
            {"name": "insulin sensitivity", "type": "Concept", "description": "a concept"},
        ],
        "relationships": [{
            "subject": "Metformin",
            "relation": "improves",
            "object": "insulin sensitivity",
            "evidence": "Metformin improves insulin sensitivity.",
            "doc_id": "doc-1",
            "chunk_id": "doc-1:chunk:0",
        }],
    })
    return store


def test_upload_and_delete_endpoints(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(main, "store", KnowledgeStore(tmp_path / "knowledge.json"))
    monkeypatch.setattr(main, "llm_client", LLMClient(enabled=False))
    client = TestClient(main.app)
    upload = client.post(
        "/api/documents/upload",
        files=[("files", ("sample.txt", b"Metformin improves insulin sensitivity.", "text/plain"))],
    )
    assert upload.status_code == 200
    document_id = upload.json()["documents"][0]["id"]
    assert client.get("/api/infrastructure").status_code == 200
    deleted = client.delete(f"/api/documents/{document_id}")
    assert deleted.status_code == 200
    assert client.get("/api/documents").json()["documents"] == []


def test_logs_endpoint_and_frontend_log_event(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(main, "LOG_DIR", tmp_path / "logs")
    client = TestClient(main.app)
    marker = "test-frontend-log-event"
    logged = client.post(
        "/api/logs/client",
        json={"level": "info", "message": marker, "context": {"source": "pytest"}},
    )
    assert logged.status_code == 204
    response = client.get("/api/logs?source=frontend&limit=25")
    assert response.status_code == 200
    assert marker in "\n".join(response.json()["logs"]["frontend"])
    assert response.json()["events"][0]["action"] == marker
    assert response.json()["events"][0]["source"] == "frontend"


def test_upload_creates_user_visible_activity_event(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(main, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(main, "store", KnowledgeStore(tmp_path / "knowledge.json"))
    monkeypatch.setattr(main, "llm_client", LLMClient(enabled=False))
    response = TestClient(main.app).post(
        "/api/documents/upload",
        files=[("files", ("visible-log.txt", b"Metformin improves insulin sensitivity.", "text/plain"))],
    )

    assert response.status_code == 200
    events = TestClient(main.app).get("/api/logs?source=backend&limit=25").json()["events"]
    uploaded = next(event for event in events if event["action"] == "document_uploaded")
    assert uploaded["details"]["file_name"] == "visible-log.txt"
    assert uploaded["timestamp"]


def test_upload_query_end_to_end_and_disabled_llm_fallback(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(main, "store", KnowledgeStore(tmp_path / "knowledge.json"))
    monkeypatch.setattr(main, "llm_client", LLMClient(enabled=False))
    client = TestClient(main.app)
    document_text = "Metformin improves insulin sensitivity and reduces hepatic glucose production."

    upload = client.post(
        "/api/documents/upload",
        files=[("files", ("metformin.txt", document_text.encode("utf-8"), "text/plain"))],
    )

    assert upload.status_code == 200
    uploaded_documents = upload.json()["documents"]
    assert len(uploaded_documents) == 1

    fake_llm = FakeAnswerLLM({
        "answer": "Metformin improves insulin sensitivity and reduces hepatic glucose production.",
        "citation_ids": ["source-0"],
        "confidence": 0.86,
        "insufficient_evidence": False,
    })
    monkeypatch.setattr(main, "llm_client", fake_llm)
    llm_response = client.post(
        "/api/query",
        json={"question": "What does metformin do?", "top_k": 5},
    )

    assert llm_response.status_code == 200
    llm_payload = llm_response.json()
    assert llm_payload["answer"]
    assert llm_payload["sources"]
    assert "citations" in llm_payload
    assert llm_payload["answer_method"] in {"llm", "extractive"}
    assert "graph_paths" in llm_payload
    source_chunks = {
        (source.get("document_id"), source.get("chunk_id"))
        for source in llm_payload["sources"]
    }
    assert all(
        (citation.get("document_id"), citation.get("chunk_id")) in source_chunks
        for citation in llm_payload["citations"]
    )

    monkeypatch.setattr(main, "llm_client", LLMClient(enabled=False))
    fallback_response = client.post(
        "/api/query",
        json={"question": "What does metformin do?", "top_k": 5},
    )

    assert fallback_response.status_code == 200
    fallback_payload = fallback_response.json()
    assert fallback_payload["answer"]
    assert fallback_payload["sources"]
    assert "citations" in fallback_payload
    assert fallback_payload["answer_method"] == "extractive"
    assert "graph_paths" in fallback_payload
    fallback_source_chunks = {
        (source.get("document_id"), source.get("chunk_id"))
        for source in fallback_payload["sources"]
    }
    assert all(
        (citation.get("document_id"), citation.get("chunk_id")) in fallback_source_chunks
        for citation in fallback_payload["citations"]
    )


def test_factual_query_returns_grounded_llm_answer_and_citations(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(main, "store", _store_with_document(tmp_path))
    llm = FakeAnswerLLM({
        "answer": "Metformin improves insulin sensitivity.",
        "citation_ids": ["source-0"],
        "confidence": 0.86,
        "insufficient_evidence": False,
    })
    monkeypatch.setattr(main, "llm_client", llm)
    response = TestClient(main.app).post(
        "/api/query",
        json={"question": "What does metformin do?", "top_k": 5},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["route"] == "factual"
    assert payload["answer"] == "Metformin improves insulin sensitivity."
    assert payload["answer_method"] == "llm"
    assert payload["confidence"] == 0.86
    assert payload["insufficient_evidence"] is False
    assert payload["citations"][0]["id"] == "source-0"
    assert payload["citations"][0]["chunk_id"] == "doc-1:chunk:0"
    assert len(llm.calls) == 1


def test_thematic_query_preserves_route_and_response_fields(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(main, "store", _store_with_document(tmp_path))
    monkeypatch.setattr(main, "llm_client", LLMClient(enabled=False))
    payload = TestClient(main.app).post(
        "/api/query",
        json={"question": "What are the main themes across metformin?", "top_k": 5},
    ).json()

    assert payload["route"] == "thematic"
    assert payload["answer_method"] == "extractive"
    assert payload["sources"]
    assert payload["topics"]
    assert "citations" in payload
    assert "graph_paths" in payload


def test_query_with_no_documents_returns_insufficient_evidence(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(main, "store", KnowledgeStore(tmp_path / "knowledge.json"))
    monkeypatch.setattr(main, "llm_client", LLMClient(enabled=False))
    response = TestClient(main.app).post(
        "/api/query",
        json={"question": "What does metformin do?", "top_k": 5},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["sources"] == []
    assert payload["citations"] == []
    assert payload["insufficient_evidence"] is True
    assert payload["answer_method"] == "extractive"


def test_query_with_llm_disabled_returns_compatible_extractive_response(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(main, "store", _store_with_document(tmp_path))
    monkeypatch.setattr(main, "llm_client", LLMClient(enabled=False))
    response = TestClient(main.app).post(
        "/api/query",
        json={"question": "What does metformin do?", "top_k": 5},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["question"] == "What does metformin do?"
    assert payload["answer"]
    assert payload["route"] == "factual"
    assert payload["sources"]
    assert payload["citations"]
    assert payload["answer_method"] == "extractive"
    assert "topics" in payload
    assert "graph_paths" in payload


def test_query_with_no_matching_evidence_returns_insufficient_evidence(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(main, "store", _store_with_document(tmp_path))
    monkeypatch.setattr(main, "llm_client", LLMClient(enabled=False))
    payload = TestClient(main.app).post(
        "/api/query",
        json={"question": "What does quantum computing do?", "top_k": 5},
    ).json()

    assert payload["sources"] == []
    assert payload["citations"] == []
    assert payload["insufficient_evidence"] is True
    assert "not find enough grounded evidence" in payload["answer"]


def test_query_uses_extractive_fallback_when_llm_fails(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(main, "store", _store_with_document(tmp_path))
    monkeypatch.setattr(main, "llm_client", FakeAnswerLLM(error=TimeoutError("Ollama timed out")))
    response = TestClient(main.app).post(
        "/api/query",
        json={"question": "What does metformin do?", "top_k": 5},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["question"] == "What does metformin do?"
    assert payload["answer"]
    assert payload["route"] == "factual"
    assert payload["sources"]
    assert "topics" in payload
    assert "graph_paths" in payload
    assert payload["answer_method"] == "extractive"
    assert payload["citations"]
    assert payload["citations"][0]["id"] == "source-0"
    assert payload["insufficient_evidence"] is False
