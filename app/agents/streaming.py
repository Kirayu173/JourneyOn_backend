from __future__ import annotations

import asyncio
import uuid
from typing import Any, AsyncGenerator

from sqlalchemy.orm import Session

from app.agents.orchestrator import Orchestrator
from app.schemas.agent_schemas import (
    AgentEvent,
    AgentEventType,
    AgentMessage,
    AgentMessageRole,
    AgentToolCall,
    AgentToolResult,
)


class StreamingAgentSession:
    """Produce structured streaming events for agent conversations."""

    def __init__(self, db: Session):
        self.db = db
        self.orchestrator = Orchestrator(db)

    async def run(
        self,
        *,
        trip_id: int,
        stage: str,
        message_text: str,
        user_id: int,
    ) -> AsyncGenerator[AgentEvent, None]:
        sequence = 0
        run_id = uuid.uuid4().hex

        def _next_sequence() -> int:
            nonlocal sequence
            seq = sequence
            sequence += 1
            return seq

        yield AgentEvent(
            sequence=_next_sequence(),
            event=AgentEventType.RUN_STARTED,
            data={"run_id": run_id, "stage": stage},
        )
        await asyncio.sleep(0)

        # Emit echo of user message for downstream consumers
        yield AgentEvent(
            sequence=_next_sequence(),
            event=AgentEventType.MESSAGE,
            message=AgentMessage(role=AgentMessageRole.USER, content=message_text),
        )
        await asyncio.sleep(0)

        reply = self.orchestrator.handle_message(
            trip_id=trip_id,
            stage=stage,
            message=message_text,
            user_id=user_id,
        )

        tool_inputs: dict[str, Any] = reply.get("tool_inputs", {})

        for tool_name in reply.get("tools", []):
            tool_id = uuid.uuid4().hex
            tool_call = AgentToolCall(id=tool_id, name=tool_name, input=tool_inputs.get(tool_name, {}))
            yield AgentEvent(
                sequence=_next_sequence(),
                event=AgentEventType.TOOL_CALL,
                tool_call=tool_call,
            )
            await asyncio.sleep(0)

            result_payload = reply.get("tool_results", {}).get(tool_name)
            if result_payload is not None:
                tool_result = AgentToolResult(id=tool_id, output={"result": result_payload})
                yield AgentEvent(
                    sequence=_next_sequence(),
                    event=AgentEventType.TOOL_RESULT,
                    tool_result=tool_result,
                )
                await asyncio.sleep(0)

        assistant_meta = {
            "source": reply.get("source"),
            "task_suggestions": reply.get("task_suggestions", []),
            "itinerary_suggestions": reply.get("itinerary_suggestions", []),
        }

        yield AgentEvent(
            sequence=_next_sequence(),
            event=AgentEventType.MESSAGE,
            message=AgentMessage(
                role=AgentMessageRole.ASSISTANT,
                content=reply.get("reply", ""),
                meta=assistant_meta,
            ),
        )
        await asyncio.sleep(0)

        yield AgentEvent(
            sequence=_next_sequence(),
            event=AgentEventType.RUN_COMPLETED,
            data={
                "run_id": run_id,
                "tool_count": len(reply.get("tools", [])),
            },
        )

