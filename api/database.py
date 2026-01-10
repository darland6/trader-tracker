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


# Initialize database on module load
init_database()
