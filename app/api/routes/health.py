from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import redis
import httpx

from app.core.config import settings
from app.db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Basic health check for DB, Redis, and optional Qdrant."""
    # DB check
    db_ok = True
    try:
        db.execute("SELECT 1")
    except Exception:
        db_ok = False

    # Redis check
    redis_ok = True
    try:
        r = redis.Redis.from_url(settings.REDIS_URL)
        redis_ok = r.ping()
    except Exception:
        redis_ok = False

    # Qdrant check (optional)
    qdrant_ok = None
    if settings.QDRANT_URL:
        try:
            resp = httpx.get(f"{settings.QDRANT_URL}/readyz", timeout=2)
            qdrant_ok = resp.status_code == 200
        except Exception:
            qdrant_ok = False

    return {
        "code": 0,
        "msg": "ok" if db_ok and redis_ok else "degraded",
        "data": {
            "db": db_ok,
            "redis": redis_ok,
            "qdrant": qdrant_ok,
        },
    }