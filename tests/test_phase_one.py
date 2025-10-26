import os
import uuid
from fastapi.testclient import TestClient

# Ensure tests use a local sqlite db file
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("LOG_LEVEL", "debug")

from app.main import app  # noqa: E402

# client = TestClient(app)


def test_auth_register_and_login(client: TestClient):
    # Unique user credentials
    uid = uuid.uuid4().hex[:8]
    username = f"user_{uid}"
    email = f"{uid}@example.com"
    password = "TestPass123!"

    # Register
    r = client.post("/api/auth/register", json={"username": username, "email": email, "password": password})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["code"] == 0
    assert "token" in body["data"], body
    token = body["data"]["token"]

    # Login by username
    r2 = client.post("/api/auth/login", json={"username_or_email": username, "password": password})
    assert r2.status_code == 200, r2.text
    body2 = r2.json()
    assert body2["code"] == 0
    assert "token" in body2["data"], body2

    # Login by email
    r3 = client.post("/api/auth/login", json={"username_or_email": email, "password": password})
    assert r3.status_code == 200, r3.text
    body3 = r3.json()
    assert body3["code"] == 0
    assert "token" in body3["data"], body3

    # Do not return values from tests (pytest strict)
    # formerly: return token


def test_trips_crud_flow(client: TestClient):
    # Prepare user and token
    uid = uuid.uuid4().hex[:8]
    username = f"user_{uid}"
    email = f"{uid}@example.com"
    password = "TestPass123!"
    r = client.post("/api/auth/register", json={"username": username, "email": email, "password": password})
    assert r.status_code == 200, r.text
    token = r.json()["data"]["token"]

    headers = {"Authorization": f"Bearer {token}"}

    # Create trip
    create_payload = {
        "title": "Weekend Trip",
        "destination": "Beijing",
        "duration_days": 3,
        "budget": 1500.0,
        "currency": "CNY",
    }
    rc = client.post("/api/trips", json=create_payload, headers=headers)
    assert rc.status_code == 200, rc.text
    create_body = rc.json()
    assert create_body["code"] == 0
    trip_id = create_body["data"]["id"]

    # List trips
    rl = client.get("/api/trips", headers=headers)
    assert rl.status_code == 200, rl.text
    list_body = rl.json()
    assert list_body["code"] == 0
    assert any(item["id"] == trip_id for item in list_body["data"])  # created trip present

    # Get trip
    rg = client.get(f"/api/trips/{trip_id}", headers=headers)
    assert rg.status_code == 200, rg.text
    get_body = rg.json()
    assert get_body["code"] == 0
    assert get_body["data"]["id"] == trip_id

    # Update stage to 'on'
    ru = client.patch(f"/api/trips/{trip_id}/stage", json={"new_stage": "on"}, headers=headers)
    assert ru.status_code == 200, ru.text
    update_body = ru.json()
    assert update_body["code"] == 0
    assert update_body["data"]["current_stage"] == "on"