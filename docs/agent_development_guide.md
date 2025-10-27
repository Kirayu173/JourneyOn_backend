# Agent Development Guide

This guide explains how to extend JourneyOn’s agent stack, integrate the new mem0-based memory layer, and debug memory during development.

## Overview
- Orchestrator: `app/agents/orchestrator.py` runs a linear graph across stages (pre → on → post).
- Conversations are persisted via `app/services/conversation_service.py` and exposed in `/api/trips/{trip_id}/conversations`.
- Long-term memory is provided by `mem0` and wrapped by `app/services/memory_service.py`.
- Memory is feature-gated and disabled by default.

## Enabling Memory
Set the following environment variables (e.g., in `.env`):

- `MEMORY_ENABLED=true` to turn on the memory layer.
- `MEMORY_INFER=false` to start with passive ingestion (no LLM). Switch to `true` to enable fact extraction and merge.
- `MEMORY_COLLECTION_NAME=memories` (default).
- Optional `MEMORY_HISTORY_DB_PATH=/abs/path/history.db` for the change history store.

Providers used by memory when enabled:
- Vector store: Qdrant via `QDRANT_URL`, `QDRANT_API_KEY`, `VECTOR_DIM`.
- Embeddings: `EMBEDDING_PROVIDER` (Ollama via `OLLAMA_URL` + `OLLAMA_EMBED_MODEL`, or OpenAI via `OPENAI_*`).
- LLM: `LLM_PROVIDER` (Ollama via `OLLAMA_URL` + `OLLAMA_CHAT_MODEL`, or OpenAI via `OPENAI_*`).

## Using Memory in Code
Import the lazy wrapper:

```python
from app.services.memory_service import get_memory_service

svc = get_memory_service()
svc.add_messages(
    messages=[{"role": "user", "content": "I enjoy hiking"}],
    user_id=str(user_id),
    metadata={"trip_id": trip_id, "stage": stage},
    infer=False,  # start with passive ingestion
)

mems = svc.search(
    query="hiking",
    top_k=10,
    filters={"user_id": str(user_id), "trip_id": trip_id},
)
```

Recommended metadata and filters:
- Session scope: always include `user_id`; optionally `agent_id` and `run_id`.
- Domain scope: `trip_id`, `stage`, and `source` if from tools.
- Actor context: `role` and `actor_id` (message name) when available.

## Conversation Ingestion (Optional)
To store messages as memories when the user chats (passive mode):
1. Enable memory via env.
2. In `app/api/routes/agent.py` after calling `save_message`, invoke:

```python
from app.services.memory_service import get_memory_service

svc = get_memory_service()
svc.add_messages(
    messages=[{"role": "user", "content": req.message}],
    user_id=str(current_user.id),
    metadata={"trip_id": req.trip_id, "stage": req.stage},
    infer=False,
)
```

## Retrieval in Orchestrator (Optional)
Fetch top memories to enrich prompts:

```python
from app.services.memory_service import get_memory_service

svc = get_memory_service()
context_mems = []
if getattr(settings, "MEMORY_ENABLED", False):
    context_mems = svc.search(
        query=message,
        top_k=8,
        filters={"user_id": str(user_id), "trip_id": trip_id},
    )
    # Add `context_mems` into your prompt builder
```

## Debugging Endpoints
When enabled, the following endpoints help inspect and mutate memory data:

- `POST /api/memories/add` — Add messages as memories.
- `POST /api/memories/search` — Search memories by query + filters.
- `GET /api/memories/search` — Same as above with query params.
- `GET /api/memories/{memory_id}` — Fetch a single memory.
- `PUT /api/memories/{memory_id}` — Update memory text.
- `DELETE /api/memories/{memory_id}` — Delete by ID.
- `GET /api/memories/{memory_id}/history` — Change history.
- `POST /api/memories/delete_all` — Bulk delete by filters (guarded by required scope in service).

Example search request:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -X POST http://localhost:8000/api/memories/search \
  -d '{
    "query":"hiking", "top_k": 10,
    "filters": {"user_id": "123", "trip_id": 456}
  }'
```

## Testing
- Memory is disabled by default; the existing test suite should pass unchanged.
- With memory enabled, ensure Qdrant and the embedding/LLM backends are reachable.
- Start with `MEMORY_INFER=false` to validate ingestion + retrieval paths without an LLM dependency, then enable `MEMORY_INFER=true` to test fact extraction and updates.

