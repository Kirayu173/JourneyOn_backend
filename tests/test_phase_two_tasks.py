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
        json={"title": "Tasks Trip", "destination": "City", "duration_days": 2},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["id"]


def test_tasks_crud_flow(client: TestClient):
    token = _register_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    trip_id = _create_trip(client, headers)

    payload = {
        "stage": "pre",
        "title": "Book flights",
        "description": "Research the best flight options",
        "priority": 1,
    }
    response = client.post(f"/api/trips/{trip_id}/tasks", json=payload, headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["code"] == 0
    task_id = body["data"]["id"]
    assert body["data"]["title"] == payload["title"]

    response_list = client.get(f"/api/trips/{trip_id}/tasks", headers=headers)
    assert response_list.status_code == 200, response_list.text
    assert any(t["id"] == task_id for t in response_list.json()["data"])

    patch = {"status": "done", "priority": 2}
    response_update = client.patch(f"/api/trips/{trip_id}/tasks/{task_id}", json=patch, headers=headers)
    assert response_update.status_code == 200, response_update.text
    updated = response_update.json()
    assert updated["code"] == 0
    assert updated["data"]["status"] == "done"
    assert updated["data"]["priority"] == 2

    response_delete = client.delete(f"/api/trips/{trip_id}/tasks/{task_id}", headers=headers)
    assert response_delete.status_code == 200, response_delete.text
    assert response_delete.json()["code"] == 0

    verify = client.get(f"/api/trips/{trip_id}/tasks", headers=headers)
    assert verify.status_code == 200
    assert all(t["id"] != task_id for t in verify.json()["data"])


def test_tasks_requires_auth_and_not_found(client: TestClient):
    response = client.post("/api/trips/1/tasks", json={"stage": "pre", "title": "x"})
    assert response.status_code == 401, response.text

    token = _register_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    trip_id = _create_trip(client, headers)
    response_update = client.patch(f"/api/trips/{trip_id}/tasks/999999", json={"status": "done"}, headers=headers)
    assert response_update.status_code in (404, 400), response_update.text
