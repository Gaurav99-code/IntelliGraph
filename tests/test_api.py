from pathlib import Path

from fastapi.testclient import TestClient

from backend import main
from backend.llm_client import LLMClient
from backend.store import KnowledgeStore


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
