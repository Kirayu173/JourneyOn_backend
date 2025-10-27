from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """注册异常处理器以产生统一的信封响应。"""

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        logger.warning("HTTP异常", extra={"path": str(request.url), "detail": exc.detail})
        return JSONResponse(status_code=exc.status_code, content={"code": exc.status_code, "msg": str(exc.detail), "data": None})

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        logger.warning("验证错误", extra={"path": str(request.url), "errors": exc.errors()})
        return JSONResponse(status_code=422, content={"code": 422, "msg": "validation_error", "data": exc.errors()})

    @app.middleware("http")
    async def catch_unhandled_exceptions(request: Request, call_next):  # type: ignore[no-untyped-def]
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            logger.exception("未处理的异常", extra={"path": str(request.url)})
            return JSONResponse(status_code=500, content={"code": 500, "msg": "internal_error", "data": str(exc)})