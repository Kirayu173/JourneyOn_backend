from __future__ import annotations

from datetime import date
from typing import Optional, Sequence

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.models import Task
from app.services.trip_service import get_trip


def _ensure_trip_ownership(db: Session, trip_id: int, user_id: int) -> None:
    trip = get_trip(db, trip_id, user_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="trip_not_found")


def create_task(
    db: Session,
    *,
    trip_id: int,
    user_id: int,
    stage: str,
    title: str,
    description: Optional[str] = None,
    priority: int = 1,
    assigned_to: Optional[str] = None,
    due_date: Optional[date] = None,
    meta: Optional[dict] = None,
) -> Task:
    """Create a task under a trip owned by the user."""
    _ensure_trip_ownership(db, trip_id, user_id)
    task = Task(
        trip_id=trip_id,
        stage=stage,
        title=title,
        description=description,
        priority=priority,
        assigned_to=assigned_to,
        due_date=due_date,
        meta=meta or {},
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def get_tasks_for_trip(
    db: Session, *, trip_id: int, user_id: int, stage: Optional[str] = None
) -> Sequence[Task]:
    """List tasks for a trip owned by the user, optionally filtered by stage."""
    _ensure_trip_ownership(db, trip_id, user_id)
    q = db.query(Task).filter(Task.trip_id == trip_id)
    if stage:
        q = q.filter(Task.stage == stage)
    return q.order_by(Task.id.desc()).all()


def get_task_by_id(db: Session, *, task_id: int) -> Optional[Task]:
    return db.query(Task).filter(Task.id == task_id).first()


def update_task_status(db: Session, *, task_id: int, user_id: int, new_status: str) -> Task:
    """Update status for a task if it belongs to a user's trip."""
    task = get_task_by_id(db, task_id=task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task_not_found")
    # Verify ownership via trip
    _ensure_trip_ownership(db, task.trip_id, user_id)
    task.status = new_status
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def update_task(
    db: Session,
    *,
    task_id: int,
    user_id: int,
    title: Optional[str] = None,
    description: Optional[str] = None,
    priority: Optional[int] = None,
    assigned_to: Optional[str] = None,
    due_date: Optional[date] = None,
    status: Optional[str] = None,
    meta: Optional[dict] = None,
) -> Task:
    """General task update with ownership check."""
    task = get_task_by_id(db, task_id=task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task_not_found")
    _ensure_trip_ownership(db, task.trip_id, user_id)

    if title is not None:
        task.title = title
    if description is not None:
        task.description = description
    if priority is not None:
        task.priority = priority
    if assigned_to is not None:
        task.assigned_to = assigned_to
    if due_date is not None:
        task.due_date = due_date
    if status is not None:
        task.status = status
    if meta is not None:
        task.meta = meta

    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def delete_task(db: Session, *, task_id: int, user_id: int) -> None:
    task = get_task_by_id(db, task_id=task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task_not_found")
    _ensure_trip_ownership(db, task.trip_id, user_id)
    db.delete(task)
    db.commit()