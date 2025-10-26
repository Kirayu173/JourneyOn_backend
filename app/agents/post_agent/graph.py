from __future__ import annotations

from app.agents.base_agent import AgentContext, AgentRunResult, BaseAgent
from app.db.models import TripStageEnum


class PostTripAgentGraph(BaseAgent):
    """Placeholder implementation for the post-trip stage."""

    name = "post_trip_agent"
    description = "Summarises experiences and collects feedback after the trip."
    stage = TripStageEnum.post

    async def run(self, context: AgentContext) -> AgentRunResult:
        notes = {
            "stage": self.stage.value,
            "requested_message": context.message,
            "advance_stage": context.advance_stage,
        }
        message = "📒 行后总结完成，欢迎随时发起新的旅行计划。"
        return AgentRunResult(
            stage=self.stage,
            message=message,
            status="completed",
            should_proceed=False,
            next_stage=None,
            data=notes,
        )
