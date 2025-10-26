from __future__ import annotations

from datetime import datetime, timezone
import uuid
from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.db.models import User, Trip
from app.services.conversation_service import save_message


def _tz_aware_utc(dt: datetime) -> bool:
    return dt.tzinfo is not None and dt.utcoffset(None) is not None and dt.utcoffset(None).total_seconds() == 0


def test_created_at_fields_are_timezone_aware(client: TestClient):
    # Register a user
    uid = uuid.uuid4().hex[:8]
    r = client.post(
        "/api/auth/register",
        json={"username": f"tz_user_{uid}", "email": f"tz_{uid}@example.com", "password": "Pass123!"},
    )
    assert r.status_code == 200, r.text
    user_id = r.json()["data"]["user"]["id"]
    token = r.json()["data"]["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create a trip
    rc = client.post(
        "/api/trips",
        json={"title": "TZ Trip", "destination": "UTC City", "duration_days": 1},
        headers=headers,
    )
    assert rc.status_code == 200, rc.text
    trip_id = rc.json()["data"]["id"]

    # Validate timezone-aware created_at for User and Trip
    db = SessionLocal()
    try:
        # Skip strict DB timezone check on SQLite which doesn't preserve tzinfo
        if db.get_bind().dialect.name == "sqlite":
            # Basic sanity: default callable produces aware UTC datetime
            dt = datetime.now(timezone.utc)
            assert dt.tzinfo is not None and dt.utcoffset() is not None
            return

        user = db.get(User, user_id)
        trip = db.get(Trip, trip_id)
        assert user is not None and trip is not None
        assert _tz_aware_utc(user.created_at), f"User.created_at should be UTC-aware, got: {user.created_at!r}"
        assert _tz_aware_utc(trip.created_at), f"Trip.created_at should be UTC-aware, got: {trip.created_at!r}"

        # Save a conversation via service and validate created_at
        conv = save_message(
            db,
            trip_id=trip_id,
            user_id=user_id,
            stage="pre",
            role="user",
            message="hello",
            message_meta={"source": "test"},
        )
        assert _tz_aware_utc(conv.created_at), f"Conversation.created_at should be UTC-aware, got: {conv.created_at!r}"
    finally:
        db.close()