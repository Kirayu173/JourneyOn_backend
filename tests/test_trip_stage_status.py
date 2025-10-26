from __future__ import annotations

import uuid
from fastapi.testclient import TestClient


def _register_and_get_token(client: TestClient) -> str:
    uid = uuid.uuid4().hex[:8]
    username = f"user_{uid}"
    email = f"{uid}@example.com"
    password = "TestPass123!"
    r = client.post("/api/auth/register", json={"username": username, "email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["data"]["token"]


def _create_trip(client: TestClient, headers: dict) -> int:
    rc = client.post(
        "/api/trips",
        json={"title": "StageStatus Trip", "destination": "City", "duration_days": 1},
        headers=headers,
    )
    assert rc.status_code == 200, rc.text
    return rc.json()["data"]["id"]


def test_update_stage_status_flow(client: TestClient):
    token = _register_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    trip_id = _create_trip(client, headers)

    # 'on' stage initial is 'pending' -> move to 'in_progress'
    r1 = client.patch(f"/api/trips/{trip_id}/stages/on", json={"new_status": "in_progress"}, headers=headers)
    assert r1.status_code == 200, r1.text
    body1 = r1.json()
    assert body1["code"] == 0
    assert body1["data"]["stage_name"] == "on"
    assert body1["data"]["status"] == "in_progress"
    assert body1["data"]["confirmed_at"] is None

    # Move 'on' to 'completed' -> confirmed_at should be set
    r2 = client.patch(f"/api/trips/{trip_id}/stages/on", json={"new_status": "completed"}, headers=headers)
    assert r2.status_code == 200, r2.text
    body2 = r2.json()
    assert body2["code"] == 0
    assert body2["data"]["status"] == "completed"
    assert isinstance(body2["data"]["confirmed_at"], str)

    # Idempotent update on 'pre' which starts as 'in_progress'
    r3 = client.patch(f"/api/trips/{trip_id}/stages/pre", json={"new_status": "in_progress"}, headers=headers)
    assert r3.status_code == 200, r3.text
    body3 = r3.json()
    assert body3["code"] == 0
    assert body3["data"]["status"] == "in_progress"


def test_update_stage_status_invalid_transition_and_status(client: TestClient):
    token = _register_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    trip_id = _create_trip(client, headers)

    # Invalid transition: 'post' is 'pending' -> cannot go directly to 'completed'
    r1 = client.patch(f"/api/trips/{trip_id}/stages/post", json={"new_status": "completed"}, headers=headers)
    assert r1.status_code == 400, r1.text
    body1 = r1.json()
    assert body1["code"] == 400
    assert body1["msg"] == "invalid_transition"

    # Invalid status value
    r2 = client.patch(f"/api/trips/{trip_id}/stages/on", json={"new_status": "unknown"}, headers=headers)
    assert r2.status_code == 400, r2.text
    body2 = r2.json()
    assert body2["code"] == 400
    assert body2["msg"] == "invalid_status"

    # Invalid stage name
    r3 = client.patch(f"/api/trips/{trip_id}/stages/invalid", json={"new_status": "pending"}, headers=headers)
    assert r3.status_code == 400, r3.text
    body3 = r3.json()
    assert body3["code"] == 400
    assert body3["msg"] == "invalid_stage"


def test_update_stage_status_requires_auth_and_not_found(client: TestClient):
    # Without auth
    r = client.patch("/api/trips/1/stages/pre", json={"new_status": "in_progress"})
    assert r.status_code == 401, r.text

    # With auth, non-existent trip
    token = _register_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    r2 = client.patch("/api/trips/999999/stages/pre", json={"new_status": "in_progress"}, headers=headers)
    assert r2.status_code == 404, r2.text
    body2 = r2.json()
    assert body2["code"] == 404