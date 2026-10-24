"""FastAPI application for the IntelliGraph knowledge-base backend."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .document_processor import process_document
from .graph_store import Neo4jGraphStore
from .llm_client import LLMClient
from .store import KnowledgeStore
from .vector_store import ChromaVectorStore


BASE_DIR = Path(__file__).resolve().parents[1]
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
    topics: list[dict]
    graph_paths: list[list[dict]]


# Create FastAPI application
app = FastAPI(
    title="IntelliGraph API",
    description="Topic-Augmented Knowledge Graph Backend",
    version="1.0.0",
)


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
        raise HTTPException(status_code=404, detail="Document not found")
    return {"deleted": True, "document_id": document_id}


@app.post("/api/documents/upload")
async def upload_documents(files: list[UploadFile] = File(...)):
    """Ingest PDF/text files and return graph-ready document summaries."""

    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required")

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
            raise HTTPException(status_code=422, detail=f"Could not process {filename}: {exc}") from exc
        stored = store.add_document(document)
        uploaded.append(store._document_summary(stored))

    return {"documents": uploaded, "graph": store.graph(), "backends": build_infrastructure_status()}


@app.post("/api/index/rebuild")
def rebuild_indexes():
    """Rebuild Chroma and Neo4j indexes from the local document source of truth."""

    return {"reindexed": store.reindex_backends(), "backends": build_infrastructure_status()}


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

    return store.answer(request.question, request.top_k)
