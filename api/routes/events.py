"""Event history routes."""

from fastapi import APIRouter, HTTPException
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.database import get_all_events, get_event_by_id, sync_csv_to_db, update_event, delete_event
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from cli.events import get_recent_events

router = APIRouter(prefix="/api/events", tags=["events"])


def calculate_cash_delta(event_type: str, data: dict) -> tuple[bool, float]:
    """
    Calculate cash_delta from event type and data.
    Returns (affects_cash, cash_delta).
    """
    if event_type == 'TRADE':
        action = data.get('action', '').upper()
        total = float(data.get('total', 0))
        if action == 'BUY':
            return True, -total  # Buying costs money
        elif action == 'SELL':
            return True, total   # Selling gives money
        return False, 0

    elif event_type == 'OPTION_OPEN':
        # Selling options (puts/calls) collects premium
        premium = float(data.get('total_premium', data.get('premium', 0)))
        return True, premium

    elif event_type == 'OPTION_CLOSE':
        # Buying back option costs money
        close_cost = float(data.get('close_cost', 0))
        return True, -close_cost

    elif event_type == 'OPTION_EXPIRE':
        # No cash impact - premium already collected at open
        return False, 0

    elif event_type == 'OPTION_ASSIGN':
        # Assignment: depends on put/call and action
        # For puts: you buy shares at strike
        # For calls: you sell shares at strike
        action = data.get('action', '').upper()
        total = float(data.get('total', 0))
        if action == 'BUY':
            return True, -total
        elif action == 'SELL':
            return True, total
        return False, 0

    elif event_type == 'DEPOSIT':
        amount = float(data.get('amount', 0))
        return True, amount

    elif event_type == 'WITHDRAWAL':
        amount = float(data.get('amount', 0))
        return True, -amount

    elif event_type == 'DIVIDEND':
        amount = float(data.get('amount', 0))
        return True, amount

    elif event_type in ['PRICE_UPDATE', 'NOTE', 'GOAL_UPDATE', 'STRATEGY_UPDATE']:
        return False, 0

    return False, 0


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
    formatted = [format_event(e) for e in events]

    # Track which options have been closed
    closed_option_ids = set()
    closed_position_ids = set()

    for e in formatted:
        if e['event_type'] in ['OPTION_CLOSE', 'OPTION_EXPIRE', 'OPTION_ASSIGN']:
            if e['data'].get('option_id'):
                closed_option_ids.add(e['data']['option_id'])
            if e['data'].get('position_id'):
                closed_position_ids.add(e['data']['position_id'])

    # Mark closed options in OPTION_OPEN events (only if status not already set)
    for e in formatted:
        if e['event_type'] == 'OPTION_OPEN':
            # Don't overwrite if status was manually set in CSV
            if 'status' not in e['data']:
                is_closed = (
                    e['event_id'] in closed_option_ids or
                    e['data'].get('position_id') in closed_position_ids
                )
                if is_closed:
                    e['data']['status'] = 'CLOSED'
                else:
                    e['data']['status'] = 'OPEN'

    return {
        "events": formatted,
        "total": len(formatted)
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


class EventUpdate(BaseModel):
    """Request model for updating an event."""
    data: Optional[Dict[str, Any]] = None
    reason: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None
    tags: Optional[List[str]] = None
    affects_cash: Optional[bool] = None
    cash_delta: Optional[float] = None


@router.put("/{event_id}")
async def update_event_by_id(event_id: int, update: EventUpdate):
    """
    Update an event by ID.

    Updates both the CSV (source of truth) and SQLite database.
    Automatically recalculates cash_delta when data is changed.
    """
    # Check event exists
    existing = get_event_by_id(event_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

    event_type = existing.get('event_type')

    # Build updates dict
    updates = {}
    if update.data is not None:
        updates['data_json'] = update.data
    if update.reason is not None:
        updates['reason_json'] = update.reason
    if update.notes is not None:
        updates['notes'] = update.notes
    if update.tags is not None:
        updates['tags_json'] = update.tags

    # Auto-calculate cash_delta from data if data was updated
    if update.data is not None:
        affects_cash, cash_delta = calculate_cash_delta(event_type, update.data)
        updates['affects_cash'] = affects_cash
        updates['cash_delta'] = cash_delta
    else:
        # Allow manual override only if data wasn't changed
        if update.affects_cash is not None:
            updates['affects_cash'] = update.affects_cash
        if update.cash_delta is not None:
            updates['cash_delta'] = update.cash_delta

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Perform update
    success = update_event(event_id, updates)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update event")

    # Return updated event
    sync_csv_to_db()
    updated = get_event_by_id(event_id)
    return {
        "success": True,
        "message": f"Event {event_id} updated (cash_delta auto-calculated)",
        "event": format_event(updated)
    }


@router.post("/recalculate-all")
async def recalculate_all_events():
    """
    Recalculate cash_delta for ALL events based on their data.

    Use this to fix historical inconsistencies or after bulk edits.
    """
    import pandas as pd
    from api.database import CSV_PATH

    if not CSV_PATH.exists():
        raise HTTPException(status_code=404, detail="Event log not found")

    df = pd.read_csv(CSV_PATH)
    updated_count = 0
    changes = []

    for idx, row in df.iterrows():
        event_type = row['event_type']
        try:
            data = json.loads(row['data_json']) if isinstance(row['data_json'], str) else row['data_json']
        except (json.JSONDecodeError, TypeError):
            data = {}

        affects_cash, new_delta = calculate_cash_delta(event_type, data)
        old_delta = float(row.get('cash_delta', 0) or 0)

        if abs(new_delta - old_delta) > 0.01:  # Allow small float tolerance
            changes.append({
                'event_id': int(row['event_id']),
                'event_type': event_type,
                'old_delta': old_delta,
                'new_delta': new_delta,
                'diff': new_delta - old_delta
            })
            df.at[idx, 'affects_cash'] = affects_cash
            df.at[idx, 'cash_delta'] = new_delta
            updated_count += 1

    if updated_count > 0:
        df.to_csv(CSV_PATH, index=False)
        sync_csv_to_db()

    return {
        "success": True,
        "message": f"Recalculated {updated_count} events",
        "updated_count": updated_count,
        "changes": changes
    }


@router.delete("/{event_id}")
async def delete_event_by_id(event_id: int):
    """
    Delete an event by ID.

    Removes from CSV (source of truth) and syncs to SQLite.
    WARNING: This is permanent and affects portfolio state reconstruction.
    """
    # Check event exists
    existing = get_event_by_id(event_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

    # Perform delete
    success = delete_event(event_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete event")

    return {
        "success": True,
        "message": f"Event {event_id} deleted",
        "deleted_event": format_event(existing)
    }
