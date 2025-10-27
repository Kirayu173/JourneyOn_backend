from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.schemas.common import Envelope
from app.schemas.tag_schemas import (
    UserTagCreate,
    UserTagUpdate,
    UserTagUpsert,
    UserTagResponse,
)
from app.services.tag_service import (
    create_user_tag,
    get_user_tags,
    update_user_tag,
    delete_user_tag,
    bulk_upsert_user_tags,
)

router = APIRouter(prefix="/user_tags", tags=["user_tags"])


@router.post("", response_model=Envelope[UserTagResponse])
def create_user_tag_endpoint(
    req: UserTagCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Envelope[UserTagResponse]:
    """创建用户标签。"""
    item = create_user_tag(
        db,
        user_id=current_user.id,
        tag=req.tag,
        weight=req.weight,
        source_trip_id=req.source_trip_id,
    )
    return Envelope(code=0, msg="ok", data=UserTagResponse.model_validate(item))


@router.get("", response_model=Envelope[List[UserTagResponse]])
def list_user_tags_endpoint(
    tag: str | None = None,
    source_trip_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Envelope[List[UserTagResponse]]:
    """获取用户标签列表。"""
    items = get_user_tags(
        db,
        user_id=current_user.id,
        tag=tag,
        source_trip_id=source_trip_id,
        limit=limit,
        offset=offset,
    )
    return Envelope(code=0, msg="ok", data=[UserTagResponse.model_validate(i) for i in items])


@router.patch("/{tag_id}", response_model=Envelope[UserTagResponse])
def update_user_tag_endpoint(
    tag_id: int,
    req: UserTagUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Envelope[UserTagResponse]:
    """更新用户标签。"""
    item = update_user_tag(
        db,
        user_id=current_user.id,
        tag_id=tag_id,
        tag=req.tag,
        weight=req.weight,
        source_trip_id=req.source_trip_id,
    )
    return Envelope(code=0, msg="ok", data=UserTagResponse.model_validate(item))


@router.delete("/{tag_id}")
def delete_user_tag_endpoint(
    tag_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Envelope[bool]:
    """删除用户标签。"""
    delete_user_tag(db, user_id=current_user.id, tag_id=tag_id)
    return Envelope(code=0, msg="ok", data=True)


@router.post("/bulk_upsert", response_model=Envelope[List[UserTagResponse]])
def bulk_upsert_user_tags_endpoint(
    req: list[UserTagUpsert],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Envelope[List[UserTagResponse]]:
    """批量创建或更新用户标签。"""
    items = bulk_upsert_user_tags(
        db,
        user_id=current_user.id,
        items=[r.model_dump() for r in req],
    )
    return Envelope(code=0, msg="ok", data=[UserTagResponse.model_validate(i) for i in items])