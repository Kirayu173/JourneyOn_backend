from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    trip_id: int
    filename: str | None = None
    format: str | None = None
    content_type: str | None = None
    file_size: int | None = None
    storage_key: str
    created_at: datetime


