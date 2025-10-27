from __future__ import annotations

from typing import List

import asyncio

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.schemas.common import Envelope
from app.schemas.kb_schemas import KBEntryCreate, KBEntryUpdate, KBEntryResponse
from app.services.kb_service import (
    create_kb_entry,
    get_kb_entries,
    update_kb_entry,
    delete_kb_entry,
    process_entry_embedding,
    remove_entry_vector,
)

router = APIRouter(prefix="/trips/{trip_id}/kb_entries", tags=["kb_entries"])


@router.post("", response_model=Envelope[KBEntryResponse])
async def create_kb_entry_endpoint(
    trip_id: int,
    req: KBEntryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Envelope[KBEntryResponse]:
    """创建新的知识库条目。"""
    entry = create_kb_entry(
        db,
        trip_id=trip_id,
        user_id=current_user.id,
        source=req.source,
        title=req.title,
        content=req.content,
        meta=req.meta,
    )
    asyncio.create_task(process_entry_embedding(entry.id))
    return Envelope(code=0, msg="ok", data=KBEntryResponse.model_validate(entry))


@router.get("", response_model=Envelope[List[KBEntryResponse]])
def list_kb_entries_endpoint(
    trip_id: int,
    q: str | None = None,
    source: str | None = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Envelope[List[KBEntryResponse]]:
    """获取知识库条目列表。"""
    entries = get_kb_entries(
        db,
        trip_id=trip_id,
        user_id=current_user.id,
        q=q,
        source=source,
        limit=limit,
        offset=offset,
    )
    return Envelope(code=0, msg="ok", data=[KBEntryResponse.model_validate(e) for e in entries])


@router.patch("/{entry_id}", response_model=Envelope[KBEntryResponse])
async def update_kb_entry_endpoint(
    trip_id: int,
    entry_id: int,
    req: KBEntryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Envelope[KBEntryResponse]:
    """更新知识库条目。"""
    entry = update_kb_entry(
        db,
        entry_id=entry_id,
        trip_id=trip_id,
        user_id=current_user.id,
        source=req.source,
        title=req.title,
        content=req.content,
        meta=req.meta,
    )
    asyncio.create_task(process_entry_embedding(entry.id))
    return Envelope(code=0, msg="ok", data=KBEntryResponse.model_validate(entry))


@router.delete("/{entry_id}")
async def delete_kb_entry_endpoint(
    trip_id: int,
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Envelope[bool]:
    """删除知识库条目。"""
    delete_kb_entry(db, entry_id=entry_id, trip_id=trip_id, user_id=current_user.id)
    asyncio.create_task(remove_entry_vector(entry_id))
    return Envelope(code=0, msg="ok", data=True)