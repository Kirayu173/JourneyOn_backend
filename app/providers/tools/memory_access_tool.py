from __future__ import annotations

import asyncio
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field

from app.providers.tools.standard import StandardStructuredTool
from app.services.memory_service import MemoryService, get_memory_service


class MemoryToolInput(BaseModel):
    """Schema for memory access operations."""

    action: Literal["add", "search", "update", "delete", "history", "get"] = Field(
        description="要执行的记忆操作类型。"
    )
    messages: list[dict[str, Any]] | None = Field(
        default=None, description="需要写入或更新的对话消息列表。"
    )
    query: Optional[str] = Field(default=None, description="语义检索的查询字符串。")
    filters: Dict[str, Any] | None = Field(
        default=None, description="检索或批量操作使用的过滤条件。"
    )
    metadata: Dict[str, Any] | None = Field(
        default=None, description="写入记忆时附带的元数据。"
    )
    memory_id: Optional[str] = Field(default=None, description="目标记忆的唯一ID。")
    update_mode: Literal["append", "overwrite"] = Field(
        default="append", description="更新操作的模式：append 或 overwrite。"
    )
    top_k: int = Field(default=10, ge=1, description="检索时返回的最大条目数量。")
    threshold: float | None = Field(
        default=None, description="检索的相关性阈值（可选）。"
    )
    user_id: str | None = Field(default=None, description="当前用户ID，用于隔离记忆。")
    agent_id: str | None = Field(
        default=None, description="发起调用的Agent标识，用于记忆隔离。"
    )
    run_id: str | None = Field(
        default=None, description="编排层传递的运行ID，便于审计。"
    )
    trip_id: int | None = Field(default=None, description="关联的行程ID。")
    scene: str | None = Field(default=None, description="业务场景标签，如stage_sync。")


class MemoryAccessTool(StandardStructuredTool):
    """统一封装 mem0 记忆读写能力的工具。"""

    name = "journeyon_memory_access"
    description = "读取、检索、更新 JourneyOn 记忆层的统一工具。"
    args_schema = MemoryToolInput

    def __init__(self, memory_service: MemoryService | None = None) -> None:
        self._memory_service = memory_service or get_memory_service()
        super().__init__(coroutine=self._acall)

    @staticmethod
    def _merge_metadata(
        base: Dict[str, Any] | None,
        *,
        user_id: str | None,
        agent_id: str | None,
        run_id: str | None,
        trip_id: int | None,
        scene: str | None,
    ) -> Dict[str, Any]:
        payload = dict(base or {})
        if user_id is not None:
            payload.setdefault("user_id", user_id)
        if agent_id is not None:
            payload.setdefault("agent_id", agent_id)
        if run_id is not None:
            payload.setdefault("run_id", run_id)
        if trip_id is not None:
            payload.setdefault("trip_id", trip_id)
        if scene is not None:
            payload.setdefault("scene", scene)
        return payload

    async def _acall(self, **kwargs: Any) -> Dict[str, Any]:
        input_data: MemoryToolInput = MemoryToolInput(**kwargs)
        action = input_data.action
        svc = self._memory_service

        if not svc.is_enabled():
            return {"operation": action, "status": "disabled", "payload": {}}

        metadata = self._merge_metadata(
            input_data.metadata,
            user_id=input_data.user_id,
            agent_id=input_data.agent_id,
            run_id=input_data.run_id,
            trip_id=input_data.trip_id,
            scene=input_data.scene,
        )
        filters = dict(input_data.filters or {})
        if input_data.user_id is not None:
            filters.setdefault("user_id", input_data.user_id)
        if input_data.agent_id is not None:
            filters.setdefault("agent_id", input_data.agent_id)
        if input_data.run_id is not None:
            filters.setdefault("run_id", input_data.run_id)
        if input_data.trip_id is not None:
            filters.setdefault("trip_id", input_data.trip_id)
        if input_data.scene is not None:
            filters.setdefault("scene", input_data.scene)

        try:
            if action == "add":
                if not input_data.messages:
                    raise ValueError("messages_required_for_add")
                payload = await asyncio.to_thread(
                    svc.add_messages,
                    input_data.messages,
                    user_id=input_data.user_id,
                    agent_id=input_data.agent_id,
                    run_id=input_data.run_id,
                    metadata=metadata,
                )
            elif action == "search":
                if not input_data.query:
                    raise ValueError("query_required_for_search")
                payload = await asyncio.to_thread(
                    svc.search,
                    input_data.query,
                    top_k=input_data.top_k,
                    filters=filters,
                    threshold=input_data.threshold,
                )
            elif action == "update":
                if not input_data.memory_id:
                    raise ValueError("memory_id_required_for_update")
                if not input_data.messages:
                    raise ValueError("messages_required_for_update")
                if input_data.update_mode == "overwrite":
                    payload = await asyncio.to_thread(
                        svc.replace_memory, input_data.memory_id, input_data.messages
                    )
                else:
                    payload = await asyncio.to_thread(
                        svc.append_memory, input_data.memory_id, input_data.messages
                    )
            elif action == "delete":
                if not input_data.memory_id:
                    raise ValueError("memory_id_required_for_delete")
                payload = await asyncio.to_thread(svc.delete, input_data.memory_id)
            elif action == "history":
                if not input_data.memory_id:
                    raise ValueError("memory_id_required_for_history")
                payload = await asyncio.to_thread(svc.history, input_data.memory_id)
            elif action == "get":
                if not input_data.memory_id:
                    raise ValueError("memory_id_required_for_get")
                payload = await asyncio.to_thread(svc.get, input_data.memory_id)
            else:  # pragma: no cover - validation prevents
                raise ValueError(f"unsupported_action:{action}")
        except ValueError as exc:
            return {
                "operation": action,
                "status": "fallback",
                "payload": {"error": str(exc)},
            }
        except Exception as exc:  # pragma: no cover - defensive guard
            return {
                "operation": action,
                "status": "fallback",
                "payload": {"error": str(exc)},
            }

        status = "success"
        if payload is None:
            status = "fallback"
            payload = {}

        return {"operation": action, "status": status, "payload": payload}


__all__ = ["MemoryAccessTool", "MemoryToolInput"]
