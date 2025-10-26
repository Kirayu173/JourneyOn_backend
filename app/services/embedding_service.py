from __future__ import annotations

from functools import lru_cache
from typing import Iterable, List, Tuple

import httpx

from app.core.config import settings


def _normalize_text(t: str) -> str:
    return (t or "").strip()


@lru_cache(maxsize=2048)
def _cached_single(text: str) -> Tuple[str, List[float]]:
    vec = _embed_single_http(text)
    return text, vec


def _embed_single_http(text: str) -> List[float]:
    if not settings.OLLAMA_URL:
        raise RuntimeError("OLLAMA_URL not configured")
    url = f"{settings.OLLAMA_URL.rstrip('/')}/api/embeddings"
    payload = {"model": settings.OLLAMA_EMBED_MODEL, "prompt": text}
    with httpx.Client(timeout=30) as client:
        resp = client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        # Ollama returns { embedding: [...], num_tokens: n }
        return data.get("embedding") or data.get("data") or []


def embed_texts(texts: Iterable[str]) -> List[List[float]]:
    processed: List[str] = [_normalize_text(t) for t in texts]
    results: List[List[float]] = []
    for t in processed:
        if not t:
            results.append([])
            continue
        try:
            _, vec = _cached_single(t)
            results.append(vec)
        except Exception:
            # degrade gracefully
            results.append([])
    return results


def health_check() -> dict:
    ok = False
    try:
        if settings.OLLAMA_URL:
            # A lightweight ping via model listing
            url = f"{settings.OLLAMA_URL.rstrip('/')}/api/tags"
            with httpx.Client(timeout=5) as client:
                r = client.get(url)
                ok = r.status_code == 200
    except Exception:
        ok = False
    return {"ok": ok, "model": settings.OLLAMA_EMBED_MODEL}

