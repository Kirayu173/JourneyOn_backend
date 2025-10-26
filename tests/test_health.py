from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

# client = TestClient(app)


def test_health_endpoint(client: TestClient):
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert "code" in body and body["code"] in (0, 200, 422, 500)
    assert "data" in body