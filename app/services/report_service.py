from __future__ import annotations

from typing import Optional, Sequence

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.models import Report
from app.services.audit_service import log_action
from app.services.trip_service import get_trip


def _ensure_trip(db: Session, *, trip_id: int, user_id: int) -> None:
    if get_trip(db, trip_id, user_id) is None:
        raise HTTPException(status_code=404, detail="trip_not_found")


def create_report(
    db: Session,
    *,
    trip_id: int,
    user_id: int,
    filename: str | None,
    format: str | None,
    content_type: str | None,
    file_size: int | None,
    storage_key: str,
    meta: Optional[dict] = None,
) -> Report:
    _ensure_trip(db, trip_id=trip_id, user_id=user_id)
    report = Report(
        trip_id=trip_id,
        filename=filename,
        format=format,
        content_type=content_type,
        file_size=file_size,
        storage_key=storage_key,
        meta=meta or {},
    )
    db.add(report)
    db.flush()
    log_action(
        db,
        action="report_created",
        user_id=user_id,
        trip_id=trip_id,
        detail=f"report_id={report.id}",
    )
    db.commit()
    db.refresh(report)
    return report


def list_reports(db: Session, *, trip_id: int, user_id: int) -> Sequence[Report]:
    _ensure_trip(db, trip_id=trip_id, user_id=user_id)
    return (
        db.query(Report)
        .filter(Report.trip_id == trip_id)
        .order_by(Report.created_at.desc())
        .all()
    )


def get_report(
    db: Session,
    *,
    report_id: int,
    user_id: int,
    trip_id: Optional[int] = None,
) -> Report:
    report = db.query(Report).filter(Report.id == report_id).first()
    if report is None:
        raise HTTPException(status_code=404, detail="report_not_found")
    _ensure_trip(db, trip_id=report.trip_id, user_id=user_id)
    if trip_id is not None and report.trip_id != trip_id:
        raise HTTPException(status_code=404, detail="report_not_found")
    return report


def delete_report(db: Session, *, report_id: int, user_id: int, trip_id: int) -> str:
    report = get_report(db, report_id=report_id, user_id=user_id, trip_id=trip_id)
    storage_key = report.storage_key
    db.delete(report)
    log_action(
        db,
        action="report_deleted",
        user_id=user_id,
        trip_id=trip_id,
        detail=f"report_id={report.id}",
    )
    db.commit()
    return storage_key
