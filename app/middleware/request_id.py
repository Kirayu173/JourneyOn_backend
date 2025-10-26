from __future__ import annotations

import time
import uuid
import logging
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.request_context import request_id_var


logger = logging.getLogger(__name__)


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):  # type: ignore[no-untyped-def]
        # Prefer incoming X-Request-ID; otherwise generate
        incoming = request.headers.get("X-Request-ID")
        req_id = incoming or uuid.uuid4().hex
        token = request_id_var.set(req_id)
        start = time.perf_counter()
        try:
            logger.debug("request_start", extra={"method": request.method, "path": str(request.url), "request_id": req_id})
            response = await call_next(request)
            elapsed_ms = (time.perf_counter() - start) * 1000
            response.headers["X-Request-ID"] = req_id
            logger.debug(
                "request_end",
                extra={
                    "method": request.method,
                    "path": str(request.url),
                    "status": response.status_code,
                    "duration_ms": round(elapsed_ms, 2),
                    "request_id": req_id,
                },
            )
            return response
        finally:
            request_id_var.reset(token)