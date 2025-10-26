from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy.orm import Session

from app.db.models import Trip, TripStage, TripStageEnum, AuditLog
from datetime import datetime, timezone


def get_trip(db: Session, trip_id: int, user_id: int) -> Optional[Trip]:
    """Return trip by id if owned by the given user."""
    return db.query(Trip).filter(Trip.id == trip_id, Trip.user_id == user_id).first()


def get_user_trips(db: Session, user_id: int) -> Sequence[Trip]:
    """List trips owned by the given user."""
    return db.query(Trip).filter(Trip.user_id == user_id).order_by(Trip.created_at.desc()).all()


def create_trip(db: Session, trip_data: dict, user_id: int) -> Trip:
    """Create a new trip owned by the given user and initialize its stages.

    Creates three TripStage records (pre/on/post) with initial statuses
    in a single transaction. If any step fails, the transaction is rolled back.
    """
    trip = Trip(
        user_id=user_id,
        title=trip_data.get("title"),
        origin=trip_data.get("origin"),
        origin_lat=trip_data.get("origin_lat"),
        origin_lng=trip_data.get("origin_lng"),
        destination=trip_data.get("destination"),
        destination_lat=trip_data.get("destination_lat"),
        destination_lng=trip_data.get("destination_lng"),
        start_date=trip_data.get("start_date"),
        duration_days=trip_data.get("duration_days"),
        budget=trip_data.get("budget"),
        currency=trip_data.get("currency", "CNY"),
        preferences=trip_data.get("preferences"),
        agent_context=trip_data.get("agent_context"),
    )
    try:
        db.add(trip)
        # Flush to obtain trip.id without committing the transaction yet
        db.flush()

        # Initialize trip stages: pre=in_progress, on=pending, post=pending
        stages = [
            TripStage(trip_id=trip.id, stage_name=TripStageEnum.pre.value, status="in_progress"),
            TripStage(trip_id=trip.id, stage_name=TripStageEnum.on.value, status="pending"),
            TripStage(trip_id=trip.id, stage_name=TripStageEnum.post.value, status="pending"),
        ]
        for s in stages:
            db.add(s)

        db.commit()
        db.refresh(trip)
    except Exception:
        db.rollback()
        raise
    return trip


def update_trip_stage(db: Session, trip_id: int, user_id: int, new_stage: str | TripStageEnum) -> Optional[Trip]:
    """Update the current_stage of a trip if owned by the user."""
    trip = get_trip(db, trip_id, user_id)
    if trip is None:
        return None
    # Normalize stage
    stage_enum = (
        new_stage if isinstance(new_stage, TripStageEnum) else TripStageEnum(new_stage)
    )
    trip.current_stage = stage_enum
    db.add(trip)
    db.commit()
    db.refresh(trip)
    return trip


def update_stage_status(
    db: Session,
    *,
    trip_id: int,
    user_id: int,
    stage_name: str | TripStageEnum,
    new_status: str,
) -> Optional[TripStage]:
    """Update status of a TripStage with validation and audit logging.

    Valid statuses: 'pending', 'in_progress', 'completed'.
    Allowed transitions:
      - pending -> in_progress
      - in_progress -> completed
      - idempotent updates are allowed (same status)
      - completed is terminal (no further transitions)
    Raises ValueError on invalid stage name, status, or transition.
    Returns updated TripStage or None if trip/stage not found.
    """
    # Validate stage name
    try:
        stage_value = stage_name.value if isinstance(stage_name, TripStageEnum) else TripStageEnum(stage_name).value
    except ValueError:
        raise ValueError("invalid_stage")

    # Validate status value
    allowed_status = {"pending", "in_progress", "completed"}
    if new_status not in allowed_status:
        raise ValueError("invalid_status")

    # Ensure ownership
    trip = get_trip(db, trip_id, user_id)
    if trip is None:
        return None

    # Find stage row
    stage = (
        db.query(TripStage)
        .filter(TripStage.trip_id == trip_id, TripStage.stage_name == stage_value)
        .first()
    )
    if stage is None:
        return None

    # Transition validation
    current = stage.status or "pending"
    if current == new_status:
        # idempotent
        pass
    elif current == "pending" and new_status in {"in_progress"}:
        stage.status = new_status
    elif current == "in_progress" and new_status in {"completed"}:
        stage.status = new_status
        stage.confirmed_at = datetime.now(timezone.utc)
    elif current == "completed":
        # terminal; disallow changes
        raise ValueError("invalid_transition")
    else:
        raise ValueError("invalid_transition")

    # Audit log
    log = AuditLog(
        user_id=user_id,
        trip_id=trip_id,
        action="trip_stage_status_updated",
        detail=f"{stage_value}:{current}->{stage.status}",
    )
    db.add(stage)
    db.add(log)
    db.commit()
    db.refresh(stage)
    return stage