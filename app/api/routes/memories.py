from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.models import User
from app.schemas.common import Envelope
from app.services.memory_service import get_memory_service


router = APIRouter(prefix="/memories", tags=["memories"])


class MessageItem(BaseModel):
    role: str = Field(..., examples=["user", "assistant", "system"])
    content: str
    name: Optional[str] = None


class AddRequest(BaseModel):
    messages: List[MessageItem]
    metadata: Optional[Dict[str, Any]] = None
    infer: Optional[bool] = None
    agent_id: Optional[str] = None
    run_id: Optional[str] = None


class SearchRequest(BaseModel):
    query: str
    top_k: int = 10
    threshold: Optional[float] = None
    filters: Optional[Dict[str, Any]] = None


@router.post("/add", response_model=Envelope[Dict[str, Any] | None])
async def mem_add(
    req: AddRequest,
    current_user: User = Depends(get_current_user),
) -> Envelope[Dict[str, Any] | None]:
    if not settings.MEMORY_ENABLED:
        return Envelope(code=0, msg="memory_disabled", data=None)
    svc = get_memory_service()
    result = svc.add_messages(
        [m.model_dump() for m in req.messages],
        user_id=str(current_user.id),
        agent_id=req.agent_id,
        run_id=req.run_id,
        metadata=req.metadata or {},
        infer=req.infer,
    )
    return Envelope(code=0, msg="ok", data=result)


@router.post("/search", response_model=Envelope[List[Dict[str, Any]]])
async def mem_search(
    req: SearchRequest,
    current_user: User = Depends(get_current_user),
) -> Envelope[List[Dict[str, Any]]]:
    if not settings.MEMORY_ENABLED:
        return Envelope(code=0, msg="memory_disabled", data=[])
    svc = get_memory_service()
    filters = req.filters or {}
    # Always scope to current user unless explicitly overridden
    filters.setdefault("user_id", str(current_user.id))
    data = svc.search(req.query, top_k=req.top_k, filters=filters, threshold=req.threshold)
    return Envelope(code=0, msg="ok", data=data)


@router.get("/search", response_model=Envelope[List[Dict[str, Any]]])
async def mem_search_get(
    q: str,
    top_k: int = 10,
    threshold: Optional[float] = None,
    filters: Optional[str] = None,
    current_user: User = Depends(get_current_user),
) -> Envelope[List[Dict[str, Any]]]:
    if not settings.MEMORY_ENABLED:
        return Envelope(code=0, msg="memory_disabled", data=[])
    try:
        parsed_filters = json.loads(filters) if filters else None
        if parsed_filters is not None and not isinstance(parsed_filters, dict):
            raise ValueError
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(status_code=400, detail="invalid_filters")
    svc = get_memory_service()
    f = parsed_filters or {}
    f.setdefault("user_id", str(current_user.id))
    data = svc.search(q, top_k=top_k, filters=f, threshold=threshold)
    return Envelope(code=0, msg="ok", data=data)


@router.get("/{memory_id}", response_model=Envelope[Dict[str, Any] | None])
async def mem_get(
    memory_id: str,
    current_user: User = Depends(get_current_user),
) -> Envelope[Dict[str, Any] | None]:
    if not settings.MEMORY_ENABLED:
        return Envelope(code=0, msg="memory_disabled", data=None)
    svc = get_memory_service()
    mem = svc.get(memory_id)
    return Envelope(code=0, msg="ok", data=mem)


class UpdateRequest(BaseModel):
    text: str


@router.put("/{memory_id}", response_model=Envelope[Dict[str, Any] | None])
async def mem_update(
    memory_id: str,
    req: UpdateRequest,
    current_user: User = Depends(get_current_user),
) -> Envelope[Dict[str, Any] | None]:
    if not settings.MEMORY_ENABLED:
        return Envelope(code=0, msg="memory_disabled", data=None)
    svc = get_memory_service()
    data = svc.update(memory_id, req.text)
    return Envelope(code=0, msg="ok", data=data)


@router.delete("/{memory_id}", response_model=Envelope[Dict[str, Any] | None])
async def mem_delete(
    memory_id: str,
    current_user: User = Depends(get_current_user),
) -> Envelope[Dict[str, Any] | None]:
    if not settings.MEMORY_ENABLED:
        return Envelope(code=0, msg="memory_disabled", data=None)
    svc = get_memory_service()
    data = svc.delete(memory_id)
    return Envelope(code=0, msg="ok", data=data)


@router.get("/{memory_id}/history", response_model=Envelope[List[Dict[str, Any]]])
async def mem_history(
    memory_id: str,
    current_user: User = Depends(get_current_user),
) -> Envelope[List[Dict[str, Any]]]:
    if not settings.MEMORY_ENABLED:
        return Envelope(code=0, msg="memory_disabled", data=[])
    svc = get_memory_service()
    data = svc.history(memory_id)
    return Envelope(code=0, msg="ok", data=data)


class DeleteAllRequest(BaseModel):
    filters: Dict[str, Any]


@router.post("/delete_all", response_model=Envelope[Dict[str, Any] | None])
async def mem_delete_all(
    req: DeleteAllRequest,
    current_user: User = Depends(get_current_user),
) -> Envelope[Dict[str, Any] | None]:
    if not settings.MEMORY_ENABLED:
        return Envelope(code=0, msg="memory_disabled", data=None)
    svc = get_memory_service()
    filters = dict(req.filters)
    filters.setdefault("user_id", str(current_user.id))
    data = svc.delete_all(filters=filters)
    return Envelope(code=0, msg="ok", data=data)

