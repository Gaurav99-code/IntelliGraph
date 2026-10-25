# IntelliGraph

IntelliGraph is an interactive, topic-augmented knowledge base for turning PDFs
and text documents into explainable answers. It combines document extraction,
vector retrieval, graph evidence, local LLM generation, citations, and an
interactive React interface.

## What the demo does

```text
Upload PDF/text
      ↓
Parse and chunk the document
      ↓
Extract topics, entities, and relationships
      ↓
Index chunks in ChromaDB and graph data in JSON/Neo4j
      ↓
Retrieve relevant evidence for a question
      ↓
Generate a grounded answer with citations
      ↓
Show source excerpts and graph relationships in the UI
```

The answer generator is evidence-first: it is instructed to use only retrieved
source text and validated citation IDs. If the LLM is disabled or unavailable,
IntelliGraph returns an extractive answer from the best retrieved source instead
of failing the query.

## Features

- PDF and text upload with per-document extraction status.
- Topic, entity, and relationship extraction.
- ChromaDB vector retrieval.
- Sentence-Transformers embeddings:
  - `BAAI/bge-small-en-v1.5` preferred model.
  - `all-MiniLM-L6-v2` fallback model.
- Local Ollama support through the OpenAI-compatible API.
- Grounded answer generation with:
  - `answer`
  - `sources`
  - `citations`
  - `topics`
  - `graph_paths`
  - `answer_method`
  - `confidence`
  - `insufficient_evidence`
- Extractive fallback when Ollama is disabled, unavailable, times out, or
  returns malformed JSON.
- Interactive D3 graph with evidence highlighting and node details.
- Source excerpts with searched terms highlighted.
- Clickable source and graph evidence navigation.
- Dynamic question suggestions based on uploaded documents and topics.
- Separate fullscreen views for the research workspace and graph.
- Animated empty graph state that explains the Read → Connect → Explain flow.
- In-app **See logs** viewer for backend and frontend activity.

## Requirements

- Python 3.11+ recommended.
- Node.js and npm.
- Optional: Ollama for local answer generation.
- Optional: Docker Desktop for Neo4j.

## Local setup

From the repository root:

```powershell
venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

### Recommended: local Ollama mode

Install Ollama, then pull a model:

```powershell
ollama --version
ollama pull llama3.2
ollama list
```

Configure `.env` for local inference:

```env
LLM_ENABLED=true
LLM_PROVIDER=ollama
LLM_MODEL=llama3.2
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=
LLM_TIMEOUT_SECONDS=120
LLM_MAX_RETRIES=2
```

Ollama local mode does not require a real cloud API key. The backend uses the
OpenAI-compatible client with a local placeholder key internally; no key is
sent to the frontend.

If Ollama is unavailable, set:

```env
LLM_ENABLED=false
```

The upload and query flows continue using heuristic extraction and extractive
answer fallback.

### Start the backend

```powershell
venv\Scripts\python.exe -m uvicorn backend.main:app --reload --env-file .env
```

Backend endpoints:

```text
http://localhost:8000
http://localhost:8000/docs
http://localhost:8000/api/health
```

### Start the frontend

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Frontend URL:

```text
http://localhost:5173
```

The frontend uses Vite's same-origin `/api` proxy by default, targeting the
backend at `http://localhost:8000`. This avoids accidentally sending log and
application requests to the Vite server itself, which would return `Not Found`.

If the backend is running on another port, create `frontend/.env.local`:

```powershell
Copy-Item frontend\.env.example frontend\.env.local
```

Then edit the target, for example:

```env
VITE_API_PROXY_TARGET=http://localhost:8767
```

Restart Vite after changing this file. For a frontend hosted separately from
the Vite server, set a direct API URL instead:

```env
VITE_API_BASE_URL=https://your-backend.example.com
```

For the standard local setup, start the backend on port 8000 before opening the
frontend:

```powershell
venv\Scripts\python.exe -m uvicorn backend.main:app --reload --env-file .env --port 8000
```

If the log viewer still shows `Not Found`, restart the backend from the current
checkout so that it loads the `/api/logs` route, then restart Vite so it loads
the current proxy configuration.

To run the frontend after changing its environment:

```powershell
npm run dev
```

## Demo workflow

1. Open `http://localhost:5173`.
2. Upload one or more PDFs from the upload area.
3. Use the dynamic suggestion chips or type a question.
4. Inspect the grounded answer and answer method.
5. Open a source card to view the focused excerpt and highlighted terms.
6. Click **Focus document in graph** to navigate the graph.
7. Click a graph relationship to focus its source and target nodes.
8. Use **Expand** to open the research or graph section fullscreen.
9. Use **See logs** to inspect recent backend/frontend activity.

Example questions:

```text
What does metformin do?
How are obesity and insulin resistance related?
What are the main themes across these documents?
Summarize the key findings in the uploaded documents.
```

## API contract

### Health and infrastructure

```text
GET /api/health
GET /api/infrastructure
```

`/api/infrastructure` reports vector, graph, embedding, LLM, and extraction
status. If an older backend process does not expose `/api/infrastructure`, the
frontend can use the backend status included in `/api/health`.

### Upload

```text
POST /api/documents/upload
```

Multipart field:

```text
files
```

Accepted formats include PDF, TXT, Markdown, CSV, and JSON.

### Query

```text
POST /api/query
Content-Type: application/json
```

Request:

```json
{
  "question": "What does metformin do?",
  "top_k": 5
}
```

Response fields:

```json
{
  "question": "What does metformin do?",
  "answer": "Metformin improves insulin sensitivity and reduces hepatic glucose production.",
  "route": "factual",
  "sources": [],
  "citations": [],
  "topics": [],
  "graph_paths": [],
  "answer_method": "llm",
  "confidence": 0.86,
  "insufficient_evidence": false
}
```

`answer_method` is either `llm` or `extractive`. When no grounded source is
available, `insufficient_evidence` is `true` and the API returns a clear
insufficient-evidence message instead of inventing an answer.

### Logs

The backend creates rotating local logs:

```text
logs/backend.log
logs/frontend.log
logs/activity.jsonl
```

Log endpoints:

```text
GET /api/logs?source=all
GET /api/logs?source=backend
GET /api/logs?source=frontend
POST /api/logs/client
```

The UI's **See logs** button provides a tabbed, scrollable activity viewer. Each
entry includes the local timestamp, source, action, message, uploaded filename
when applicable, document ID, byte count, extraction method, query route, and
other safe metadata. Examples include:

- `document_upload_started` with the selected filename(s).
- `document_uploaded` with filename, timestamp, document ID, bytes, chunks, and
  extraction method.
- `document_deleted` with the document ID.
- `query_completed` with route, answer method, and evidence counts.
- `indexes_rebuilt` after a vector/graph rebuild.

The activity log does not store full question text or document contents; only
safe metadata such as question length and request status is recorded.

After pulling a new version, restart both the backend and Vite dev server. A
browser tab connected to an older Vite process can send `/api/logs` to the wrong
server and display `Not Found` even when the current code has the route.

## Storage and optional Neo4j

JSON remains the local source of truth. Runtime data is stored under `data/`:

```text
data/knowledge_base.json
data/chroma/
data/extraction_cache.json
```

Neo4j is optional. To enable it:

```powershell
docker compose up -d neo4j
```

Then configure `.env`:

```env
NEO4J_ENABLED=true
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=change-this-password
NEO4J_DATABASE=neo4j
```

If Neo4j is unavailable, IntelliGraph continues with the JSON graph fallback.
Use this endpoint after restoring a backend:

```text
POST /api/index/rebuild
```

## Project checks

Run backend checks from the repository root:

```powershell
venv\Scripts\python.exe -m pytest -q
venv\Scripts\python.exe -m compileall -q backend tests
git diff --check
```

Run frontend checks from `frontend/`:

```powershell
npm run lint
npm run build
```

The project virtual environment is the supported test environment. On machines
where system Python does not have pytest installed, `python -m pytest -q` will
fail before collecting tests; use the `venv\Scripts\python.exe` command above.

## Presentation deck

The completed Hypnexis26 presentation is available at:

```text
reports/IntelliGraph_Hypnexis26_Deck.pptx
```

The deck was generated from the official template using:

```text
tools/build_hypnexis_deck.py
```

## Repository layout

```text
backend/
  answer_generator.py     Grounded LLM answer generation and fallback
  document_processor.py   PDF/text parsing and extraction
  embedding_service.py    Sentence-Transformer and fallback embeddings
  graph_store.py          Optional Neo4j adapter
  llm_client.py           OpenAI-compatible and Ollama client
  logging_config.py       Rotating backend/frontend log setup
  main.py                 FastAPI routes and middleware
  store.py                JSON source of truth and hybrid retrieval
  vector_store.py         ChromaDB integration

frontend/src/
  App.jsx                 Application orchestration
  Chat.jsx                Chat, citations, excerpts, and evidence UI
  GraphPanel.jsx          D3 graph and node detail panel
  LogViewer.jsx           In-app log viewer
  api.js                  Backend API client

tests/
  test_api.py             Upload/query/fallback/log endpoint tests
  test_answer_generator.py
  test_document_processor.py
  test_entity_resolution.py
  test_llm_client.py

reports/
  IntelliGraph_Hypnexis26_Deck.pptx
```
