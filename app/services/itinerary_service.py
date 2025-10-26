from __future__ import annotations

from typing import Optional, Sequence

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.models import ItineraryItem
from app.services.audit_service import log_action
from app.services.trip_service import get_trip


def _ensure_trip_ownership(db: Session, trip_id: int, user_id: int) -> None:
    trip = get_trip(db, trip_id, user_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="trip_not_found")


def create_item(
    db: Session,
    *,
    trip_id: int,
    user_id: int,
    day: int,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    kind: Optional[str] = None,
    title: Optional[str] = None,
    location: Optional[str] = None,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    details: Optional[str] = None,
) -> ItineraryItem:
    _ensure_trip_ownership(db, trip_id, user_id)
    item = ItineraryItem(
        trip_id=trip_id,
        day=day,
        start_time=start_time,
        end_time=end_time,
        kind=kind,
        title=title,
        location=location,
        lat=lat,
        lng=lng,
        details=details,
    )
    db.add(item)
    db.flush()
    log_action(
        db,
        action="itinerary_item_created",
        user_id=user_id,
        trip_id=trip_id,
        detail=f"item_id={item.id}",
    )
    db.commit()
    db.refresh(item)
    return item


def get_items(
    db: Session, *, trip_id: int, user_id: int, day: Optional[int] = None
) -> Sequence[ItineraryItem]:
    _ensure_trip_ownership(db, trip_id, user_id)
    q = db.query(ItineraryItem).filter(ItineraryItem.trip_id == trip_id)
    if day is not None:
        q = q.filter(ItineraryItem.day == day)
    return q.order_by(ItineraryItem.day.asc(), ItineraryItem.id.asc()).all()


def get_item_by_id(db: Session, *, item_id: int) -> Optional[ItineraryItem]:
    return db.query(ItineraryItem).filter(ItineraryItem.id == item_id).first()


def update_item(
    db: Session,
    *,
    item_id: int,
    user_id: int,
    day: Optional[int] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    kind: Optional[str] = None,
    title: Optional[str] = None,
    location: Optional[str] = None,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    details: Optional[str] = None,
) -> ItineraryItem:
    item = get_item_by_id(db, item_id=item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="itinerary_item_not_found")
    _ensure_trip_ownership(db, item.trip_id, user_id)

    if day is not None:
        item.day = day
    if start_time is not None:
        item.start_time = start_time
    if end_time is not None:
        item.end_time = end_time
    if kind is not None:
        item.kind = kind
    if title is not None:
        item.title = title
    if location is not None:
        item.location = location
    if lat is not None:
        item.lat = lat
    if lng is not None:
        item.lng = lng
    if details is not None:
        item.details = details

    db.add(item)
    db.flush()
    log_action(
        db,
        action="itinerary_item_updated",
        user_id=user_id,
        trip_id=item.trip_id,
        detail=f"item_id={item.id}",
    )
    db.commit()
    db.refresh(item)
    return item


def delete_item(db: Session, *, item_id: int, user_id: int) -> None:
    item = get_item_by_id(db, item_id=item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="itinerary_item_not_found")
    _ensure_trip_ownership(db, item.trip_id, user_id)
    item_id = item.id
    trip_id = item.trip_id
    db.delete(item)
    log_action(
        db,
        action="itinerary_item_deleted",
        user_id=user_id,
        trip_id=trip_id,
        detail=f"item_id={item_id}",
    )
    db.commit()