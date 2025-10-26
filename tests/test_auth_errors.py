from __future__ import annotations

import uuid
from fastapi.testclient import TestClient


def _register_and_get_token(client: TestClient) -> tuple[str, str, str]:
    uid = uuid.uuid4().hex[:8]
    username = f"user_{uid}"
    email = f"{uid}@example.com"
    password = "TestPass123!"
    r = client.post("/api/auth/register", json={"username": username, "email": email, "password": password})
    assert r.status_code == 200, r.text
    token = r.json()["data"]["token"]
    return username, email, password


def test_register_duplicate_user(client: TestClient):
    username, email, password = _register_and_get_token(client)
    r = client.post("/api/auth/register", json={"username": username, "email": email, "password": password})
    assert r.status_code == 409, r.text
    body = r.json()
    assert body["code"] == 409
    assert body["msg"] == "user_already_exists"


def test_login_invalid_credentials(client: TestClient):
    username, email, password = _register_and_get_token(client)
    r = client.post("/api/auth/login", json={"username_or_email": username, "password": "WrongPass!"})
    assert r.status_code == 401, r.text
    body = r.json()
    assert body["code"] == 401
    assert body["msg"] == "invalid_credentials"