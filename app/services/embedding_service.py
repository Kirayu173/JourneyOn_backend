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
    pass


def _normalize(text: str) -> str:
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
        results = await self.embed_batch([text])
        return results[0] if results else []

    async def embed_batch(self, texts: Iterable[str]) -> List[List[float]]:
        normalized = [_normalize(t) for t in texts]
        tasks = [self._embed_single(t) for t in normalized]
        return await asyncio.gather(*tasks)

    async def _embed_single(self, text: str) -> List[float]:
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
        if not documents:
            return []
        payload = {
            "model": self._model,
            "stream": False,
            "prompt": json.dumps({"query": query, "documents": list(documents)}, ensure_ascii=False),
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(f"{self._base_url}/api/generate", json=payload)
        if response.status_code >= 400:
            raise EmbeddingError(f"rerank_failed:{response.status_code}")
        data = response.json()
        text = data.get("response") or ""
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [RerankResult(index=i, score=float(item.get("score", 0.0))) for i, item in enumerate(parsed)]
        except json.JSONDecodeError:
            pass
        scores: List[RerankResult] = []
        for idx, line in enumerate(text.splitlines()):
            try:
                score = float(line.strip())
            except ValueError:
                continue
            scores.append(RerankResult(index=idx, score=score))
        return scores


__all__ = ["EmbeddingService", "EmbeddingError", "RerankService", "RerankResult"]
