from __future__ import annotations

import time
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.schemas.common import Envelope
from app.services.embedding_service import embed_texts, health_check as embedding_health
from app.services.qdrant_service import ensure_collection, search as qdrant_search

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


_rate_bucket: dict[int, List[float]] = {}
_search_cache: dict[tuple, tuple[float, list[dict]]] = {}
_CACHE_TTL = 30.0


def _rate_limited(user_id: int) -> bool:
    now = time.time()
    window = 60.0
    max_req = max(1, settings.RATE_LIMIT_PER_MINUTE)
    lst = _rate_bucket.setdefault(user_id, [])
    lst[:] = [t for t in lst if now - t <= window]
    if len(lst) >= max_req:
        return True
    lst.append(now)
    return False


@router.get("/health")
def kb_health() -> Envelope[dict[str, Any]]:
    ok = ensure_collection()
    emb = embedding_health()
    return Envelope(code=0 if ok else 500, msg="ok" if ok else "qdrant_unavailable", data={"qdrant": ok, "embedding": emb})


@router.post("/search")
def kb_search(
    req: SearchRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> Envelope[list[dict[str, Any]]]:
    if _rate_limited(current_user.id):
        raise HTTPException(status_code=429, detail="rate_limited")

    key = (current_user.id, req.query, req.top_k, req.rerank)
    cached = _search_cache.get(key)
    now = time.time()
    if cached and now - cached[0] < _CACHE_TTL:
        return Envelope(code=0, msg="ok", data=cached[1])

    vec = embed_texts([req.query])[0]
    points = qdrant_search(vec, top_k=req.top_k) if vec else []
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

    _search_cache[key] = (now, results)
    return Envelope(code=0, msg="ok", data=results)

