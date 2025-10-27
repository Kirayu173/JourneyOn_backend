from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.db.models import User
from app.schemas.common import Envelope

router = APIRouter(prefix="/system", tags=["system"])


class LogLevelPatch(BaseModel):
    level: str


@router.patch("/log-level", response_model=Envelope[Dict[str, Any]])
def patch_log_level(
    req: LogLevelPatch, current_user: User = Depends(get_current_user)
) -> Envelope[Dict[str, Any]]:
    """运行时调整应用程序根日志级别。
    
    接受debug、info、warning、error等日志级别。
    """
    level_upper = req.level.upper()
    if level_upper not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        return Envelope(code=400, msg="invalid_log_level", data={"accepted": ["debug", "info", "warning", "error", "critical"]})
    logging.getLogger().setLevel(level_upper)
    logging.getLogger(__name__).info("Log level changed", extra={"new_level": level_upper})
    return Envelope(code=0, msg="ok", data={"level": level_upper})