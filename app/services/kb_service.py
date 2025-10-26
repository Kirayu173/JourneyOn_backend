from __future__ import annotations

from typing import Optional, Sequence

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from app.db.models import KBEntry
from app.services.trip_service import get_trip


def _ensure_trip_ownership(db: Session, trip_id: int, user_id: int) -> None:
    trip = get_trip(db, trip_id, user_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="trip_not_found")


def create_kb_entry(
    db: Session,
    *,
    trip_id: int,
    user_id: int,
    source: Optional[str],
    title: Optional[str],
    content: Optional[str],
    meta: Optional[dict] = None,
) -> KBEntry:
    """Create a KB entry under a user's trip."""
    _ensure_trip_ownership(db, trip_id, user_id)
    entry = KBEntry(
        trip_id=trip_id,
        source=source,
        title=title,
        content=content,
        meta=meta or {},
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_kb_entries(
    db: Session,
    *,
    trip_id: int,
    user_id: int,
    q: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
) -> Sequence[KBEntry]:
    """List KB entries for a trip with optional search and pagination."""
    _ensure_trip_ownership(db, trip_id, user_id)
    qset = db.query(KBEntry).filter(KBEntry.trip_id == trip_id)
    if source:
        qset = qset.filter(KBEntry.source == source)
    if q:
        like = f"%{q}%"
        qset = qset.filter(or_(KBEntry.title.ilike(like), KBEntry.content.ilike(like)))
    # basic optimization: order by newest first and paginate
    return (
        qset.order_by(KBEntry.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def get_kb_entry(db: Session, *, entry_id: int, trip_id: int, user_id: int) -> KBEntry:
    """Fetch a KB entry by id, ensuring ownership via trip."""
    _ensure_trip_ownership(db, trip_id, user_id)
    entry = db.query(KBEntry).filter(KBEntry.id == entry_id, KBEntry.trip_id == trip_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="kb_entry_not_found")
    return entry


def update_kb_entry(
    db: Session,
    *,
    entry_id: int,
    trip_id: int,
    user_id: int,
    source: Optional[str] = None,
    title: Optional[str] = None,
    content: Optional[str] = None,
    meta: Optional[dict] = None,
) -> KBEntry:
    """Update a KB entry fields."""
    entry = get_kb_entry(db, entry_id=entry_id, trip_id=trip_id, user_id=user_id)
    if source is not None:
        entry.source = source
    if title is not None:
        entry.title = title
    if content is not None:
        entry.content = content
    if meta is not None:
        entry.meta = meta
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def delete_kb_entry(db: Session, *, entry_id: int, trip_id: int, user_id: int) -> None:
    """Delete a KB entry under the user's trip."""
    entry = get_kb_entry(db, entry_id=entry_id, trip_id=trip_id, user_id=user_id)
    db.delete(entry)
    db.commit()