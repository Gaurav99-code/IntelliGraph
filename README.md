# IntelliGraph

Topic-Augmented Knowledge Graph Builder with a React/Vite frontend and FastAPI
backend. The local implementation extracts topics, entities, and relationships
from PDF/text uploads, persists them to a JSON knowledge store, routes thematic
or factual questions, and returns supporting graph edges for the frontend.

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

## Frontend integration contract

- `GET /api/health` — health and document count.
- `POST /api/documents/upload` — multipart field `files`, accepts PDF/text.
- `GET /api/documents` — document cards/list.
- `DELETE /api/documents/{document_id}` — remove an uploaded document.
- `GET /api/graph` — `{nodes, edges}` for the graph visualization.
- `GET /api/graph/nodes/{node_id}` — selected node and connected edges.
- `POST /api/query` — JSON `{ "question": "...", "top_k": 5 }`; returns the
  answer, route, sources, topics, and `graph_paths` for highlighting evidence.

The frontend supports document upload/removal, live document/topic/entity graph
rendering, factual/thematic query routing, grounded sources, and evidence-path
highlighting. The CORS defaults support common Vite and Create React App
development ports.

## Design note

The local JSON store and lexical retrieval are intentionally dependency-light so
the complete flow works without Neo4j, ChromaDB, or an LLM API key.  The
extraction and storage boundaries are isolated in `backend/document_processor.py`
and `backend/store.py`, making it straightforward to replace those internals
with production graph/vector services later.
