"""Utilities for verifying external service dependencies.

This module provides async helpers that probe Redis, Qdrant, the embedding
service, and the configured large language model provider.  The helpers return
structured results that can be surfaced in health checks or diagnostics
scripts so developers can quickly identify missing configuration or
connectivity problems before working on agent logic.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Iterable, List, Literal

from app.cache.redis_client import ping as redis_ping
from app.core.config import settings
from app.llm.client import ChatResponse, LLMError, get_llm_client
from app.services.embedding_service import EmbeddingService, EmbeddingError
from app.services.kb_service import get_qdrant_service


CheckStatus = Literal["ok", "failed", "skipped"]


@dataclass(slots=True)
class DependencyCheckResult:
    """Represents the outcome of verifying one external dependency."""

    name: str
    status: CheckStatus
    detail: str

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation of the result."""

        return asdict(self)


def _skip(name: str, reason: str) -> DependencyCheckResult:
    return DependencyCheckResult(name=name, status="skipped", detail=reason)


def _failure(name: str, reason: str) -> DependencyCheckResult:
    return DependencyCheckResult(name=name, status="failed", detail=reason)


def _success(name: str, detail: str) -> DependencyCheckResult:
    return DependencyCheckResult(name=name, status="ok", detail=detail)


async def check_redis_connection() -> DependencyCheckResult:
    """Verify Redis connectivity using the configured client."""

    if not settings.REDIS_URL:
        return _skip("redis", "REDIS_URL not configured")
    try:
        ok = await redis_ping()
    except Exception as exc:  # pragma: no cover - safety net
        return _failure("redis", f"ping raised {exc.__class__.__name__}")
    if not ok:
        return _failure("redis", "ping failed")
    return _success("redis", "connected")


async def check_qdrant_connection() -> DependencyCheckResult:
    """Ensure the configured Qdrant collection is reachable."""

    if not settings.QDRANT_URL:
        return _skip("qdrant", "QDRANT_URL not configured")
    service = await get_qdrant_service()
    if service is None:
        return _failure("qdrant", "service unavailable")
    try:
        ok = await service.ensure_collection()
    except Exception as exc:  # pragma: no cover - safety net
        return _failure("qdrant", f"ensure_collection raised {exc.__class__.__name__}")
    if not ok:
        return _failure("qdrant", "unable to access collection")
    return _success("qdrant", "collection ready")


async def check_embedding_service() -> DependencyCheckResult:
    """Perform a lightweight probe against the embedding provider."""

    if not settings.ENABLE_EMBEDDING:
        return _skip("embedding", "embeddings disabled via settings")
    try:
        service = EmbeddingService()
    except RuntimeError as exc:
        return _failure("embedding", str(exc))
    except Exception as exc:  # pragma: no cover - safety net
        return _failure("embedding", f"initialisation failed: {exc.__class__.__name__}")

    try:
        status = await service.health()
    except EmbeddingError as exc:
        return _failure("embedding", str(exc))
    except Exception as exc:  # pragma: no cover - safety net
        return _failure("embedding", f"health check raised {exc.__class__.__name__}")

    ok = bool(status.get("ok"))
    detail = "model reachable" if ok else "provider reported not ok"
    if model := status.get("model"):
        detail = f"{detail} ({model})"
    return _success("embedding", detail) if ok else _failure("embedding", detail)


def _llm_configured() -> tuple[bool, str | None]:
    provider = (settings.LLM_PROVIDER or "ollama").lower()
    if provider == "zhipu":
        if not settings.ZHIPU_API_KEY:
            return False, "ZHIPU_API_KEY not configured"
        return True, None
    if not settings.OLLAMA_URL:
        return False, "OLLAMA_URL not configured"
    return True, None


async def check_llm_connection() -> DependencyCheckResult:
    """Issue a minimal chat request against the configured LLM provider."""

    configured, reason = _llm_configured()
    if not configured:
        return _skip("llm", reason or "provider not configured")

    try:
        client = await get_llm_client()
    except RuntimeError as exc:
        return _failure("llm", str(exc))
    except Exception as exc:  # pragma: no cover - safety net
        return _failure("llm", f"client initialisation failed: {exc.__class__.__name__}")

    messages = [
        {"role": "system", "content": "You are a health probe."},
        {"role": "user", "content": "ping"},
    ]
    try:
        response = await client.chat(messages)
    except LLMError as exc:
        detail = f"request failed ({exc.status_code or 'no status'})"
        return _failure("llm", detail)
    except Exception as exc:  # pragma: no cover - safety net
        return _failure("llm", f"chat raised {exc.__class__.__name__}")

    if isinstance(response, ChatResponse) and response.content:
        snippet = response.content.strip()[:40]
        return _success("llm", f"responded: {snippet or 'empty response'}")
    return _failure("llm", "empty response from provider")


async def run_dependency_checks() -> List[DependencyCheckResult]:
    """Run all dependency probes sequentially and collect results."""

    checks: Iterable = (
        check_redis_connection,
        check_qdrant_connection,
        check_embedding_service,
        check_llm_connection,
    )
    results: List[DependencyCheckResult] = []
    for check in checks:
        results.append(await check())
    return results


__all__ = [
    "CheckStatus",
    "DependencyCheckResult",
    "check_redis_connection",
    "check_qdrant_connection",
    "check_embedding_service",
    "check_llm_connection",
    "run_dependency_checks",
]
