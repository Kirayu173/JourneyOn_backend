from __future__ import annotations

import asyncio

import pytest

from app.core.config import settings
from app.llm.client import ChatResponse
from app.utils import dependency_check


def test_check_redis_skipped_without_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "REDIS_URL", None)
    result = asyncio.run(dependency_check.check_redis_connection())
    assert result.status == "skipped"
    assert "not configured" in result.detail


def test_check_redis_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "REDIS_URL", "redis://example")

    async def fake_ping() -> bool:
        return True

    monkeypatch.setattr(dependency_check, "redis_ping", fake_ping)
    result = asyncio.run(dependency_check.check_redis_connection())
    assert result.status == "ok"
    assert result.detail == "connected"


def test_check_qdrant_skipped_without_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "QDRANT_URL", None)
    result = asyncio.run(dependency_check.check_qdrant_connection())
    assert result.status == "skipped"


def test_check_qdrant_failure_when_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "QDRANT_URL", "http://localhost:6333")

    async def fake_get_service():
        return None

    monkeypatch.setattr(dependency_check, "get_qdrant_service", fake_get_service)
    result = asyncio.run(dependency_check.check_qdrant_connection())
    assert result.status == "failed"
    assert "unavailable" in result.detail


def test_check_llm_skipped_without_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "LLM_PROVIDER", "ollama")
    monkeypatch.setattr(settings, "OLLAMA_URL", None)
    result = asyncio.run(dependency_check.check_llm_connection())
    assert result.status == "skipped"


def test_check_llm_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "LLM_PROVIDER", "ollama")
    monkeypatch.setattr(settings, "OLLAMA_URL", "http://ollama")

    class DummyClient:
        async def chat(self, messages):
            return ChatResponse(content="pong", run_id="123")

    async def fake_get_client():
        return DummyClient()

    monkeypatch.setattr(dependency_check, "get_llm_client", fake_get_client)
    result = asyncio.run(dependency_check.check_llm_connection())
    assert result.status == "ok"
    assert "responded" in result.detail


def test_check_embedding_skipped_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ENABLE_EMBEDDING", False)
    result = asyncio.run(dependency_check.check_embedding_service())
    assert result.status == "skipped"


def test_check_embedding_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ENABLE_EMBEDDING", True)
    monkeypatch.setattr(settings, "OLLAMA_URL", "http://ollama")

    class DummyEmbeddingService:
        async def health(self) -> dict[str, object]:
            return {"ok": True, "model": "dummy"}

    monkeypatch.setattr(dependency_check, "EmbeddingService", DummyEmbeddingService)
    result = asyncio.run(dependency_check.check_embedding_service())
    assert result.status == "ok"
    assert "dummy" in result.detail
