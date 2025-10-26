from __future__ import annotations

import json
import logging
import uuid
from typing import Any, AsyncIterator, Dict, List, cast

from sqlalchemy.orm import Session

from app.llm import ChatResponse, LLMError, StreamChunk, get_llm_client
from app.services.trip_service import get_trip

logger = logging.getLogger(__name__)


class Orchestrator:
    """Agent orchestrator stub for Phase Three.

    Coordinates simple keyword-based suggestions without LLM, validates
    trip ownership via DB session.
    """

    def __init__(self, db: Session):
        self.db = db

    async def _build_messages(self, trip_id: int, stage: str, message: str, user_id: int) -> List[Dict[str, Any]]:
        trip = get_trip(self.db, trip_id, user_id)
        if trip is None:
            raise PermissionError("trip_not_found")

        trip_meta = {
            "destination": getattr(trip, "destination", "unknown"),
            "budget": getattr(trip, "budget", None),
            "start_date": getattr(trip, "start_date", None),
            "end_date": getattr(trip, "end_date", None),
        }
        system_prompt = (
            "你是 JourneyOn 的旅行规划智能体，需要根据用户行程阶段提供帮助。"
            "请结合旅行目的地、时间和预算，回复中文并给出可执行建议。"
        )
        context = f"行程信息: {json_safe(trip_meta)}\n阶段: {stage}"
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{context}\n用户消息: {message}"},
        ]

    async def chat(self, trip_id: int, stage: str, message: str, user_id: int) -> Dict[str, Any]:
        run_id = uuid.uuid4().hex
        try:
            messages = await self._build_messages(trip_id, stage, message, user_id)
        except PermissionError:
            return {
                "reply": "未找到对应行程或没有访问权限。",
                "run_id": run_id,
                "tools": [],
                "tool_results": {},
                "task_suggestions": [],
                "itinerary_suggestions": [],
                "source": "llm",
            }

        client = await get_llm_client()
        try:
            response: ChatResponse = await client.chat(messages, run_id=run_id)  # type: ignore[arg-type]
        except LLMError as exc:
            logger.exception("llm_chat_failed", extra={"run_id": run_id, "code": exc.status_code})
            return {
                "reply": "智能体服务暂时不可用，请稍后重试。",
                "run_id": run_id,
                "error": exc.args[0],
                "tools": [],
                "tool_results": {},
                "task_suggestions": [],
                "itinerary_suggestions": [],
                "source": "llm",
            }

        return {
            "reply": response.content,
            "run_id": run_id,
            "tools": [],
            "tool_results": {},
            "task_suggestions": [],
            "itinerary_suggestions": [],
            "source": "llm",
            "usage": response.usage or {},
        }

    async def stream(
        self,
        trip_id: int,
        stage: str,
        message: str,
        user_id: int,
    ) -> AsyncIterator[StreamChunk]:
        run_id = uuid.uuid4().hex
        try:
            messages = await self._build_messages(trip_id, stage, message, user_id)
        except PermissionError:
            yield StreamChunk(delta="未找到行程", run_id=run_id, done=True)
            return

        client = await get_llm_client()
        try:
            stream = await client.chat(messages, stream=True, run_id=run_id)  # type: ignore[arg-type]
        except LLMError as exc:
            logger.exception("llm_stream_failed", extra={"run_id": run_id, "code": exc.status_code})
            yield StreamChunk(delta="智能体暂不可用。", run_id=run_id, done=True)
            return

        stream_iter = cast(AsyncIterator[StreamChunk], stream)
        async for chunk in stream_iter:
            yield chunk


def json_safe(payload: Any) -> str:
    try:
        return json.dumps(payload, ensure_ascii=False)
    except Exception:
        return str(payload)
