"""FastAPI application for the IntelliGraph knowledge-base backend."""

from __future__ import annotations

import os
import logging
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .answer_generator import generate_grounded_answer
from .document_processor import process_document
from .graph_store import Neo4jGraphStore
from .llm_client import LLMClient
from .logging_config import configure_logging, read_activity_events, read_log_lines, record_activity
from .store import KnowledgeStore
from .vector_store import ChromaVectorStore


BASE_DIR = Path(__file__).resolve().parents[1]
LOG_DIR = BASE_DIR / "logs"
configure_logging(LOG_DIR)
logger = logging.getLogger("intelligraph.backend")
DATA_PATH = Path(os.getenv("INTELLIGRAPH_DATA_PATH", BASE_DIR / "data" / "knowledge_base.json"))
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
CHROMA_PATH = Path(os.getenv("CHROMA_PATH", BASE_DIR / "data" / "chroma"))
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "intelligraph_chunks")
NEO4J_ENABLED = os.getenv("NEO4J_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
vector_store = ChromaVectorStore(CHROMA_PATH, CHROMA_COLLECTION)
llm_client = LLMClient.from_env()
graph_store = Neo4jGraphStore(
    os.getenv("NEO4J_URI") if NEO4J_ENABLED else None,
    os.getenv("NEO4J_USER") if NEO4J_ENABLED else None,
    os.getenv("NEO4J_PASSWORD") if NEO4J_ENABLED else None,
    os.getenv("NEO4J_DATABASE", "neo4j"),
)
store = KnowledgeStore(DATA_PATH, vector_store=vector_store, graph_store=graph_store)
store.reindex_backends()


def build_infrastructure_status() -> dict:
    """Return safe status for every extraction and persistence backend."""

    status = store.backend_status()
    status.update(llm_client.status())
    status["embedding_model"] = status["vector"].get("embedding_model")
    status["extraction_method_counts"] = store.extraction_method_counts()
    return status


class QueryRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=20)


class QueryResponse(BaseModel):
    question: str
    answer: str
    route: str
    sources: list[dict]
    citations: list[dict]
    topics: list[dict]
    graph_paths: list[list[dict]]
    answer_method: str
    confidence: float
    insufficient_evidence: bool


class ClientLogRequest(BaseModel):
    level: str = Field(default="info", max_length=20)
    message: str = Field(min_length=1, max_length=2000)
    context: dict[str, Any] = Field(default_factory=dict)


# Create FastAPI application
app = FastAPI(
    title="IntelliGraph API",
    description="Topic-Augmented Knowledge Graph Backend",
    version="1.0.0",
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    started = time.perf_counter()
    try:
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.info("%s %s -> %s (%.1fms)", request.method, request.url.path, response.status_code, elapsed_ms)
        return response
    except Exception:
        logger.exception("Unhandled error during %s %s", request.method, request.url.path)
        raise


# Allow React frontend to access our backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv(
        "FRONTEND_ORIGINS", "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000"
    ).split(",") if origin.strip()],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"]
)


# Home endpoint
@app.get("/")
def home():
    return {
        "message": "Welcome to IntelliGraph Backend",
        "docs": "/docs",
    }


# Health check endpoint
@app.get("/api/health")
def health_check():
    return {
        "status": "success",
        "message": "IntelliGraph Backend is Running",
        "documents": len(store.documents),
        "backends": build_infrastructure_status(),
    }


@app.get("/api/infrastructure")
def infrastructure_status():
    """Return the configured vector and graph backend status."""

    return build_infrastructure_status()


@app.get("/api/logs")
def application_logs(source: str = "all", limit: int = 250):
    """Return recent raw lines and structured activity events for the viewer."""

    source = source.lower().strip()
    if source not in {"all", "backend", "frontend"}:
        raise HTTPException(status_code=400, detail="source must be all, backend, or frontend")
    bounded_limit = max(1, min(limit, 500))
    return {
        "source": source,
        "logs": read_log_lines(LOG_DIR, source, bounded_limit),
        "events": read_activity_events(LOG_DIR, source, bounded_limit),
    }


@app.post("/api/logs/client", status_code=204)
def client_log(payload: ClientLogRequest):
    """Accept short, non-sensitive frontend events for the local frontend log."""

    safe_context = {str(key)[:80]: str(value)[:500] for key, value in payload.context.items()}
    message = payload.message.replace("\r", " ").replace("\n", " ")
    level = payload.level.lower().strip()
    if level not in {"debug", "info", "warning", "error", "critical"}:
        level = "info"
    record_activity(
        LOG_DIR,
        source="frontend",
        action=message,
        message=message.replace("_", " ").capitalize(),
        details=safe_context,
        level=level,
    )
    return None


@app.get("/api/documents")
def list_documents():
    """Return uploaded documents for the left-hand document panel."""

    return {"documents": store.list_documents()}


@app.get("/api/documents/{document_id}")
def get_document(document_id: str):
    document = store.get_document(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return {
        **store._document_summary(document),
        "chunks": document.get("chunks", []),
        "relationships": document.get("relationships", []),
    }


@app.delete("/api/documents/{document_id}")
def delete_document(document_id: str):
    if not store.delete_document(document_id):
        record_activity(
            LOG_DIR,
            source="backend",
            action="document_delete_failed",
            message="Document delete failed",
            details={"document_id": document_id},
            level="error",
        )
        raise HTTPException(status_code=404, detail="Document not found")
    record_activity(
        LOG_DIR,
        source="backend",
        action="document_deleted",
        message="Document deleted",
        details={"document_id": document_id},
    )
    return {"deleted": True, "document_id": document_id}


@app.post("/api/documents/upload")
async def upload_documents(files: list[UploadFile] = File(...)):
    """Ingest PDF/text files and return graph-ready document summaries."""

    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required")

    record_activity(
        LOG_DIR,
        source="backend",
        action="document_upload_started",
        message="Document upload started",
        details={"file_names": [file.filename or "untitled.txt" for file in files], "file_count": len(files)},
    )
    uploaded: list[dict] = []
    for file in files:
        content = await file.read()
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"{file.filename or 'File'} exceeds the {MAX_UPLOAD_BYTES} byte limit",
            )
        filename = file.filename or "untitled.txt"
        try:
            document = process_document(str(uuid4()), filename, content, llm_client=llm_client)
        except ValueError as exc:
            record_activity(
                LOG_DIR,
                source="backend",
                action="document_upload_failed",
                message=f"Could not process {filename}",
                details={"file_name": filename, "error": str(exc)},
                level="error",
            )
            raise HTTPException(status_code=422, detail=f"Could not process {filename}: {exc}") from exc
        stored = store.add_document(document)
        uploaded.append(store._document_summary(stored))
        record_activity(
            LOG_DIR,
            source="backend",
            action="document_uploaded",
            message=f"Uploaded {filename}",
            details={
                "file_name": filename,
                "document_id": stored.get("id"),
                "bytes": len(content),
                "chunks": len(stored.get("chunks", [])),
                "extraction_methods": sorted({chunk.get("extraction_method", "unknown") for chunk in stored.get("chunks", [])}),
            },
        )

    return {"documents": uploaded, "graph": store.graph(), "backends": build_infrastructure_status()}


@app.post("/api/index/rebuild")
def rebuild_indexes():
    """Rebuild Chroma and Neo4j indexes from the local document source of truth."""

    result = store.reindex_backends()
    record_activity(
        LOG_DIR,
        source="backend",
        action="indexes_rebuilt",
        message="Vector and graph indexes rebuilt",
        details={"documents": len(store.documents)},
    )
    return {"reindexed": result, "backends": build_infrastructure_status()}


@app.get("/api/graph")
def get_graph(document_id: str | None = None):
    """Return nodes and edges for the interactive graph panel."""

    return store.graph(document_id=document_id)


@app.get("/api/graph/nodes/{node_id}")
def get_graph_node(node_id: str):
    details = store.node_details(node_id)
    if not details:
        raise HTTPException(status_code=404, detail="Graph node not found")
    return details


@app.post("/api/query", response_model=QueryResponse)
def query_knowledge_base(request: QueryRequest):
    """Route a thematic or factual question and return grounded evidence."""

    search_result = store.search(request.question, request.top_k)
    sources = [
        {
            "document_id": match["document_id"],
            "document_name": match["document_name"],
            "chunk_id": match["chunk_id"],
            "chunk_index": match["chunk_index"],
            "score": match["score"],
            "text": match["text"],
        }
        for match in search_result["matches"]
    ]
    generated = generate_grounded_answer(
        request.question,
        sources,
        search_result["paths"],
        search_result["topics"],
        llm_client,
    )
    source_by_id = {f"source-{index}": source for index, source in enumerate(sources)}
    citations = [
        {"id": citation_id, **source_by_id[citation_id]}
        for citation_id in generated["citation_ids"]
        if citation_id in source_by_id
    ]
    record_activity(
        LOG_DIR,
        source="backend",
        action="query_completed",
        message="Knowledge-base query completed",
        details={
            "question_length": len(request.question),
            "route": search_result["route"],
            "answer_method": generated["answer_method"],
            "source_count": len(sources),
            "citation_count": len(citations),
            "insufficient_evidence": generated["insufficient_evidence"],
        },
    )
    return {
        "question": request.question,
        "answer": generated["answer"],
        "route": search_result["route"],
        "sources": sources,
        "citations": citations,
        "topics": search_result["topics"],
        "graph_paths": search_result["paths"],
        "answer_method": generated["answer_method"],
        "confidence": generated["confidence"],
        "insufficient_evidence": generated["insufficient_evidence"],
    }
