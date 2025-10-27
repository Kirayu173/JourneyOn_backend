from __future__ import annotations

from contextvars import ContextVar

# 上下文变量，存储请求ID用于日志关联
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)