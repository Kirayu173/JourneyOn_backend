from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.cache.redis_client import get_value, incr, set_value, ping
from app.core.config import settings
from app.db.session import get_db
from app.schemas.common import Envelope
from app.services.embedding_service import embed_texts, health_check as embedding_health
from app.services.qdrant_service import ensure_collection, search as qdrant_search
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


def _rate_limited(user_id: int) -> bool:
    max_req = max(1, settings.RATE_LIMIT_PER_MINUTE)
    counter = incr(f"kb:rate:{user_id}", expire_seconds=_RATE_WINDOW)
    if counter is None:
        # Fallback to in-process rate limiting
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


def _build_filter(filters: Optional[Dict[str, Any]]) -> Optional[qmodels.Filter]:
    if not filters:
        return None
    conditions: List[qmodels.FieldCondition] = []
    for key, value in filters.items():
        if isinstance(value, list):
            conditions.append(
                qmodels.FieldCondition(key=key, match=qmodels.MatchAny(any=value))
            )
        else:
            conditions.append(
                qmodels.FieldCondition(key=key, match=qmodels.MatchValue(value=value))
            )
    if not conditions:
        return None
    return qmodels.Filter(must=conditions)


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


@router.get("/health")
def kb_health() -> Envelope[dict[str, Any]]:
    ok = ensure_collection()
    emb = embedding_health()
    redis_ok = ping()
    return Envelope(
        code=0 if ok else 500,
        msg="ok" if ok else "qdrant_unavailable",
        data={"qdrant": ok, "embedding": emb, "redis": redis_ok},
    )


@router.post("/search")
def kb_search(
    req: SearchRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> Envelope[list[dict[str, Any]]]:
    if _rate_limited(current_user.id):
        raise HTTPException(status_code=429, detail="rate_limited")

    cache_key = _cache_key(current_user.id, req)
    cached = get_value(cache_key)
    if cached:
        try:
            payload = json.loads(cached)
            return Envelope(code=0, msg="ok", data=payload)
        except json.JSONDecodeError:
            logger.debug("Ignoring corrupt cache entry for %s", cache_key)

    vec = embed_texts([req.query])[0]
    filter_ = _build_filter(req.filters)
    points = qdrant_search(vec, top_k=req.top_k, filter_=filter_) if vec else []
    results = [
        {
            "id": int(p.id),
            "score": float(p.score),
            "payload": getattr(p, "payload", {}) or {},
        }
        for p in points
    ]

    # Optional rerank placeholder: maintain input order when not available
    # A real reranker can be integrated via Ollama if exposed.
    if req.rerank and settings.OLLAMA_RERANK_MODEL:
        # TODO: call reranker here when available
        results = results  # keep same order for now

    try:
        set_value(cache_key, json.dumps(results), expire_seconds=_CACHE_TTL)
    except TypeError:
        logger.debug("Failed to serialize cache entry for %s", cache_key)
    return Envelope(code=0, msg="ok", data=results)

