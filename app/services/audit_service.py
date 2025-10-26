from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy.orm import Session

from app.db.models import AuditLog


def log_action(
    db: Session,
    *,
    action: str,
    user_id: Optional[int] = None,
    trip_id: Optional[int] = None,
    detail: Optional[str] = None,
) -> AuditLog:
    """Persist an audit log entry without committing the transaction."""

    log = AuditLog(
        user_id=user_id,
        trip_id=trip_id,
        action=action,
        detail=detail,
    )
    db.add(log)
    return log


def list_logs(
    db: Session,
    *,
    limit: int = 100,
    offset: int = 0,
    user_id: Optional[int] = None,
    trip_id: Optional[int] = None,
) -> Sequence[AuditLog]:
    """Fetch audit logs with optional filters."""

    query = db.query(AuditLog)
    if user_id is not None:
        query = query.filter(AuditLog.user_id == user_id)
    if trip_id is not None:
        query = query.filter(AuditLog.trip_id == trip_id)
    return query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()
