from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.schemas.common import Envelope
from app.schemas.task_schemas import TaskCreate, TaskUpdate, TaskResponse
from app.services.task_service import (
    create_task,
    get_tasks_for_trip,
    update_task,
    delete_task,
)

router = APIRouter(prefix="/trips/{trip_id}/tasks", tags=["tasks"])


@router.post("", response_model=Envelope[TaskResponse])
def create_trip_task(
    trip_id: int,
    payload: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Envelope[TaskResponse]:
    task = create_task(
        db,
        trip_id=trip_id,
        user_id=current_user.id,
        stage=payload.stage,
        title=payload.title,
        description=payload.description,
        priority=payload.priority,
        assigned_to=payload.assigned_to,
        due_date=payload.due_date,
        meta=payload.meta,
    )
    return Envelope(code=0, msg="ok", data=TaskResponse.model_validate(task))


@router.get("", response_model=Envelope[List[TaskResponse]])
def list_trip_tasks(
    trip_id: int,
    stage: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Envelope[List[TaskResponse]]:
    tasks = get_tasks_for_trip(db, trip_id=trip_id, user_id=current_user.id, stage=stage)
    return Envelope(code=0, msg="ok", data=[TaskResponse.model_validate(t) for t in tasks])


@router.patch("/{task_id}", response_model=Envelope[TaskResponse])
def patch_trip_task(
    trip_id: int,
    task_id: int,
    payload: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Envelope[TaskResponse]:
    # Ensure trip ownership implicitly via service update
    try:
        updated = update_task(
            db,
            task_id=task_id,
            user_id=current_user.id,
            title=payload.title,
            description=payload.description,
            priority=payload.priority,
            assigned_to=payload.assigned_to,
            due_date=payload.due_date,
            status=payload.status,
            meta=payload.meta,
        )
    except HTTPException as e:
        if e.status_code == 404:
            # Either trip or task not found
            raise
        raise
    return Envelope(code=0, msg="ok", data=TaskResponse.model_validate(updated))


@router.delete("/{task_id}", response_model=Envelope[None])
def delete_trip_task(
    trip_id: int,
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Envelope[None]:
    delete_task(db, task_id=task_id, user_id=current_user.id)
    return Envelope(code=0, msg="ok", data=None)