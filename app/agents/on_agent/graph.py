from __future__ import annotations

from app.agents.base_agent import AgentContext, AgentRunResult, BaseAgent
from app.db.models import TripStageEnum


class OnTripAgentGraph(BaseAgent):
    """Placeholder implementation for the on-trip stage."""

    name = "on_trip_agent"
    description = "Guides travellers while the trip is in progress."
    stage = TripStageEnum.on

    async def run(self, context: AgentContext) -> AgentRunResult:
        notes = {
            "stage": self.stage.value,
            "requested_message": context.message,
            "advance_stage": context.advance_stage,
        }
        status = "ready_to_proceed" if context.advance_stage else "in_progress"
        message = (
            "🧭 行程建议已生成，确认后进入行后总结阶段。"
            if context.advance_stage
            else "🧭 这是行中阶段建议，可在完成后确认进入下一阶段。"
        )
        return AgentRunResult(
            stage=self.stage,
            message=message,
            status=status,
            should_proceed=context.advance_stage,
            next_stage=TripStageEnum.post,
            data=notes,
        )
