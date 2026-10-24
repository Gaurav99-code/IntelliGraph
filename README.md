# IntelliGraph

Topic-Augmented Knowledge Graph Builder with a React/Vite frontend and FastAPI
backend. The backend extracts topics, entities, and relationships from PDF/text
uploads, stores chunks in ChromaDB for vector-similarity retrieval, mirrors graph data to
Neo4j when enabled, routes thematic or factual questions, and returns supporting
graph edges for the frontend. JSON remains the local source of truth and keeps
the app usable when Neo4j is not running.

## Run locally

```powershell
venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\python.exe -m uvicorn backend.main:app --reload --env-file .env
```

The API is available at `http://localhost:8000`; interactive OpenAPI docs are
at `http://localhost:8000/docs`.

Start the frontend in a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

The frontend is available at `http://localhost:5173`.

## Phase 1: ChromaDB and Neo4j

ChromaDB runs as a local persistent vector index at `data/chroma` by default. It
uses the deterministic feature-hash embedding adapter in
`backend/embeddings.py`, which is kept small and offline-friendly so the first
run does not download a model. A production embedding model can replace this
adapter in a later phase without changing the Chroma integration.

Neo4j is optional during local development. To enable it:

```powershell
docker compose up -d neo4j
```

Copy `.env.example` to `.env`, set `NEO4J_ENABLED=true`, and keep the matching
Neo4j password. Then restart the backend. Existing JSON documents are mirrored
into both indexes at startup. The status is available at:

```text
GET /api/infrastructure
```

If Neo4j is unavailable, the API reports the error and continues using the JSON
graph fallback. `POST /api/index/rebuild` replays all stored documents into the
configured backends after a service is restored.

## Phase 2: structured extraction and embeddings

The default Phase 2 provider is OpenAI-compatible JSON generation. Configure it
only through `.env`:

```text
LLM_ENABLED=true
LLM_PROVIDER=openai
LLM_API_KEY=your-key
LLM_MODEL=gpt-4o-mini
```

When the key is missing, `LLM_ENABLED=false`, or an individual call fails, the
upload continues with the heuristic extractor and records
`extraction_method=heuristic` for that chunk. Successful structured calls are
recorded as `extraction_method=llm`. Results are cached by SHA-256 in
`data/extraction_cache.json`.

Entity names are normalized and resolved with typed compatibility checks,
RapidFuzz, and embedding similarity. The preferred embedding model is
`BAAI/bge-small-en-v1.5`, with `all-MiniLM-L6-v2` and then the existing hash
embedding as fallbacks. The model name is stored in Chroma collection metadata;
changing it causes the collection to rebuild.

## Frontend integration contract

- `GET /api/health` — health and document count.
- `POST /api/documents/upload` — multipart field `files`, accepts PDF/text.
- `GET /api/documents` — document cards/list.
- `DELETE /api/documents/{document_id}` — remove an uploaded document.
- `GET /api/graph` — `{nodes, edges}` for the graph visualization.
- `GET /api/graph/nodes/{node_id}` — selected node and connected edges.
- `POST /api/query` — JSON `{ "question": "...", "top_k": 5 }`; returns the
  answer, route, sources, topics, and `graph_paths` for highlighting evidence.
- `GET /api/infrastructure` — ChromaDB/Neo4j availability and index counts.
- `POST /api/index/rebuild` — rebuild configured indexes from JSON documents.

The frontend supports document upload/removal, live document/topic/entity graph
rendering, factual/thematic query routing, grounded sources, and evidence-path
highlighting. The CORS defaults support common Vite and Create React App
development ports.

## Design note

The extraction layer is still deterministic for now; Phase 1 focuses on real
vector and graph infrastructure. The extraction and storage boundaries are
isolated in `backend/document_processor.py`, `backend/vector_store.py`,
`backend/graph_store.py`, and `backend/store.py`, making it possible to replace
the embedding or extraction provider in a later phase without changing the
frontend contract.
