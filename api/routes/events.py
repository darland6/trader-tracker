"""Event history routes."""

from fastapi import APIRouter, HTTPException
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.database import get_all_events, get_event_by_id, sync_csv_to_db
from cli.events import get_recent_events

router = APIRouter(prefix="/api/events", tags=["events"])


def format_event(event: dict) -> dict:
    """Format event for API response."""
    return {
        "event_id": event.get('event_id'),
        "timestamp": event.get('timestamp'),
        "event_type": event.get('event_type'),
        "data": json.loads(event.get('data_json', '{}')),
        "reason": json.loads(event.get('reason_json', '{}')),
        "notes": event.get('notes', ''),
        "tags": json.loads(event.get('tags_json', '[]')),
        "affects_cash": bool(event.get('affects_cash')),
        "cash_delta": event.get('cash_delta', 0)
    }


@router.get("")
async def list_events(limit: int = 50, event_type: str = None, ticker: str = None):
    """Get list of events with optional filtering."""
    # Sync database first
    sync_csv_to_db()

    events = get_all_events(limit=limit, event_type=event_type, ticker=ticker)
    return {
        "events": [format_event(e) for e in events],
        "total": len(events)
    }


@router.get("/{event_id}")
async def get_event(event_id: int):
    """Get a single event by ID."""
    sync_csv_to_db()

    event = get_event_by_id(event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

    return format_event(event)


@router.get("/recent/{count}")
async def get_recent(count: int = 10, ticker: str = None):
    """Get recent events."""
    events = get_recent_events(limit=count, ticker=ticker)
    return {
        "events": [format_event(e) for e in events],
        "count": len(events)
    }
