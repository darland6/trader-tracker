"""Core data access layer - CSV is single source of truth.

This module centralizes all event log operations. CSV is the ONLY writable source.
SQLite is a read-only cache that is rebuilt from CSV.

KEY PRINCIPLES:
1. All event writes go through append_event() in this module
2. CSV is the canonical source of truth
3. SQLite is rebuilt from CSV via sync_to_cache()
4. File locking prevents concurrent write corruption
5. Never write directly to SQLite events table
"""

import pandas as pd
import json
import fcntl
import os
from datetime import datetime, date
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from contextlib import contextmanager

SCRIPT_DIR = Path(__file__).parent.parent.resolve()
CSV_PATH = SCRIPT_DIR / 'data' / 'event_log_enhanced.csv'


@contextmanager
def csv_lock(mode='r'):
    """
    File lock context manager for CSV operations.
    Prevents concurrent write corruption.

    Usage:
        with csv_lock('w'):
            # perform write operations
            df.to_csv(CSV_PATH, index=False)
    """
    lock_path = CSV_PATH.with_suffix('.lock')
    lock_file = open(lock_path, 'w')

    try:
        # Acquire exclusive lock for writes, shared lock for reads
        lock_type = fcntl.LOCK_EX if mode == 'w' else fcntl.LOCK_SH
        fcntl.flock(lock_file.fileno(), lock_type)
        yield
    finally:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        lock_file.close()


def load_events(parse_json: bool = True) -> pd.DataFrame:
    """
    Load all events from CSV (source of truth).

    Args:
        parse_json: If True, parse JSON columns into dicts/lists

    Returns:
        DataFrame with all events
    """
    with csv_lock('r'):
        df = pd.read_csv(CSV_PATH)

        if parse_json:
            # Parse JSON columns
            for col in ['data_json', 'reason_json', 'tags_json']:
                if col in df.columns:
                    df[col.replace('_json', '')] = df[col].apply(
                        lambda x: json.loads(x) if pd.notna(x) and x else ({} if col != 'tags_json' else [])
                    )

        return df


def get_next_event_id() -> int:
    """Get the next available event ID."""
    df = load_events(parse_json=False)
    return int(df['event_id'].max()) + 1 if len(df) > 0 else 1


def append_event(
    event_type: str,
    data: Dict[str, Any],
    reason: Optional[Dict[str, Any]] = None,
    notes: str = "",
    tags: Optional[List[str]] = None,
    affects_cash: bool = False,
    cash_delta: float = 0
) -> int:
    """
    Append a new event to the CSV log (source of truth).

    This is the ONLY function that should write events.
    All event creation must go through this function.

    Args:
        event_type: Type of event (TRADE, OPTION_OPEN, etc.)
        data: Event data dictionary
        reason: Reason dictionary with primary, explanation, etc.
        notes: Free-form notes
        tags: List of tags
        affects_cash: Whether this event affects cash balance
        cash_delta: Change in cash (positive = inflow, negative = outflow)

    Returns:
        The event_id of the created event
    """
    if reason is None:
        reason = {}
    if tags is None:
        tags = []

    with csv_lock('w'):
        df = pd.read_csv(CSV_PATH)

        event_id = int(df['event_id'].max()) + 1 if len(df) > 0 else 1
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        new_row = {
            'event_id': event_id,
            'timestamp': timestamp,
            'event_type': event_type,
            'data_json': json.dumps(data),
            'reason_json': json.dumps(reason),
            'notes': notes,
            'tags_json': json.dumps(tags),
            'affects_cash': affects_cash,
            'cash_delta': cash_delta
        }

        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        df.to_csv(CSV_PATH, index=False)

    return event_id


def update_event(event_id: int, updates: Dict[str, Any]) -> bool:
    """
    Update an event in the CSV (source of truth).

    Args:
        event_id: The event ID to update
        updates: Dict with fields to update (data, reason, notes, tags, affects_cash, cash_delta)

    Returns:
        True if successful, False if event not found
    """
    with csv_lock('w'):
        df = pd.read_csv(CSV_PATH)

        mask = df['event_id'] == event_id
        if not mask.any():
            return False

        # Update fields
        for field, value in updates.items():
            # Map field names to CSV column names
            if field == 'data':
                field = 'data_json'
                value = json.dumps(value) if isinstance(value, dict) else value
            elif field == 'reason':
                field = 'reason_json'
                value = json.dumps(value) if isinstance(value, dict) else value
            elif field == 'tags':
                field = 'tags_json'
                value = json.dumps(value) if isinstance(value, list) else value

            if field in df.columns:
                if field in ['affects_cash']:
                    df.loc[mask, field] = bool(value)
                elif field in ['cash_delta']:
                    df.loc[mask, field] = float(value)
                else:
                    df.loc[mask, field] = value

        df.to_csv(CSV_PATH, index=False)

    return True


def delete_event(event_id: int) -> bool:
    """
    Delete an event from the CSV (source of truth).

    Args:
        event_id: The event ID to delete

    Returns:
        True if successful, False if event not found
    """
    with csv_lock('w'):
        df = pd.read_csv(CSV_PATH)
        mask = df['event_id'] == event_id

        if not mask.any():
            return False

        df = df[~mask]
        df.to_csv(CSV_PATH, index=False)

    return True


def get_event_by_id(event_id: int, parse_json: bool = True) -> Optional[Dict[str, Any]]:
    """
    Get a single event by ID from CSV.

    Args:
        event_id: The event ID to retrieve
        parse_json: If True, parse JSON columns

    Returns:
        Event dict or None if not found
    """
    df = load_events(parse_json=parse_json)
    mask = df['event_id'] == event_id

    if not mask.any():
        return None

    row = df[mask].iloc[0]
    return row.to_dict()


def get_events(
    limit: Optional[int] = None,
    event_type: Optional[str] = None,
    ticker: Optional[str] = None,
    parse_json: bool = True
) -> List[Dict[str, Any]]:
    """
    Get events with optional filtering.

    Args:
        limit: Maximum number of events to return (most recent first)
        event_type: Filter by event type
        ticker: Filter by ticker (searches in data_json)
        parse_json: If True, parse JSON columns

    Returns:
        List of event dicts
    """
    df = load_events(parse_json=False)

    if event_type:
        df = df[df['event_type'] == event_type]

    if ticker:
        ticker_upper = ticker.upper()
        df = df[df['data_json'].str.contains(f'"{ticker_upper}"', case=False, na=False)]

    # Sort by event_id descending (most recent first)
    df = df.sort_values('event_id', ascending=False)

    if limit:
        df = df.head(limit)

    if parse_json:
        for col in ['data_json', 'reason_json', 'tags_json']:
            if col in df.columns:
                df[col.replace('_json', '')] = df[col].apply(
                    lambda x: json.loads(x) if pd.notna(x) and x else ({} if col != 'tags_json' else [])
                )

    return df.to_dict('records')


def sync_to_cache():
    """
    Sync CSV to SQLite cache (read-only rebuild).

    This function rebuilds the SQLite events table from the CSV.
    SQLite should NEVER be written to directly for events - only through this sync.
    """
    from api.database import sync_csv_to_db
    return sync_csv_to_db()


def compact_price_events() -> Dict[str, int]:
    """
    Compact PRICE_UPDATE events - keep only first and last of each day.
    This reduces event log bloat from frequent price checks.

    Returns:
        Dict with count of events removed per day
    """
    with csv_lock('w'):
        df = pd.read_csv(CSV_PATH)

        # Parse timestamps
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['date'] = df['timestamp'].dt.date

        # Get only PRICE_UPDATE events
        price_events = df[df['event_type'] == 'PRICE_UPDATE'].copy()

        if len(price_events) <= 2:
            return {}  # Nothing to compact

        removed_counts = {}
        events_to_remove = []

        # Group by date
        for date_val, group in price_events.groupby('date'):
            if len(group) <= 2:
                continue  # Keep all if only 1 or 2 events

            # Sort by timestamp within the day
            group_sorted = group.sort_values('timestamp')

            # Keep first and last, mark middle ones for removal
            middle_events = group_sorted.iloc[1:-1]
            events_to_remove.extend(middle_events['event_id'].tolist())
            removed_counts[str(date_val)] = len(middle_events)

        if not events_to_remove:
            return {}

        # Remove the middle events
        df = df[~df['event_id'].isin(events_to_remove)]

        # Drop helper column and save
        df = df.drop('date', axis=1)
        df.to_csv(CSV_PATH, index=False)

    return removed_counts


# Helper functions for backward compatibility with existing code

def calculate_cash_delta(event_type: str, data: dict) -> Tuple[bool, float]:
    """
    Calculate cash_delta from event type and data.
    Returns (affects_cash, cash_delta).

    This is a helper function for automatic cash delta calculation.
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
        # For SELL: receive premium (positive), for BUY: pay premium (negative)
        action = data.get('action', 'SELL').upper()
        premium = float(data.get('total_premium', data.get('premium', 0)))
        if action == 'SELL':
            return True, premium
        else:  # BUY
            return True, -premium

    elif event_type == 'OPTION_CLOSE':
        # Buying back option costs money
        close_cost = float(data.get('close_cost', 0))
        return True, -close_cost

    elif event_type == 'OPTION_EXPIRE':
        # No cash impact - premium already collected at open
        return False, 0

    elif event_type == 'OPTION_ASSIGN':
        # Assignment: depends on put/call and action
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

    elif event_type in ['PRICE_UPDATE', 'NOTE', 'GOAL_UPDATE', 'STRATEGY_UPDATE', 'INSIGHT_LOG', 'ADJUSTMENT']:
        return False, 0

    return False, 0
