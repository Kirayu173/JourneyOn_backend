from __future__ import annotations

import logging
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.providers.mock_tools import (
    generate_agent_reply,
    get_mock_weather,
    search_mock_flights,
    search_mock_hotels,
    search_mock_pois,
    suggest_itinerary_items,
    suggest_tasks,
)
from app.services.trip_service import get_trip

logger = logging.getLogger(__name__)


class Orchestrator:
    """Agent orchestrator stub for Phase Three.

    Coordinates simple keyword-based suggestions without LLM, validates
    trip ownership via DB session.
    """

    def __init__(self, db: Session):
        self.db = db

    def handle_message(self, trip_id: int, stage: str, message: str, user_id: int) -> Dict[str, Any]:
        logger.info({"event": "agent_chat_stub", "trip_id": trip_id, "stage": stage})
        trip = get_trip(self.db, trip_id, user_id)
        if trip is None:
            return {
                "reply": "Trip not found or access is not permitted.",
                "tools": [],
                "tool_results": {},
                "task_suggestions": [],
                "itinerary_suggestions": [],
                "source": "orchestrator_stub",
            }

        reply = generate_agent_reply(stage, message)
        tasks: List[Dict[str, Any]] = suggest_tasks(stage, message)
        itinerary: List[Dict[str, Any]] = suggest_itinerary_items(stage, message)

        tools_called: List[str] = []
        tool_results: Dict[str, Any] = {}
        msg = message.lower()
        dest = getattr(trip, "destination", None) or "unknown"
        budget = getattr(trip, "budget", None)

        if stage == "pre" and ("hotel" in msg or "stay" in msg):
            hotels = search_mock_hotels(dest, budget)
            tools_called.append("hotel_search_mock")
            tool_results["hotel_search_mock"] = {"items": hotels}
        if stage == "pre" and ("flight" in msg or "air" in msg):
            flights = search_mock_flights("origin", dest)
            tools_called.append("flight_search_mock")
            tool_results["flight_search_mock"] = {"items": flights}
        if "weather" in msg:
            weather = get_mock_weather(dest)
            tools_called.append("weather_mock")
            tool_results["weather_mock"] = weather
        if "poi" in msg or "sight" in msg or "attraction" in msg:
            pois = search_mock_pois(dest)
            tools_called.append("poi_search_mock")
            tool_results["poi_search_mock"] = {"items": pois}

        if not tools_called:
            tools_called.append("mock_tools")

        return {
            "reply": reply["reply"],
            "tools": tools_called,
            "tool_results": tool_results,
            "task_suggestions": tasks,
            "itinerary_suggestions": itinerary,
            "source": "orchestrator_stub",
        }
