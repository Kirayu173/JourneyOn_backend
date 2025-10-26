from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.schemas.common import Envelope
from app.schemas.conversation_schemas import ConversationResponse
from app.services.conversation_service import get_history

router = APIRouter(prefix="/trips/{trip_id}/conversations", tags=["conversations"])


@router.get("", response_model=Envelope[List[ConversationResponse]])
def list_conversations(
    trip_id: int,
    stage: str | None = None,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    items = get_history(db, trip_id=trip_id, user_id=current_user.id, stage=stage, limit=limit)
    return Envelope(code=0, msg="ok", data=[ConversationResponse.model_validate(i) for i in items])