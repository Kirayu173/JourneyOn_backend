from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List

from pydantic import BaseModel, Field

from app.providers.tools.standard import StandardStructuredTool
from app.services.memory_service import MemoryService, get_memory_service


class PreferenceSuggestionInput(BaseModel):
    """输入结构，用于生成用户下一次行程的偏好建议。"""

    user_id: int = Field(description="用户ID")
    trip_id: int = Field(description="当前行程ID")
    feedback_items: list[dict[str, Any]] = Field(
        default_factory=list, description="本次行程中的反馈或异常事件"
    )
    profile_tags: list[dict[str, Any]] = Field(
        default_factory=list, description="画像中已有的偏好标签"
    )
    memory_refs: list[str] | None = Field(
        default=None, description="需要补充读取的记忆ID列表"
    )
    agent_id: str | None = Field(default=None, description="调用工具的Agent标识")
    run_id: str | None = Field(default=None, description="调用运行ID")


class PreferenceSuggestionTool(StandardStructuredTool):
    """根据反馈和偏好生成下一次行程的结构化建议。"""

    name = "journeyon_preference_suggestion"
    description = "聚合偏好标签与反馈，生成下一次旅行可复用的建议并写入记忆。"
    args_schema = PreferenceSuggestionInput

    def __init__(self, memory_service: MemoryService | None = None) -> None:
        self._memory_service = memory_service or get_memory_service()
        super().__init__(coroutine=self._acall)

    async def _gather_memory_snippets(
        self, memory_ids: Iterable[str] | None
    ) -> list[dict[str, Any]]:
        if not memory_ids or not self._memory_service.is_enabled():
            return []
        tasks = [asyncio.to_thread(self._memory_service.get, mem_id) for mem_id in memory_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        payloads: list[dict[str, Any]] = []
        for result in results:
            if isinstance(result, Exception) or result is None:
                continue
            payloads.append(result)
        return payloads

    @staticmethod
    def _normalize_feedback(feedback_items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for item in feedback_items:
            if not isinstance(item, dict):
                continue
            category = str(item.get("category") or item.get("type") or "general")
            issue = str(item.get("issue") or item.get("summary") or "体验待提升")
            suggestion = item.get("recommendation")
            severity = str(item.get("severity") or "medium")
            normalized.append(
                {
                    "category": category,
                    "issue": issue,
                    "severity": severity,
                    "suggestion": suggestion,
                    "evidence": item.get("evidence") or [],
                }
            )
        return normalized

    @staticmethod
    def _compose_recommendation(
        feedback: dict[str, Any],
        tags: list[dict[str, Any]],
        memories: list[dict[str, Any]],
    ) -> dict[str, Any]:
        category = feedback["category"]
        base_suggestion = feedback.get("suggestion")
        if not base_suggestion:
            intensity = feedback.get("severity", "medium")
            prefix = "建议" if intensity != "high" else "优先考虑"
            base_suggestion = f"{prefix}{category}相关的改进方案，避免再次出现{feedback['issue']}。"

        related_tags = [
            t for t in tags if category.lower() in str(t.get("tag", "")).lower()
        ]
        if not related_tags:
            related_tags = tags[:1]

        memory_evidence: list[str] = []
        for item in memories:
            text = item.get("text") or ""
            if text and category.lower() in text.lower():
                memory_evidence.append(text)

        evidence = list(dict.fromkeys(feedback.get("evidence", []) + memory_evidence))
        if not evidence:
            evidence = [feedback["issue"]]

        return {
            "category": category,
            "recommendation": base_suggestion,
            "evidence": evidence,
            "related_tags": related_tags,
        }

    async def _persist_to_memory(
        self,
        *,
        suggestions: list[dict[str, Any]],
        user_id: int,
        trip_id: int,
        agent_id: str | None,
        run_id: str | None,
    ) -> Dict[str, Any] | None:
        if not self._memory_service.is_enabled():
            return None
        serialized = json.dumps(
            {"suggestions": suggestions}, ensure_ascii=False, separators=(",", ":")
        )
        messages = [
            {
                "role": "system",
                "content": f"next_trip_suggestions::{serialized}",
            }
        ]
        metadata = {
            "trip_id": trip_id,
            "scene": "post_insight",
            "agent_id": agent_id,
            "run_id": run_id,
            "user_id": str(user_id),
        }
        return await asyncio.to_thread(
            self._memory_service.add_messages,
            messages,
            user_id=str(user_id),
            agent_id=agent_id,
            run_id=run_id,
            metadata=metadata,
        )

    async def _acall(self, **kwargs: Any) -> Dict[str, Any]:
        params = PreferenceSuggestionInput(**kwargs)

        feedback = self._normalize_feedback(params.feedback_items)
        memories = await self._gather_memory_snippets(params.memory_refs)

        suggestions = [
            self._compose_recommendation(item, params.profile_tags, memories)
            for item in feedback
        ]

        generated_at = datetime.now(timezone.utc).isoformat()
        version = params.run_id or generated_at
        source = "session_and_memory" if memories else "session_only"

        memory_payload = await self._persist_to_memory(
            suggestions=suggestions,
            user_id=params.user_id,
            trip_id=params.trip_id,
            agent_id=params.agent_id,
            run_id=params.run_id,
        )

        payload = {
            "suggestions": suggestions,
            "generated_at": generated_at,
            "version": version,
            "source": source,
            "memory_record": memory_payload,
        }

        status = "success" if suggestions else "fallback"
        if memory_payload is None and self._memory_service.is_enabled():
            payload["memory_record"] = {}

        return {
            "operation": "generate_suggestions",
            "status": status,
            "payload": payload,
        }


__all__ = ["PreferenceSuggestionTool", "PreferenceSuggestionInput"]
