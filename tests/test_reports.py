import base64
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

import app.storage as storage_module
from app.storage import LocalFileStorage


def _register_user(client: TestClient) -> tuple[str, int]:
    uid = uuid.uuid4().hex[:8]
    username = f"report_user_{uid}"
    email = f"{username}@example.com"
    password = "TestPass123!"
    response = client.post(
        "/api/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    return data["token"], data["user"]["id"]


def _create_trip(client: TestClient, headers: dict) -> int:
    response = client.post(
        "/api/trips",
        json={"title": "Report Trip", "destination": "Shanghai", "duration_days": 3},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["id"]


def test_reports_crud_flow(client: TestClient, tmp_path: Path) -> None:
    storage_module._storage_instance = LocalFileStorage(tmp_path)
    try:
        token, _ = _register_user(client)
        headers = {"Authorization": f"Bearer {token}"}
        trip_id = _create_trip(client, headers)

        file_bytes = b"PDF binary content"
        payload = {
            "filename": "summary.pdf",
            "content_type": "application/pdf",
            "data": base64.b64encode(file_bytes).decode("ascii"),
            "format": "pdf",
        }

        upload_resp = client.post(
            f"/api/trips/{trip_id}/reports",
            json=payload,
            headers=headers,
        )
        assert upload_resp.status_code == 200, upload_resp.text
        body = upload_resp.json()
        assert body["code"] == 0
        report_id = body["data"]["id"]
        storage_key = body["data"]["storage_key"]

        stored_path = tmp_path / storage_key
        assert stored_path.exists()

        list_resp = client.get(f"/api/trips/{trip_id}/reports", headers=headers)
        assert list_resp.status_code == 200, list_resp.text
        listed_ids = [item["id"] for item in list_resp.json()["data"]]
        assert report_id in listed_ids

        detail_resp = client.get(
            f"/api/trips/{trip_id}/reports/{report_id}", headers=headers
        )
        assert detail_resp.status_code == 200, detail_resp.text
        assert detail_resp.json()["data"]["filename"] == "summary.pdf"

        download_resp = client.get(
            f"/api/trips/{trip_id}/reports/{report_id}/download",
            headers=headers,
        )
        assert download_resp.status_code == 200, download_resp.text
        assert download_resp.content == file_bytes

        delete_resp = client.delete(
            f"/api/trips/{trip_id}/reports/{report_id}", headers=headers
        )
        assert delete_resp.status_code == 200, delete_resp.text
        assert delete_resp.json()["code"] == 0

        assert not stored_path.exists()
    finally:
        storage_module._storage_instance = None


def test_report_upload_invalid_base64(client: TestClient, tmp_path: Path) -> None:
    storage_module._storage_instance = LocalFileStorage(tmp_path)
    try:
        token, _ = _register_user(client)
        headers = {"Authorization": f"Bearer {token}"}
        trip_id = _create_trip(client, headers)

        payload = {
            "filename": "broken.pdf",
            "content_type": "application/pdf",
            "data": "not_base64",
        }

        response = client.post(
            f"/api/trips/{trip_id}/reports",
            json=payload,
            headers=headers,
        )
        assert response.status_code == 400, response.text
        body = response.json()
        assert body["msg"] == "invalid_base64"
    finally:
        storage_module._storage_instance = None
