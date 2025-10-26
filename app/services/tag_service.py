from __future__ import annotations

from typing import Optional, Sequence, Iterable

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.models import UserTag


def create_user_tag(
    db: Session,
    *,
    user_id: int,
    tag: str,
    weight: Optional[float] = None,
    source_trip_id: Optional[int] = None,
) -> UserTag:
    """Create a tag for the current user."""
    item = UserTag(user_id=user_id, tag=tag, weight=weight, source_trip_id=source_trip_id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def get_user_tags(
    db: Session,
    *,
    user_id: int,
    tag: Optional[str] = None,
    source_trip_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
) -> Sequence[UserTag]:
    q = db.query(UserTag).filter(UserTag.user_id == user_id)
    if tag:
        q = q.filter(UserTag.tag == tag)
    if source_trip_id:
        q = q.filter(UserTag.source_trip_id == source_trip_id)
    return q.order_by(UserTag.id.desc()).offset(offset).limit(limit).all()


def get_user_tag(db: Session, *, user_id: int, tag_id: int) -> UserTag:
    item = db.query(UserTag).filter(UserTag.id == tag_id, UserTag.user_id == user_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="user_tag_not_found")
    return item


def update_user_tag(
    db: Session,
    *,
    user_id: int,
    tag_id: int,
    tag: Optional[str] = None,
    weight: Optional[float] = None,
    source_trip_id: Optional[int] = None,
) -> UserTag:
    item = get_user_tag(db, user_id=user_id, tag_id=tag_id)
    if tag is not None:
        item.tag = tag
    if weight is not None:
        item.weight = weight
    if source_trip_id is not None:
        item.source_trip_id = source_trip_id
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def delete_user_tag(db: Session, *, user_id: int, tag_id: int) -> None:
    item = get_user_tag(db, user_id=user_id, tag_id=tag_id)
    db.delete(item)
    db.commit()


def bulk_upsert_user_tags(
    db: Session,
    *,
    user_id: int,
    items: Iterable[dict],
) -> Sequence[UserTag]:
    """Upsert multiple tags for the user by tag name.

    If a tag exists for the user, update its weight and source_trip_id.
    Otherwise, create a new tag.
    """
    # Fetch existing tags map for user
    existing = {t.tag: t for t in db.query(UserTag).filter(UserTag.user_id == user_id).all()}
    result: list[UserTag] = []
    for payload in items:
        name = payload.get("tag")
        weight = payload.get("weight")
        source_trip_id = payload.get("source_trip_id")
        if not name:
            # Skip invalid payloads silently; could also raise
            continue
        if name in existing:
            tag_obj = existing[name]
            if weight is not None:
                tag_obj.weight = weight
            if source_trip_id is not None:
                tag_obj.source_trip_id = source_trip_id
            db.add(tag_obj)
            result.append(tag_obj)
        else:
            tag_obj = UserTag(user_id=user_id, tag=name, weight=weight, source_trip_id=source_trip_id)
            db.add(tag_obj)
            result.append(tag_obj)
    db.commit()
    # Refresh to ensure latest values
    for t in result:
        db.refresh(t)
    return result