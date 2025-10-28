from __future__ import annotations

"""
mem0 集成真实环境测试：
- 需在 docker-compose 中启用 MEMORY_ENABLED=true
- 流程：注册/登录 -> add -> search -> get -> history -> update -> delete -> delete_all
运行：docker-compose exec -T web python scripts/test_memories.py
"""

import asyncio
import json
from typing import Any, Dict, List, Tuple

import httpx

BASE = "http://localhost:8000"


async def _auth(client: httpx.AsyncClient) -> Tuple[str, int]:
    u = "user_mem0"
    reg = await client.post(f"{BASE}/api/auth/register", json={"username":u, "email":f"{u}@ex.com", "password":"p@ss"})
    if reg.status_code == 200:
        data = reg.json()["data"]
        return data["token"], data["user"]["id"]
    login = await client.post(f"{BASE}/api/auth/login", json={"username_or_email":u, "password":"p@ss"})
    data = login.json()["data"]
    return data["token"], data["user"]["id"]


async def main() -> int:
    async with httpx.AsyncClient(timeout=20) as client:
        # wait health
        for _ in range(15):
            try:
                h = await client.get(f"{BASE}/api/health")
                if h.status_code == 200:
                    break
            except Exception:
                pass
            await asyncio.sleep(2)

        token, user_id = await _auth(client)
        headers = {"Authorization": f"Bearer {token}"}

        # add
        add = await client.post(
            f"{BASE}/api/memories/add",
            headers=headers,
            json={
                "messages": [
                    {"role": "user", "content": "我喜欢夜景摄影和本帮菜"},
                    {"role": "assistant", "content": "好的，已记录你的偏好。"}
                ],
                "metadata": {"scene": "pre", "trip": "demo"}
            },
        )
        print("add:", add.status_code, add.json().get("data"))

        # search
        search = await client.post(
            f"{BASE}/api/memories/search",
            headers=headers,
            json={"query": "夜景 摄影", "top_k": 5},
        )
        data = search.json().get("data", [])
        print("search count:", len(data))

        # get + history if id exists
        memory_id = None
        if data:
            memory_id = data[0].get("id") or data[0].get("memory_id")
        if memory_id:
            get = await client.get(f"{BASE}/api/memories/{memory_id}", headers=headers)
            print("get:", get.status_code)
            hist = await client.get(f"{BASE}/api/memories/{memory_id}/history", headers=headers)
            print("history len:", len(hist.json().get("data", [])))
            # update
            upd = await client.put(f"{BASE}/api/memories/{memory_id}", headers=headers, json={"text":"偏好更新：也喜欢清淡口味"})
            print("update:", upd.status_code)
            # delete
            dele = await client.delete(f"{BASE}/api/memories/{memory_id}", headers=headers)
            print("delete:", dele.status_code)

        # delete_all by user scope
        delall = await client.post(f"{BASE}/api/memories/delete_all", headers=headers, json={"filters": {"user_id": str(user_id)}})
        print("delete_all:", delall.status_code)

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

