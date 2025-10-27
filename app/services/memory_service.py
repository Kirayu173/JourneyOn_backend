from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.config import settings


class MemoryService:
    """Thin wrapper around mem0 Memory with lazy init.

    Notes:
    - Completely disabled unless `settings.MEMORY_ENABLED` is True.
    - Avoids importing mem0 at module import time to prevent optional
      dependency issues in environments without LLM/embedding providers.
    """

    def __init__(self) -> None:
        self._enabled = bool(getattr(settings, "MEMORY_ENABLED", False))
        self._infer = bool(getattr(settings, "MEMORY_INFER", False))
        self._memory = None  # type: ignore[var-annotated]

    def _build_config(self):  # type: ignore[no-untyped-def]
        # Import locally to avoid import-time side effects when disabled
        from mem0.configs.base import MemoryConfig

        # Vector store configuration (Qdrant by default)
        vector_provider = "qdrant"
        vector_cfg: Dict[str, Any] = {
            "collection_name": getattr(settings, "MEMORY_COLLECTION_NAME", "memories"),
            "embedding_model_dims": getattr(settings, "VECTOR_DIM", 1024),
        }
        if settings.QDRANT_URL:
            vector_cfg["url"] = settings.QDRANT_URL
        if settings.QDRANT_API_KEY:
            vector_cfg["api_key"] = settings.QDRANT_API_KEY

        # Embedder configuration
        embedder_provider = getattr(settings, "EMBEDDING_PROVIDER", "ollama").lower()
        embedder_cfg: Dict[str, Any] = {
            "model": getattr(settings, "OLLAMA_EMBED_MODEL", "bge-m3:latest"),
            "embedding_dims": getattr(settings, "VECTOR_DIM", 1024),
        }
        if embedder_provider == "ollama" and settings.OLLAMA_URL:
            embedder_cfg["ollama_base_url"] = settings.OLLAMA_URL
        if embedder_provider == "openai":
            embedder_cfg["api_key"] = settings.OPENAI_API_KEY
            embedder_cfg["openai_base_url"] = getattr(settings, "OPENAI_BASE_URL", None)
            embedder_cfg["model"] = getattr(settings, "OPENAI_EMBED_MODEL", None)

        # LLM configuration
        llm_provider = getattr(settings, "LLM_PROVIDER", "ollama").lower()
        llm_cfg: Dict[str, Any] = {
            "model": getattr(settings, "OLLAMA_CHAT_MODEL", None),
        }
        if llm_provider == "ollama" and settings.OLLAMA_URL:
            llm_cfg["ollama_base_url"] = settings.OLLAMA_URL
        if llm_provider == "openai":
            llm_cfg["api_key"] = settings.OPENAI_API_KEY
            llm_cfg["openai_base_url"] = getattr(settings, "OPENAI_BASE_URL", None)

        # History DB path (optional override)
        history_db_path = getattr(settings, "MEMORY_HISTORY_DB_PATH", None)

        return MemoryConfig(
            vector_store={"provider": vector_provider, "config": vector_cfg},
            embedder={"provider": embedder_provider, "config": embedder_cfg},
            llm={"provider": llm_provider, "config": llm_cfg},
            history_db_path=history_db_path or MemoryConfig().history_db_path,
        )

    def _ensure_memory(self) -> None:
        if not self._enabled or self._memory is not None:
            return
        # Import locally to avoid side effects when disabled
        from mem0.memory.main import Memory

        config = self._build_config()
        self._memory = Memory(config)

    def add_messages(
        self,
        messages: List[Dict[str, Any]],
        *,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        run_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        infer: Optional[bool] = None,
    ) -> Dict[str, Any] | None:
        if not self._enabled:
            return None
        self._ensure_memory()
        if self._memory is None:
            return None
        try:
            return self._memory.add(
                messages,
                user_id=user_id,
                agent_id=agent_id,
                run_id=run_id,
                metadata=metadata or {},
                infer=self._infer if infer is None else infer,
            )
        except Exception:
            # Avoid raising to upstream flows; operate best-effort
            return None

    def search(
        self,
        query: str,
        *,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        threshold: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        if not self._enabled:
            return []
        self._ensure_memory()
        if self._memory is None:
            return []
        try:
            return self._memory.search(query, limit=top_k, filters=filters or {}, threshold=threshold)
        except Exception:
            return []

    def update(self, memory_id: str, text: str) -> Dict[str, Any] | None:
        if not self._enabled:
            return None
        self._ensure_memory()
        if self._memory is None:
            return None
        try:
            return self._memory.update(memory_id, text)
        except Exception:
            return None

    def delete(self, memory_id: str) -> Dict[str, Any] | None:
        if not self._enabled:
            return None
        self._ensure_memory()
        if self._memory is None:
            return None
        try:
            return self._memory.delete(memory_id)
        except Exception:
            return None

    def get(self, memory_id: str) -> Dict[str, Any] | None:
        if not self._enabled:
            return None
        self._ensure_memory()
        if self._memory is None:
            return None
        try:
            return self._memory.get(memory_id)
        except Exception:
            return None

    def delete_all(self, *, filters: Dict[str, Any]) -> Dict[str, Any] | None:
        if not self._enabled:
            return None
        self._ensure_memory()
        if self._memory is None:
            return None
        try:
            return self._memory.delete_all(
                user_id=filters.get("user_id"),
                agent_id=filters.get("agent_id"),
                run_id=filters.get("run_id"),
            )
        except Exception:
            return None

    def history(self, memory_id: str) -> List[Dict[str, Any]]:
        if not self._enabled:
            return []
        self._ensure_memory()
        if self._memory is None:
            return []
        try:
            return self._memory.history(memory_id)
        except Exception:
            return []


_memory_service: MemoryService | None = None


def get_memory_service() -> MemoryService:
    global _memory_service
    if _memory_service is None:
        _memory_service = MemoryService()
    return _memory_service


__all__ = ["MemoryService", "get_memory_service"]
