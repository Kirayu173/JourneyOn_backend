from __future__ import annotations

from typing import Optional
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ConversationResponse(BaseModel):
    id: int
    trip_id: int
    stage: str
    role: str
    message: str
    message_meta: dict
    created_at: Optional[datetime]

    # Enable Pydantic v2 ORM mode
    model_config = ConfigDict(from_attributes=True)