from __future__ import annotations

from typing import Dict, List

from app.agents.base_agent import AgentContext, AgentRunResult
from app.agents.on_agent.graph import OnTripAgentGraph
from app.agents.post_agent.graph import PostTripAgentGraph
from app.agents.pre_agent.graph import PreTripAgentGraph
from app.db.models import TripStageEnum


class AgentOrchestratorGraph:
    """Linear LangGraph-style orchestrator for JourneyOn agents."""

    stage_order: List[TripStageEnum] = [
        TripStageEnum.pre,
        TripStageEnum.on,
        TripStageEnum.post,
    ]

    def __init__(self) -> None:
        self._nodes: Dict[TripStageEnum, object] = {
            TripStageEnum.pre: PreTripAgentGraph(),
            TripStageEnum.on: OnTripAgentGraph(),
            TripStageEnum.post: PostTripAgentGraph(),
        }

    async def run(self, context: AgentContext) -> List[AgentRunResult]:
        """Execute the orchestrator and return a list of stage results."""

        if context.stage not in self._nodes:
            raise ValueError(f"unknown_stage:{context.stage}")

        start_index = self.stage_order.index(context.stage)
        index = start_index
        results: List[AgentRunResult] = []

        while index < len(self.stage_order):
            stage = self.stage_order[index]
            node = self._nodes[stage]
            context.stage = stage
            result = await node.run(context)
            results.append(result)

            if not result.should_proceed:
                break

            next_stage = result.next_stage
            if next_stage is None:
                break

            try:
                next_index = self.stage_order.index(next_stage)
            except ValueError:
                break

            if next_index <= index:
                break

            index = next_index
            context.advance_stage = False

        return results
