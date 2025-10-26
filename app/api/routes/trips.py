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
from app.services.trip_service import create_trip, get_user_trips, get_trip, update_trip_stage, update_stage_status

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


@router.post("")
def create_trip_endpoint(
    req: TripCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Envelope[dict[str, Any]]:
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
    trips = get_user_trips(db, user_id=user.id)
    items = [
        {
            "id": t.id,
            "title": t.title,
            "destination": t.destination,
            "start_date": str(t.start_date) if t.start_date else None,
            "current_stage": t.current_stage.value,
            "status": t.status,
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
            "destination": trip.destination,
            "start_date": str(trip.start_date) if trip.start_date else None,
            "duration_days": trip.duration_days,
            "budget": float(trip.budget) if trip.budget is not None else None,
            "currency": trip.currency,
            "current_stage": trip.current_stage.value,
            "status": trip.status,
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