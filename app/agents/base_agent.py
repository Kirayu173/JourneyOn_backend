from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, MutableMapping, Optional

from app.db.models import TripStageEnum


@dataclass(slots=True)
class AgentContext:
    """Mutable context passed between graph nodes."""

    trip_id: int
    user_id: int
    stage: TripStageEnum
    message: str
    client_ctx: Mapping[str, Any] | None = None
    advance_stage: bool = False
    extra: MutableMapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "trip_id": self.trip_id,
            "user_id": self.user_id,
            "stage": self.stage.value,
            "message": self.message,
            "advance_stage": self.advance_stage,
            "extra": dict(self.extra),
        }
        if self.client_ctx is not None:
            payload["client_ctx"] = dict(self.client_ctx)
        return payload


@dataclass(slots=True)
class AgentRunResult:
    """Structured result returned by each stage agent."""

    stage: TripStageEnum
    message: str
    status: str
    should_proceed: bool = False
    next_stage: Optional[TripStageEnum] = None
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "stage": self.stage.value,
            "message": self.message,
            "status": self.status,
            "should_proceed": self.should_proceed,
            "data": self.data,
        }
        if self.next_stage is not None:
            payload["next_stage"] = self.next_stage.value
        else:
            payload["next_stage"] = None
        return payload


class BaseAgent(ABC):
    """Base class for all stage agents."""

    name: str = ""
    description: str = ""
    stage: TripStageEnum

    def __init__(self) -> None:
        if not getattr(self, "name", None):
            self.name = self.__class__.__name__
        if not getattr(self, "description", None):
            self.description = self.name
        if not hasattr(self, "stage"):
            raise ValueError("stage attribute must be defined on agent subclasses")

    @abstractmethod
    async def run(self, context: AgentContext) -> AgentRunResult:
        """Execute the agent logic and return a structured result."""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "stage": self.stage.value,
        }
