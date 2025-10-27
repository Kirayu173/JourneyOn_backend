from __future__ import annotations

from typing import Any, Dict, List, TypedDict


class HotelItem(TypedDict):
    name: str
    price: float
    rating: float
    address: str


def suggest_tasks(stage: str, message: str) -> List[Dict[str, Any]]:
    """Return stub task suggestions based on stage and message keywords."""
    msg = message.lower()
    suggestions: List[Dict[str, Any]] = []
    if stage == "pre":
        if "flight" in msg or "ticket" in msg:
            suggestions.append(
                {
                    "title": "Research and book flights",
                    "description": "Filter flight options by budget and preferred airlines",
                    "priority": 1,
                    "stage": stage,
                }
            )
        if "hotel" in msg or "stay" in msg:
            suggestions.append(
                {
                    "title": "Select hotels near attractions",
                    "description": "Shortlist hotels with rating above 8.5 within budget",
                    "priority": 1,
                    "stage": stage,
                }
            )
    elif stage == "on":
        if "restaurant" in msg or "dinner" in msg:
            suggestions.append(
                {
                    "title": "Book dinner reservation",
                    "description": "Recommend top-rated restaurants within 3 km of current location",
                    "priority": 2,
                    "stage": stage,
                }
            )
        if "transport" in msg or "traffic" in msg:
            suggestions.append(
                {
                    "title": "Plan daily transportation",
                    "description": "Combine metro, walking, and ride-hailing for optimal time and cost",
                    "priority": 2,
                    "stage": stage,
                }
            )
    elif stage == "post":
        suggestions.append(
            {
                "title": "Organise trip recap",
                "description": "Select 20 highlight photos and summarise key experiences",
                "priority": 3,
                "stage": stage,
            }
        )
    return suggestions


def suggest_itinerary_items(stage: str, message: str) -> List[Dict[str, Any]]:
    """Return stub itinerary items based on stage and keywords."""
    msg = message.lower()
    items: List[Dict[str, Any]] = []
    if stage == "pre" and ("plan" in msg or "arrange" in msg):
        items.extend(
            [
                {"day": 1, "start_time": "09:00", "end_time": "12:00", "kind": "sightseeing", "title": "City highlights tour"},
                {"day": 1, "start_time": "13:30", "end_time": "15:00", "kind": "food", "title": "Iconic street food walk"},
            ]
        )
    if stage == "on" and ("today" in msg or "now" in msg):
        items.extend(
            [
                {"day": 1, "start_time": "10:00", "end_time": "11:30", "kind": "museum", "title": "Museum visit"},
            ]
        )
    return items


def generate_agent_reply(stage: str, message: str) -> Dict[str, Any]:
    """Return deterministic agent reply without calling any LLM."""
    base = {
        "stage": stage,
        "reply": "I have prepared an outline to help with your request.",
    }
    if stage == "pre":
        base["reply"] = "Got it! I will arrange flight, hotel, and a high-level travel plan for you."
    elif stage == "on":
        base["reply"] = "While you are travelling, I'll assist with transport tweaks, dining, and daily adjustments."
    elif stage == "post":
        base["reply"] = "After the trip we can assemble a recap with highlights, spend, and preference tags."
    return base


# --- Mock provider functions per Phase Three design ---

def get_mock_weather(city: str) -> Dict[str, Any]:
    return {
        "city": city,
        "temperature_c": 22,
        "condition": "sunny",
        "wind_kmh": 12,
        "humidity": 0.55,
    }


def search_mock_hotels(city: str, budget: float | None = None) -> List[HotelItem]:
    items: List[HotelItem] = [
        {
            "name": "Central City Hotel",
            "price": 480.0,
            "rating": 8.7,
            "address": f"{city} central district",
        },
        {
            "name": "Riverside Hotel",
            "price": 560.0,
            "rating": 9.0,
            "address": f"{city} riverside",
        },
    ]
    if budget is not None:
        items = [h for h in items if h["price"] <= budget]
    return items


def search_mock_flights(origin: str, destination: str, date_str: str | None = None) -> List[Dict[str, Any]]:
    return [
        {
            "carrier": "JO",
            "flight_no": "JO123",
            "origin": origin,
            "destination": destination,
            "depart": "08:30",
            "arrive": "11:15",
        },
        {
            "carrier": "JO",
            "flight_no": "JO456",
            "origin": origin,
            "destination": destination,
            "depart": "18:45",
            "arrive": "21:30",
        },
    ]


def search_mock_pois(city: str, kind: str | None = None) -> List[Dict[str, Any]]:
    pois = [
        {"kind": "sightseeing", "title": "City landmark", "rating": 4.6},
        {"kind": "museum", "title": "History museum", "rating": 4.5},
        {"kind": "food", "title": "Famous food street", "rating": 4.4},
    ]
    if kind:
        pois = [p for p in pois if p["kind"] == kind]
    return pois
