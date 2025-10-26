# Agent Development Guide

This document explains how to extend the JourneyOn backend from the current pre‑agent baseline to a production agent runtime. It covers architecture assumptions, streaming interfaces, data structures, and development guidelines so that agent logic can be implemented consistently.

## 1. Baseline Architecture Snapshot

- **Framework**: FastAPI with SQLAlchemy ORM, Pydantic v2 schemas, pytest test-suite.
- **Services**: Trips, tasks, itinerary items, conversations, knowledge base entries, user tags, and audit logs are already functional with authentication and ownership checks.
- **Agent Stub**: `app/agents/orchestrator.py` returns deterministic suggestions using mock data providers. No LLM, tool execution, or memory layers are wired yet.
- **Streaming Support**: `/api/agent/chat/stream` (HTTP SSE) and `/api/agent/ws/chat` (WebSocket) expose a consistent event protocol for incremental agent responses.
- **Persistence**: User messages are stored via `save_message`. Assistant and tool messages are not yet persisted; this will be part of the agent implementation phase.

## 2. Agent Data Structures

All agent-related payloads are defined in `app/schemas/agent_schemas.py` to guarantee forward compatibility.

| Model | Key Fields | Description |
| --- | --- | --- |
| `AgentMessageRole` | `user`, `assistant`, `tool`, `system` | Enumerates logical speaker roles. |
| `AgentToolCall` | `id`, `name`, `input` | Represents a tool invocation request emitted by the agent. |
| `AgentToolResult` | `id`, `output`, `status`, `error` | Reports tool execution outcome. |
| `AgentMessage` | `role`, `content`, `meta`, `tool_calls` | Structured message used for persistence and streaming. |
| `AgentEventType` | `run_started`, `message`, `tool_call`, `tool_result`, `run_completed`, `error`, `heartbeat` | Declares all stream event types. |
| `AgentEvent` | `sequence`, `event`, `timestamp`, `message`, `tool_call`, `tool_result`, `data` | Canonical streaming envelope. |

### Sequencing and Versioning

- `sequence`: monotonically increasing integer starting at 0 within a single run.
- `schema_version`: currently `"1.0"`; bump this value if payload contracts evolve.
- Timestamps are stored in UTC with timezone awareness.

### Recommended Extensions

- Add `run_id`, `parent_id`, or `trace_id` fields to relate events in long-running workflows.
- Persist `AgentEvent` records in a dedicated table for audit, replay, and debugging once the agent move beyond the stub.

## 3. Streaming Endpoints

### 3.1 Server-Sent Events (SSE)

- **Endpoint**: `POST /api/agent/chat/stream`
- **Request Body**: Same as `/api/agent/chat` (`trip_id`, `stage`, `message`, optional `client_ctx`).
- **Authentication**: Bearer token via `Authorization` header (handled by `OAuth2PasswordBearer`).
- **Response**: `text/event-stream` where each event serialises an `AgentEvent` object.

Example event (line breaks per SSE spec):

```
event: message
id: 3
data: {"sequence":3,"event":"message","timestamp":"2025-10-26T10:34:11.012345+00:00","message":{"role":"assistant","content":"...","meta":{"source":"orchestrator_stub"}}, "data":{}}

```

### 3.2 WebSocket Channel

- **Endpoint**: `GET /api/agent/ws/chat?token=<JWT>` or provide `Authorization: Bearer <JWT>` header.
- **Client Flow**:
  1. Connect and wait for acceptance.
  2. Send a JSON payload matching `ChatRequest` once per conversation run.
  3. Consume JSON frames, each mapping to `AgentEvent`.
  4. Connection closes with code `1000` when `run_completed` is emitted.
- **Error Handling**: Invalid tokens close with code `4401`. Malformed payloads close with `4400`.

### Implementation Notes

- Both endpoints reuse `StreamingAgentSession` to guarantee identical event ordering.
- When moving to real agents, inject your orchestrator (LangGraph workflow, pipeline runner, etc.) into `StreamingAgentSession` and yield events as they complete.
- Keep the SSE/WebSocket contract backward compatible to avoid breaking the existing mobile client.

## 4. Runtime Sequence Overview

1. **Persist user message** via `save_message` (already implemented).
2. **Yield `run_started` event** with generated `run_id` and stage.
3. **Echo user message** (optional but useful downstream).
4. **Execute agent logic**:
   - produce intermediate `message` events for reasoning status.
   - emit `tool_call` and `tool_result` events for each tool invocation.
   - final assistant reply as `message` event with `role=assistant`.
5. **Conclude with `run_completed`** (include counts, metrics, or summary data in `data`).
6. **Persist assistant/tool messages** (to be added when agent is feature-complete).

## 5. Technical Roadmap for Agent Logic

### 5.1 Core Components

| Component | Suggested Implementation | Notes |
| --- | --- | --- |
| Orchestration | LangGraph / LangChain workflows wrapped in a service | Replace stub orchestrator with graph-runner. |
| LLM Access | OpenAI, Azure OpenAI, DeepSeek, or local models via provider abstraction | Encapsulate in `app/llm/` with retry/backoff. |
| Tool Layer | Implement real connectors in `app/providers/` (flights, hotels, weather, POI, calendar, etc.) | Record tool schemas for deterministic validation. |
| Memory & Retrieval | Embed conversations/KB entries and index in Qdrant (container already configured) | Add asynchronous pipelines for ingestion and query. |
| Persistence | Create `agent_runs`, `agent_events`, `agent_messages` tables with Alembic migrations | Ensure referential integrity to `trips` and `conversations`. |
| Observability | OpenTelemetry traces, structured logs (already set up) and Prometheus metrics | Attach `run_id`/`request_id` to logs and traces. |

### 5.2 Suggested Development Steps

1. **Data Model Migration**: Add Alembic migrations for new tables (runs/events) and link to existing conversation records.
2. **Provider Abstraction**: Define tool registry with structured schemas and central execution pipeline (sync/async).
3. **Orchestrator Replacement**: Build LangGraph plan with state store, hooking into streaming session to forward events.
4. **Message Persistence**: Extend `conversation_service.save_message` to handle assistant and tool roles.
5. **RAG Integration**: Add embedding pipeline (OpenAI text-embedding-3-large or local alternative) and retrieval logic.
6. **Testing**: Create golden-path tests with deterministic adapters, plus property-based tests for tool invocation sequences.
7. **Configuration**: Introduce environment separation (DEV/STAGE/PROD) for API keys and model selection.

## 6. Stream Event Contract

| Event Type | Required Fields | Usage |
| --- | --- | --- |
| `run_started` | `data.run_id`, `data.stage` | Announce a new run, allow clients to show loading states. |
| `message` | `message.role`, `message.content` | Send user/assistant/system messages (multi-part allowed). |
| `tool_call` | `tool_call.id`, `tool_call.name`, `tool_call.input` | Request client/tool subsystem invocation. |
| `tool_result` | `tool_result.id`, `tool_result.output`, `tool_result.status` | Return outcome of tool invocation. |
| `error` | `data.error_code`, `data.error_message` | Optional; if emitted, follow with `run_completed`. |
| `run_completed` | `data.run_id`, optional metrics | Signal end of run; close SSE stream / WebSocket gracefully. |

Maintain strict sequencing to support UI playback and audit logs. Never skip `run_completed`, even on errors.

## 7. API Interaction Checklist

- **Authentication**: All agent endpoints require JWT tokens; follow `/api/auth/login` and include `Authorization: Bearer <token>`.
- **Trip Ownership**: `StreamingAgentSession` validates trip ownership via `get_trip`. Preserve this guard in future implementations.
- **Client Context**: `client_ctx` is stored but currently unused. Expect to pass device metadata, UI version, or lat/long for contextual responses.
- **Schema Compatibility**: Exposed JSON uses camel-case keys when consumed by clients? (currently snake_case). Decide and document a stable standard before GA.
- **Error Handling**: Always surface machine-readable `code` and human-readable `msg` in REST responses; reuse existing `Envelope`.

## 8. Development Tips

- **Keep ASCII in code**: The repository defaults to ASCII to avoid encoding issues. Use locale-specific copy in documentation only.
- **Use type hints aggressively**: Mypy runs on CI; maintain `disallow_untyped_defs`.
- **Test Strategy**: Extend `tests/test_phase_three_agent.py` with new scenarios (tool failure, retry, streaming partial responses).
- **Streaming Backpressure**: For long-running runs, consider `heartbeat` events every N seconds to keep connections alive.
- **Idempotence**: When implementing retries (e.g., LLM or tool), ensure sequence numbers remain monotonic and do not duplicate previously emitted events.

## 9. Next Steps Tracker

1. **Alembic Migration**: Introduce migrations for agent run tables and update `init_db`.
2. **Observability**: Add counters (successful runs, tool latency) and logs referencing `run_id`.
3. **LLM Integration**: Build `LLMClient` abstraction with configurable provider and streaming token handler.
4. **Tool Sandbox**: Implement a registry (`app/providers/registry.py`) to allow dynamic tool enablement per stage/trip.
5. **Replay & Debug UI**: Optional but recommended — provide an internal admin endpoint to re-stream stored events.

With these foundations, the team can move from the stub orchestrator to a fully fledged agent system while sharing a consistent protocol across HTTP SSE, WebSocket, and future gRPC or message bus integrations.
