from __future__ import annotations

import asyncio
import json
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator, Dict, Iterable, List, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    """Raised when the LLM provider fails to satisfy a request."""

    def __init__(self, message: str, *, status_code: Optional[int] = None, run_id: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.run_id = run_id


@dataclass
class ChatResponse:
    content: str
    run_id: str
    usage: Dict[str, object] | None = None


@dataclass
class StreamChunk:
    delta: str
    run_id: str
    done: bool = False
    usage: Dict[str, object] | None = None


class LLMClient(ABC):
    """Base abstraction for chat and embedding capabilities."""

    def __init__(self) -> None:
        self._chat_timeout = settings.LLM_REQUEST_TIMEOUT
        self._stream_timeout = settings.LLM_STREAM_TIMEOUT
        self._max_retries = max(1, settings.LLM_MAX_RETRIES)
        self._backoff = max(0.1, settings.LLM_RETRY_BASE_DELAY)

    async def chat(
        self,
        messages: List[Dict[str, object]],
        *,
        stream: bool = False,
        run_id: Optional[str] = None,
    ) -> ChatResponse | AsyncIterator[StreamChunk]:
        run_id = run_id or uuid.uuid4().hex
        if stream:
            return self._chat_stream(messages, run_id=run_id)
        return await self._chat(messages, run_id=run_id)

    async def embed(self, text: str) -> List[float]:
        vectors = await self.embed_batch([text])
        return vectors[0] if vectors else []

    async def embed_batch(self, texts: Iterable[str]) -> List[List[float]]:
        texts_list = list(texts)
        if not texts_list:
            return []
        return await self._embed_batch(texts_list)

    @abstractmethod
    async def _chat(self, messages: List[Dict[str, object]], *, run_id: str) -> ChatResponse:
        ...

    @abstractmethod
    def _chat_stream(self, messages: List[Dict[str, object]], *, run_id: str) -> AsyncIterator[StreamChunk]:
        ...

    @abstractmethod
    async def _embed_batch(self, texts: List[str]) -> List[List[float]]:
        ...


class OllamaLLMClient(LLMClient):
    def __init__(self) -> None:
        super().__init__()
        if not settings.OLLAMA_URL:
            raise RuntimeError("OLLAMA_URL must be configured for Ollama provider")
        self._base_url = settings.OLLAMA_URL.rstrip("/")
        self._chat_model = settings.OLLAMA_CHAT_MODEL
        self._embed_model = settings.OLLAMA_EMBED_MODEL

    async def _post_with_retry(self, path: str, payload: dict, *, timeout: float | None = None) -> httpx.Response:
        timeout_cfg = httpx.Timeout(timeout or self._chat_timeout)
        delay = self._backoff
        for attempt in range(1, self._max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=timeout_cfg) as client:
                    response = await client.post(f"{self._base_url}{path}", json=payload)
                if response.status_code >= 400:
                    raise LLMError(
                        f"Ollama request failed: {response.status_code}",
                        status_code=response.status_code,
                    )
                return response
            except httpx.RequestError as exc:
                if attempt == self._max_retries:
                    raise exc
                await asyncio.sleep(delay)
                delay = min(delay * 2, 10)
        raise RuntimeError("ollama_retry_failed")

    async def _chat(self, messages: List[Dict[str, object]], *, run_id: str) -> ChatResponse:
        payload = {"model": self._chat_model, "messages": messages, "stream": False}
        try:
            response = await self._post_with_retry("/api/chat", payload)
        except LLMError as exc:
            exc.run_id = run_id
            logger.error("ollama_chat_failed", extra={"run_id": run_id, "code": exc.status_code})
            raise
        except httpx.RequestError as exc:
            logger.error("ollama_chat_retry_exhausted", extra={"run_id": run_id})
            raise LLMError("ollama_request_timeout", run_id=run_id) from exc
        data = response.json()
        message = data.get("message", {})
        content = message.get("content") or data.get("response") or ""
        usage = {
            "model": data.get("model"),
            "total_duration": data.get("total_duration"),
        }
        return ChatResponse(content=content, run_id=run_id, usage=usage)

    async def _stream_iter(self, messages: List[Dict[str, object]], *, run_id: str) -> AsyncIterator[StreamChunk]:
        payload = {"model": self._chat_model, "messages": messages, "stream": True}
        timeout_cfg = httpx.Timeout(self._stream_timeout)
        try:
            async with httpx.AsyncClient(timeout=timeout_cfg) as client:
                async with client.stream("POST", f"{self._base_url}/api/chat", json=payload) as response:
                    if response.status_code >= 400:
                        raise LLMError(
                            f"Ollama stream failed: {response.status_code}",
                            status_code=response.status_code,
                            run_id=run_id,
                        )
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        try:
                            chunk = json.loads(line)
                        except json.JSONDecodeError:
                            logger.debug("ollama_stream_bad_json", extra={"run_id": run_id})
                            continue
                        delta = ""
                        message = chunk.get("message")
                        if isinstance(message, dict):
                            delta = message.get("content") or ""
                        elif "response" in chunk:
                            delta = chunk.get("response") or ""
                        done = bool(chunk.get("done"))
                        usage = None
                        if done:
                            usage = {
                                "total_duration": chunk.get("total_duration"),
                                "eval_count": chunk.get("eval_count"),
                            }
                        yield StreamChunk(delta=delta, run_id=run_id, done=done, usage=usage)
        except httpx.RequestError as exc:
            logger.error("ollama_stream_error", exc_info=True, extra={"run_id": run_id})
            raise LLMError("ollama_stream_error", run_id=run_id) from exc

    def _chat_stream(self, messages: List[Dict[str, object]], *, run_id: str) -> AsyncIterator[StreamChunk]:
        return self._stream_iter(messages, run_id=run_id)

    async def _embed_batch(self, texts: List[str]) -> List[List[float]]:
        payload = {"model": self._embed_model, "prompt": texts[0] if len(texts) == 1 else texts}
        try:
            response = await self._post_with_retry("/api/embeddings", payload, timeout=settings.EMBEDDING_TIMEOUT)
        except LLMError as exc:
            logger.error("ollama_embed_failed", extra={"code": exc.status_code})
            raise
        data = response.json()
        # Ollama returns {"embedding": [...]} for single input; for batch we map manually
        if "embedding" in data:
            vec = data.get("embedding") or []
            return [vec] if isinstance(vec, list) else [[]]
        embeddings = data.get("data") or []
        results: List[List[float]] = []
        for item in embeddings:
            vec = item.get("embedding") if isinstance(item, dict) else None
            results.append(vec or [])
        if not results:
            results = [[] for _ in texts]
        return results


class ZhipuLLMClient(LLMClient):
    def __init__(self) -> None:
        super().__init__()
        if not settings.ZHIPU_API_KEY:
            raise RuntimeError("ZHIPU_API_KEY must be configured for Zhipu provider")
        self._base_url = settings.ZHIPU_BASE_URL.rstrip("/")
        self._chat_model = settings.ZHIPU_CHAT_MODEL
        self._embed_model = "embedding-2"
        self._headers = {"Authorization": f"Bearer {settings.ZHIPU_API_KEY}"}

    async def _chat(self, messages: List[Dict[str, object]], *, run_id: str) -> ChatResponse:
        payload = {"model": self._chat_model, "messages": messages, "stream": False}
        delay = self._backoff
        for attempt in range(1, self._max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self._chat_timeout) as client:
                    response = await client.post(
                        f"{self._base_url}/chat/completions",
                        json=payload,
                        headers=self._headers,
                    )
                if response.status_code >= 400:
                    raise LLMError(
                        f"zhipu_chat_failed: {response.status_code}",
                        status_code=response.status_code,
                        run_id=run_id,
                    )
                data = response.json()
                choices = data.get("choices") or []
                content = ""
                if choices:
                    message = choices[0].get("message") or {}
                    content = message.get("content", "")
                usage = data.get("usage")
                return ChatResponse(content=content, run_id=run_id, usage=usage)
            except httpx.RequestError as exc:
                if attempt == self._max_retries:
                    raise LLMError("zhipu_chat_retry_exhausted", run_id=run_id) from exc
                await asyncio.sleep(delay)
                delay = min(delay * 2, 10)
        raise LLMError("zhipu_chat_retry_exhausted", run_id=run_id)

    async def _zhipu_stream(self, messages: List[Dict[str, object]], *, run_id: str) -> AsyncIterator[StreamChunk]:
        payload = {"model": self._chat_model, "messages": messages, "stream": True}
        async with httpx.AsyncClient(timeout=self._stream_timeout) as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/chat/completions",
                json=payload,
                headers=self._headers,
            ) as response:
                if response.status_code >= 400:
                    raise LLMError(
                        f"zhipu_stream_failed: {response.status_code}",
                        status_code=response.status_code,
                        run_id=run_id,
                    )
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data:"):
                        line = line[5:].strip()
                    if line == "[DONE]":
                        yield StreamChunk(delta="", run_id=run_id, done=True)
                        break
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        logger.debug("zhipu_stream_bad_json", extra={"run_id": run_id})
                        continue
                    choices = payload.get("choices") or []
                    delta = ""
                    if choices:
                        delta = choices[0].get("delta", {}).get("content", "")
                    done = choices and bool(choices[0].get("finish_reason"))
                    usage = payload.get("usage") if done else None
                    yield StreamChunk(delta=delta, run_id=run_id, done=done, usage=usage)

    def _chat_stream(self, messages: List[Dict[str, object]], *, run_id: str) -> AsyncIterator[StreamChunk]:
        return self._zhipu_stream(messages, run_id=run_id)

    async def _embed_batch(self, texts: List[str]) -> List[List[float]]:
        payload = {"model": self._embed_model, "input": texts}
        async with httpx.AsyncClient(timeout=settings.EMBEDDING_TIMEOUT) as client:
            response = await client.post(
                f"{self._base_url}/embeddings",
                json=payload,
                headers=self._headers,
            )
        if response.status_code >= 400:
            raise LLMError(
                f"zhipu_embed_failed: {response.status_code}",
                status_code=response.status_code,
            )
        data = response.json()
        results: List[List[float]] = []
        for item in data.get("data", []):
            vec = item.get("embedding") if isinstance(item, dict) else None
            results.append(vec or [])
        if not results:
            results = [[] for _ in texts]
        return results


_client: Optional[LLMClient] = None
_client_lock = asyncio.Lock()


async def get_llm_client() -> LLMClient:
    global _client
    if _client is not None:
        return _client
    async with _client_lock:
        if _client is not None:
            return _client
        provider = (settings.LLM_PROVIDER or "ollama").lower()
        if provider == "zhipu":
            _client = ZhipuLLMClient()
        else:
            _client = OllamaLLMClient()
        return _client


__all__ = [
    "ChatResponse",
    "StreamChunk",
    "LLMError",
    "LLMClient",
    "OllamaLLMClient",
    "ZhipuLLMClient",
    "get_llm_client",
]
