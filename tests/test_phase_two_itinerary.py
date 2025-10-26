from __future__ import annotations

import uuid
from fastapi.testclient import TestClient


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
        json={"title": "Itinerary Trip", "destination": "City", "duration_days": 3},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["id"]


def test_itinerary_crud_flow(client: TestClient):
    token = _register_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    trip_id = _create_trip(client, headers)

    payload = {
        "day": 1,
        "start_time": "09:00",
        "end_time": "11:00",
        "kind": "sightseeing",
        "title": "City highlights tour",
        "location": "Downtown",
    }
    response = client.post(f"/api/trips/{trip_id}/itinerary", json=payload, headers=headers)
    assert response.status_code == 200, response.text
    created = response.json()
    assert created["code"] == 0
    item_id = created["data"]["id"]

    response_list = client.get(f"/api/trips/{trip_id}/itinerary", headers=headers)
    assert response_list.status_code == 200, response_list.text
    assert any(item["id"] == item_id for item in response_list.json()["data"])

    patch = {"day": 2, "title": "Museum visit"}
    response_update = client.patch(f"/api/trips/{trip_id}/itinerary/{item_id}", json=patch, headers=headers)
    assert response_update.status_code == 200, response_update.text
    body = response_update.json()
    assert body["code"] == 0
    assert body["data"]["day"] == 2
    assert body["data"]["title"] == "Museum visit"

    response_delete = client.delete(f"/api/trips/{trip_id}/itinerary/{item_id}", headers=headers)
    assert response_delete.status_code == 200, response_delete.text
    assert response_delete.json()["code"] == 0

    verify = client.get(f"/api/trips/{trip_id}/itinerary", headers=headers)
    assert verify.status_code == 200
    assert all(item["id"] != item_id for item in verify.json()["data"])


def test_itinerary_requires_auth_and_not_found(client: TestClient):
    response = client.post("/api/trips/1/itinerary", json={"day": 1})
    assert response.status_code == 401, response.text

    token = _register_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    trip_id = _create_trip(client, headers)
    response_update = client.patch(f"/api/trips/{trip_id}/itinerary/999999", json={"day": 1}, headers=headers)
    assert response_update.status_code in (404, 400), response_update.text
