import sys
from types import ModuleType
from typing import Any, Dict, List

import pytest

from app.services import memory_service
from app.services.memory_service import MemoryService


class DummyMemory:
    def __init__(self, config: Any) -> None:
        self.config = config
        self.calls: List[Dict[str, Any]] = []
        self.storage: Dict[str, str] = {}
        self.histories: Dict[str, List[Dict[str, Any]]] = {}
        self._counter = 0

    def add(self, messages: List[Dict[str, Any]], **kwargs: Any) -> Dict[str, Any]:
        self.calls.append({"method": "add", "messages": messages, "kwargs": kwargs})
        self._counter += 1
        memory_id = kwargs.get("memory_id") or f"mem-{self._counter}"
        text = "\n".join(m.get("content", "") for m in messages)
        self.storage[memory_id] = text
        self.histories.setdefault(memory_id, []).append({"text": text, "messages": messages})
        payload = {"id": memory_id, "messages": messages, **kwargs}
        return payload

    def search(self, query: str, *, limit: int, filters: Dict[str, Any], threshold: float | None) -> List[Dict[str, Any]]:
        self.calls.append({
            "method": "search",
            "query": query,
            "limit": limit,
            "filters": filters,
            "threshold": threshold,
        })
        results: List[Dict[str, Any]] = []
        for memory_id, text in self.storage.items():
            if query and query not in text:
                continue
            results.append({
                "id": memory_id,
                "text": text,
                "metadata": filters,
            })
        return results[:limit] or [{"id": "mem-1", "query": query, "filters": filters}]

    def update(self, memory_id: str, text: str) -> Dict[str, Any]:
        self.calls.append({"method": "update", "memory_id": memory_id, "text": text})
        self.storage[memory_id] = text
        self.histories.setdefault(memory_id, []).append({"text": text})
        return {"id": memory_id, "text": text}

    def delete(self, memory_id: str) -> Dict[str, Any]:
        self.calls.append({"method": "delete", "memory_id": memory_id})
        self.storage.pop(memory_id, None)
        self.histories.pop(memory_id, None)
        return {"id": memory_id, "deleted": True}

    def get(self, memory_id: str) -> Dict[str, Any]:
        self.calls.append({"method": "get", "memory_id": memory_id})
        return {"id": memory_id, "text": self.storage.get(memory_id, "")}

    def delete_all(self, *, user_id: str | None = None, agent_id: str | None = None, run_id: str | None = None) -> Dict[str, Any]:
        self.calls.append({
            "method": "delete_all",
            "user_id": user_id,
            "agent_id": agent_id,
            "run_id": run_id,
        })
        self.storage.clear()
        self.histories.clear()
        return {"deleted": True, "user_id": user_id, "agent_id": agent_id, "run_id": run_id}

    def history(self, memory_id: str) -> List[Dict[str, Any]]:
        self.calls.append({"method": "history", "memory_id": memory_id})
        return self.histories.get(memory_id, [{"id": memory_id, "text": "stub-history"}])


class DummyMemoryConfig:
    def __init__(
        self,
        vector_store: Any | None = None,
        embedder: Any | None = None,
        llm: Any | None = None,
        history_db_path: str | None = None,
    ) -> None:
        self.vector_store = vector_store
        self.embedder = embedder
        self.llm = llm
        self.history_db_path = history_db_path or "history.sqlite"


class DummyVectorStoreConfig:
    def __init__(self, provider: str, config: Dict[str, Any]) -> None:
        self.provider = provider
        self.config = config


class DummyEmbedderConfig:
    def __init__(self, provider: str, config: Dict[str, Any]) -> None:
        self.provider = provider
        self.config = config


class DummyLlmConfig:
    def __init__(self, provider: str, config: Dict[str, Any]) -> None:
        self.provider = provider
        self.config = config


@pytest.fixture(autouse=True)
def reset_memory_service(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(memory_service, "_memory_service", None)
    monkeypatch.setattr(memory_service.settings, "MEMORY_ENABLED", False)
    monkeypatch.setattr(memory_service.settings, "MEMORY_INFER", False)


@pytest.fixture
def patched_mem0(monkeypatch: pytest.MonkeyPatch) -> DummyMemory:
    dummy_memory = DummyMemory(config=None)

    mem0_module = ModuleType("mem0")

    configs_base = ModuleType("mem0.configs.base")
    configs_base.MemoryConfig = DummyMemoryConfig

    embeddings_configs = ModuleType("mem0.embeddings.configs")
    embeddings_configs.EmbedderConfig = DummyEmbedderConfig

    llms_configs = ModuleType("mem0.llms.configs")
    llms_configs.LlmConfig = DummyLlmConfig

    vector_configs = ModuleType("mem0.vector_stores.configs")
    vector_configs.VectorStoreConfig = DummyVectorStoreConfig

    memory_main = ModuleType("mem0.memory.main")

    def factory(config: Any) -> DummyMemory:
        dummy_memory.config = config
        return dummy_memory

    memory_main.Memory = factory

    sys.modules["mem0"] = mem0_module
    sys.modules["mem0.configs"] = ModuleType("mem0.configs")
    sys.modules["mem0.configs.base"] = configs_base
    sys.modules["mem0.embeddings"] = ModuleType("mem0.embeddings")
    sys.modules["mem0.embeddings.configs"] = embeddings_configs
    sys.modules["mem0.llms"] = ModuleType("mem0.llms")
    sys.modules["mem0.llms.configs"] = llms_configs
    sys.modules["mem0.vector_stores"] = ModuleType("mem0.vector_stores")
    sys.modules["mem0.vector_stores.configs"] = vector_configs
    sys.modules["mem0.memory"] = ModuleType("mem0.memory")
    sys.modules["mem0.memory.main"] = memory_main

    monkeypatch.setattr(memory_service.settings, "MEMORY_ENABLED", True)
    monkeypatch.setattr(memory_service.settings, "MEMORY_INFER", True)
    monkeypatch.setattr(memory_service.settings, "VECTOR_DIM", 1536)
    monkeypatch.setattr(memory_service.settings, "MEMORY_COLLECTION_NAME", "journeyon-test")
    monkeypatch.setattr(memory_service.settings, "QDRANT_URL", "http://qdrant:6333")
    monkeypatch.setattr(memory_service.settings, "QDRANT_API_KEY", "secret")
    monkeypatch.setattr(memory_service.settings, "EMBEDDING_PROVIDER", "ollama")
    monkeypatch.setattr(memory_service.settings, "OLLAMA_URL", "http://ollama:11434")
    monkeypatch.setattr(memory_service.settings, "OLLAMA_EMBED_MODEL", "test-embed")
    monkeypatch.setattr(memory_service.settings, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(memory_service.settings, "OPENAI_API_KEY", "openai-key")
    monkeypatch.setattr(memory_service.settings, "OPENAI_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setattr(memory_service.settings, "OPENAI_EMBED_MODEL", "text-embedding-test")
    monkeypatch.setattr(memory_service.settings, "OLLAMA_CHAT_MODEL", "chat-test")
    monkeypatch.setattr(memory_service.settings, "MEMORY_HISTORY_DB_PATH", "/tmp/mem0-history.db")

    return dummy_memory


def test_memory_service_disabled_returns_safe_defaults() -> None:
    svc = MemoryService()

    assert svc.add_messages([{"role": "user", "content": "hi"}]) is None
    assert svc.search("query") == []
    assert svc.update("mem", "text") is None
    assert svc.delete("mem") is None
    assert svc.get("mem") is None
    assert svc.history("mem") == []
    assert svc.delete_all(filters={"user_id": "u"}) is None


def test_memory_service_enabled_invokes_mem0(monkeypatch: pytest.MonkeyPatch, patched_mem0: DummyMemory) -> None:
    svc = MemoryService()

    payload = svc.add_messages([
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "记录"},
    ], user_id="user-1", metadata={"stage": "pre"})

    assert payload and payload["id"] == "mem-1"
    assert patched_mem0.calls[0]["method"] == "add"
    assert patched_mem0.calls[0]["kwargs"]["infer"] is True
    assert svc.search("夜景摄影", top_k=5, filters={"user_id": "user-1"})[0]["id"] == "mem-1"
    assert svc.update("mem-1", "updated") == {"id": "mem-1", "text": "updated"}
    assert svc.get("mem-1") == {"id": "mem-1", "text": "updated"}
    assert svc.history("mem-1")[0]["text"] == "你好\n记录"
    assert svc.delete("mem-1") == {"id": "mem-1", "deleted": True}
    assert svc.delete_all(filters={"user_id": "user-1", "agent_id": "agent", "run_id": "run"}) == {
        "deleted": True,
        "user_id": "user-1",
        "agent_id": "agent",
        "run_id": "run",
    }

    config = patched_mem0.config
    assert config.vector_store.provider == "qdrant"
    assert config.vector_store.config["collection_name"] == "journeyon-test"
    assert config.vector_store.config["url"] == "http://qdrant:6333"
    assert config.embedder.provider == "ollama"
    assert config.embedder.config["model"] == "test-embed"
    assert config.llm.provider == "openai"
    assert config.llm.config["model"] == "chat-test"
    assert config.history_db_path == "/tmp/mem0-history.db"


def test_memory_service_handles_mem0_errors(monkeypatch: pytest.MonkeyPatch, patched_mem0: DummyMemory) -> None:
    svc = MemoryService()

    def raise_error(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(patched_mem0, "add", raise_error)
    monkeypatch.setattr(patched_mem0, "search", raise_error)
    monkeypatch.setattr(patched_mem0, "update", raise_error)
    monkeypatch.setattr(patched_mem0, "delete", raise_error)
    monkeypatch.setattr(patched_mem0, "get", raise_error)
    monkeypatch.setattr(patched_mem0, "history", raise_error)
    monkeypatch.setattr(patched_mem0, "delete_all", raise_error)

    assert svc.add_messages([{"role": "user", "content": "hi"}]) is None
    assert svc.search("query") == []
    assert svc.update("mem", "text") is None
    assert svc.delete("mem") is None
    assert svc.get("mem") is None
    assert svc.history("mem") == []
    assert svc.delete_all(filters={"user_id": "u"}) is None


def test_memory_service_update_modes(monkeypatch: pytest.MonkeyPatch, patched_mem0: DummyMemory) -> None:
    svc = MemoryService()

    # Ensure an existing memory entry
    payload = svc.add_messages([{"role": "user", "content": "初始"}], user_id="u")
    assert payload is not None
    memory_id = payload["id"]

    append_result = svc.append_memory(memory_id, [{"role": "assistant", "content": "补充"}])
    assert append_result is not None
    assert append_result["text"].endswith("补充")

    overwrite_result = svc.replace_memory(memory_id, [{"role": "system", "content": "覆盖"}])
    assert overwrite_result is not None
    assert overwrite_result["text"] == "system: 覆盖"

    mode_result = svc.update_memory(memory_id, [{"role": "user", "content": "再补充"}], mode="append")
    assert mode_result is not None
    assert "再补充" in mode_result["text"]
