# Data Layer Architecture - BEDROCK

**Code Name: BEDROCK** - Consolidated data layer with CSV as single source of truth

## Overview

As of 2026-01-12, the trader-tracker project has consolidated its data layer to enforce a strict separation of concerns:

- **CSV is the SINGLE SOURCE OF TRUTH** for all event data
- **SQLite is a READ-ONLY CACHE** for query performance
- **All event writes go through `core/data.py`**
- **File locking prevents concurrent write corruption**

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        APPLICATION LAYER                         │
│  (CLI, API Routes, Services)                                     │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            │ All event operations
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                        core/data.py                              │
│               Centralized Data Access Layer                      │
│                                                                  │
│  Functions:                                                      │
│  • append_event()    - Write new events                          │
│  • update_event()    - Modify existing events                    │
│  • delete_event()    - Remove events                             │
│  • load_events()     - Read all events                           │
│  • get_event_by_id() - Get single event                          │
│                                                                  │
│  Features:                                                       │
│  • File locking (fcntl) for concurrent access safety             │
│  • JSON parsing/serialization                                    │
│  • Event ID generation                                           │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            │ Writes (with file lock)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              data/event_log_enhanced.csv                         │
│                   SOURCE OF TRUTH                                │
│                                                                  │
│  • All events stored here                                        │
│  • Immutable event log (append-only philosophy)                  │
│  • Can be backed up, versioned, restored                         │
│  • Human-readable for debugging                                  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            │ sync_csv_to_db() rebuilds cache
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      portfolio.db (SQLite)                       │
│                      READ-ONLY CACHE                             │
│                                                                  │
│  Tables:                                                         │
│  • events          - Cached from CSV for fast queries            │
│  • price_cache     - Stock prices (OK to write directly)         │
│  • notifications   - System notifications (OK to write)          │
│                                                                  │
│  Events table is NEVER written to directly!                      │
│  It is rebuilt from CSV via sync_csv_to_db()                     │
└─────────────────────────────────────────────────────────────────┘
```

## Key Principles

### 1. Single Source of Truth
- **CSV is authoritative** - If there's a conflict between CSV and SQLite, CSV wins
- **SQLite is rebuildable** - Can delete `portfolio.db` and regenerate from CSV
- **No direct SQLite writes** - Events table is populated only via `sync_csv_to_db()`

### 2. File Locking
- Uses `fcntl.flock()` to prevent concurrent write corruption
- Shared locks for reads (`LOCK_SH`)
- Exclusive locks for writes (`LOCK_EX`)
- Lock file: `data/event_log_enhanced.csv.lock`

### 3. Backward Compatibility
- Old functions in `api/database.py` are marked as `DEPRECATED`
- They delegate to `core/data.py` internally
- No breaking changes to existing route code

### 4. Cache Synchronization
- After every CSV write, call `sync_to_cache()` to update SQLite
- Sync happens automatically in most cases
- Can manually trigger via `api.database.sync_csv_to_db()`

## File Structure

```
trader-tracker/
├── core/
│   └── data.py                    # NEW: Centralized data access layer
├── api/
│   ├── database.py                # UPDATED: Now delegates to core/data.py
│   │                              # Price cache and notifications still use SQLite
│   └── routes/
│       ├── events.py              # Uses api.database (which delegates to core)
│       ├── trades.py              # Uses cli.events (which uses core)
│       └── options.py             # Uses cli.events (which uses core)
├── cli/
│   └── events.py                  # UPDATED: Uses core/data.py for CSV writes
└── data/
    └── event_log_enhanced.csv     # SOURCE OF TRUTH
```

## Usage Guide

### Writing Events (CORRECT)

```python
from core.data import append_event

# Create a new event
event_id = append_event(
    event_type="TRADE",
    data={"action": "BUY", "ticker": "TSLA", "shares": 10, "price": 445.0},
    reason={"primary": "GROWTH", "explanation": "Bullish on EV"},
    notes="Strong buy signal",
    tags=["trade", "tsla"],
    affects_cash=True,
    cash_delta=-4450.0
)

# Sync to SQLite cache
from core.data import sync_to_cache
sync_to_cache()
```

### Writing Events (WRONG - Don't do this!)

```python
# ❌ NEVER write directly to SQLite events table
import sqlite3
conn = sqlite3.connect('portfolio.db')
cursor = conn.cursor()
cursor.execute("INSERT INTO events ...")  # ❌ BAD!

# ❌ NEVER write to CSV without file locking
import pandas as pd
df = pd.read_csv('data/event_log_enhanced.csv')
df = pd.concat([df, new_row])
df.to_csv('data/event_log_enhanced.csv')  # ❌ NO FILE LOCK!
```

### Reading Events

```python
from core.data import load_events, get_event_by_id

# Load all events (with parsed JSON)
df = load_events(parse_json=True)

# Get single event
event = get_event_by_id(event_id=42)

# Or use existing api.database functions (they use SQLite cache)
from api.database import get_all_events
events = get_all_events(limit=10, event_type="TRADE")
```

### Updating Events

```python
from core.data import update_event, sync_to_cache

# Update event data
success = update_event(
    event_id=42,
    updates={
        "data": {"action": "SELL", "ticker": "TSLA", "shares": 5},
        "notes": "Profit taking"
    }
)

# Sync to cache
sync_to_cache()
```

## Migration Notes

### What Changed?

1. **New module**: `core/data.py` created with all CSV operations
2. **Updated**: `cli/events.py` now uses `core/data.py` for writes
3. **Updated**: `api/database.py` functions delegate to `core/data.py`
4. **Added**: File locking with `fcntl` to prevent corruption
5. **Clarified**: SQLite events table is read-only cache

### What Stayed the Same?

1. **CSV format** - No changes to event_log_enhanced.csv structure
2. **API routes** - No breaking changes to endpoints
3. **CLI commands** - All commands work as before
4. **Database schema** - SQLite schema unchanged
5. **Existing code** - Route files don't need updates (backward compatible)

### Testing

All 43 E2E tests pass after BEDROCK migration:
```bash
pytest tests/test_e2e_workflow.py -v
# 43 passed, 4 warnings in 10.38s
```

## Benefits

1. **Data Integrity** - Single source of truth eliminates inconsistencies
2. **Concurrency Safety** - File locking prevents race conditions
3. **Disaster Recovery** - Easy to backup/restore from CSV
4. **Debugging** - CSV is human-readable and git-friendly
5. **Performance** - SQLite cache provides fast queries
6. **Clarity** - Explicit data flow is easier to reason about

## Exceptions (OK to Write to SQLite Directly)

These SQLite tables are NOT event data and can be written to directly:

1. **price_cache** - Stock price caching (temporary data)
2. **notifications** - System notification queue (transient data)
3. **agent_schedules** - Background job schedules (configuration data)

These are separate concerns and don't need CSV backing.

## Future Improvements

1. **CSV Compression** - Archive old events to compressed format
2. **Event Replay** - Rebuild entire portfolio state from CSV
3. **Git Integration** - Version control event log changes
4. **Audit Trail** - Track who/when events were modified
5. **Batch Operations** - Optimize bulk event writes

---

**BEDROCK Status**: ✅ Complete (2026-01-12)

All event writes now flow through `core/data.py` with file locking.
SQLite is a read-only cache rebuilt from CSV.
