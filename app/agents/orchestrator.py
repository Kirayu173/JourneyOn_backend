from __future__ import annotations

import logging
import uuid
from typing import Any, AsyncIterator, Dict

from sqlalchemy.orm import Session

from app.agents.base_agent import AgentContext
from app.agents.graph import AgentOrchestratorGraph
from app.db.models import Trip, TripStageEnum
from app.llm import StreamChunk, get_llm_client as _get_llm_client
from app.services.stage_service import StageAdvanceResult, advance_stage
from app.services.trip_service import get_trip

logger = logging.getLogger(__name__)

# Backwards compatibility hook for existing tests that patch get_llm_client
get_llm_client = _get_llm_client


class Orchestrator:
    """JourneyOn LangGraph orchestrator managing stage transitions."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.graph = AgentOrchestratorGraph()

    def _load_trip(self, trip_id: int, user_id: int) -> Trip:
        trip = get_trip(self.db, trip_id, user_id)
        if trip is None:
            raise PermissionError("trip_not_found")
        return trip

    @staticmethod
    def _should_advance(message: str, stage: TripStageEnum) -> bool:
        if stage == TripStageEnum.post:
            return False
        normalized = message.strip().lower()
        if not normalized:
            return False
        chinese_keywords = ["确认", "下一阶段", "进入下一阶段", "完成阶段"]
        english_keywords = ["go next", "next stage", "proceed"]
        if any(keyword in message for keyword in chinese_keywords):
            return True
        if any(keyword in normalized for keyword in english_keywords):
            return True
        return normalized in {"yes", "ok", "next", "y"}

    async def chat(
        self,
        *,
        trip_id: int,
        stage: str,
        message: str,
        user_id: int,
        client_ctx: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        run_id = uuid.uuid4().hex
        try:
            stage_enum = TripStageEnum(stage)
        except ValueError:
            return {
                "reply": "未知的行程阶段。",
                "run_id": run_id,
                "error": "invalid_stage",
                "tools": [],
                "tool_results": {},
                "stage_history": [],
                "transition": None,
                "source": "graph",
            }

        try:
            trip = self._load_trip(trip_id, user_id)
        except PermissionError:
            return {
                "reply": "未找到对应行程或没有访问权限。",
                "run_id": run_id,
                "error": "trip_not_found",
                "tools": [],
                "tool_results": {},
                "stage_history": [],
                "transition": None,
                "source": "graph",
            }

        advance_requested = self._should_advance(message, stage_enum)
        context = AgentContext(
            trip_id=trip_id,
            user_id=user_id,
            stage=stage_enum,
            message=message,
            client_ctx=client_ctx or {},
            advance_stage=advance_requested,
        )

        try:
            stage_results = await self.graph.run(context)
        except ValueError as exc:
            logger.warning("graph_run_failed", exc_info=True)
            return {
                "reply": "智能体编排异常，稍后再试。",
                "run_id": run_id,
                "error": str(exc),
                "tools": [],
                "tool_results": {},
                "stage_history": [],
                "transition": None,
                "source": "graph",
            }

        if not stage_results:
            return {
                "reply": "未能生成有效的阶段结果。",
                "run_id": run_id,
                "error": "empty_result",
                "tools": [],
                "tool_results": {},
                "stage_history": [],
                "transition": None,
                "source": "graph",
            }

        transition: StageAdvanceResult | None = None
        final_stage = stage_results[-1].stage
        if final_stage != stage_enum:
            try:
                transition = advance_stage(
                    self.db,
                    trip_id=trip_id,
                    user_id=user_id,
                    to_stage=final_stage,
                )
            except ValueError as exc:
                logger.warning("advance_stage_failed", extra={"trip_id": trip_id, "error": str(exc)})
        stage_history = [result.to_dict() for result in stage_results]

        reply = stage_results[-1].message
        return {
            "reply": reply,
            "run_id": run_id,
            "tools": [],
            "tool_results": {},
            "stage_history": stage_history,
            "transition": transition.to_dict() if transition else None,
            "trip": {
                "id": trip.id,
                "current_stage": (transition.to_stage.value if transition and transition.updated else trip.current_stage.value),
                "destination": getattr(trip, "destination", None),
            },
            "source": "graph",
        }

    async def stream(
        self,
        *,
        trip_id: int,
        stage: str,
        message: str,
        user_id: int,
        client_ctx: Dict[str, Any] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        result = await self.chat(
            trip_id=trip_id,
            stage=stage,
            message=message,
            user_id=user_id,
            client_ctx=client_ctx,
        )
        reply = result.get("reply", "")
        run_id = result.get("run_id", uuid.uuid4().hex)
        if reply:
            yield StreamChunk(delta=reply, run_id=run_id, done=False)
        usage: Dict[str, Any] | None = None
        if "stage_history" in result or "transition" in result or "trip" in result:
            usage = {
                "stage_history": result.get("stage_history", []),
                "transition": result.get("transition"),
                "trip": result.get("trip"),
            }
        yield StreamChunk(delta="", run_id=run_id, done=True, usage=usage)
