from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict, Iterable

import pytest

from app.db.models import Base, Trip, TripStageEnum, User, UserTag
from app.db.session import SessionLocal, engine
from app.providers.tools.memory_access_tool import MemoryAccessTool
from app.providers.tools.preference_suggestion_tool import PreferenceSuggestionTool
from app.providers.tools.preference_tag_tool import PreferenceTagExtractionTool
from app.providers.tools.trip_context_sync_tool import TripContextSyncTool


class StubMemoryService:
    def __init__(self) -> None:
        self.enabled = True
        self.records: Dict[str, Dict[str, Any]] = {}
        self.histories: Dict[str, list[Dict[str, Any]]] = {}
        self.counter = 0

    def is_enabled(self) -> bool:
        return self.enabled

    @staticmethod
    def _format_messages(messages: Iterable[dict[str, Any]]) -> str:
        parts: list[str] = []
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "")
            if role:
                parts.append(f"{role}: {content}")
            else:
                parts.append(str(content))
        return "\n".join(parts)

    def add_messages(
        self,
        messages: list[dict[str, Any]],
        *,
        user_id: str | None = None,
        agent_id: str | None = None,
        run_id: str | None = None,
        metadata: Dict[str, Any] | None = None,
        infer: bool | None = None,
    ) -> Dict[str, Any] | None:
        if not self.enabled:
            return None
        self.counter += 1
        memory_id = metadata.get("memory_id") if metadata else None
        memory_id = memory_id or f"mem-{self.counter}"
        formatted = self._format_messages(messages)
        record = {
            "id": memory_id,
            "messages": [dict(m) for m in messages],
            "metadata": dict(metadata or {}),
            "user_id": user_id,
            "agent_id": agent_id,
            "run_id": run_id,
        }
        record["text"] = formatted
        self.records[memory_id] = record
        self.histories.setdefault(memory_id, []).append({"messages": record["messages"]})
        return record

    def search(
        self,
        query: str,
        *,
        top_k: int = 10,
        filters: Dict[str, Any] | None = None,
        threshold: float | None = None,
    ) -> list[Dict[str, Any]]:
        if not self.enabled:
            return []
        filters = filters or {}
        result: list[Dict[str, Any]] = []
        for record in self.records.values():
            text = record.get("text", "")
            if query and query not in text and query not in record.get("id", ""):
                continue
            include = True
            for key, value in filters.items():
                if record.get("metadata", {}).get(key) != value and record.get(key) != value:
                    include = False
                    break
            if include:
                result.append(record)
        return result[:top_k]

    def append_memory(self, memory_id: str, messages: list[dict[str, Any]]) -> Dict[str, Any] | None:
        if memory_id not in self.records:
            return None
        record = self.records[memory_id]
        record["messages"].extend(messages)
        record["text"] = self._format_messages(record["messages"])
        self.histories.setdefault(memory_id, []).append({"messages": list(record["messages"])})
        return record

    def replace_memory(self, memory_id: str, messages: list[dict[str, Any]]) -> Dict[str, Any] | None:
        if memory_id not in self.records:
            return None
        record = self.records[memory_id]
        record["messages"] = [dict(m) for m in messages]
        record["text"] = self._format_messages(messages)
        self.histories.setdefault(memory_id, []).append({"messages": list(record["messages"])})
        return record

    def delete(self, memory_id: str) -> Dict[str, Any] | None:
        return self.records.pop(memory_id, None)

    def history(self, memory_id: str) -> list[Dict[str, Any]]:
        return self.histories.get(memory_id, [])

    def get(self, memory_id: str) -> Dict[str, Any] | None:
        return self.records.get(memory_id)


@pytest.fixture(scope="module", autouse=True)
def _init_db() -> None:
    Base.metadata.create_all(engine)


@pytest.fixture
def memory_service() -> StubMemoryService:
    return StubMemoryService()


@pytest.fixture
def user_and_trip() -> tuple[int, int]:
    session = SessionLocal()
    try:
        suffix = datetime.utcnow().strftime("%H%M%S%f")
        user = User(username=f"tool_user_{suffix}", email=f"tool_{suffix}@example.com")
        session.add(user)
        session.flush()
        trip = Trip(user_id=user.id, title="测试行程", current_stage=TripStageEnum.pre)
        session.add(trip)
        session.commit()
        return user.id, trip.id
    finally:
        session.close()


def test_memory_access_tool_full_flow(memory_service: StubMemoryService) -> None:
    tool = MemoryAccessTool(memory_service=memory_service)

    async def _run() -> None:
        add_result = await tool.ainvoke(
            {
                "action": "add",
                "messages": [{"role": "user", "content": "记录偏好海滩"}],
                "user_id": "u1",
                "agent_id": "stage-pre",
                "trip_id": 100,
            }
        )
        assert add_result["status"] == "success"
        memory_id = add_result["payload"]["id"]

        search_result = await tool.ainvoke(
            {
                "action": "search",
                "query": "海滩",
                "user_id": "u1",
            }
        )
        assert search_result["payload"]

        update_append = await tool.ainvoke(
            {
                "action": "update",
                "memory_id": memory_id,
                "messages": [{"role": "assistant", "content": "追加潜水偏好"}],
                "update_mode": "append",
            }
        )
        assert "追加" in update_append["payload"]["text"]

        update_overwrite = await tool.ainvoke(
            {
                "action": "update",
                "memory_id": memory_id,
                "messages": [{"role": "system", "content": "覆盖为城市漫游"}],
                "update_mode": "overwrite",
            }
        )
        assert update_overwrite["payload"]["text"].startswith("system")

        history = await tool.ainvoke({"action": "history", "memory_id": memory_id})
        assert history["payload"], "history should not be empty"

        delete_result = await tool.ainvoke({"action": "delete", "memory_id": memory_id})
        assert delete_result["payload"]["id"] == memory_id

        memory_service.enabled = False
        disabled = await tool.ainvoke({"action": "search", "query": "海滩"})
        assert disabled["status"] == "disabled"

    asyncio.run(_run())


def test_preference_tag_tool_dry_run(memory_service: StubMemoryService, user_and_trip: tuple[int, int]) -> None:
    user_id, trip_id = user_and_trip
    memory_service.add_messages(
        [{"role": "user", "content": "#海滩 体验很棒"}],
        user_id=str(user_id),
        metadata={"trip_id": trip_id, "scene": "pre"},
    )

    tool = PreferenceTagExtractionTool(
        memory_service=memory_service,
        session_factory=SessionLocal,
    )

    async def _run() -> None:
        result = await tool.ainvoke(
            {
                "user_id": user_id,
                "trip_id": trip_id,
                "messages": [
                    {"content": "用户喜欢#海滩(0.9)，也热爱#美食"},
                ],
                "dry_run": True,
                "limit": 3,
            }
        )

        assert result["status"] == "success"
        assert any(item["tag"] == "海滩" for item in result["payload"]["candidates"])
        assert result["payload"]["applied"] == []

    asyncio.run(_run())


def test_preference_tag_tool_persist(memory_service: StubMemoryService, user_and_trip: tuple[int, int]) -> None:
    user_id, trip_id = user_and_trip
    tool = PreferenceTagExtractionTool(
        memory_service=memory_service,
        session_factory=SessionLocal,
    )

    async def _run() -> None:
        result = await tool.ainvoke(
            {
                "user_id": user_id,
                "trip_id": trip_id,
                "messages": [
                    {"tag": "山地徒步", "weight": 0.8},
                ],
                "dry_run": False,
            }
        )

        assert result["payload"]["applied"]
        session = SessionLocal()
        try:
            tags = session.query(UserTag).filter(UserTag.user_id == user_id).all()
            assert any(t.tag == "山地徒步" for t in tags)
        finally:
            session.close()

    asyncio.run(_run())


def test_preference_suggestion_tool(memory_service: StubMemoryService, user_and_trip: tuple[int, int]) -> None:
    user_id, trip_id = user_and_trip
    existing = memory_service.add_messages(
        [
            {
                "role": "system",
                "content": "上次交通安排导致排队",
            }
        ],
        user_id=str(user_id),
        metadata={"trip_id": trip_id, "scene": "post"},
    )

    tool = PreferenceSuggestionTool(memory_service=memory_service)
    async def _run() -> None:
        result = await tool.ainvoke(
            {
                "user_id": user_id,
                "trip_id": trip_id,
                "feedback_items": [
                    {
                        "category": "交通",
                        "issue": "机场排队时间过长",
                        "severity": "high",
                    }
                ],
                "profile_tags": [{"tag": "交通效率", "weight": 0.8}],
                "memory_refs": [existing["id"]],
            }
        )

        payload = result["payload"]
        assert payload["suggestions"]
        assert payload["source"] == "session_and_memory"
        assert payload["memory_record"]

    asyncio.run(_run())


def test_trip_context_sync_tool(memory_service: StubMemoryService, user_and_trip: tuple[int, int]) -> None:
    user_id, trip_id = user_and_trip
    tool = TripContextSyncTool(memory_service=memory_service)

    async def _run() -> None:
        sync_result = await tool.ainvoke(
            {
                "operation": "sync",
                "trip_id": trip_id,
                "user_id": user_id,
                "stage_from": "pre",
                "stage_to": "on",
                "facts": ["用户选择自由行"],
                "tool_outputs": {"itinerary": "完成"},
            }
        )
        assert sync_result["status"] == "success"
        memory_id = sync_result["payload"]["id"]

        # Second sync should overwrite the same record
        sync_result_2 = await tool.ainvoke(
            {
                "operation": "sync",
                "trip_id": trip_id,
                "user_id": user_id,
                "stage_from": "pre",
                "stage_to": "on",
                "facts": ["加入城市通票"],
                "tool_outputs": {"budget": "调整"},
            }
        )
        assert sync_result_2["payload"]["id"] == memory_id

        load_result = await tool.ainvoke(
            {
                "operation": "load",
                "trip_id": trip_id,
                "user_id": user_id,
                "stage_to": "on",
            }
        )
        assert load_result["payload"]["items"]

    asyncio.run(_run())

