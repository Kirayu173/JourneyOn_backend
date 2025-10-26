from __future__ import annotations

from app.agents.base_agent import AgentContext, AgentRunResult, BaseAgent
from app.db.models import TripStageEnum


class PreTripAgentGraph(BaseAgent):
    """Placeholder implementation for the pre-trip stage."""

    name = "pre_trip_agent"
    description = "Collects requirements and prepares travellers before departure."
    stage = TripStageEnum.pre

    async def run(self, context: AgentContext) -> AgentRunResult:
        notes = {
            "stage": self.stage.value,
            "requested_message": context.message,
            "advance_stage": context.advance_stage,
        }
        status = "ready_to_proceed" if context.advance_stage else "awaiting_confirmation"
        message = (
            "🧳 行前准备完成。请确认是否进入行中阶段。"
            if context.advance_stage
            else "🧳 这是行前筹备建议。确认后可进入行中阶段。"
        )
        return AgentRunResult(
            stage=self.stage,
            message=message,
            status=status,
            should_proceed=context.advance_stage,
            next_stage=TripStageEnum.on,
            data=notes,
        )
