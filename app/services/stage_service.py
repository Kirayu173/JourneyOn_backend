from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.db.models import Trip, TripStage, TripStageEnum
from app.services.audit_service import log_action
from app.services.trip_service import get_trip


STAGE_SEQUENCE = [TripStageEnum.pre, TripStageEnum.on, TripStageEnum.post]


@dataclass(slots=True)
class StageAdvanceResult:
    trip_id: int
    from_stage: TripStageEnum
    to_stage: TripStageEnum
    updated: bool
    stage_statuses: Dict[str, str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trip_id": self.trip_id,
            "from_stage": self.from_stage.value,
            "to_stage": self.to_stage.value,
            "updated": self.updated,
            "stage_statuses": self.stage_statuses,
        }


def _load_stage(db: Session, trip_id: int, stage: TripStageEnum) -> Optional[TripStage]:
    return (
        db.query(TripStage)
        .filter(TripStage.trip_id == trip_id, TripStage.stage_name == stage.value)
        .first()
    )


def advance_stage(db: Session, *, trip_id: int, user_id: int, to_stage: TripStageEnum | str) -> StageAdvanceResult | None:
    """Advance a trip to the next stage and update stage rows."""

    target_stage = to_stage if isinstance(to_stage, TripStageEnum) else TripStageEnum(to_stage)
    trip: Trip | None = get_trip(db, trip_id, user_id)
    if trip is None:
        return None

    current_stage = trip.current_stage or TripStageEnum.pre
    if target_stage not in STAGE_SEQUENCE:
        raise ValueError("invalid_stage")

    current_index = STAGE_SEQUENCE.index(current_stage)
    target_index = STAGE_SEQUENCE.index(target_stage)

    if target_index < current_index:
        raise ValueError("cannot_rewind_stage")
    if target_index > current_index + 1:
        raise ValueError("invalid_transition")

    if target_index == current_index:
        stage_rows = (
            db.query(TripStage)
            .filter(TripStage.trip_id == trip_id)
            .all()
        )
        statuses = {row.stage_name: row.status for row in stage_rows}
        return StageAdvanceResult(
            trip_id=trip.id,
            from_stage=current_stage,
            to_stage=target_stage,
            updated=False,
            stage_statuses=statuses,
        )

    current_row = _load_stage(db, trip_id, current_stage)
    if current_row is not None:
        current_row.status = "completed"
        current_row.confirmed_at = datetime.now(timezone.utc)
        db.add(current_row)

    next_row = _load_stage(db, trip_id, target_stage)
    if next_row is not None and next_row.status != "completed":
        next_row.status = "in_progress"
        db.add(next_row)

    trip.current_stage = target_stage
    db.add(trip)

    log_action(
        db,
        action="trip_stage_advanced",
        user_id=user_id,
        trip_id=trip.id,
        detail=f"{current_stage.value}->{target_stage.value}",
    )

    db.commit()
    db.refresh(trip)

    stage_rows = (
        db.query(TripStage)
        .filter(TripStage.trip_id == trip_id)
        .all()
    )
    statuses = {row.stage_name: row.status for row in stage_rows}

    return StageAdvanceResult(
        trip_id=trip.id,
        from_stage=current_stage,
        to_stage=target_stage,
        updated=True,
        stage_statuses=statuses,
    )
