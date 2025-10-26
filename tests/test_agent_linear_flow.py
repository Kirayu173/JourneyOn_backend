from __future__ import annotations

import uuid
from typing import Dict

from fastapi.testclient import TestClient

from app.db.models import TripStage
from app.db.session import SessionLocal


def _register_and_get_token(client: TestClient) -> str:
    uid = uuid.uuid4().hex[:8]
    username = f"user_{uid}"
    email = f"{uid}@example.com"
    password = "TestPass123!"
    response = client.post(
        "/api/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["token"]


def _create_trip(client: TestClient, headers: Dict[str, str]) -> int:
    response = client.post(
        "/api/trips",
        json={"title": "LangGraph Trip", "destination": "City", "duration_days": 3},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["id"]


def _stage_statuses(trip_id: int) -> Dict[str, str]:
    with SessionLocal() as db:
        rows = db.query(TripStage).filter(TripStage.trip_id == trip_id).all()
        return {row.stage_name: row.status for row in rows}


def test_linear_agent_flow_with_stage_advancement(client: TestClient) -> None:
    token = _register_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    trip_id = _create_trip(client, headers)

    # Step 1: initial pre-trip message (no advancement)
    payload1 = {"trip_id": trip_id, "stage": "pre", "message": "请给我行前建议"}
    response1 = client.post("/api/agent/chat", json=payload1, headers=headers)
    assert response1.status_code == 200, response1.text
    body1 = response1.json()["data"]["agent"]
    assert body1["stage_history"][0]["stage"] == "pre"
    assert body1["transition"] is None
    statuses1 = _stage_statuses(trip_id)
    assert statuses1["pre"] == "in_progress"
    assert statuses1["on"] == "pending"
    assert statuses1["post"] == "pending"

    # Step 2: confirm advancement to on-trip stage
    payload2 = {"trip_id": trip_id, "stage": "pre", "message": "确认进入下一阶段"}
    response2 = client.post("/api/agent/chat", json=payload2, headers=headers)
    assert response2.status_code == 200, response2.text
    body2 = response2.json()["data"]["agent"]
    assert [item["stage"] for item in body2["stage_history"]] == ["pre", "on"]
    assert body2["transition"]["to_stage"] == "on"
    assert body2["transition"]["updated"] is True
    statuses2 = _stage_statuses(trip_id)
    assert statuses2["pre"] == "completed"
    assert statuses2["on"] == "in_progress"
    assert statuses2["post"] == "pending"

    # Step 3: stay in on-trip stage without confirmation
    payload3 = {"trip_id": trip_id, "stage": "on", "message": "继续提供行程建议"}
    response3 = client.post("/api/agent/chat", json=payload3, headers=headers)
    assert response3.status_code == 200, response3.text
    body3 = response3.json()["data"]["agent"]
    assert [item["stage"] for item in body3["stage_history"]] == ["on"]
    statuses3 = _stage_statuses(trip_id)
    assert statuses3 == statuses2

    # Step 4: confirm advancement to post-trip stage
    payload4 = {"trip_id": trip_id, "stage": "on", "message": "确认进入下一阶段"}
    response4 = client.post("/api/agent/chat", json=payload4, headers=headers)
    assert response4.status_code == 200, response4.text
    body4 = response4.json()["data"]["agent"]
    assert [item["stage"] for item in body4["stage_history"]] == ["on", "post"]
    assert body4["transition"]["to_stage"] == "post"
    statuses4 = _stage_statuses(trip_id)
    assert statuses4["pre"] == "completed"
    assert statuses4["on"] == "completed"
    assert statuses4["post"] == "in_progress"

    trip_info = client.get(f"/api/trips/{trip_id}", headers=headers)
    assert trip_info.status_code == 200, trip_info.text
    assert trip_info.json()["data"]["current_stage"] == "post"

    # Step 5: final message in post-trip stage (no further advancement)
    payload5 = {"trip_id": trip_id, "stage": "post", "message": "请输出行后总结"}
    response5 = client.post("/api/agent/chat", json=payload5, headers=headers)
    assert response5.status_code == 200, response5.text
    body5 = response5.json()["data"]["agent"]
    assert [item["stage"] for item in body5["stage_history"]] == ["post"]
    assert body5["transition"] is None
    statuses5 = _stage_statuses(trip_id)
    assert statuses5 == statuses4
