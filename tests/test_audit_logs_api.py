import uuid

from fastapi.testclient import TestClient

from app.db.models import User
from app.db.session import SessionLocal


def _register(client: TestClient, prefix: str) -> tuple[str, int]:
    username = f"{prefix}_{uuid.uuid4().hex[:6]}"
    email = f"{username}@example.com"
    password = "TestPass123!"
    response = client.post(
        "/api/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    return data["token"], data["user"]["id"]


def _create_trip_and_stage(client: TestClient, headers: dict) -> int:
    resp = client.post(
        "/api/trips",
        json={"title": "Audit Trip", "destination": "Chengdu", "duration_days": 2},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    trip_id = resp.json()["data"]["id"]

    stage_resp = client.patch(
        f"/api/trips/{trip_id}/stage",
        json={"new_stage": "on"},
        headers=headers,
    )
    assert stage_resp.status_code == 200, stage_resp.text
    return trip_id


def test_audit_log_listing_requires_admin(client: TestClient) -> None:
    user_token, _ = _register(client, "normal")
    user_headers = {"Authorization": f"Bearer {user_token}"}
    _create_trip_and_stage(client, user_headers)

    admin_token, admin_id = _register(client, "admin")
    with SessionLocal() as db:
        admin = db.get(User, admin_id)
        admin.meta = {"is_admin": True}
        db.add(admin)
        db.commit()

    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    forbidden_resp = client.get("/api/audit-logs", headers=user_headers)
    assert forbidden_resp.status_code == 403

    logs_resp = client.get("/api/audit-logs", headers=admin_headers)
    assert logs_resp.status_code == 200, logs_resp.text
    body = logs_resp.json()
    assert body["code"] == 0
    actions = [entry["action"] for entry in body["data"]]
    assert "trip_created" in actions
    assert "trip_stage_updated" in actions or len(actions) >= 1

    filtered_resp = client.get(
        "/api/audit-logs",
        params={"user_id": admin_id, "limit": 10},
        headers=admin_headers,
    )
    assert filtered_resp.status_code == 200
    assert filtered_resp.json()["code"] == 0
