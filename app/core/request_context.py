from __future__ import annotations

from contextvars import ContextVar

# Context variable storing request id for logging correlation
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)