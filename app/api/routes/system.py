from __future__ import annotations

import logging
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.schemas.common import Envelope

router = APIRouter(prefix="/system", tags=["system"])


class LogLevelPatch(BaseModel):
    level: str


@router.patch("/log-level", response_model=Envelope[dict])
def patch_log_level(req: LogLevelPatch, current_user=Depends(get_current_user)) -> Envelope[dict]:
    """Adjust application root log level at runtime.

    Accepts levels like debug, info, warning, error.
    """
    level_upper = req.level.upper()
    if level_upper not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        return Envelope(code=400, msg="invalid_log_level", data={"accepted": ["debug", "info", "warning", "error", "critical"]})
    logging.getLogger().setLevel(level_upper)
    logging.getLogger(__name__).info("Log level changed", extra={"new_level": level_upper})
    return Envelope(code=0, msg="ok", data={"level": level_upper})