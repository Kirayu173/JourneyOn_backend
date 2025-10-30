from __future__ import annotations

from typing import Any, List
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.schemas.common import Envelope
from app.api.deps import get_current_user
from app.db.session import get_db
from app.db.models import TripStageEnum, User
from app.services.trip_service import (
    create_trip,
    get_user_trips,
    get_trip,
    update_trip_stage,
    update_stage_status,
)
from app.services.stage_service import STAGE_SEQUENCE, advance_stage

router = APIRouter(prefix="/trips", tags=["trips"])


class TripCreateRequest(BaseModel):
    title: str | None = None
    origin: str | None = None
    origin_lat: float | None = None
    origin_lng: float | None = None
    destination: str | None = None
    destination_lat: float | None = None
    destination_lng: float | None = None
    start_date: date | None = None
    duration_days: int | None = None
    budget: float | None = None
    currency: str = "CNY"
    preferences: dict | None = None
    agent_context: dict | None = None


class TripStageUpdateRequest(BaseModel):
    new_stage: TripStageEnum | str


class TripStageStatusUpdateRequest(BaseModel):
    new_status: str


class StageAdvanceRequest(BaseModel):
    to_stage: TripStageEnum | None = None


@router.post("")
def create_trip_endpoint(
    req: TripCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Envelope[dict[str, Any]]:
    """创建新的行程。"""
    trip = create_trip(db, trip_data=req.model_dump(), user_id=user.id)
    return Envelope(
        code=0,
        msg="ok",
        data={
            "id": trip.id,
            "title": trip.title,
            "origin": trip.origin,
            "destination": trip.destination,
            "start_date": str(trip.start_date) if trip.start_date else None,
            "duration_days": trip.duration_days,
            "budget": float(trip.budget) if trip.budget is not None else None,
            "currency": trip.currency,
            "current_stage": trip.current_stage.value,
            "status": trip.status,
        },
    )


@router.get("")
def list_trips_endpoint(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Envelope[List[dict[str, Any]]]:
    """获取用户行程列表。"""
    trips = get_user_trips(db, user_id=user.id)
    items = [
        {
            "id": t.id,
            "title": t.title,
            "origin": t.origin,
            "destination": t.destination,
            "start_date": str(t.start_date) if t.start_date else None,
            "current_stage": t.current_stage.value,
            "stage": t.current_stage.value,
            "status": t.status,
            "fromCity": t.origin,
            "toCity": t.destination,
            "duration": t.duration_days,
            "archived": (t.status == "archived"),
        }
        for t in trips
    ]
    return Envelope(code=0, msg="ok", data=items)


@router.get("/{trip_id}")
def get_trip_endpoint(
    trip_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Envelope[dict[str, Any]]:
    """获取单个行程详情。"""
    trip = get_trip(db, trip_id=trip_id, user_id=user.id)
    if not trip:
        raise HTTPException(status_code=404, detail="trip_not_found")
    return Envelope(
        code=0,
        msg="ok",
        data={
            "id": trip.id,
            "title": trip.title,
            "origin": trip.origin,
            "fromCity": trip.origin,
            "destination": trip.destination,
            "toCity": trip.destination,
            "start_date": str(trip.start_date) if trip.start_date else None,
            "duration_days": trip.duration_days,
            "duration": trip.duration_days,
            "budget": float(trip.budget) if trip.budget is not None else None,
            "currency": trip.currency,
            "current_stage": trip.current_stage.value,
            "stage": trip.current_stage.value,
            "status": trip.status,
            "archived": (trip.status == "archived"),
            "preferences": trip.preferences,
            "agent_context": trip.agent_context,
        },
    )


@router.patch("/{trip_id}/stage")
def update_trip_stage_endpoint(
    trip_id: int,
    req: TripStageUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Envelope[dict[str, Any]]:
    """更新行程阶段。"""
    new_stage_value = req.new_stage.value if isinstance(req.new_stage, TripStageEnum) else req.new_stage
    try:
        updated = update_trip_stage(db, trip_id=trip_id, user_id=user.id, new_stage=new_stage_value)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid_stage")

    if not updated:
        raise HTTPException(status_code=404, detail="trip_not_found")

    return Envelope(
        code=0,
        msg="ok",
        data={
            "id": updated.id,
            "current_stage": updated.current_stage.value,
            "stage": updated.current_stage.value,
            "status": updated.status,
        },
    )


@router.patch("/{trip_id}/stages/{stage_name}")
def update_trip_stage_status_endpoint(
    trip_id: int,
    stage_name: str,
    req: TripStageStatusUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Envelope[dict[str, Any]]:
    """更新行程阶段状态。"""
    try:
        updated = update_stage_status(
            db,
            trip_id=trip_id,
            user_id=user.id,
            stage_name=stage_name,
            new_status=req.new_status,
        )
    except ValueError as e:
        reason = str(e)
        if reason in ("invalid_stage", "invalid_status", "invalid_transition"):
            raise HTTPException(status_code=400, detail=reason)
        raise

    if not updated:
        raise HTTPException(status_code=404, detail="stage_not_found")

    return Envelope(
        code=0,
        msg="ok",
        data={
            "trip_id": trip_id,
            "stage_name": updated.stage_name,
            "status": updated.status,
            "confirmed_at": updated.confirmed_at.isoformat() if updated.confirmed_at else None,
        },
    )


@router.post("/{trip_id}/stage/advance")
def advance_trip_stage_endpoint(
    trip_id: int,
    req: StageAdvanceRequest | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Envelope[dict[str, Any]]:
    """严格推进行程阶段（pre -> on -> post），可选指定目标阶段。

    - 如果未提供 `to_stage`，将推进到下一个阶段；
    - 如果提供了 `to_stage`，将根据规则校验是否允许（不可越级、不可回退）。
    """
    trip = get_trip(db, trip_id=trip_id, user_id=user.id)
    if not trip:
        raise HTTPException(status_code=404, detail="trip_not_found")

    # 计算目标阶段
    if req and req.to_stage is not None:
        target = req.to_stage if isinstance(req.to_stage, TripStageEnum) else TripStageEnum(req.to_stage)
    else:
        try:
            idx = STAGE_SEQUENCE.index(trip.current_stage)
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid_current_stage")
        if idx >= len(STAGE_SEQUENCE) - 1:
            raise HTTPException(status_code=400, detail="already_at_last_stage")
        target = STAGE_SEQUENCE[idx + 1]

    try:
        result = advance_stage(db, trip_id=trip_id, user_id=user.id, to_stage=target)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if result is None:
        raise HTTPException(status_code=404, detail="trip_not_found")

    return Envelope(
        code=0,
        msg="ok",
        data={
            "trip_id": result.trip_id,
            "from_stage": result.from_stage.value,
            "to_stage": result.to_stage.value,
            "updated": result.updated,
            "stage_statuses": result.stage_statuses,
        },
    )


@router.post("/{trip_id}/archive")
def archive_trip_endpoint(
    trip_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Envelope[dict[str, Any]]:
    """归档行程：确保阶段为 post 并将状态标记为 archived。"""
    trip = get_trip(db, trip_id=trip_id, user_id=user.id)
    if not trip:
        raise HTTPException(status_code=404, detail="trip_not_found")

    # 若未到 post，逐步推进到 post
    while trip.current_stage != TripStageEnum.post:
        try:
            idx = STAGE_SEQUENCE.index(trip.current_stage)
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid_current_stage")
        if idx >= len(STAGE_SEQUENCE) - 1:
            break
        target = STAGE_SEQUENCE[idx + 1]
        res = advance_stage(db, trip_id=trip_id, user_id=user.id, to_stage=target)
        if res is None:
            raise HTTPException(status_code=404, detail="trip_not_found")
        # 重新获取最新trip
        trip = get_trip(db, trip_id=trip_id, user_id=user.id)
        if not trip:
            raise HTTPException(status_code=404, detail="trip_not_found")

    # 设置归档状态
    trip.status = "archived"
    db.add(trip)
    db.commit()
    db.refresh(trip)

    return Envelope(
        code=0,
        msg="ok",
        data={
            "id": trip.id,
            "current_stage": trip.current_stage.value,
            "stage": trip.current_stage.value,
            "status": trip.status,
            "archived": True,
        },
    )
