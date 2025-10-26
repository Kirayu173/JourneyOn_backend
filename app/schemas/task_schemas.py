from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class TaskCreate(BaseModel):
    stage: str = Field(..., description="Trip stage the task belongs to")
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    priority: int = 1
    assigned_to: Optional[str] = None
    due_date: Optional[date] = None
    meta: Optional[dict] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[int] = None
    assigned_to: Optional[str] = None
    due_date: Optional[date] = None
    status: Optional[str] = None
    meta: Optional[dict] = None


class TaskResponse(BaseModel):
    id: int
    trip_id: int
    stage: str
    title: str
    description: Optional[str]
    status: str
    priority: int
    assigned_to: Optional[str]
    due_date: Optional[date]
    meta: dict

    # Enable Pydantic v2 ORM mode
    model_config = ConfigDict(from_attributes=True)