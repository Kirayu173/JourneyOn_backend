from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class AgentSchemaVersion(str, Enum):
    """Agent payload schema version for forwards compatibility."""

    V1 = "1.0"


class AgentMessageRole(str, Enum):
    """Logical role for messages exchanged with the agent runtime."""

    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    SYSTEM = "system"


class AgentToolCall(BaseModel):
    """Description of a tool invocation request issued by the agent."""

    id: str = Field(..., description="Opaque identifier for the tool invocation")
    name: str = Field(..., description="Tool name registered with the orchestrator")
    input: dict[str, Any] = Field(default_factory=dict, description="Structured tool input payload")


class AgentToolResult(BaseModel):
    """Result payload emitted after a tool invocation completes."""

    id: str = Field(..., description="Tool invocation identifier matching AgentToolCall.id")
    output: dict[str, Any] = Field(default_factory=dict, description="Structured tool output payload")
    status: Literal["success", "error"] = Field("success", description="Execution outcome flag")
    error: Optional[str] = Field(None, description="Optional error message when status == 'error'")


class AgentMessage(BaseModel):
    """Structured agent message persisted into conversations or emitted in the stream."""

    role: AgentMessageRole
    content: str = Field("", description="Primary natural language content")
    meta: dict[str, Any] = Field(default_factory=dict, description="Additional metadata from the runtime")
    tool_calls: list[AgentToolCall] = Field(default_factory=list, description="Tool invocations requested by agent")


class AgentEventType(str, Enum):
    """Discriminator for streaming events."""

    RUN_STARTED = "run_started"
    MESSAGE = "message"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    RUN_COMPLETED = "run_completed"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


class AgentEvent(BaseModel):
    """Unified event envelope for SSE/WebSocket streaming."""

    sequence: int = Field(..., ge=0, description="Monotonic increasing sequence id")
    event: AgentEventType
    schema_version: AgentSchemaVersion = AgentSchemaVersion.V1
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    message: Optional[AgentMessage] = None
    tool_call: Optional[AgentToolCall] = None
    tool_result: Optional[AgentToolResult] = None
    data: dict[str, Any] = Field(default_factory=dict, description="Additional auxiliary data")

    @field_validator("timestamp", mode="before")
    def _ensure_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class AgentStreamResponse(BaseModel):
    """Final response returned once streaming is complete."""

    run_id: str
    events: list[AgentEvent]
