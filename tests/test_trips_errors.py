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


def test_trips_requires_auth(client: TestClient):
    rc = client.post("/api/trips", json={"title": "NoAuth Trip"})
    assert rc.status_code == 401, rc.text
    body = rc.json()
    assert body["code"] == 401


def test_get_trip_not_found(client: TestClient):
    token = _register_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    rg = client.get("/api/trips/999999", headers=headers)
    assert rg.status_code == 404, rg.text
    body = rg.json()
    assert body["code"] == 404
    assert body["msg"] == "trip_not_found"


def test_update_trip_stage_invalid_value(client: TestClient):
    token = _register_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    # Create a trip
    rc = client.post("/api/trips", json={"title": "Stage Test", "destination": "City"}, headers=headers)
    assert rc.status_code == 200, rc.text
    trip_id = rc.json()["data"]["id"]
    # Try invalid stage
    ru = client.patch(f"/api/trips/{trip_id}/stage", json={"new_stage": "invalid"}, headers=headers)
    assert ru.status_code == 400, ru.text
    body = ru.json()
    assert body["code"] == 400
    assert body["msg"] == "invalid_stage"