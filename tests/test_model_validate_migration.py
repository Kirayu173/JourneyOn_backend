from __future__ import annotations

from datetime import datetime, timezone

from app.schemas.conversation_schemas import ConversationResponse
from app.schemas.itinerary_schemas import ItineraryItemResponse
from app.schemas.task_schemas import TaskResponse


class _TaskORM:
    def __init__(self):
        self.id = 1
        self.trip_id = 7
        self.stage = "pre"
        self.title = "Book flights"
        self.description = "Purchase tickets before Friday"
        self.status = "todo"
        self.priority = 1
        self.assigned_to = None
        self.due_date = None
        self.meta = {}


class _ItineraryORM:
    def __init__(self):
        self.id = 2
        self.trip_id = 7
        self.day = 1
        self.start_time = "09:00"
        self.end_time = "10:00"
        self.kind = "poi"
        self.title = "Museum visit"
        self.location = "Downtown"
        self.lat = 30.0
        self.lng = 120.0
        self.details = "Book tickets in advance"


class _ConversationORM:
    def __init__(self):
        self.id = 3
        self.trip_id = 7
        self.stage = "pre"
        self.role = "user"
        self.message = "Help me plan pre-trip tasks"
        self.message_meta = {"source": "test"}
        self.created_at = datetime.now(timezone.utc)


def test_task_response_model_validate():
    orm = _TaskORM()
    resp = TaskResponse.model_validate(orm)
    data = resp.model_dump()
    assert data["id"] == 1 and data["trip_id"] == 7
    assert data["stage"] == "pre" and data["title"] == "Book flights"
    assert data["status"] == "todo" and data["priority"] == 1


def test_itinerary_item_response_model_validate():
    orm = _ItineraryORM()
    resp = ItineraryItemResponse.model_validate(orm)
    data = resp.model_dump()
    assert data["id"] == 2 and data["day"] == 1
    assert data["title"] == "Museum visit" and data["kind"] == "poi"
    assert data["start_time"] == "09:00" and data["end_time"] == "10:00"


def test_conversation_response_model_validate():
    orm = _ConversationORM()
    resp = ConversationResponse.model_validate(orm)
    data = resp.model_dump()
    assert data["id"] == 3 and data["trip_id"] == 7
    assert data["role"] == "user" and data["stage"] == "pre"
    assert isinstance(data["created_at"], datetime)
