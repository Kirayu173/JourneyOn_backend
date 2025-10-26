from __future__ import annotations

from typing import Optional, Sequence

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.models import Conversation
from app.services.trip_service import get_trip


def _ensure_trip_ownership(db: Session, trip_id: int, user_id: int) -> None:
    trip = get_trip(db, trip_id, user_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="trip_not_found")


def save_message(
    db: Session,
    *,
    trip_id: int,
    user_id: int,
    stage: str,
    role: str,
    message: str,
    message_meta: Optional[dict] = None,
) -> Conversation:
    """Persist a conversation message under a user's trip."""
    _ensure_trip_ownership(db, trip_id, user_id)
    conv = Conversation(
        trip_id=trip_id,
        stage=stage,
        role=role,
        message=message,
        message_meta=message_meta or {},
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def get_history(
    db: Session,
    *,
    trip_id: int,
    user_id: int,
    stage: Optional[str] = None,
    limit: int = 20,
) -> Sequence[Conversation]:
    """Return recent conversation messages for a trip, optionally filtered by stage."""
    _ensure_trip_ownership(db, trip_id, user_id)
    q = db.query(Conversation).filter(Conversation.trip_id == trip_id)
    if stage:
        q = q.filter(Conversation.stage == stage)
    return q.order_by(Conversation.id.desc()).limit(limit).all()