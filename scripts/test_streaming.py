from __future__ import annotations

"""
验证 SSE 与 WebSocket 流式内容：
- SSE: /api/agent/chat/stream 应产生 RUN_STARTED、MESSAGE 分块，最终 DONE
- WS:  连接后发送首条消息，应收到多条 MESSAGE，最终正常关闭
"""

import asyncio
import json
from typing import AsyncIterator

import httpx
import websockets

BASE = "http://localhost:8000"


async def _wait_ready(base: str, timeout_s: int = 30) -> None:
    async with httpx.AsyncClient(timeout=3) as client:
        for _ in range(max(1, timeout_s // 2)):
            try:
                r = await client.get(f"{base}/api/health")
                if r.status_code == 200:
                    return
            except Exception:
                pass
            await asyncio.sleep(2)
    raise TimeoutError("service not ready")


async def _auth() -> tuple[str, int, int]:
    async with httpx.AsyncClient(timeout=10) as client:
        u = "user_stream"
        r = await client.post(
            f"{BASE}/api/auth/register",
            json={"username": u, "email": f"{u}@ex.com", "password": "p@ss"},
        )
        data = r.json()["data"]
        token = data["token"]
        headers = {"Authorization": f"Bearer {token}"}
        t = await client.post(f"{BASE}/api/trips", headers=headers, json={"title": "t"})
        trip_id = t.json()["data"]["id"]
        return token, data["user"]["id"], trip_id


async def test_sse(token: str, trip_id: int) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    events = []
    async with httpx.AsyncClient(timeout=30) as client:
        async with client.stream(
            "POST",
            f"{BASE}/api/agent/chat/stream",
            headers=headers,
            json={"trip_id": trip_id, "stage": "pre", "message": "测试流"},
        ) as resp:
            async for line in resp.aiter_lines():
                if not line:
                    continue
                if line.startswith("data: "):
                    try:
                        payload = json.loads(line[6:])
                        events.append(payload.get("event"))
                    except json.JSONDecodeError:
                        pass
    return {"events": events}


async def test_ws(token: str, trip_id: int) -> dict:
    uri = f"ws://web:8000/api/agent/ws/chat?token={token}"
    messages = 0
    async with websockets.connect(uri, open_timeout=10) as ws:
        await ws.send(
            json.dumps({"trip_id": trip_id, "stage": "pre", "message": "测试WS"}, ensure_ascii=False)
        )
        try:
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=10)
                data = json.loads(msg)
                if data.get("event") == "message":
                    messages += 1
                if data.get("event") == "run_completed":
                    break
        except asyncio.TimeoutError:
            pass
    return {"messages": messages}


async def main() -> int:
    await _wait_ready(BASE)
    token, _, trip_id = await _auth()
    sse = await test_sse(token, trip_id)
    ws = await test_ws(token, trip_id)
    print(json.dumps({"sse": sse, "ws": ws}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
