from __future__ import annotations

import json
import uuid
from typing import Generator

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


def _register_and_get_token(client: TestClient) -> str:
    uid = uuid.uuid4().hex[:8]
    username = f"user_{uid}"
    email = f"{uid}@example.com"
    password = "TestPass123!"
    response = client.post("/api/auth/register", json={"username": username, "email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["data"]["token"]


def _create_trip(client: TestClient, headers: dict) -> int:
    response = client.post(
        "/api/trips",
        json={"title": "Agent Trip", "destination": "City", "duration_days": 2},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["id"]


def test_agent_chat_and_conversations_history(client: TestClient):
    token = _register_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    trip_id = _create_trip(client, headers)

    payload1 = {"trip_id": trip_id, "stage": "pre", "message": "Plan flights and hotels"}
    response1 = client.post("/api/agent/chat", json=payload1, headers=headers)
    assert response1.status_code == 200, response1.text
    body1 = response1.json()
    assert body1["code"] == 0
    assert "agent" in body1["data"] and "tools" in body1["data"]["agent"]

    payload2 = {"trip_id": trip_id, "stage": "pre", "message": "Plan today's transport"}
    response2 = client.post("/api/agent/chat", json=payload2, headers=headers)
    assert response2.status_code == 200, response2.text

    history = client.get(f"/api/trips/{trip_id}/conversations", params={"stage": "pre"}, headers=headers)
    assert history.status_code == 200, history.text
    items = history.json()["data"]
    assert len(items) >= 2
    assert items[0]["role"] == "user" and items[1]["role"] == "user"
    assert any(item["message"] == payload2["message"] for item in items)


def test_agent_chat_stream_sends_structured_events(client: TestClient):
    token = _register_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    trip_id = _create_trip(client, headers)

    payload = {"trip_id": trip_id, "stage": "pre", "message": "Recommend hotels and weather"}
    with client.stream("POST", "/api/agent/chat/stream", json=payload, headers=headers) as stream:
        raw_chunks = list(_collect_sse_chunks(stream.iter_text()))

    events = [json.loads(chunk["data"]) for chunk in raw_chunks if "data" in chunk]
    event_types = [e["event"] for e in events]

    assert "run_started" in event_types
    assert any(e["event"] == "message" and e["message"]["role"] == "assistant" for e in events)
    assert events[-1]["event"] == "run_completed"


def _collect_sse_chunks(iterator: Generator[str, None, None]):
    buffer = ""
    for chunk in iterator:
        buffer += chunk
        while "\n\n" in buffer:
            block, buffer = buffer.split("\n\n", 1)
            event_block: dict[str, str] = {}
            for line in block.splitlines():
                line = line.strip()
                if not line:
                    continue
                if line.startswith("data:"):
                    event_block["data"] = line.split("data:", 1)[1].strip()
                elif line.startswith("event:"):
                    event_block["event"] = line.split("event:", 1)[1].strip()
                elif line.startswith("id:"):
                    event_block["id"] = line.split("id:", 1)[1].strip()
            if event_block:
                yield event_block
    if buffer.strip():
        event_block: dict[str, str] = {}
        for line in buffer.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("data:"):
                event_block["data"] = line.split("data:", 1)[1].strip()
            elif line.startswith("event:"):
                event_block["event"] = line.split("event:", 1)[1].strip()
            elif line.startswith("id:"):
                event_block["id"] = line.split("id:", 1)[1].strip()
        if event_block:
            yield event_block


def test_agent_websocket_flow(client: TestClient):
    token = _register_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    trip_id = _create_trip(client, headers)

    ws_url = f"/api/agent/ws/chat?token={token}"
    with client.websocket_connect(ws_url) as websocket:
        websocket.send_json({"trip_id": trip_id, "stage": "pre", "message": "Generate pre-trip tasks"})
        received = []
        while True:
            try:
                received.append(websocket.receive_json())
            except (RuntimeError, WebSocketDisconnect):
                break

    assert any(event["event"] == "message" for event in received)
    assert received[-1]["event"] == "run_completed"


def test_agent_and_conversations_requires_auth(client: TestClient):
    response = client.post("/api/agent/chat", json={"trip_id": 1, "stage": "pre", "message": "hello"})
    assert response.status_code == 401, response.text
    response2 = client.get("/api/trips/1/conversations", params={"stage": "pre"})
    assert response2.status_code == 401, response2.text
