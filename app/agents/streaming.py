from __future__ import annotations

import uuid
from typing import AsyncGenerator, List

from sqlalchemy.orm import Session

from app.agents.orchestrator import Orchestrator
from app.schemas.agent_schemas import AgentEvent, AgentEventType, AgentMessage, AgentMessageRole


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

        # Emit echo of user message for downstream consumers
        yield AgentEvent(
            sequence=_next_sequence(),
            event=AgentEventType.MESSAGE,
            message=AgentMessage(role=AgentMessageRole.USER, content=message_text),
        )
        stream = self.orchestrator.stream(
            trip_id=trip_id,
            stage=stage,
            message=message_text,
            user_id=user_id,
        )

        full_chunks: List[str] = []
        async for chunk in stream:
            if chunk.delta:
                full_chunks.append(chunk.delta)
                yield AgentEvent(
                    sequence=_next_sequence(),
                    event=AgentEventType.MESSAGE,
                    message=AgentMessage(
                        role=AgentMessageRole.ASSISTANT,
                        content=chunk.delta,
                        meta={"delta": True, "run_id": chunk.run_id, "usage": chunk.usage or {}},
                    ),
                )
            if chunk.done:
                break

        final_message = "".join(full_chunks)
        yield AgentEvent(
            sequence=_next_sequence(),
            event=AgentEventType.MESSAGE,
            message=AgentMessage(
                role=AgentMessageRole.ASSISTANT,
                content=final_message,
                meta={"delta": False, "run_id": run_id},
            ),
        )

        yield AgentEvent(
            sequence=_next_sequence(),
            event=AgentEventType.RUN_COMPLETED,
            data={
                "run_id": run_id,
                "tool_count": 0,
            },
        )

