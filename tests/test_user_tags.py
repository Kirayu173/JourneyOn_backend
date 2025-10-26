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


def test_user_tags_crud_and_bulk(client: TestClient):
    token = _register_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Create
    r1 = client.post("/api/user_tags", json={"tag": "beach", "weight": 0.7}, headers=headers)
    assert r1.status_code == 200, r1.text
    body1 = r1.json()
    assert body1["code"] == 0
    tag_id = body1["data"]["id"]

    # List
    r2 = client.get("/api/user_tags", headers=headers)
    assert r2.status_code == 200, r2.text
    assert any(t["id"] == tag_id for t in r2.json()["data"])

    # Update
    r3 = client.patch(f"/api/user_tags/{tag_id}", json={"weight": 0.9}, headers=headers)
    assert r3.status_code == 200
    assert r3.json()["data"]["weight"] == 0.9

    # Bulk upsert
    bulk = [
        {"tag": "beach", "weight": 1.0},
        {"tag": "hiking", "weight": 0.6},
        {"tag": "city"},
    ]
    r4 = client.post("/api/user_tags/bulk_upsert", json=bulk, headers=headers)
    assert r4.status_code == 200, r4.text
    names = {t["tag"] for t in r4.json()["data"]}
    assert {"beach", "hiking", "city"}.issubset(names)

    # Delete
    r5 = client.delete(f"/api/user_tags/{tag_id}", headers=headers)
    assert r5.status_code == 200
    assert r5.json()["data"] is True

    # Verify deletion
    r6 = client.get("/api/user_tags", headers=headers)
    assert r6.status_code == 200
    assert all(t["id"] != tag_id for t in r6.json()["data"]) 


def test_user_tags_requires_auth(client: TestClient):
    r = client.post("/api/user_tags", json={"tag": "x"})
    assert r.status_code == 401, r.text