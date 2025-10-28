from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Iterable, List, Sequence

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingError(RuntimeError):
    """Raised when embedding or rerank requests fail."""
    pass


def _normalize(text: str) -> str:
    """Clean up whitespace and handle None values."""
    return (text or "").strip()


class EmbeddingService:
    """Async embedding client backed by Ollama."""

    def __init__(self) -> None:
        if not settings.OLLAMA_URL:
            raise RuntimeError("OLLAMA_URL not configured for embeddings")
        self._base_url = settings.OLLAMA_URL.rstrip("/")
        self._model = settings.OLLAMA_EMBED_MODEL
        self._timeout = httpx.Timeout(settings.EMBEDDING_TIMEOUT)
        self._semaphore = asyncio.Semaphore(max(1, settings.EMBEDDING_CONCURRENCY))

    async def embed(self, text: str) -> List[float]:
        """Embed a single text string asynchronously."""
        results = await self.embed_batch([text])
        return results[0] if results else []

    async def embed_batch(self, texts: Iterable[str]) -> List[List[float]]:
        """Embed multiple texts concurrently."""
        normalized = [_normalize(t) for t in texts]
        tasks = [self._embed_single(t) for t in normalized]
        return await asyncio.gather(*tasks)

    async def _embed_single(self, text: str) -> List[float]:
        """Send one text to Ollama embedding endpoint with retry logic."""
        if not text:
            return []

        payload = {"model": self._model, "prompt": text}
        async with self._semaphore:
            delay = settings.LLM_RETRY_BASE_DELAY
            for attempt in range(1, settings.LLM_MAX_RETRIES + 1):
                try:
                    async with httpx.AsyncClient(timeout=self._timeout) as client:
                        response = await client.post(
                            f"{self._base_url}/api/embeddings",
                            json=payload,
                        )
                    if response.status_code >= 400:
                        raise EmbeddingError(f"embedding_failed:{response.status_code}")
                    data = response.json()
                    # Ollama API may return {"embedding": [...]} or {"data": [{"embedding": [...]}]}
                    if "embedding" in data:
                        vector = data.get("embedding") or []
                        return vector if isinstance(vector, list) else []
                    if "data" in data:
                        embedding = data["data"][0].get("embedding") if data["data"] else []
                        return embedding or []
                    return []
                except httpx.RequestError:
                    if attempt == settings.LLM_MAX_RETRIES:
                        raise
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, 8)
        raise EmbeddingError("embedding_retry_exhausted")

    async def health(self) -> dict[str, object]:
        """Perform a lightweight embedding health check."""
        payload = {"model": self._model, "prompt": "ping"}
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(f"{self._base_url}/api/embeddings", json=payload)
            ok = response.status_code < 400
        except httpx.RequestError:
            logger.warning("embedding_health_failed", exc_info=True)
            ok = False
        return {"ok": ok, "model": self._model}


@dataclass
class RerankResult:
    index: int
    score: float


class RerankService:
    """Invoke Ollama reranker model to score retrieved passages."""

    def __init__(self) -> None:
        if not settings.OLLAMA_URL:
            raise RuntimeError("OLLAMA_URL not configured for reranker")
        self._base_url = settings.OLLAMA_URL.rstrip("/")
        self._model = settings.OLLAMA_RERANK_MODEL or "dengcao/bge-reranker-v2-m3:latest"
        self._timeout = httpx.Timeout(settings.LLM_REQUEST_TIMEOUT)

    async def rerank(self, query: str, documents: Sequence[str]) -> List[RerankResult]:
        """Rerank a list of documents given a query.

        为适配不同 Ollama 模型的生成行为，这里构造明确的指令化提示，并做多种解析回退：
        - 首选解析 JSON 数组（如 [0.9, 0.2, ...]）
        - 次选解析每行一个浮点数
        - 若以上均失败则返回空（保持原排序）
        """
        if not documents:
            return []

        numbered_docs = "\n".join(f"{i+1}. {d}" for i, d in enumerate(documents))
        instruction = (
            "You are a reranker. Given a query and a list of documents, "
            "return ONLY a JSON array of relevance scores between 0 and 1, in the same order as the documents. "
            "Do not include any explanation.\n\n"
            f"Query: {query}\n"
            f"Documents:\n{numbered_docs}\n\n"
            "Output format example: [0.91, 0.12, 0.57]"
        )

        payload = {
            "model": self._model,
            "stream": False,
            "prompt": instruction,
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(f"{self._base_url}/api/generate", json=payload)
        if response.status_code >= 400:
            raise EmbeddingError(f"rerank_failed:{response.status_code}")
        data = response.json()
        text = (data.get("response") or "").strip()

        # 尝试解析 JSON 数组
        def _parse_json_array(s: str) -> List[float] | None:
            s_stripped = s
            # 容错：截取第一个方括号片段
            if "[" in s and "]" in s:
                s_stripped = s[s.find("[") : s.rfind("]") + 1]
            try:
                arr = json.loads(s_stripped)
                if isinstance(arr, list):
                    floats: List[float] = []
                    for item in arr:
                        try:
                            floats.append(float(item))
                        except (TypeError, ValueError):
                            floats.append(0.0)
                    return floats
            except json.JSONDecodeError:
                return None
            return None

        scores_array = _parse_json_array(text)
        if scores_array is None:
            # 逐行解析浮点数
            scores_array = []
            for line in text.splitlines():
                try:
                    scores_array.append(float(line.strip()))
                except ValueError:
                    continue

        results: List[RerankResult] = []
        for idx in range(min(len(documents), len(scores_array or []))):
            results.append(RerankResult(index=idx, score=float(scores_array[idx])))
        return results


__all__ = ["EmbeddingService", "EmbeddingError", "RerankService", "RerankResult"]

