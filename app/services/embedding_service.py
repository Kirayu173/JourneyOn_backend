from __future__ import annotations

from typing import Dict, Iterable, List

import httpx

from app.core.config import settings


def _normalize_text(t: str) -> str:
    return (t or "").strip()


def _embed_single_ollama(text: str) -> List[float]:
    if not settings.OLLAMA_URL:
        raise RuntimeError("OLLAMA_URL not configured")
    url = f"{settings.OLLAMA_URL.rstrip('/')}/api/embeddings"
    payload = {"model": settings.OLLAMA_EMBED_MODEL, "prompt": text}
    with httpx.Client(timeout=30) as client:
        resp = client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data.get("embedding") or data.get("data") or []


def _embed_single_openai(text: str) -> List[float]:
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not configured")
    base_url = (settings.OPENAI_BASE_URL or "https://api.openai.com/v1").rstrip("/")
    url = f"{base_url}/embeddings"
    payload = {"model": settings.OPENAI_EMBED_MODEL, "input": text}
    headers = {
        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
    }
    with httpx.Client(timeout=30) as client:
        resp = client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        try:
            embedding = data["data"][0]["embedding"]
        except (KeyError, IndexError, TypeError):
            embedding = []
        return embedding


def _provider_name() -> str:
    return (settings.EMBEDDING_PROVIDER or "ollama").lower()


def embed_texts(texts: Iterable[str]) -> List[List[float]]:
    processed: List[str] = [_normalize_text(t) for t in texts]
    results: List[List[float]] = []
    provider = _provider_name()
    for t in processed:
        if not t:
            results.append([])
            continue
        try:
            if provider == "openai":
                vec = _embed_single_openai(t)
            else:
                vec = _embed_single_ollama(t)
            results.append(vec)
        except Exception:
            results.append([])
    return results


def health_check() -> Dict[str, object]:
    provider = _provider_name()
    status: Dict[str, object] = {"provider": provider, "ok": False}
    if not settings.ENABLE_EMBEDDING:
        status.update({"ok": False, "detail": "disabled"})
        return status

    if provider == "openai":
        status["model"] = settings.OPENAI_EMBED_MODEL
        if not settings.OPENAI_API_KEY:
            status["detail"] = "missing_api_key"
            return status
        try:
            base_url = (settings.OPENAI_BASE_URL or "https://api.openai.com/v1").rstrip("/")
            url = f"{base_url}/models"
            headers = {"Authorization": f"Bearer {settings.OPENAI_API_KEY}"}
            with httpx.Client(timeout=5) as client:
                resp = client.get(url, headers=headers)
                status["ok"] = resp.status_code == 200
                status["detail"] = "reachable" if status["ok"] else resp.text[:100]
        except Exception:
            status["ok"] = False
            status["detail"] = "request_failed"
        return status

    status["model"] = settings.OLLAMA_EMBED_MODEL
    if not settings.OLLAMA_URL:
        status["detail"] = "missing_url"
        return status
    try:
        url = f"{settings.OLLAMA_URL.rstrip('/')}/api/tags"
        with httpx.Client(timeout=5) as client:
            resp = client.get(url)
            status["ok"] = resp.status_code == 200
            status["detail"] = "reachable" if status["ok"] else resp.text[:100]
    except Exception:
        status["ok"] = False
        status["detail"] = "request_failed"
    return status

