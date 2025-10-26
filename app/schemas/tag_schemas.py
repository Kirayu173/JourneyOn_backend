from __future__ import annotations

from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class UserTagCreate(BaseModel):
    tag: str = Field(..., max_length=64)
    weight: Optional[float] = None
    source_trip_id: Optional[int] = None


class UserTagUpdate(BaseModel):
    tag: Optional[str] = Field(None, max_length=64)
    weight: Optional[float] = None
    source_trip_id: Optional[int] = None


class UserTagUpsert(BaseModel):
    tag: str = Field(..., max_length=64)
    weight: Optional[float] = None
    source_trip_id: Optional[int] = None


class UserTagResponse(BaseModel):
    id: int
    tag: str
    weight: Optional[float]
    source_trip_id: Optional[int]

    model_config = ConfigDict(from_attributes=True)