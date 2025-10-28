from __future__ import annotations

"""
验证限流在 Redis 不可用时的本地退化路径：
- 先启动：docker-compose up -d
- 执行：docker-compose exec -T web python scripts/test_rate_limit_fallback.py
- 脚本会：注册/登录 -> 连续调用 /api/kb/search，预期在阈值后收到 429。
  建议临时停止 redis 以验证退化：docker stop journeyon_redis
  结束后恢复：docker start journeyon_redis
"""

import asyncio
import json
from typing import Tuple

import httpx


BASE = "http://web:8000"


async def _auth(client: httpx.AsyncClient) -> Tuple[str, int]:
    u = "user_rl"
    payload = {"username": u, "email": f"{u}@ex.com", "password": "p@ss"}
    r = await client.post(f"{BASE}/api/auth/register", json=payload)
    if r.status_code == 200:
        data = r.json()["data"]
        return data["token"], data["user"]["id"]
    # 已存在则尝试登录
    r2 = await client.post(
        f"{BASE}/api/auth/login",
        json={"username_or_email": u, "password": payload["password"]},
    )
    data2 = r2.json()["data"]
    return data2["token"], data2["user"]["id"]


async def main() -> int:
    async with httpx.AsyncClient(timeout=30) as client:
        token, _ = await _auth(client)
        headers = {"Authorization": f"Bearer {token}"}
        ok, limited, errors = 0, 0, 0
        # 进行 80 次请求，默认阈值 60；若 Redis 不可用，应触发本地退化限流
        for i in range(80):
            try:
                r = await client.post(
                    f"{BASE}/api/kb/search",
                    headers=headers,
                    json={"query": "外滩 夜景", "top_k": 3, "rerank": False},
                )
                if r.status_code == 429:
                    limited += 1
                elif r.status_code == 200:
                    ok += 1
                else:
                    errors += 1
            except Exception:
                errors += 1
        print(json.dumps({"ok": ok, "limited": limited, "errors": errors}))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
