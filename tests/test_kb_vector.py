import uuid

from fastapi.testclient import TestClient

from app.api.routes import kb_vector as kb_vector_module
from app.core.config import settings


def _register(client: TestClient) -> str:
    uid = uuid.uuid4().hex[:8]
    username = f"kbvec_{uid}"
    email = f"{username}@example.com"
    password = "TestPass123!"
    response = client.post(
        "/api/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["token"]


def test_kb_vector_search_and_rate_limit(client: TestClient) -> None:
    token = _register(client)
    headers = {"Authorization": f"Bearer {token}"}

    original_limit = settings.RATE_LIMIT_PER_MINUTE
    settings.RATE_LIMIT_PER_MINUTE = 2
    kb_vector_module._local_rate.clear()
    try:
        first = client.post(
            "/api/kb/search",
            json={"query": "美食推荐", "filters": {"stage": "pre"}, "top_k": 5},
            headers=headers,
        )
        assert first.status_code == 200, first.text
        assert first.json()["data"] == []

        second = client.get(
            "/api/kb/search",
            params={"q": "城市推荐"},
            headers=headers,
        )
        assert second.status_code == 200, second.text
        assert second.json()["data"] == []

        third = client.post(
            "/api/kb/search",
            json={"query": "更多建议"},
            headers=headers,
        )
        assert third.status_code == 429
        assert third.json()["msg"] == "rate_limited"
    finally:
        settings.RATE_LIMIT_PER_MINUTE = original_limit
        kb_vector_module._local_rate.clear()


def test_kb_health_endpoint(client: TestClient) -> None:
    response = client.get("/api/kb/health")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["code"] in (0, 500)
    assert set(body["data"].keys()) == {"qdrant", "embedding", "redis"}
