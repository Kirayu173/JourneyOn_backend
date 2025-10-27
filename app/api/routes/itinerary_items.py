from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.schemas.common import Envelope
from app.schemas.itinerary_schemas import (
    ItineraryItemCreate,
    ItineraryItemUpdate,
    ItineraryItemResponse,
)
from app.services.itinerary_service import (
    create_item,
    get_items,
    update_item,
    delete_item,
)

router = APIRouter(prefix="/trips/{trip_id}/itinerary", tags=["itinerary"])


@router.post("", response_model=Envelope[ItineraryItemResponse])
def create_itinerary_item(
    trip_id: int,
    payload: ItineraryItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Envelope[ItineraryItemResponse]:
    """创建新的行程项。"""
    item = create_item(
        db,
        trip_id=trip_id,
        user_id=current_user.id,
        day=payload.day,
        start_time=payload.start_time,
        end_time=payload.end_time,
        kind=payload.kind,
        title=payload.title,
        location=payload.location,
        lat=payload.lat,
        lng=payload.lng,
        details=payload.details,
    )
    return Envelope(code=0, msg="ok", data=ItineraryItemResponse.model_validate(item))


@router.get("", response_model=Envelope[List[ItineraryItemResponse]])
def list_itinerary_items(
    trip_id: int,
    day: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Envelope[List[ItineraryItemResponse]]:
    """获取行程项列表。"""
    items = get_items(db, trip_id=trip_id, user_id=current_user.id, day=day)
    return Envelope(code=0, msg="ok", data=[ItineraryItemResponse.model_validate(i) for i in items])


@router.patch("/{item_id}", response_model=Envelope[ItineraryItemResponse])
def patch_itinerary_item(
    trip_id: int,
    item_id: int,
    payload: ItineraryItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Envelope[ItineraryItemResponse]:
    """更新行程项。"""
    updated = update_item(
        db,
        item_id=item_id,
        user_id=current_user.id,
        day=payload.day,
        start_time=payload.start_time,
        end_time=payload.end_time,
        kind=payload.kind,
        title=payload.title,
        location=payload.location,
        lat=payload.lat,
        lng=payload.lng,
        details=payload.details,
    )
    return Envelope(code=0, msg="ok", data=ItineraryItemResponse.model_validate(updated))


@router.delete("/{item_id}", response_model=Envelope[None])
def delete_itinerary_item(
    trip_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Envelope[None]:
    """删除行程项。"""
    delete_item(db, item_id=item_id, user_id=current_user.id)
    return Envelope(code=0, msg="ok", data=None)