from __future__ import annotations

from typing import Optional
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict


class KBEntryCreate(BaseModel):
    source: Optional[str] = None
    title: Optional[str] = Field(None, max_length=255)
    content: Optional[str] = None
    meta: Optional[dict] = None


class KBEntryUpdate(BaseModel):
    source: Optional[str] = None
    title: Optional[str] = Field(None, max_length=255)
    content: Optional[str] = None
    meta: Optional[dict] = None


class KBEntryResponse(BaseModel):
    id: int
    trip_id: int
    source: Optional[str]
    title: Optional[str]
    content: Optional[str]
    meta: dict
    embedding_id: Optional[str]
    created_at: Optional[datetime]

    # Enable Pydantic v2 ORM mode
    model_config = ConfigDict(from_attributes=True)