from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any, Dict, List, Optional, TypeAlias, cast

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.cache.redis_client import get_value, incr, set_value, ping
from app.core.config import settings
from app.db.models import User
from app.db.session import get_db
from app.schemas.common import Envelope
from app.services.embedding_service import EmbeddingService
from app.services.kb_service import get_qdrant_service, rerank_results
from qdrant_client.http import models as qmodels

router = APIRouter(prefix="/kb", tags=["kb"])


class IngestItem(BaseModel):
    trip_id: int
    source: Optional[str] = None
    title: Optional[str] = Field(None, max_length=255)
    content: Optional[str] = None
    meta: Optional[dict] = None


class SearchRequest(BaseModel):
    query: str
    top_k: int = 10
    rerank: bool = False
    filters: Optional[Dict[str, Any]] = None


_CACHE_TTL = 30
_RATE_WINDOW = 60
logger = logging.getLogger(__name__)


async def _rate_limited(user_id: int) -> bool:
    max_req = max(1, settings.RATE_LIMIT_PER_MINUTE)
    counter = await incr(f"kb:rate:{user_id}", expire_seconds=_RATE_WINDOW)
    if counter is None:
        return _rate_limited_local(user_id, max_req)
    return counter > max_req


_local_rate: dict[int, List[float]] = {}


def _rate_limited_local(user_id: int, max_req: int) -> bool:
    now = time.time()
    entries = _local_rate.setdefault(user_id, [])
    entries[:] = [t for t in entries if now - t <= _RATE_WINDOW]
    if len(entries) >= max_req:
        return True
    entries.append(now)
    return False


ConditionType: TypeAlias = (
    qmodels.FieldCondition
    | qmodels.IsEmptyCondition
    | qmodels.IsNullCondition
    | qmodels.HasIdCondition
    | qmodels.NestedCondition
    | qmodels.Filter
)


def _build_filter(filters: Optional[Dict[str, Any]]) -> Optional[qmodels.Filter]:
    if not filters:
        return None
    conditions: List[ConditionType] = []
    for key, value in filters.items():
        if isinstance(value, list):
            conditions.append(
                qmodels.FieldCondition(key=key, match=qmodels.MatchAny(any=value))
            )
        else:
            conditions.append(
                qmodels.FieldCondition(key=key, match=qmodels.MatchValue(value=value))
            )
    return qmodels.Filter(must=conditions) if conditions else None


def _cache_key(user_id: int, payload: SearchRequest) -> str:
    data = {
        "user": user_id,
        "query": payload.query,
        "top_k": payload.top_k,
        "rerank": payload.rerank,
        "filters": payload.filters or {},
    }
    digest = hashlib.sha256(json.dumps(data, sort_keys=True).encode("utf-8")).hexdigest()
    return f"kb:search:{digest}"


_embedding_service: EmbeddingService | None = None


def _get_embedding_service() -> EmbeddingService | None:
    global _embedding_service
    if _embedding_service is not None:
        return _embedding_service
    try:
        _embedding_service = EmbeddingService()
    except RuntimeError:
        logger.warning("embedding_service_not_configured")
        _embedding_service = None
    return _embedding_service


@router.get("/health")
async def kb_health() -> Envelope[dict[str, Any]]:
    """知识库向量健康检查。"""
    qdrant = await get_qdrant_service()
    qdrant_ok = await qdrant.ensure_collection() if qdrant else False
    embedding_service = _get_embedding_service()
    emb_status = (
        await embedding_service.health()
        if embedding_service
        else {"ok": False, "detail": "disabled"}
    )
    redis_ok = await ping()
    return Envelope(
        code=0 if qdrant_ok else 500,
        msg="ok" if qdrant_ok else "qdrant_unavailable",
        data={"qdrant": qdrant_ok, "embedding": emb_status, "redis": redis_ok},
    )


async def _search_impl(
    req: SearchRequest,
    db: Session,
    current_user: User,
) -> Envelope[list[dict[str, Any]]]:
    """知识库搜索实现。"""
    if await _rate_limited(current_user.id):
        raise HTTPException(status_code=429, detail="rate_limited")

    cache_key = _cache_key(current_user.id, req)
    cached = await get_value(cache_key)
    if cached:
        try:
            payload = json.loads(cached)
            if isinstance(payload, list):
                data = cast(list[dict[str, Any]], payload)
                return Envelope(code=0, msg="ok", data=data)
        except json.JSONDecodeError:
            logger.debug("Ignoring corrupt cache entry for %s", cache_key)

    embedding_service = _get_embedding_service()
    if embedding_service is None:
        logger.warning("embedding_service_unavailable")
        return Envelope(code=0, msg="embedding_disabled", data=[])

    vector = await embedding_service.embed(req.query)
    filter_ = _build_filter(req.filters)
    qdrant = await get_qdrant_service()
    if qdrant is None:
        logger.warning("qdrant_unavailable")
        return Envelope(code=0, msg="kb_unavailable", data=[])
    points = await qdrant.search(vector, top_k=req.top_k, filter_=filter_) if vector else []

    results: list[dict[str, Any]] = []
    for point in points:
        payload_obj = getattr(point, "payload", {}) or {}
        payload = payload_obj if isinstance(payload_obj, dict) else {}
        results.append(
            {
                "id": int(point.id),
                "score": float(point.score),
                "payload": payload,
            }
        )

    if req.rerank and settings.OLLAMA_RERANK_ENABLED:
        try:
            results = await rerank_results(req.query, results)
        except Exception:
            logger.exception("rerank_failed")

    final_payload: list[dict[str, Any]] = []
    for item in results:
        payload = item.get("payload")
        payload_dict = payload if isinstance(payload, dict) else {}
        entry_id = payload_dict.get("entry_id", item.get("id"))
        title = payload_dict.get("title")
        score_value = item.get("score", 0.0)
        try:
            similarity = round(float(score_value), 4)
        except (TypeError, ValueError):
            similarity = 0.0
        final_payload.append({"id": entry_id, "title": title, "similarity": similarity})

    try:
        await set_value(cache_key, json.dumps(final_payload), expire_seconds=_CACHE_TTL)
    except TypeError:
        logger.debug("Failed to serialize cache entry for %s", cache_key)
    return Envelope(code=0, msg="ok", data=final_payload)


@router.post("/search")
async def kb_search(
    req: SearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Envelope[list[dict[str, Any]]]:
    """POST方式搜索知识库。"""
    return await _search_impl(req, db, current_user)


@router.get("/search")
async def kb_search_get(
    q: str,
    top_k: int = 10,
    rerank: bool = False,
    filters: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Envelope[list[dict[str, Any]]]:
    """GET方式搜索知识库。"""
    try:
        filter_payload = json.loads(filters) if filters else None
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="invalid_filters")
    req = SearchRequest(query=q, top_k=top_k, rerank=rerank, filters=filter_payload)
    return await _search_impl(req, db, current_user)


