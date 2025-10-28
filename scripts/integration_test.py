"""
JourneyOn 后端集成测试（真实环境）

此脚本对依赖 PostgreSQL、Redis、Qdrant、Ollama 的关键路径做端到端验证：
- /api/health 健康检查
- /api/auth 注册/登录
- /api/trips CRUD（只测创建）
- /api/trips/{trip_id}/kb_entries 创建，异步向量化入库（如启用）
- /api/kb/search 向量检索 + 可选重排序
- /api/agent/chat 基本 LLM 能力（需要 Ollama 模型可用）

使用方法：
    python scripts/integration_test.py --base http://localhost:8000

提示：
- 需先 docker-compose up -d（本仓库 compose 已包含 Postgres/Redis/Qdrant/Ollama）
- Ollama 首次启动需拉取大镜像与模型，等待较久；脚本会自动做有限次重试。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import string
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx


def _rand(n: int = 6) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


@dataclass
class TestContext:
    base: str
    token: Optional[str] = None
    user_id: Optional[int] = None
    trip_id: Optional[int] = None


async def _wait_until_ready(base: str, *, timeout_s: int = 180) -> None:
    async with httpx.AsyncClient() as client:
        for _ in range(max(1, timeout_s // 3)):
            try:
                r = await client.get(f"{base}/api/health", timeout=3)
                if r.status_code == 200:
                    return
            except Exception:
                pass
            await asyncio.sleep(3)
    raise TimeoutError("服务未在期待时间内变为可用")


async def test_health(ctx: TestContext) -> Dict[str, Any]:
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{ctx.base}/api/health", timeout=5)
        return r.json()


async def test_register_login(ctx: TestContext) -> None:
    username = f"test_{_rand()}"
    email = f"{username}@ex.com"
    password = "P@ssw0rd!"
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{ctx.base}/api/auth/register",
            json={"username": username, "email": email, "password": password},
            timeout=10,
        )
        data = r.json()["data"]
        ctx.token = data["token"]
        ctx.user_id = data["user"]["id"]

        # 再测一次登录
        r2 = await client.post(
            f"{ctx.base}/api/auth/login",
            json={"username_or_email": username, "password": password},
            timeout=10,
        )
        data2 = r2.json()["data"]
        assert data2["user"]["id"] == ctx.user_id


async def test_create_trip(ctx: TestContext) -> None:
    assert ctx.token
    headers = {"Authorization": f"Bearer {ctx.token}"}
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{ctx.base}/api/trips",
            headers=headers,
            json={"title": "集成测试行程", "origin": "北京", "destination": "上海", "duration_days": 3},
            timeout=10,
        )
        payload = r.json()["data"]
        ctx.trip_id = payload["id"]


async def test_kb_ingest_and_search(ctx: TestContext) -> Dict[str, Any]:
    assert ctx.token and ctx.trip_id
    headers = {"Authorization": f"Bearer {ctx.token}"}
    async with httpx.AsyncClient() as client:
        # 创建 KB 条目（触发异步向量化）
        r = await client.post(
            f"{ctx.base}/api/trips/{ctx.trip_id}/kb_entries",
            headers=headers,
            json={
                "source": "note",
                "title": "上海外滩夜景",
                "content": "黄浦江畔，夜景迷人，适合拍照散步。",
            },
            timeout=10,
        )
        assert r.status_code == 200

        # 等待向量化落库/索引完成（最多 30s）
        for _ in range(10):
            rr = await client.get(f"{ctx.base}/api/kb/health", timeout=5)
            h = rr.json()["data"]
            if h.get("qdrant"):
                break
            await asyncio.sleep(3)

        # 搜索
        s = await client.post(
            f"{ctx.base}/api/kb/search",
            headers=headers,
            json={"query": "外滩 夜景", "top_k": 5, "rerank": False},
            timeout=15,
        )
        return s.json()


async def test_agent_chat(ctx: TestContext) -> Dict[str, Any]:
    assert ctx.token and ctx.trip_id
    headers = {"Authorization": f"Bearer {ctx.token}"}
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{ctx.base}/api/agent/chat",
            headers=headers,
            json={"trip_id": ctx.trip_id, "stage": "pre", "message": "帮我规划下第一天行程"},
            timeout=60,
        )
        return r.json()


async def main() -> int:
    parser = argparse.ArgumentParser(description="JourneyOn 集成测试")
    parser.add_argument("--base", default="http://localhost:8000", help="后端基础 URL")
    args = parser.parse_args()

    ctx = TestContext(base=args.base.rstrip("/"))
    await _wait_until_ready(ctx.base)

    print("[1] /api/health …")
    h = await test_health(ctx)
    print(json.dumps(h, ensure_ascii=False))

    print("[2] 注册/登录 …")
    await test_register_login(ctx)
    print(f"token: {ctx.token[:12]}… user: {ctx.user_id}")

    print("[3] 创建行程 …")
    await test_create_trip(ctx)
    print(f"trip_id: {ctx.trip_id}")

    print("[4] KB 向量搜索 …")
    kb = await test_kb_ingest_and_search(ctx)
    print(json.dumps(kb, ensure_ascii=False))

    print("[5] 代理对话（LLM） …")
    try:
        chat = await test_agent_chat(ctx)
        print(json.dumps(chat, ensure_ascii=False)[:400])
    except Exception as exc:
        print(f"agent chat 跳过/失败: {exc}")

    print("完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

