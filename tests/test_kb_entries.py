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
        json={"title": "KB Trip", "destination": "City", "duration_days": 2},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["id"]


def test_kb_entries_crud_flow(client: TestClient):
    token = _register_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    trip_id = _create_trip(client, headers)

    payload = {
        "source": "manual",
        "title": "Destination brief",
        "content": "Collected travel notes for the destination",
        "meta": {"category": "guide"},
    }
    response = client.post(f"/api/trips/{trip_id}/kb_entries", json=payload, headers=headers)
    assert response.status_code == 200, response.text
    created = response.json()
    assert created["code"] == 0
    entry_id = created["data"]["id"]
    assert created["data"]["title"] == payload["title"]

    response_list = client.get(f"/api/trips/{trip_id}/kb_entries", params={"q": "travel"}, headers=headers)
    assert response_list.status_code == 200, response_list.text
    assert any(entry["id"] == entry_id for entry in response_list.json()["data"])

    patch = {"title": "Updated trip clue", "meta": {"category": "guide", "score": 0.9}}
    response_update = client.patch(f"/api/trips/{trip_id}/kb_entries/{entry_id}", json=patch, headers=headers)
    assert response_update.status_code == 200, response_update.text
    body = response_update.json()
    assert body["code"] == 0
    assert body["data"]["title"] == "Updated trip clue"
    assert body["data"]["meta"]["score"] == 0.9

    response_delete = client.delete(f"/api/trips/{trip_id}/kb_entries/{entry_id}", headers=headers)
    assert response_delete.status_code == 200, response_delete.text
    assert response_delete.json()["code"] == 0

    verify = client.get(f"/api/trips/{trip_id}/kb_entries", headers=headers)
    assert verify.status_code == 200
    assert all(entry["id"] != entry_id for entry in verify.json()["data"])


def test_kb_entries_requires_auth_and_not_found(client: TestClient):
    response = client.post("/api/trips/1/kb_entries", json={"title": "x"})
    assert response.status_code == 401, response.text

    token = _register_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    trip_id = _create_trip(client, headers)

    response_update = client.patch(f"/api/trips/{trip_id}/kb_entries/999999", json={"title": "x"}, headers=headers)
    assert response_update.status_code in (404, 400), response_update.text
