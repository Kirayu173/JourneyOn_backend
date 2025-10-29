from __future__ import annotations

import asyncio
from typing import Any, Dict

from pydantic import BaseModel, Field

from app.providers.tools.standard import StandardStructuredTool
from app.services.memory_service import MemoryService, get_memory_service


class StageContextSyncInput(BaseModel):
    """用于阶段上下文同步的输入模型。"""

    operation: str = Field(
        description="执行 sync（写入）或 load（读取）操作",
        pattern=r"^(sync|load)$",
    )
    trip_id: int = Field(description="行程ID")
    user_id: int = Field(description="用户ID")
    stage_from: str | None = Field(default=None, description="来源阶段标识")
    stage_to: str | None = Field(default=None, description="目标阶段标识")
    facts: list[str] | None = Field(
        default=None, description="需要同步的事实或摘要列表"
    )
    tool_outputs: dict[str, Any] | None = Field(
        default=None, description="需要跨阶段共享的工具输出"
    )
    run_id: str | None = Field(default=None, description="运行ID")
    agent_id: str | None = Field(default=None, description="调用方Agent")
    limit: int = Field(default=3, ge=1, description="load操作时返回的最大条目")


class TripContextSyncTool(StandardStructuredTool):
    """阶段切换时同步行程上下文到记忆层或从记忆层读取。"""

    name = "journeyon_trip_context_sync"
    description = "在多阶段流程中同步行程上下文的记忆工具。"
    args_schema = StageContextSyncInput

    def __init__(self, memory_service: MemoryService | None = None) -> None:
        self._memory_service = memory_service or get_memory_service()
        super().__init__(coroutine=self._acall)

    async def _sync_context(self, params: StageContextSyncInput) -> Dict[str, Any]:
        if not params.stage_from or not params.stage_to:
            raise ValueError("stage_from_and_stage_to_required")
        if not (params.facts or params.tool_outputs):
            raise ValueError("facts_or_tool_outputs_required")

        metadata = {
            "trip_id": params.trip_id,
            "user_id": str(params.user_id),
            "stage_from": params.stage_from,
            "stage_to": params.stage_to,
            "scene": "stage_sync",
            "agent_id": params.agent_id,
            "run_id": params.run_id,
        }

        summary_lines: list[str] = []
        summary_lines.append(f"transition={params.stage_from}->{params.stage_to}")
        for fact in params.facts or []:
            summary_lines.append(str(fact))
        if params.tool_outputs:
            summary_lines.append(f"tool_outputs={params.tool_outputs}")
        message = {
            "role": "system",
            "content": "stage_context::" + " | ".join(summary_lines),
        }

        # 先尝试检索已有快照以便覆盖更新
        existing = await asyncio.to_thread(
            self._memory_service.search,
            f"{params.stage_from}->{params.stage_to}",
            top_k=1,
            filters={
                "trip_id": params.trip_id,
                "scene": "stage_sync",
                "stage_to": params.stage_to,
            },
            threshold=None,
        )

        if existing:
            memory_id = existing[0].get("id")
            if memory_id:
                updated = await asyncio.to_thread(
                    self._memory_service.replace_memory,
                    memory_id,
                    [message],
                )
                if updated is not None:
                    return updated

        result = await asyncio.to_thread(
            self._memory_service.add_messages,
            [message],
            user_id=str(params.user_id),
            agent_id=params.agent_id,
            run_id=params.run_id,
            metadata=metadata,
        )
        if result is None:
            raise RuntimeError("memory_write_failed")
        return result

    async def _load_context(self, params: StageContextSyncInput) -> Dict[str, Any]:
        filters = {
            "trip_id": params.trip_id,
            "scene": "stage_sync",
        }
        if params.stage_to:
            filters["stage_to"] = params.stage_to
        results = await asyncio.to_thread(
            self._memory_service.search,
            "stage_context",
            top_k=params.limit,
            filters=filters,
            threshold=None,
        )
        return {"items": results}

    async def _acall(self, **kwargs: Any) -> Dict[str, Any]:
        params = StageContextSyncInput(**kwargs)
        if not self._memory_service.is_enabled():
            return {
                "operation": params.operation,
                "status": "disabled",
                "payload": {},
            }

        try:
            if params.operation == "sync":
                payload = await self._sync_context(params)
            else:
                payload = await self._load_context(params)
        except ValueError as exc:
            return {
                "operation": params.operation,
                "status": "fallback",
                "payload": {"error": str(exc)},
            }

        status = "success"
        if params.operation == "load" and not payload.get("items"):
            status = "fallback"

        return {
            "operation": params.operation,
            "status": status,
            "payload": payload,
        }


__all__ = ["TripContextSyncTool", "StageContextSyncInput"]
