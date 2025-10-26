from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def test_request_id_header_and_dynamic_level(client: TestClient):
    # Request ID generated and returned
    r1 = client.get("/api/health")
    assert r1.status_code == 200
    assert "X-Request-ID" in r1.headers
    rid = r1.headers["X-Request-ID"]
    assert isinstance(rid, str) and len(rid) > 0

    # Request ID propagated when provided
    r2 = client.get("/api/health", headers={"X-Request-ID": "test-req-123"})
    assert r2.headers.get("X-Request-ID") == "test-req-123"

    # Dynamic log level endpoint requires auth
    # Register and login
    uid = uuid.uuid4().hex[:8]
    username = f"loguser_{uid}"
    email = f"log_{uid}@example.com"
    reg = client.post("/api/auth/register", json={"username": username, "email": email, "password": "Secret123!"})
    assert reg.status_code == 200
    token = reg.json()["data"]["token"]
    headers = {"Authorization": f"Bearer {token}"}
    p = client.patch("/api/system/log-level", json={"level": "debug"}, headers=headers)
    assert p.status_code == 200
    assert p.json()["data"]["level"] == "DEBUG"

    # Invalid level
    p2 = client.patch("/api/system/log-level", json={"level": "invalid"}, headers=headers)
    assert p2.status_code == 200
    assert p2.json()["code"] == 400
