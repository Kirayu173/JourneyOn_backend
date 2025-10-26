# JourneyOn Backend (FastAPI Skeleton)

A modular FastAPI project skeleton aligned with the design docs in `_design/`. It includes SQLAlchemy models, health endpoint, auth and agent stubs, error handling middleware, request validation, Docker setup, logging, and testing.

## Features
- Modular `app/` layout (api, db, core, middleware, schemas, agents, services, providers, llm, cache, storage)
- SQLAlchemy ORM models consistent with design docs
- Health endpoint `/api/health` (DB/Redis/Qdrant checks)
- Auth stub: `/api/auth/register`, `/api/auth/login`
- Agent orchestrator stub: `/api/agent/chat` for JSON responses
- Streaming endpoints for incremental replies: `/api/agent/chat/stream` (SSE) and `/api/agent/ws/chat` (WebSocket)
- Error handling middleware returning uniform envelope `{code, msg, data}`
- Typed settings (`pydantic-settings`) and structured logging
- Mypy config and pytest tests

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

## Testing & Type Checking
```bash
pytest
mypy app
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
