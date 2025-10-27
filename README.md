# JourneyOn Backend (FastAPI Skeleton)

A modular FastAPI project skeleton aligned with the design docs in `_design/`. It includes SQLAlchemy models, health endpoint, auth and agent stubs, error handling middleware, request validation, Docker setup, logging, and testing.

## Features
- Modular `app/` layout (api, db, core, middleware, schemas, agents, services, providers, llm, cache, storage)
- SQLAlchemy ORM models consistent with design docs
- Health endpoint `/api/health` (DB/Redis/Qdrant checks)
- Auth stub: `/api/auth/register`, `/api/auth/login`
- Unified LLM client with Ollama/Zhipu backends powering `/api/agent/chat`, `/api/agent/chat/stream` (SSE), and `/api/agent/ws/chat` (WebSocket) for real-time conversations
- Error handling middleware returning uniform envelope `{code, msg, data}`
- Typed settings (`pydantic-settings`) and structured logging
- Mypy config and pytest tests
- Redis cache helpers with shared rate-limiting/search cache for knowledge base vector search
- Local file storage abstraction with `/api/trips/{trip_id}/reports` endpoints (base64 upload, metadata list, download, delete)
- Audit logging service and admin `/api/audit-logs` endpoint for operational tracing

## Quick Start (Docker)

1. Ensure Docker is installed.
2. From project root, run:
   ```bash
   docker-compose up --build
   ```
3. Open API docs at: `http://localhost:8000/docs`

## Local Development (without Docker)

1. Create virtual env and install deps:
   ```bash
   python -m venv .venv && . .venv/Scripts/activate
   pip install -r requirements.txt
   ```
2. Start server:
   ```bash
   uvicorn app.main:app --reload
   ```

## Configuration
- Environment variables (see `.env.example`):
  - `DATABASE_URL` (default: Postgres)
  - `REDIS_URL`
  - `QDRANT_URL` (optional)
  - `SECRET_KEY`, `LOG_LEVEL`
  - `STORAGE_BACKEND`, `LOCAL_STORAGE_PATH`
- LLM controls: `LLM_PROVIDER` (`ollama`/`zhipu`), `OLLAMA_CHAT_MODEL`, `ZHIPU_API_KEY`, `ZHIPU_BASE_URL`, retry knobs (`LLM_MAX_RETRIES`, `LLM_RETRY_BASE_DELAY`, `LLM_REQUEST_TIMEOUT`)
- Embedding/RAG controls: `ENABLE_EMBEDDING`, `EMBEDDING_CONCURRENCY`, `OLLAMA_EMBED_MODEL`, `OLLAMA_RERANK_MODEL`, `OLLAMA_RERANK_ENABLED`

### Memory Layer (mem0)
- Feature flags:
  - `MEMORY_ENABLED` (default: false)
  - `MEMORY_INFER` (default: false) — turn on LLM-based fact extraction/merge
- Storage/config:
  - `MEMORY_COLLECTION_NAME` (default: `memories`)
  - `MEMORY_HISTORY_DB_PATH` (optional override; default in user home)
- Providers used when enabled:
  - Vector store: Qdrant via `QDRANT_URL`/`QDRANT_API_KEY` and `VECTOR_DIM`
  - Embeddings: `EMBEDDING_PROVIDER` with Ollama (`OLLAMA_URL`, `OLLAMA_EMBED_MODEL`) or OpenAI
  - LLM for inference: `LLM_PROVIDER` with Ollama (`OLLAMA_URL`, `OLLAMA_CHAT_MODEL`) or OpenAI

The memory layer is off by default. When enabled, you can import and use `get_memory_service()` from `app/services/memory_service.py` to add/search/update/delete memories with user/agent/run scoping and history.

Debug endpoints (when enabled): `/api/memories/*` — add/search/get/update/delete/history/delete_all`.
See `docs/agent_development_guide.md` for end-to-end usage in orchestrator flows.

## File Storage and Reports API
- Upload reports using base64 payloads via `POST /api/trips/{trip_id}/reports` (fields: `filename`, `content_type`, `data`, optional `format`).
- Download stored files with `GET /api/trips/{trip_id}/reports/{report_id}/download`.
- Manage metadata with list/get/delete endpoints under the same prefix.
- Storage backend defaults to local disk (configurable via settings); keys are persisted in the new `reports` table.

## Testing & Type Checking
```bash
pytest
mypy app
```

## External Dependency Verification

Run lightweight connectivity checks for Redis, Qdrant, embeddings, and the LLM
provider before developing new agent flows:

```bash
python scripts/check_dependencies.py
```

Use `--json` to emit machine-readable output that can be plugged into CI jobs:

```bash
python scripts/check_dependencies.py --json
```

## Project Structure
```
app/
  api/
    routes/
      health.py, auth.py, agent.py
    deps.py
  db/
    models.py, session.py
  core/
    config.py, logging.py
  middleware/
    errors.py
  schemas/
    common.py
  agents/
    orchestrator.py
  ... (services/providers/cache/storage/llm)
```

## Notes
- DB schema is created on app startup for development.
- Auth and agent modules are stubs, ready for full implementation.
- Streaming protocol and agent integration guidelines are documented in `docs/agent_development_guide.md`.
- Logging uses JSON-like output suitable for containers.
