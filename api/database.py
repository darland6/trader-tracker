"""SQLite database setup and event synchronization."""

import sqlite3
import json
import pandas as pd
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager

SCRIPT_DIR = Path(__file__).parent.parent.resolve()
DB_PATH = SCRIPT_DIR / 'portfolio.db'
CSV_PATH = SCRIPT_DIR / 'data' / 'event_log_enhanced.csv'


def get_db_path():
    return str(DB_PATH)


@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_database():
    """Create SQLite schema mirroring CSV structure."""
    with get_db() as conn:
        cursor = conn.cursor()

        # Events table - mirrors event_log_enhanced.csv
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                event_id INTEGER PRIMARY KEY,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                data_json TEXT NOT NULL,
                reason_json TEXT DEFAULT '{}',
                notes TEXT DEFAULT '',
                tags_json TEXT DEFAULT '[]',
                affects_cash INTEGER DEFAULT 0,
                cash_delta REAL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                is_deleted INTEGER DEFAULT 0
            )
        ''')

        # Indexes for common queries
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_event_type ON events(event_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON events(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_is_deleted ON events(is_deleted)')

        # Price cache table for quick lookups
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS price_cache (
                ticker TEXT PRIMARY KEY,
                price REAL NOT NULL,
                updated_at TEXT NOT NULL,
                session TEXT DEFAULT 'regular'
            )
        ''')

        # Add session column if it doesn't exist (for existing databases)
        try:
            cursor.execute('ALTER TABLE price_cache ADD COLUMN session TEXT DEFAULT "regular"')
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Notifications table for agent alerts
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                severity TEXT DEFAULT 'info',
                title TEXT NOT NULL,
                message TEXT,
                data_json TEXT DEFAULT '{}',
                action_type TEXT,
                action_data_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                read_at TEXT,
                dismissed_at TEXT,
                snoozed_until TEXT
            )
        ''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_notification_severity ON notifications(severity)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_notification_dismissed ON notifications(dismissed_at)')

        # Agent schedules table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS agent_schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_type TEXT NOT NULL UNIQUE,
                description TEXT,
                cron_expression TEXT,
                enabled INTEGER DEFAULT 1,
                last_run TEXT,
                next_run TEXT,
                config_json TEXT DEFAULT '{}'
            )
        ''')

        conn.commit()


def sync_csv_to_db():
    """Full sync from CSV to SQLite (CSV is authoritative source)."""
    if not CSV_PATH.exists():
        return

    df = pd.read_csv(CSV_PATH)

    with get_db() as conn:
        cursor = conn.cursor()

        # Clear existing events (CSV is source of truth)
        cursor.execute('DELETE FROM events')

        for _, row in df.iterrows():
            cursor.execute('''
                INSERT INTO events
                (event_id, timestamp, event_type, data_json, reason_json, notes, tags_json, affects_cash, cash_delta)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                int(row['event_id']),
                str(row['timestamp']),
                str(row['event_type']),
                str(row['data_json']),
                str(row.get('reason_json', '{}')),
                str(row.get('notes', '')),
                str(row.get('tags_json', '[]')),
                1 if row.get('affects_cash', False) else 0,
                float(row.get('cash_delta', 0))
            ))

        conn.commit()

    return len(df)


def get_all_events(limit=None, event_type=None, ticker=None):
    """Get events from database with optional filtering."""
    with get_db() as conn:
        cursor = conn.cursor()

        query = 'SELECT * FROM events WHERE is_deleted = 0'
        params = []

        if event_type:
            query += ' AND event_type = ?'
            params.append(event_type)

        if ticker:
            query += ' AND data_json LIKE ?'
            params.append(f'%"{ticker.upper()}"%')

        query += ' ORDER BY event_id DESC'

        if limit:
            query += ' LIMIT ?'
            params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()

        return [dict(row) for row in rows]


def get_event_by_id(event_id):
    """Get a single event by ID."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM events WHERE event_id = ? AND is_deleted = 0', (event_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def update_price_cache(prices):
    """Update price cache in database.

    Accepts either:
    - dict of {ticker: price} (legacy format)
    - dict of {ticker: {price, session}} (new format with session info)
    """
    now = datetime.now().isoformat()

    with get_db() as conn:
        cursor = conn.cursor()

        for ticker, data in prices.items():
            # Handle both old format (just price) and new format (dict with price/session)
            if isinstance(data, dict):
                price = data.get('price', 0)
                session = data.get('session', 'regular')
            else:
                price = data
                session = 'regular'

            cursor.execute('''
                INSERT OR REPLACE INTO price_cache (ticker, price, updated_at, session)
                VALUES (?, ?, ?, ?)
            ''', (ticker.upper(), float(price), now, session))

        conn.commit()


def get_cached_prices():
    """Get all cached prices with session info."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT ticker, price, updated_at, session FROM price_cache')
        rows = cursor.fetchall()
        return {
            row['ticker']: {
                'price': row['price'],
                'updated_at': row['updated_at'],
                'session': row['session'] or 'regular'
            }
            for row in rows
        }


def update_event(event_id: int, updates: dict) -> bool:
    """
    Update an event in both CSV (source of truth) and SQLite.

    Args:
        event_id: The event ID to update
        updates: Dict with fields to update (data_json, reason_json, notes, tags_json, affects_cash, cash_delta)

    Returns:
        True if successful, False otherwise
    """
    if not CSV_PATH.exists():
        return False

    # Read CSV
    df = pd.read_csv(CSV_PATH)

    # Find the event
    mask = df['event_id'] == event_id
    if not mask.any():
        return False

    # Update fields
    for field, value in updates.items():
        if field in df.columns:
            if field in ['data_json', 'reason_json', 'tags_json']:
                # Ensure JSON fields are strings
                df.loc[mask, field] = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
            elif field == 'affects_cash':
                df.loc[mask, field] = bool(value)
            elif field == 'cash_delta':
                df.loc[mask, field] = float(value)
            else:
                df.loc[mask, field] = value

    # Write back to CSV
    df.to_csv(CSV_PATH, index=False)

    # Sync to SQLite
    sync_csv_to_db()

    return True


def delete_event(event_id: int) -> bool:
    """
    Soft-delete an event (marks as deleted, doesn't remove from CSV).

    For actual deletion, removes from CSV entirely.
    """
    if not CSV_PATH.exists():
        return False

    df = pd.read_csv(CSV_PATH)
    mask = df['event_id'] == event_id

    if not mask.any():
        return False

    # Remove from CSV
    df = df[~mask]
    df.to_csv(CSV_PATH, index=False)

    # Sync to SQLite
    sync_csv_to_db()

    return True


def compact_price_events() -> dict:
    """
    Compact PRICE_UPDATE events - keep only first and last of each day.

    Returns dict with count of events removed per day.
    """
    if not CSV_PATH.exists():
        return {}

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
    for date, group in price_events.groupby('date'):
        if len(group) <= 2:
            continue  # Keep all if only 1 or 2 events

        # Sort by timestamp within the day
        group_sorted = group.sort_values('timestamp')

        # Keep first and last, mark middle ones for removal
        middle_events = group_sorted.iloc[1:-1]
        events_to_remove.extend(middle_events['event_id'].tolist())
        removed_counts[str(date)] = len(middle_events)

    if not events_to_remove:
        return {}

    # Remove the middle events
    df = df[~df['event_id'].isin(events_to_remove)]

    # Drop helper column and save
    df = df.drop('date', axis=1)
    df.to_csv(CSV_PATH, index=False)

    # Sync to SQLite
    sync_csv_to_db()

    return removed_counts


# ============== NOTIFICATION FUNCTIONS ==============

def create_notification(
    type: str,
    title: str,
    message: str = None,
    severity: str = 'info',
    data: dict = None,
    action_type: str = None,
    action_data: dict = None
) -> int:
    """Create a new notification. Returns the notification ID."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO notifications (type, severity, title, message, data_json, action_type, action_data_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            type,
            severity,
            title,
            message,
            json.dumps(data or {}),
            action_type,
            json.dumps(action_data or {})
        ))
        conn.commit()
        return cursor.lastrowid


def get_active_notifications(include_snoozed: bool = False) -> list:
    """Get all non-dismissed notifications."""
    with get_db() as conn:
        cursor = conn.cursor()
        now = datetime.now().isoformat()

        if include_snoozed:
            cursor.execute('''
                SELECT * FROM notifications
                WHERE dismissed_at IS NULL
                ORDER BY
                    CASE severity WHEN 'urgent' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END,
                    created_at DESC
            ''')
        else:
            cursor.execute('''
                SELECT * FROM notifications
                WHERE dismissed_at IS NULL
                AND (snoozed_until IS NULL OR snoozed_until <= ?)
                ORDER BY
                    CASE severity WHEN 'urgent' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END,
                    created_at DESC
            ''', (now,))

        rows = cursor.fetchall()
        notifications = []
        for row in rows:
            n = dict(row)
            n['data'] = json.loads(n.get('data_json') or '{}')
            n['action_data'] = json.loads(n.get('action_data_json') or '{}')
            notifications.append(n)
        return notifications


def get_notification_by_id(notification_id: int) -> dict:
    """Get a single notification by ID."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM notifications WHERE id = ?', (notification_id,))
        row = cursor.fetchone()
        if row:
            n = dict(row)
            n['data'] = json.loads(n.get('data_json') or '{}')
            n['action_data'] = json.loads(n.get('action_data_json') or '{}')
            return n
        return None


def dismiss_notification(notification_id: int) -> bool:
    """Mark a notification as dismissed."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE notifications SET dismissed_at = ? WHERE id = ?
        ''', (datetime.now().isoformat(), notification_id))
        conn.commit()
        return cursor.rowcount > 0


def snooze_notification(notification_id: int, until: str) -> bool:
    """Snooze a notification until a specific time."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE notifications SET snoozed_until = ? WHERE id = ?
        ''', (until, notification_id))
        conn.commit()
        return cursor.rowcount > 0


def mark_notification_read(notification_id: int) -> bool:
    """Mark a notification as read."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE notifications SET read_at = ? WHERE id = ? AND read_at IS NULL
        ''', (datetime.now().isoformat(), notification_id))
        conn.commit()
        return cursor.rowcount > 0


def get_notification_count() -> dict:
    """Get counts of active notifications by severity."""
    with get_db() as conn:
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute('''
            SELECT severity, COUNT(*) as count FROM notifications
            WHERE dismissed_at IS NULL
            AND (snoozed_until IS NULL OR snoozed_until <= ?)
            GROUP BY severity
        ''', (now,))
        rows = cursor.fetchall()
        counts = {'total': 0, 'urgent': 0, 'warning': 0, 'info': 0}
        for row in rows:
            counts[row['severity']] = row['count']
            counts['total'] += row['count']
        return counts


def clear_old_notifications(days: int = 30) -> int:
    """Delete dismissed notifications older than N days."""
    with get_db() as conn:
        cursor = conn.cursor()
        cutoff = datetime.now().isoformat()  # Would need date math for proper implementation
        cursor.execute('''
            DELETE FROM notifications
            WHERE dismissed_at IS NOT NULL
            AND datetime(dismissed_at) < datetime('now', ?)
        ''', (f'-{days} days',))
        conn.commit()
        return cursor.rowcount


# Initialize database and sync from CSV on module load
init_database()
if CSV_PATH.exists():
    sync_csv_to_db()
