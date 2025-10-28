from __future__ import annotations

"""
在 Web 启动前等待关键依赖就绪：
- PostgreSQL: 依赖 compose 健康检查，此处不重复
- Redis:     依赖 compose 健康检查，此处不重复
- Qdrant:    轮询 /readyz（最多 ~60 秒）
- Ollama:    如启用嵌入，则轻量探测 /api/embeddings（最多 ~30 秒）

该脚本由 docker-compose 的 web 命令在 uvicorn 之前执行。
"""

import asyncio
import os
from typing import Optional

import httpx


QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333").rstrip("/")
ENABLE_EMBEDDING = os.getenv("ENABLE_EMBEDDING", "false").lower() == "true"
OLLAMA_URL = (os.getenv("OLLAMA_URL") or "").rstrip("/")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "bge-m3:latest")


async def wait_qdrant(timeout_s: int = 60) -> None:
    if not QDRANT_URL:
        return
    async with httpx.AsyncClient(timeout=3.0) as client:
        for _ in range(max(1, timeout_s // 3)):
            try:
                r = await client.get(f"{QDRANT_URL}/readyz")
                if r.status_code == 200:
                    return
            except Exception:
                pass
            await asyncio.sleep(3)
    raise TimeoutError("Qdrant not ready in time")


async def wait_ollama(timeout_s: int = 30) -> None:
    if not (ENABLE_EMBEDDING and OLLAMA_URL):
        return
    payload = {"model": OLLAMA_EMBED_MODEL, "prompt": "ping"}
    async with httpx.AsyncClient(timeout=5.0) as client:
        for _ in range(max(1, timeout_s // 3)):
            try:
                r = await client.post(f"{OLLAMA_URL}/api/embeddings", json=payload)
                if r.status_code < 400:
                    return
            except Exception:
                pass
            await asyncio.sleep(3)
    raise TimeoutError("Ollama embedding backend not ready in time")


async def main() -> int:
    await wait_qdrant()
    await wait_ollama()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

