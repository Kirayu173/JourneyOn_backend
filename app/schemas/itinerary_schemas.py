from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class ItineraryItemCreate(BaseModel):
    day: int = Field(..., ge=1)
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    kind: Optional[str] = None
    title: Optional[str] = None
    location: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    details: Optional[str] = None


class ItineraryItemUpdate(BaseModel):
    day: Optional[int] = Field(None, ge=1)
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    kind: Optional[str] = None
    title: Optional[str] = None
    location: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    details: Optional[str] = None


class ItineraryItemResponse(BaseModel):
    id: int
    trip_id: int
    day: int
    start_time: Optional[str]
    end_time: Optional[str]
    kind: Optional[str]
    title: Optional[str]
    location: Optional[str]
    lat: Optional[float]
    lng: Optional[float]
    details: Optional[str]

    # Enable Pydantic v2 ORM mode
    model_config = ConfigDict(from_attributes=True)