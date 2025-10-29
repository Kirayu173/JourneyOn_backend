from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Sequence

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.models import UserTag
from app.db.session import SessionLocal
from app.providers.tools.standard import StandardStructuredTool
from app.services.memory_service import MemoryService, get_memory_service
from app.services import tag_service


class PreferenceTagInput(BaseModel):
    """输入参数，用于抽取并沉淀用户偏好标签。"""

    user_id: int = Field(description="当前用户ID")
    trip_id: int | None = Field(default=None, description="关联行程ID，可选")
    messages: list[dict[str, Any]] | None = Field(
        default=None, description="最新对话消息（可包含候选标签）"
    )
    query: str | None = Field(default=None, description="用于检索历史记忆的查询词")
    dry_run: bool = Field(default=False, description="是否仅返回候选而不写入数据库")
    limit: int = Field(default=5, ge=1, le=20, description="最多返回的标签数量")
    agent_id: str | None = Field(default=None, description="调用方Agent标识")
    run_id: str | None = Field(default=None, description="当前运行的唯一ID")


class PreferenceTagExtractionTool(StandardStructuredTool):
    """聚合会话与记忆，输出用户偏好标签并写入画像。"""

    name = "journeyon_preference_tag_extraction"
    description = "抽取用户偏好标签，并支持dry_run模式或批量入库。"
    args_schema = PreferenceTagInput

    def __init__(
        self,
        memory_service: MemoryService | None = None,
        session_factory: Callable[[], Session] | None = None,
    ) -> None:
        self._memory_service = memory_service or get_memory_service()
        self._session_factory = session_factory or SessionLocal
        super().__init__(coroutine=self._acall)

    @staticmethod
    def _iter_tags_from_messages(messages: Iterable[dict[str, Any]]) -> Iterable[dict[str, Any]]:
        pattern = re.compile(r"[#＃]?(?P<tag>[\w\u4e00-\u9fff]{2,})(?:[(:：](?P<weight>\d(?:\.\d+)?))?", re.UNICODE)
        for message in messages:
            if not isinstance(message, dict):
                continue
            if "tags" in message and isinstance(message["tags"], list):
                for item in message["tags"]:
                    if isinstance(item, dict) and "tag" in item:
                        yield {
                            "tag": str(item["tag"]).strip(),
                            "weight": float(item.get("weight", 0.7) or 0.7),
                            "source_trip_id": message.get("source_trip_id"),
                        }
                continue
            if "tag" in message:
                weight = float(message.get("weight", 0.7) or 0.7)
                yield {
                    "tag": str(message["tag"]).strip(),
                    "weight": weight,
                    "source_trip_id": message.get("source_trip_id"),
                }
                continue
            content = str(message.get("content", "")).strip()
            if not content:
                continue
            for match in pattern.finditer(content):
                tag = match.group("tag").strip("#＃：: ")
                if not tag:
                    continue
                raw_weight = match.group("weight")
                weight = float(raw_weight) if raw_weight else 0.7
                weight = min(max(weight, 0.1), 1.0)
                yield {
                    "tag": tag,
                    "weight": weight,
                    "source_trip_id": message.get("source_trip_id"),
                }

    @staticmethod
    def _normalize_candidates(
        candidates: Iterable[dict[str, Any]],
        *,
        trip_id: int | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        ranked: dict[str, dict[str, Any]] = {}
        for item in candidates:
            tag = str(item.get("tag", "")).strip()
            if not tag:
                continue
            weight = float(item.get("weight", 0.7) or 0.7)
            weight = min(max(weight, 0.0), 1.0)
            existing = ranked.get(tag)
            if existing is None or weight > existing["weight"]:
                ranked[tag] = {
                    "tag": tag,
                    "weight": round(weight, 4),
                    "source_trip_id": item.get("source_trip_id") or trip_id,
                }
        sorted_items = sorted(
            ranked.values(),
            key=lambda x: (x["weight"], -len(x["tag"])),
            reverse=True,
        )
        return sorted_items[:limit]

    async def _fetch_memories(
        self,
        query: str | None,
        *,
        limit: int,
        user_id: int,
        agent_id: str | None,
        run_id: str | None,
        trip_id: int | None,
    ) -> List[dict[str, Any]]:
        if not query or not self._memory_service.is_enabled():
            return []
        filters: Dict[str, Any] = {"user_id": str(user_id)}
        if agent_id:
            filters["agent_id"] = agent_id
        if run_id:
            filters["run_id"] = run_id
        if trip_id is not None:
            filters["trip_id"] = trip_id
        memories = await asyncio.to_thread(
            self._memory_service.search,
            query,
            top_k=limit,
            filters=filters,
            threshold=None,
        )
        return memories

    async def _write_tags(
        self, user_id: int, items: Sequence[dict[str, Any]]
    ) -> Sequence[UserTag]:
        def _worker() -> Sequence[UserTag]:
            session_factory = self._session_factory
            if session_factory is None:
                raise RuntimeError("session_factory_not_configured")
            session: Session = session_factory()
            try:
                return tag_service.bulk_upsert_user_tags(
                    session, user_id=user_id, items=items
                )
            finally:
                session.close()

        return await asyncio.to_thread(_worker)

    @staticmethod
    def _serialize_tags(tags: Sequence[UserTag]) -> list[dict[str, Any]]:
        return [
            {
                "id": tag.id,
                "tag": tag.tag,
                "weight": tag.weight,
                "source_trip_id": tag.source_trip_id,
            }
            for tag in tags
        ]

    async def _acall(self, **kwargs: Any) -> Dict[str, Any]:
        params = PreferenceTagInput(**kwargs)

        query_text: str | None = params.query
        if query_text is None:
            if params.messages:
                last_message = params.messages[-1]
                if isinstance(last_message, dict):
                    query_text = str(
                        last_message.get("content")
                        or last_message.get("tag")
                        or "用户偏好"
                    )
            if query_text is None:
                query_text = "用户偏好"

        memories = await self._fetch_memories(
            query_text,
            limit=params.limit,
            user_id=params.user_id,
            agent_id=params.agent_id,
            run_id=params.run_id,
            trip_id=params.trip_id,
        )

        candidates = list(self._iter_tags_from_messages(params.messages or []))
        for item in memories:
            memory_messages = item.get("messages")
            if isinstance(memory_messages, list):
                candidates.extend(self._iter_tags_from_messages(memory_messages))
            text = item.get("text")
            if isinstance(text, str) and text:
                candidates.extend(
                    self._iter_tags_from_messages([{"content": text, "source_trip_id": params.trip_id}])
                )

        normalized = self._normalize_candidates(
            candidates,
            trip_id=params.trip_id,
            limit=params.limit,
        )

        applied: list[dict[str, Any]] = []
        if normalized and not params.dry_run:
            persisted = await self._write_tags(params.user_id, normalized)
            applied = self._serialize_tags(persisted)

        payload = {
            "candidates": normalized,
            "applied": applied,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        status = "success"
        if not normalized and not memories and not (params.messages or []):
            status = "fallback"

        return {
            "operation": "extract_tags",
            "status": status,
            "payload": payload,
        }


__all__ = ["PreferenceTagExtractionTool", "PreferenceTagInput"]
